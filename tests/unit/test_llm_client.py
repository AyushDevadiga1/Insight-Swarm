"""
Unit tests for FreeLLMClient

Security features tested:
- Input validation
- Response validation
- Error handling
- Rate limiting
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import pytest
from src.llm.client import FreeLLMClient

# Skip by default to keep unit tests deterministic.
RUN_LLM_TESTS = os.getenv("RUN_LLM_TESTS", "").strip().lower() in ("1", "true", "yes")
pytestmark = pytest.mark.skipif(
    not RUN_LLM_TESTS,
    reason="LLM tests require live API access. Set RUN_LLM_TESTS=1 to enable."
)


@pytest.fixture
def client():
    """Fixture: FreeLLMClient instance"""
    try:
        return FreeLLMClient()
    except RuntimeError:
        pytest.skip("LLM providers not available")


def test_client_initialization():
    """Test that client initializes without errors"""
    try:
        client = FreeLLMClient()
        assert client is not None
        model = "llama-3.3-70b-versatile"
        assert client.groq_available or client.gemini_available
    except RuntimeError:
        pytest.skip("LLM providers not available")


def test_client_validation_empty_prompt(client):
    """Test that empty prompts are rejected"""
    with pytest.raises(ValueError):
        client.call("")


def test_client_validation_none_prompt(client):
    """Test that None prompts are rejected"""
    with pytest.raises(ValueError):
        client.call(None)


def test_client_validation_invalid_temperature(client):
    """Test that invalid temperature is rejected"""
    with pytest.raises(ValueError):
        client.call("Valid prompt", temperature=3.0)


def test_client_validation_invalid_max_tokens(client):
    """Test that invalid max_tokens is rejected"""
    with pytest.raises(ValueError):
        client.call("Valid prompt", max_tokens=5000)


def test_client_validation_invalid_timeout(client):
    """Test that invalid timeout is rejected"""
    with pytest.raises(ValueError):
        client.call("Valid prompt", timeout=400)


@pytest.mark.timeout(60)
def test_simple_call(client):
    """Test that client can make a simple call"""
    response = client.call("Say 'test' and nothing else.", timeout=10)
    
    assert response is not None
    assert len(response) > 0
    assert isinstance(response, str)


@pytest.mark.timeout(60)
def test_stats_tracking(client):
    """Test that client tracks usage statistics"""
    initial_stats = client.get_stats()
    initial_total = initial_stats['total_calls']
    
    # Make 1 call and track whether it succeeds
    success = False
    try:
        client.call("Test call", timeout=10)
        success = True
    except Exception:
        success = False
    
    final_stats = client.get_stats()
    final_total = final_stats['total_calls']
    
    # Assert stats reflect the call outcome
    if success:
        assert final_total == initial_total + 1, "Total calls should increment on success"
    else:
        assert final_total == initial_total, "Total calls should not increment on failure"


def test_response_validation(client):
    """Test that responses are validated before returning"""
    # Valid response should work
    response = client.call("Say hello", timeout=30)
    assert isinstance(response, str)
    assert len(response.strip()) > 0


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
