"""
Load tests for InsightSwarm — concurrent users + memory stability.

Run with:
    pytest tests/load/ -v

By default these tests use the DummyClient (no real API calls).
Set RUN_INTEGRATION_LLM=1 to run against live providers.
"""

import os
import time
import threading
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

logger = logging.getLogger(__name__)

RUN_INTEGRATION_LLM = os.getenv("RUN_INTEGRATION_LLM", "").strip().lower() in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class DummyClient:
    """Fast in-process stub — no real LLM calls, no network."""
    openrouter_available = True
    groq_available = True
    gemini_available = True
    cerebras_available = True

    def call_structured(self, prompt, output_schema, temperature=0.7, max_tokens=2000, **kwargs):
        name = getattr(output_schema, "__name__", "")
        if name == "ModeratorVerdict":
            return output_schema(
                verdict="INSUFFICIENT EVIDENCE",
                confidence=0.5,
                reasoning="Load-test stub moderator reasoning " * 5,
                metrics={"credibility": 0.5, "balance": 0.5},
            )
        if name == "ConsensusResponse":
            return output_schema(
                verdict="DEBATE", score=0.5, confidence=0.5,
                reasoning="Load-test stub consensus reasoning.",
            )
        return output_schema(
            agent="PRO", round=1,
            argument="Load-test stub argument. " * 10,
            sources=["https://example.com"],
            confidence=0.6,
        )

    def call(self, prompt, temperature=0.7, max_tokens=1000, timeout=30, **kwargs):
        return "Load-test stub response."


def _make_orchestrator():
    from src.orchestration.debate import DebateOrchestrator
    if RUN_INTEGRATION_LLM:
        return DebateOrchestrator()
    return DebateOrchestrator(llm_client=DummyClient())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.timeout(120)
def test_10_concurrent_users():
    """Ten users submit claims simultaneously — all should complete without errors."""
    claims = [
        "Coffee has health benefits",
        "Exercise is good for the heart",
        "Reading improves cognition",
        "Sleep deprivation impairs memory",
        "Stress causes physical illness",
        "Meditation reduces anxiety",
        "Sugar causes tooth decay",
        "Sunlight boosts vitamin D",
        "Music aids concentration",
        "Laughter is good medicine",
    ]

    results = {}
    errors = {}

    def run(claim: str):
        try:
            orch = _make_orchestrator()
            result = orch.run(claim)
            results[claim] = result['verdict']
        except Exception as exc:
            errors[claim] = str(exc)
            logger.error(f"Concurrent test failed for '{claim}': {exc}")

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(run, c): c for c in claims}
        for f in as_completed(futures):
            f.result()           # surface any thread-level exceptions

    assert len(errors) == 0, f"Some concurrent runs failed: {errors}"
    assert len(results) == len(claims), "Not all claims produced a result"

    # Every verdict must be a valid value
    VALID_VERDICTS = {"TRUE", "FALSE", "PARTIALLY TRUE", "INSUFFICIENT EVIDENCE", "RATE_LIMITED"}
    for claim, verdict in results.items():
        assert verdict in VALID_VERDICTS, f"'{claim}' returned unexpected verdict: {verdict!r}"


@pytest.mark.timeout(300)
def test_memory_stability_20_runs():
    """Run the orchestrator 20 times sequentially and assert memory is stable."""
    try:
        import psutil
        import os as _os
        process = psutil.Process(_os.getpid())
        track_mem = True
    except ImportError:
        track_mem = False
        logger.warning("psutil not installed — skipping memory measurement; only testing for crashes")

    if track_mem:
        mem_before = process.memory_info().rss / (1024 * 1024)  # MB

    orch = _make_orchestrator()
    for i in range(20):
        result = orch.run(f"Test claim number {i + 1}")
        assert result.verdict is not None, f"Run {i + 1} returned None verdict"

    if track_mem:
        mem_after = process.memory_info().rss / (1024 * 1024)
        growth_mb = mem_after - mem_before
        logger.info(f"Memory growth over 20 runs: {growth_mb:.1f} MB")
        assert growth_mb < 200, (
            f"Memory grew by {growth_mb:.1f} MB over 20 runs — possible leak"
        )


@pytest.mark.timeout(60)
def test_no_thread_leaks():
    """Thread count should not grow unboundedly after many orchestrator creations."""
    initial_threads = threading.active_count()

    for _ in range(5):
        orch = _make_orchestrator()
        orch.run("Quick stability claim")

    final_threads = threading.active_count()
    thread_growth = final_threads - initial_threads
    logger.info(f"Thread growth after 5 orchestrators: {thread_growth}")
    assert thread_growth <= 10, (
        f"Too many new threads after 5 runs: +{thread_growth} (possible leak)"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
