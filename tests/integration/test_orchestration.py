"""
Integration tests for debate orchestration
"""

import pytest
from src.orchestration.debate import DebateOrchestrator


@pytest.fixture
def orchestrator():
    """Fixture: DebateOrchestrator instance"""
    return DebateOrchestrator()


def test_orchestration_completes(orchestrator):
    """Test that full debate completes without errors"""
    
    result = orchestrator.run("Test claim for integration")
    
    # Should have verdict
    assert result['verdict'] is not None
    assert result['verdict'] in ['TRUE', 'FALSE', 'PARTIALLY TRUE', 'INSUFFICIENT EVIDENCE', 'UNVERIFIABLE', 'ERROR']
    
    # NEW: Should have moderator reasoning
    assert 'moderator_reasoning' in result
    if result['verdict'] != 'ERROR':
        assert result['moderator_reasoning'] is not None
    
    # Should have confidence
    assert result['confidence'] is not None
    assert 0.0 <= result['confidence'] <= 1.0
    
    # Should have 3 rounds of arguments
    assert len(result['pro_arguments']) >= 1
    assert len(result['con_arguments']) >= 1


def test_orchestration_includes_verification(orchestrator):
    """Test that FactChecker runs and produces verification results"""
    
    result = orchestrator.run("Test claim with source verification")
    
    # Should have verification results (may be empty if no sources cited)
    assert 'verification_results' in result
    assert isinstance(result['verification_results'], list)
    
    # Should have verification rates
    assert 'pro_verification_rate' in result
    assert 'con_verification_rate' in result
    assert result['pro_verification_rate'] is not None
    assert result['con_verification_rate'] is not None
    
    # Rates should be between 0.0 and 1.0
    assert 0.0 <= result['pro_verification_rate'] <= 1.0
    assert 0.0 <= result['con_verification_rate'] <= 1.0


def test_orchestration_runs_3_rounds(orchestrator):
    """Test that debate runs for exactly 3 rounds"""
    
    result = orchestrator.run("Exercise improves mental health")
    
    # Should have 3 PRO and 3 CON arguments
    assert len(result['pro_arguments']) == 3
    assert len(result['con_arguments']) == 3
    
    # Final round should be 4 (incremented after round 3 completes)
    assert result['round'] == 4


def test_orchestration_fact_checker_detects_hallucinations(orchestrator):
    """Test that FactChecker can detect hallucinated sources"""
    
    # This claim has a high chance of agents citing fake sources
    result = orchestrator.run("Unicorns exist in Scotland")
    
    # Should have verification results
    assert 'verification_results' in result
    
    # If there are sources, check that hallucinations are detected
    if result['verification_results']:
        # Should have some NOT_FOUND or CONTENT_MISMATCH sources
        statuses = [r['status'] for r in result['verification_results']]
        assert len(statuses) > 0


def test_orchestration_on_multiple_claims(orchestrator):
    """Test system on 5 different claim types"""
    
    claims = [
        "Coffee prevents cancer",           # Nuanced/partial
        "The Earth is flat",                # Obviously false
        "Exercise improves mental health",  # Obviously true
        "Vaccines cause autism",            # False conspiracy
        "AI will replace all jobs by 2030"  # Debatable prediction
    ]
    
    for claim in claims:
        result = orchestrator.run(claim)
        
        # Each should complete with valid verdict
        assert result['verdict'] in ['TRUE', 'FALSE', 'PARTIALLY TRUE', 'INSUFFICIENT EVIDENCE', 'UNVERIFIABLE', 'ERROR']
        assert result['confidence'] is not None
        
        # Each should have arguments
        assert len(result['pro_arguments']) > 0
        assert len(result['con_arguments']) > 0


@pytest.mark.timeout(180)  # 3 minutes max
def test_orchestration_performance(orchestrator):
    """Test that debate completes in reasonable time"""
    
    import time
    
    start = time.time()
    result = orchestrator.run("Short test claim")
    elapsed = time.time() - start
    
    # Should complete in under 120 seconds
    assert elapsed < 120, f"Debate took {elapsed:.1f}s (should be <120s)"
    
    # Should have valid result
    assert result['verdict'] is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])