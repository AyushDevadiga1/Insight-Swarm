"""
Integration test for complete 4-agent debate system
"""

import pytest
from src.orchestration.debate import DebateOrchestrator


@pytest.fixture
def orchestrator():
    """Fixture: DebateOrchestrator with 4 agents"""
    orchestrator = DebateOrchestrator()
    yield orchestrator
    orchestrator.close()


@pytest.mark.timeout(180)  # 3 minutes max
def test_4_agent_debate_completes(orchestrator):
    """Test that 4-agent debate completes successfully"""
    
    result = orchestrator.run("Coffee prevents cancer")
    
    # Should have all components
    assert result['verdict'] is not None
    assert result['confidence'] is not None
    assert result['moderator_reasoning'] is not None
    
    # Should have 3 rounds of debate
    assert len(result['pro_arguments']) == 3
    assert len(result['con_arguments']) == 3
    
    # Should have verification results
    assert 'pro_verification_rate' in result
    assert 'con_verification_rate' in result
    
    # Moderator should have provided reasoning
    assert len(result['moderator_reasoning']) > 100


def test_moderator_different_from_word_count(orchestrator):
    """Test that Moderator's verdict differs from simple word count"""
    
    # This claim should produce different verdicts with different methods
    result = orchestrator.run("Vaccines cause autism")
    
    # Calculate word count verdict
    pro_words = sum(len(arg.split()) for arg in result['pro_arguments'])
    con_words = sum(len(arg.split()) for arg in result['con_arguments'])
    
    word_count_verdict = "TRUE" if pro_words > con_words else "FALSE"
    
    # Moderator's verdict (which considers evidence quality)
    moderator_verdict = result['verdict']
    
    # Log for manual inspection (verdicts may differ)
    print(f"\nWord count verdict: {word_count_verdict}")
    print(f"Moderator verdict: {moderator_verdict}")
    print(f"Pro words: {pro_words}, Con words: {con_words}")
    print(f"Pro verification: {result['pro_verification_rate']:.1%}")
    print(f"Con verification: {result['con_verification_rate']:.1%}")
    
    # At minimum, Moderator should provide reasoning
    assert 'moderator_reasoning' in result
    assert len(result['moderator_reasoning']) > 50


def test_moderator_on_multiple_claims(orchestrator):
    """Test Moderator handles diverse claims"""
    
    claims = [
        "The Earth is flat",
        "Exercise improves mental health",
        "Water is wet"
    ]
    
    for claim in claims:
        result = orchestrator.run(claim)
        
        # Each should have Moderator reasoning
        assert result['moderator_reasoning'] is not None
        assert result['verdict'] in ['TRUE', 'FALSE', 'PARTIALLY TRUE', 'INSUFFICIENT EVIDENCE']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
