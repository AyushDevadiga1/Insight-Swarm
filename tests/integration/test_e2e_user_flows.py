"""
End-to-end tests simulating complete user workflows
Tests from UI input through to final verdict display
"""

import pytest
import time
from src.orchestration.debate import DebateOrchestrator
from src.utils.validation import validate_claim


class TestUserWorkflows:
    """Test complete user interaction flows"""
    
    def test_valid_claim_submission(self):
        """User submits valid claim, gets verdict"""
        claim = "Regular exercise improves cardiovascular health"
        
        # Step 1: Validation
        valid, error = validate_claim(claim)
        assert valid == True
        assert error == ""
        
        # Step 2: Debate
        orch = DebateOrchestrator()
        result = orch.run(claim)
        
        # Step 3: Verify result structure
        assert result.verdict in ("TRUE", "FALSE", "PARTIALLY TRUE", "INSUFFICIENT EVIDENCE")
        assert result.confidence >= 0.0 and result.confidence <= 1.0
        assert result.moderator_reasoning is not None
    
    def test_invalid_claim_rejection(self):
        """User submits invalid claim, gets validation error"""
        invalid_claims = [
            "",  # Empty
            "abc",  # Too short
            "a b c d e f g h i",  # Meaningless
            "x" * 501,  # Too long
        ]
        
        for claim in invalid_claims:
            valid, error = validate_claim(claim)
            assert valid == False
            assert len(error) > 0
    
    def test_rapid_consecutive_claims(self):
        """User submits multiple claims rapidly"""
        claims = [
            "Coffee is healthy",
            "Tea has caffeine",
            "Water is essential",
        ]
        
        orch = DebateOrchestrator()
        results = []
        
        start = time.time()
        for claim in claims:
            result = orch.run(claim)
            results.append(result)
        elapsed = time.time() - start
        
        # All should complete successfully
        assert len(results) == 3
        assert all(r.verdict is not None for r in results)
        
        # Later claims should hit cache or complete quickly
        assert any(r.is_cached for r in results[1:]) or elapsed < 60
    
    def test_feedback_collection(self):
        """User provides feedback on verdict"""
        from src.orchestration.cache import record_feedback
        
        claim = "Test claim for feedback"
        verdict = "TRUE"
        
        # Should not raise exception
        try:
            record_feedback(claim, verdict, "UP")
            record_feedback(claim, verdict, "DOWN")
            success = True
        except Exception as e:
            success = False
            print(f"Feedback failed: {e}")
        
        assert success == True
    
    def test_claim_length_validation(self):
        """Test claim length boundaries"""
        # Minimum length (10 chars)
        valid, _ = validate_claim("Short test")
        assert valid == True
        
        valid, error = validate_claim("Too short")  # 9 chars
        assert valid == False
        
        # Maximum length (500 chars)
        valid, _ = validate_claim("x" * 500)
        assert valid == True
        
        valid, error = validate_claim("x" * 501)
        assert valid == False
        assert "too long" in error.lower()
    
    def test_settled_facts_fast_path(self):
        """Settled facts should skip debate and return quickly"""
        settled_claims = [
            "The Earth is round",
            "Water is H2O",
            "Vaccines cause autism",  # False but settled
        ]
        
        orch = DebateOrchestrator()
        
        for claim in settled_claims:
            start = time.time()
            result = orch.run(claim)
            elapsed = time.time() - start
            
            # Should complete quickly (consensus skip)
            assert elapsed < 30  # Much faster than full debate
            assert result.verdict is not None
            assert result.confidence > 0.9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
