"""
Baseline tests for current 4-agent system.

Run these BEFORE adding adversarial components to establish baseline.
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import pytest
from src.orchestration.debate import DebateOrchestrator


@pytest.fixture
def orchestrator():
    """Current 4-agent orchestrator"""
    orchestrator = DebateOrchestrator()
    yield orchestrator
    orchestrator.close()


def test_current_system_complete_flow(orchestrator):
    """Test current system runs end-to-end"""
    
    result = orchestrator.run("Coffee prevents cancer")
    
    # Should have all components
    assert result['verdict'] is not None
    assert result['confidence'] is not None
    assert result['moderator_reasoning'] is not None
    assert 'pro_verification_rate' in result
    assert 'con_verification_rate' in result
    
    # Should have 3 rounds
    assert len(result['pro_arguments']) == 3
    assert len(result['con_arguments']) == 3


def test_current_factchecker_works(orchestrator):
    """Test FactChecker verifies sources correctly"""
    
    result = orchestrator.run("The Earth is flat")
    
    # Should have verification results
    assert 'verification_results' in result
    
    # Should detect some sources (even if they're bad)
    total_sources = sum(len(s) for s in result['pro_sources'] + result['con_sources'])
    if total_sources > 0:
        assert result.get('verification_results') is not None


def test_current_moderator_produces_reasoning(orchestrator):
    """Test Moderator provides detailed reasoning"""
    
    result = orchestrator.run("Exercise improves mental health")
    
    # Moderator should provide reasoning
    assert result['moderator_reasoning'] is not None
    assert len(result['moderator_reasoning']) > 100  # Substantial reasoning


if __name__ == "__main__":
    pytest.main([__file__, "-v"])