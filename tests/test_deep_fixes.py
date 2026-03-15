import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestration.debate import DebateOrchestrator
from src.agents.moderator import Moderator
from src.agents.base import DebateState

def test_moderator_parsing_robustness():
    """Verify moderator parsing handles varied casing and spacing (FIX 6)"""
    client = MagicMock()
    moderator = Moderator(client)
    
    test_responses = [
        "verdict: true\nconfidence: 0.8\nreasoning: because it is",
        "VERDICT - FALSE\nCONFIDENCE: 0.2\nREASONING: no way",
        "Verdict: Partially True\nConfidence: 0.5\nReasoning: maybe",
        "Verdict: Insufficient Evidence\nConfidence: 0.1\nReasoning: what?"
    ]
    
    expected_verdicts = ["TRUE", "FALSE", "PARTIALLY TRUE", "INSUFFICIENT EVIDENCE"]
    
    for resp, expected in zip(test_responses, expected_verdicts):
        verdict, conf, reasoning, metrics = moderator._parse_moderator_response(resp)
def test_verification_rate_semantics():
    """Verify agents with no sources get 0.0% verification and use DebateState."""
    orchestrator = DebateOrchestrator()
    # Use a real DebateState, not a dict.
    state = DebateState(
        claim="Test",
        round=3,
        pro_arguments=["Arg"],
        con_arguments=["Arg"],
        pro_sources=[[]],           # Pro has no sources
        con_sources=[["http://test.com"]],
    )
    mock_response = {
        "verification_results": [
            {"agent_source": "CON", "url": "http://test.com", "status": "VERIFIED"}
        ]
    }
    orchestrator.fact_checker.generate = MagicMock(return_value=mock_response)

    updated_state = orchestrator._fact_checker_node(state)

    assert updated_state.pro_verification_rate == 0.0
    assert updated_state.con_verification_rate == 1.0

def test_round_counter_logic():
    """Verify debate continues or stops based on round number."""
    orchestrator = DebateOrchestrator()

    # After Round 3 con_agent increments round from 3 to 4.
    # _should_continue then receives round=4 with num_rounds=3.
    # 4 > 3 → "end"  (correct)
    state = {"round": 4}
    assert orchestrator._should_continue(state) == "end"

    # Mid-debate: round=3 means Round 3 is in progress, should continue.
    # 3 > 3 is False → "continue"  (correct)
    state = {"round": 3}
    assert orchestrator._should_continue(state) == "continue"

    # After Round 1: round=2 → "continue"
    state = {"round": 2}
    assert orchestrator._should_continue(state) == "continue"

def test_moderator_fallback_on_rate_limit():
    """Verify fallback verdict is produced when call_structured raises."""
    from src.llm.client import RateLimitError
    client = MagicMock()
    client.call_structured.side_effect = RateLimitError("groq", "rate limited", 30.0)
    moderator = Moderator(client)

    state = DebateState(
        claim="Test claim", round=3,
        pro_arguments=["Pro arg"] * 3,
        con_arguments=["Con arg"] * 3,
    )
    result = moderator.generate(state)

    assert result.agent == "MODERATOR"
    assert result.verdict == "RATE_LIMITED"
    assert result.confidence == 0.0
