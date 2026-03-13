"""
Unit tests for Moderator agent
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import pytest
from unittest.mock import Mock
from src.agents.moderator import Moderator
from src.core.models import DebateState, AgentResponse, ModeratorVerdict
from src.llm.client import FreeLLMClient

@pytest.fixture
def mock_client():
    client = Mock(spec=FreeLLMClient)
    client.call_structured.return_value = ModeratorVerdict(
        verdict="TRUE",
        confidence=0.9,
        reasoning="The evidence strongly supports the claim.",
        metrics={"evidence_quality": 0.9}
    )
    return client

@pytest.fixture
def moderator(mock_client):
    return Moderator(mock_client)

@pytest.fixture
def balanced_debate():
    return DebateState(
        claim="Test claim",
        round=4,
        pro_arguments=["Pro arg"] * 3,
        con_arguments=["Con arg"] * 3,
        pro_sources=[["url1"]] * 3,
        con_sources=[["url2"]] * 3
    )

def test_moderator_initialization(moderator):
    assert moderator.role == "MODERATOR"

def test_moderator_generates_verdict(moderator, balanced_debate):
    result = moderator.generate(balanced_debate)
    assert result.agent == "MODERATOR"
    assert result.verdict == "TRUE"
    assert result.confidence == 0.9

def test_moderator_fallback_verdict(moderator, balanced_debate):
    fallback = moderator._fallback_verdict(balanced_debate)
    assert fallback.agent == "MODERATOR"
    assert fallback.verdict in ['TRUE', 'FALSE', 'PARTIALLY TRUE', 'INSUFFICIENT EVIDENCE']

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
