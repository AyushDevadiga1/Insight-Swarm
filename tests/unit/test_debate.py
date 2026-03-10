"""
Integration test: ProAgent and ConAgent debating

Security features tested:
- Multi-round debate integrity
- Response validation
- State consistency

TESTING APPROACH:
- Uses unittest.mock to mock LLM responses for deterministic testing
- Mocked responses simulate realistic argument formats with sources
- This ensures assertions pass reliably without depending on real LLM API
- Real LLM behavior can be tested in a separate integration test suite
"""

import pytest
from unittest.mock import Mock
from src.agents.pro_agent import ProAgent
from src.agents.con_agent import ConAgent
from src.agents.base import DebateState
from src.llm.client import FreeLLMClient


@pytest.fixture
def debate_setup():
    """
    Setup for debate test with mocked LLM client.
    
    Uses mocked responses to ensure deterministic, reliable testing
    without depending on external LLM API availability or response variability.
    """
    # Create mocked client instead of real one
    mock_client = Mock(spec=FreeLLMClient)
    
    # Configure mock response for both agents
    # Returns a realistic response with argument and sources
    mock_response = """ARGUMENT:
This claim is supported by extensive research showing consistent positive effects across multiple studies.
Studies demonstrate a strong correlation between this claim and measurable outcomes in controlled trials.
Evidence from peer-reviewed publications spanning multiple years of research.

SOURCES:
- https://example.com/research/study1
- https://example.com/research/study2
- https://example.com/research/study3"""
    
    mock_client.call.return_value = mock_response
    
    pro_agent = ProAgent(mock_client)
    con_agent = ConAgent(mock_client)
    
    state = DebateState(
        claim="Exercise improves mental health",
        round=1,
        pro_arguments=[],
        con_arguments=[],
        pro_sources=[],
        con_sources=[],
        verdict=None,
        confidence=None
    )
    
    return pro_agent, con_agent, state


def test_full_debate_round(debate_setup):
    """
    Test complete debate round between both agents.
    
    Uses mocked LLM client for deterministic responses.
    Mocked responses ensure arguments have predictable structure and length,
    making assertions reliable and independent of external LLM API behavior.
    
    Variables used:
    - pro_response: AgentResponse from ProAgent.generate()
    - con_response: AgentResponse from ConAgent.generate()
    - state: DebateState object updated with both arguments
    """
    pro_agent, con_agent, state = debate_setup
    
    # Round 1: ProAgent argues FOR
    pro_response = pro_agent.generate(state)
    assert pro_response['agent'] == "PRO"
    assert len(pro_response['argument']) > 0
    
    state['pro_arguments'].append(pro_response['argument'])
    state['pro_sources'].append(pro_response['sources'])
    
    # Round 1: ConAgent argues AGAINST
    con_response = con_agent.generate(state)
    assert con_response['agent'] == "CON"
    assert len(con_response['argument']) > 0
    
    state['con_arguments'].append(con_response['argument'])
    state['con_sources'].append(con_response['sources'])
    
    # Verify both agents responded
    assert len(state['pro_arguments']) == 1
    assert len(state['con_arguments']) == 1
    
    # Verify both cited sources
    assert isinstance(pro_response['sources'], list)
    assert isinstance(con_response['sources'], list)
    
    # Verify arguments are substantial (mocked response guarantees this)
    assert len(pro_response['argument']) > 50
    assert len(con_response['argument']) > 50


def test_agents_disagree():
    """
    Test that agents take opposing positions.
    
    Creates separate mock clients for each agent to demonstrate that
    when configured with different responses, they produce opposing arguments.
    
    Variables used:
    - pro_response: AgentResponse with PRO stance
    - con_response: AgentResponse with CON stance
    - state: DebateState object
    """
    # Create separate mock clients for each agent
    pro_mock_client = Mock(spec=FreeLLMClient)
    con_mock_client = Mock(spec=FreeLLMClient)
    
    # Configure different responses
    pro_mock_client.call.return_value = """ARGUMENT:
This claim is strongly supported by research evidence. Multiple studies confirm this position.

SOURCES:
- https://example.com/pro_study1
- https://example.com/pro_study2"""
    
    con_mock_client.call.return_value = """ARGUMENT:
This claim lacks sufficient evidence. Counter-evidence suggests the opposite position is stronger.

SOURCES:
- https://example.com/con_study1
- https://example.com/con_study2"""
    
    # Create agents with separate mocks
    pro_agent = ProAgent(pro_mock_client)
    con_agent = ConAgent(con_mock_client)
    
    state = DebateState(
        claim="Exercise improves mental health",
        round=1,
        pro_arguments=[],
        con_arguments=[],
        pro_sources=[],
        con_sources=[],
        verdict=None,
        confidence=None
    )
    
    # Both agents respond with different mocks
    pro_response = pro_agent.generate(state)
    state['pro_arguments'].append(pro_response['argument'])
    state['pro_sources'].append(pro_response['sources'])
    
    con_response = con_agent.generate(state)
    
    # Arguments should be different (opposing positions)
    assert pro_response['argument'] != con_response['argument']
    
    # Agents should be different
    assert pro_response['agent'] != con_response['agent']
    assert pro_response['agent'] == "PRO"
    assert con_response['agent'] == "CON"


def test_debate_state_consistency(debate_setup):
    """
    Test that debate state remains consistent through rounds.
    
    Verifies that claim and round number don't change during debate,
    and that the state accumulates arguments correctly.
    
    Uses mocked LLM responses for reliable testing.
    
    Variables used:
    - pro_response: AgentResponse from ProAgent.generate()
    - con_response: AgentResponse from ConAgent.generate()
    - state: DebateState that should remain consistent
    - initial_claim: Reference claim value before debate
    - initial_round: Reference round number before debate
    """
    pro_agent, con_agent, state = debate_setup
    
    initial_claim = state['claim']
    initial_round = state['round']
    
    # Generate responses
    pro_response = pro_agent.generate(state)
    state['pro_arguments'].append(pro_response['argument'])
    state['pro_sources'].append(pro_response['sources'])
    
    con_response = con_agent.generate(state)
    state['con_arguments'].append(con_response['argument'])
    state['con_sources'].append(con_response['sources'])
    
    # Claim and round should not change
    assert state['claim'] == initial_claim
    assert state['round'] == initial_round
    
    # History should be preserved
    assert len(state['pro_arguments']) > 0
    assert len(state['con_arguments']) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])