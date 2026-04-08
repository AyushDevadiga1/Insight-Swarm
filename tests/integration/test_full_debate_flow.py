"""
Integration tests for complete debate flow.
FIXED: Added RUN_INTEGRATION_LLM guard — these tests call real LLMs and burn
       API quota. They are skipped by default unless explicitly opted-in.
       Use: RUN_INTEGRATION_LLM=1 pytest tests/integration/test_full_debate_flow.py
"""

import os
import pytest
from src.orchestration.debate import DebateOrchestrator

RUN_INTEGRATION_LLM = os.getenv("RUN_INTEGRATION_LLM", "").strip().lower() in ("1", "true", "yes")
pytestmark = pytest.mark.skipif(
    not RUN_INTEGRATION_LLM,
    reason="Full debate integration tests require live LLM access. Set RUN_INTEGRATION_LLM=1 to enable."
)


class TestFullDebateFlow:

    def test_simple_true_claim(self):
        """Consensus pre-check returns TRUE for settled science."""
        orch = DebateOrchestrator()
        result = orch.run("The Earth is round")
        assert result.verdict == "TRUE"
        assert result.confidence > 0.9
        assert len(result.pro_arguments) > 0
        assert len(result.con_arguments) > 0
        orch.close()

    def test_simple_false_claim(self):
        """Consensus pre-check returns FALSE for settled science."""
        orch = DebateOrchestrator()
        result = orch.run("The Earth is flat")
        assert result.verdict == "FALSE"
        assert result.confidence > 0.9
        orch.close()

    def test_consensus_skip_path(self):
        """Known-false settled claim skips debate."""
        orch = DebateOrchestrator()
        result = orch.run("Vaccines cause autism")
        assert result.verdict == "FALSE"
        assert result.confidence > 0.95
        assert len(result.pro_arguments) > 0
        orch.close()

    def test_cache_hit(self):
        """Second call to same claim returns cached result."""
        orch = DebateOrchestrator()
        result1 = orch.run("Water is H2O")
        result2 = orch.run("Water is H2O")
        assert result2.is_cached is True
        assert result2.verdict == result1.verdict
        orch.close()

    def test_moderator_reasoning(self):
        """Moderator provides non-trivial reasoning."""
        orch = DebateOrchestrator()
        result = orch.run("The sky is blue")
        assert result.moderator_reasoning is not None
        assert len(result.moderator_reasoning) > 10
        orch.close()

    def test_orchestrator_creation(self):
        """Orchestrator instantiates and close() is idempotent."""
        orch = DebateOrchestrator()
        assert orch is not None
        orch.close()
        orch.close()  # safe to call twice


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
