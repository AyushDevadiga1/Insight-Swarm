import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestration.debate import DebateOrchestrator
from src.agents.moderator import Moderator
from src.core.models import DebateState, AgentResponse
from src.llm.client import RateLimitError


def test_verification_rate_semantics():
    """
    Fact-checker node correctly reads pro_rate / con_rate from AgentResponse metrics.
    Pro agent has zero sources → rate must be 0.0.
    Con agent has one verified source → rate must be 1.0.
    """
    orchestrator = DebateOrchestrator()

    state = DebateState(
        claim="Test",
        round=3,
        pro_arguments=["Arg"],
        con_arguments=["Arg"],
        pro_sources=[[]],                         # Pro: no URLs
        con_sources=[["http://test.com"]],
    )

    # ── FIX: mock must return AgentResponse (not a plain dict) ───────────────
    # _fact_checker_node calls response.metrics, which fails on a dict.
    mock_response = AgentResponse(
        agent="FACT_CHECKER",
        round=3,
        argument="Verification complete. PRO: 0/0 verified. CON: 1/1 verified.",
        sources=[],
        confidence=1.0,
        metrics={
            "verification_results": [
                {"agent_source": "CON", "url": "http://test.com",
                 "status": "VERIFIED", "trust_score": 0.5}
            ],
            "pro_rate": 0.0,
            "con_rate": 1.0,
        },
    )
    orchestrator.fact_checker.generate = MagicMock(return_value=mock_response)

    updated_state = orchestrator._fact_checker_node(state)

    assert updated_state.pro_verification_rate == 0.0
    assert updated_state.con_verification_rate == 1.0
    orchestrator.close()


def test_round_counter_logic():
    """
    _should_continue must honour the post-increment round convention:
    ConAgent increments round AFTER generating, so after Round 3 state.round == 4.
    4 > 3 → 'end';  3 > 3 is False → 'continue';  2 > 3 is False → 'continue'.
    """
    orchestrator = DebateOrchestrator()

    # After Round 3: ConAgent bumps round 3 → 4
    assert orchestrator._should_continue({"round": 4}) == "end"

    # Round 3 in progress: not yet incremented
    assert orchestrator._should_continue({"round": 3}) == "continue"

    # After Round 1: round == 2, still has 2 rounds to go
    assert orchestrator._should_continue({"round": 2}) == "continue"

    orchestrator.close()


def test_moderator_fallback_on_rate_limit():
    """
    Moderator must produce a RATE_LIMITED AgentResponse when call_structured raises
    RateLimitError — and confidence must be 0.0.
    """
    client = MagicMock()
    client.call_structured.side_effect = RateLimitError("groq", "rate limited", 30.0)
    moderator = Moderator(client)

    state = DebateState(
        claim="Test claim",
        round=3,
        pro_arguments=["Pro arg"] * 3,
        con_arguments=["Con arg"] * 3,
    )
    result = moderator.generate(state)

    assert result.agent      == "MODERATOR"
    assert result.verdict    == "RATE_LIMITED"
    assert result.confidence == 0.0
