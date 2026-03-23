"""
Integration tests for API key quota handling and resilience.

Tests the system's behaviour when:
  - All providers are rate-limited / exhausted
  - Only some providers fail (partial failure)
  - Keys recover after reset

Run with:
    pytest tests/integration/test_api_quota_handling.py -v

Uses MockChaosClient from tests/sandbox/api_simulator.py.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from tests.sandbox.api_simulator import MockChaosClient, ChaosConfig
from src.orchestration.debate import DebateOrchestrator

VALID_VERDICTS = {"TRUE", "FALSE", "PARTIALLY TRUE", "INSUFFICIENT EVIDENCE", "RATE_LIMITED"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _orch(chaos_config: ChaosConfig) -> DebateOrchestrator:
    client = MockChaosClient(chaos_config)
    return DebateOrchestrator(llm_client=client)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.timeout(120)
def test_all_providers_rate_limited_returns_safe_verdict():
    """
    When every provider is rate-limited (failure_rate=1.0), the system must
    return a graceful verdict rather than raising an unhandled exception.
    """
    config = ChaosConfig(failure_rate=1.0, rate_limit_rate=1.0, min_latency=0.0, max_latency=0.1)
    orch = _orch(config)

    # Should not raise — must degrade gracefully
    result = orch.run("Does high failure rate cause crash?")
    assert result['verdict'] in VALID_VERDICTS, (
        f"Unexpected verdict under total failure: {result['verdict']!r}"
    )


@pytest.mark.timeout(120)
def test_partial_provider_failure_falls_back():
    """
    When Groq fails 100% of the time but other providers succeed,
    the FallbackHandler should route to a working provider and produce a verdict.
    """
    config = ChaosConfig(
        failure_rate=0.0,
        rate_limit_rate=0.0,
        min_latency=0.0,
        max_latency=0.1,
        provider_specific_failure={"groq": 1.0, "cerebras": 1.0},  # Groq+Cerebras down
    )
    orch = _orch(config)

    result = orch.run("Does partial failure cascade correctly?")
    assert result['verdict'] in VALID_VERDICTS, (
        f"Unexpected verdict under partial failure: {result['verdict']!r}"
    )
    # Moderator must still supply reasoning
    assert result['moderator_reasoning'] is not None


@pytest.mark.timeout(60)
def test_clean_run_completes_with_all_fields():
    """
    A zero-chaos run via MockChaosClient should produce a complete, well-formed result.
    """
    config = ChaosConfig(failure_rate=0.0, rate_limit_rate=0.0, min_latency=0.0, max_latency=0.0)
    orch = _orch(config)

    result = orch.run("Clean mock run produces valid result structure")

    assert result['verdict'] in VALID_VERDICTS
    assert result['confidence'] is not None
    assert 0.0 <= result['confidence'] <= 1.0
    assert result['moderator_reasoning'] is not None
    assert len(result['pro_arguments']) > 0
    assert len(result['con_arguments']) > 0
    assert result['pro_verification_rate'] is not None
    assert result['con_verification_rate'] is not None


@pytest.mark.timeout(60)
def test_key_reset_allows_recovery():
    """
    After resetting all API keys, the key manager should report them as working again.
    This simulates auto-recovery between sessions.
    """
    from src.utils.api_key_manager import get_api_key_manager, APIKeyStatus

    km = get_api_key_manager()

    # Mark every provider key as rate-limited
    for provider in ("groq", "gemini", "cerebras", "openrouter"):
        for key_info in km.keys.get(provider, []):
            key_info.status = APIKeyStatus.RATE_LIMITED
            key_info.consecutive_failures = 10
            key_info.cooldown_until = float("inf")  # never expires naturally

    # Now reset and verify recovery
    km.reset_all_keys()

    for provider in ("groq", "gemini"):  # check the two primary providers
        keys = km.keys.get(provider, [])
        if keys:
            assert any(k.consecutive_failures == 0 for k in keys), (
                f"{provider} keys were not reset — consecutive_failures still non-zero"
            )


@pytest.mark.timeout(120)
def test_high_failure_rate_does_not_crash():
    """
    50% random failure + 20% rate-limit should still complete without unhandled exception.
    The system is expected to degrade gracefully.
    """
    config = ChaosConfig(failure_rate=0.5, rate_limit_rate=0.2, min_latency=0.0, max_latency=0.2)
    orch = _orch(config)

    # Run multiple times: at least some should succeed
    verdicts = []
    for _ in range(3):
        try:
            result = orch.run("Stress test under high failure rate")
            verdicts.append(result.verdict)
        except Exception as exc:
            pytest.fail(f"Unhandled exception under chaos: {exc}")

    assert len(verdicts) == 3, "Some runs did not produce a result"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
