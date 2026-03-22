"""
Unit tests for FactChecker agent
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import pytest
from unittest.mock import Mock, patch
from src.agents.fact_checker import FactChecker
from src.core.models import DebateState, SourceVerification, AgentResponse

@pytest.fixture
def mock_llm_client():
    return Mock()

@pytest.fixture
def fact_checker(mock_llm_client):
    return FactChecker(mock_llm_client)

@pytest.fixture
def sample_state():
    return DebateState(
        claim="Test claim",
        round=1,
        pro_sources=[["https://example.com/pro1"]],
        con_sources=[["https://example.com/con1"]]
    )

def test_fact_checker_initialization(fact_checker):
    assert fact_checker.role == "FACT_CHECKER"

@patch('requests.get')
def test_fact_checker_verifies_urls(mock_get, fact_checker, sample_state):
    # Mock successful response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.iter_content = Mock(return_value=[b"Sample content for verification"])
    mock_get.return_value = mock_response
    
    response = fact_checker.generate(sample_state)
    
    assert isinstance(response, AgentResponse)
    assert response.agent == "FACT_CHECKER"
    # Metrics should contain verification_results
    assert "verification_results" in response.metrics
    results = response.metrics["verification_results"]
    assert len(results) == 2
    assert results[0]["status"] == "VERIFIED"
    assert results[1]["status"] == "VERIFIED"

@patch('requests.get')
def test_fact_checker_handles_errors(mock_get, fact_checker, sample_state):
    # Mock failed response
    mock_response = Mock()
    mock_response.status_code = 404
    mock_response.iter_content = Mock(return_value=[b"Error"])
    mock_get.return_value = mock_response
    
    response = fact_checker.generate(sample_state)
    results = response.metrics["verification_results"]
    assert results[0]["status"] == "NOT_FOUND"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
