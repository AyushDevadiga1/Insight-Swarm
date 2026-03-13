"""
Integration test: ProAgent and ConAgent debating
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import pytest
from unittest.mock import Mock
from src.agents.pro_agent import ProAgent
from src.agents.con_agent import ConAgent
from src.core.models import DebateState, AgentResponse
from src.llm.client import FreeLLMClient

@pytest.fixture
def debate_setup():
    """Setup for debate test with mocked LLM client."""
    mock_client = Mock(spec=FreeLLMClient)
    
    # Mock responses for call_structured
    pro_response = AgentResponse(
        agent="PRO",
        round=1,
        argument="This claim is supported by extensive research. Evidence from multiple studies.",
        sources=["https://example.com/study1"]
    )
    con_response = AgentResponse(
        agent="CON",
        round=1,
        argument="This claim lacks sufficient evidence. Counter-evidence suggests otherwise.",
        sources=["https://example.com/study2"]
    )
    
    def mock_call_structured(prompt, output_schema, **kwargs):
        system_prompt = kwargs.get("system_prompt", "")
        if "pro" in system_prompt.lower() or "pro" in prompt.lower():
            return pro_response
        return con_response

    mock_client.call_structured.side_effect = mock_call_structured
    
    pro_agent = ProAgent(mock_client)
    con_agent = ConAgent(mock_client)
    
    state = DebateState(claim="Exercise improves mental health")
    
    return pro_agent, con_agent, state

def test_full_debate_round(debate_setup):
    """Test complete debate round between both agents."""
    pro_agent, con_agent, state = debate_setup
    
    # Round 1: ProAgent argues FOR
    response = pro_agent.generate(state)
    assert response.agent == "PRO"
    state.pro_arguments.append(response.argument)
    state.pro_sources.append(response.sources)
    
    # Round 1: ConAgent argues AGAINST
    response = con_agent.generate(state)
    assert response.agent == "CON"
    state.con_arguments.append(response.argument)
    state.con_sources.append(response.sources)
    
    # Verify both agents responded
    assert len(state.pro_arguments) == 1
    assert len(state.con_arguments) == 1
    assert len(state.pro_sources) == 1
    assert len(state.con_sources) == 1

def test_debate_state_consistency(debate_setup):
    """Test that debate state remains consistent through rounds."""
    pro_agent, con_agent, state = debate_setup
    
    initial_claim = state.claim
    initial_round = state.round
    
    pro_agent.generate(state)
    con_agent.generate(state)
    
    assert state.claim == initial_claim
    assert state.round == initial_round

if __name__ == "__main__":
    pytest.main([__file__, "-v"])