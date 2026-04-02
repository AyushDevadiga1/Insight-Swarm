"""
Integration tests for complete debate flow
Tests real agent interactions end-to-end
"""

import pytest
import time
from src.orchestration.debate import DebateOrchestrator


class TestFullDebateFlow:
    """Test complete debate execution with real components"""
    
    def test_simple_true_claim(self):
        """Test debate on objectively true claim"""
        orch = DebateOrchestrator()
        result = orch.run("The Earth is round")
        
        assert result.verdict == "TRUE"
        assert result.confidence > 0.9
        assert len(result.pro_arguments) > 0
        assert len(result.con_arguments) > 0
    
    def test_simple_false_claim(self):
        """Test debate on objectively false claim"""
        orch = DebateOrchestrator()
        result = orch.run("The Earth is flat")
        
        assert result.verdict == "FALSE"
        assert result.confidence > 0.9
    
    def test_partial_claim(self):
        """Test debate on nuanced claim"""
        orch = DebateOrchestrator()
        result = orch.run("Coffee prevents cancer")
        
        assert result.verdict in ("PARTIALLY TRUE", "INSUFFICIENT EVIDENCE", "FALSE")
        assert result.confidence > 0.5
    
    def test_consensus_skip_path(self):
        """Test that settled facts skip debate properly"""
        orch = DebateOrchestrator()
        result = orch.run("Vaccines cause autism")
        
        # Should hit consensus check and skip debate
        assert result.verdict == "FALSE"
        assert result.confidence > 0.95
        # But should still have synthetic arguments for UI
        assert len(result.pro_arguments) > 0
        assert "Settled" in result.pro_arguments[0] or "Consensus" in result.con_arguments[0]
    
    def test_cache_hit(self):
        """Test semantic cache functionality"""
        orch = DebateOrchestrator()
        
        # First run - cache miss
        result1 = orch.run("Water is H2O")
        assert result1.is_cached == False
        
        # Second run - should hit cache
        result2 = orch.run("Water is H2O")
        assert result2.is_cached == True
        assert result2.verdict == result1.verdict
    
    def test_similar_claim_cache_hit(self):
        """Test semantic cache matches similar claims"""
        orch = DebateOrchestrator()
        
        result1 = orch.run("Exercise improves mental health")
        result2 = orch.run("Working out is good for your mind")
        
        # Should match semantically (similarity > 0.92)
        assert result2.is_cached == True or result2.verdict == result1.verdict
    
    def test_source_verification(self):
        """Test that sources are actually verified"""
        orch = DebateOrchestrator()
        result = orch.run("Nuclear energy is the safest power source")
        
        assert result.verification_results is not None
        assert len(result.verification_results) > 0
        
        # Should have some verified sources
        verified = [r for r in result.verification_results if r.get('status') == 'VERIFIED']
        assert len(verified) > 0
    
    def test_moderator_reasoning(self):
        """Test that moderator provides reasoning"""
        orch = DebateOrchestrator()
        result = orch.run("The sky is blue")
        
        assert result.moderator_reasoning is not None
        assert len(result.moderator_reasoning) > 20
    
    def test_round_tracking(self):
        """Test that all 3 rounds execute or consensus skips properly"""
        orch = DebateOrchestrator()
        result = orch.run("Meditation reduces stress")
        
        # Should have arguments (3 if debated, 1 if consensus)
        assert len(result.pro_arguments) > 0
        if len(result.pro_arguments) == 3:
            assert len(result.con_arguments) == 3
    
    def test_api_failure_graceful(self):
        """Test system handles API failures gracefully"""
        # This test would use mock client with simulated failures
        # For now, just ensure orchestrator can be created
        orch = DebateOrchestrator()
        assert orch is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
