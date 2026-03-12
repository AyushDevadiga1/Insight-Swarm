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
        assert verdict == expected
        assert isinstance(conf, float)
        assert len(reasoning) > 0
        assert isinstance(metrics, dict)

def test_verification_rate_semantics():
    """Verify agents with no sources get 0.0% verification (FIX 2)"""
    orchestrator = DebateOrchestrator()
    state: DebateState = {
        "claim": "Test",
        "round": 3,
        "pro_arguments": ["Arg"],
        "con_arguments": ["Arg"],
        "pro_sources": [[]],  # No sources
        "con_sources": [["http://test.com"]],
        "verdict": None,
        "confidence": None,
        "verification_results": None,
        "pro_verification_rate": None,
        "con_verification_rate": None,
        "fact_check_result": None,
        "moderator_reasoning": None,
        "metrics": None,
        "retry_count": 0
    }
    
    # Mock fact checker return
    mock_response = {
        "verification_results": [
            {"agent_source": "CON", "url": "http://test.com", "status": "VERIFIED"}
        ]
    }
    orchestrator.fact_checker.generate = MagicMock(return_value=mock_response)
    
    updated_state = orchestrator._fact_checker_node(state)
    
    assert updated_state['pro_verification_rate'] == 0.0
    assert updated_state['con_verification_rate'] == 1.0

def test_round_counter_logic():
    """Verify debate stops at round 3 (FIX 1)"""
    orchestrator = DebateOrchestrator()
    
    # Round 3 just finished
    state = {"round": 3}
    assert orchestrator._should_continue(state) == "end"
    
    # Round 2 just finished
    state = {"round": 2}
    assert orchestrator._should_continue(state) == "continue"
