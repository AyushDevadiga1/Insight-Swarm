"""
Unit tests for FreeLLMClient
"""

import pytest
from src.llm.client import FreeLLMClient


def test_client_initialization():
    """Test that client initializes without errors"""
    client = FreeLLMClient()
    assert client is not None
    assert client.groq_available or client.gemini_available


def test_simple_call():
    """Test that client can make a simple call"""
    client = FreeLLMClient()
    
    response = client.call("Say 'test' and nothing else.")
    
    assert response is not None
    assert len(response) > 0
    assert isinstance(response, str)


def test_stats_tracking():
    """Test that client tracks usage statistics"""
    client = FreeLLMClient()
    
    # Make 2 calls
    client.call("Test 1")
    client.call("Test 2")
    
    stats = client.get_stats()
    
    assert stats['total_calls'] == 2
    assert stats['groq_calls'] + stats['gemini_calls'] == 2


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])