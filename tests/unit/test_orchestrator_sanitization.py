import pytest
from types import SimpleNamespace

from src.core.models import DebateState


def test_orchestrator_sanitizes_bare_domains_and_skips_titles(monkeypatch):
    # Monkeypatch FreeLLMClient in the debate module before importing DebateOrchestrator
    from src.orchestration import debate as debate_mod

    class DummyClient:
        pass

    monkeypatch.setattr(debate_mod, "FreeLLMClient", DummyClient)

    # Import here after monkeypatch to ensure class is used
    from src.orchestration.debate import DebateOrchestrator

    orchestrator = DebateOrchestrator()

    # Create a state with mixed source formats
    state = DebateState(claim="Test", pro_sources=[["Stanton et al. (2020) - Exercise and neuroplasticity", "www.example.com"]], con_sources=[])

    # Replace fact_checker.generate to avoid network calls
    orchestrator.fact_checker.generate = lambda s: SimpleNamespace(metrics={"verification_results": [], "pro_rate": 0.0, "con_rate": 0.0})

    # Run the internal node
    new_state = orchestrator._fact_checker_node(state)

    # After sanitization, the bare domain should have been converted to https://www.example.com
    assert any("https://www.example.com" in item for round_sources in new_state.pro_sources for item in round_sources)

    # Titles should be skipped (not coerced into http://...)
    assert not any("Stanton et al." in item for round_sources in new_state.pro_sources for item in round_sources)

    orchestrator.close()
