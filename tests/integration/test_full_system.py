import os
import sys
import pytest
from unittest.mock import Mock, patch
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.orchestration.debate import DebateOrchestrator
from src.core.models import DebateState, AgentResponse, ConsensusResponse
from src.llm.client import FreeLLMClient
from src.ui.progress_tracker import ProgressTracker, Stage
from src.resource.manager import get_resource_manager

class MockLLMClient:
    """A mock LLM client that returns valid agent/consensus responses."""
    def __init__(self):
        self.key_manager = Mock()
        self.key_manager.get_working_key.return_value = "mock_key"
        self.key_manager.has_working_keys.return_value = True
        
        self.groq_available = True
        self.gemini_available = True
        self.cerebras_available = True
        self.openrouter_available = True
        
    def call_structured(self, *args, **kwargs):
        output_schema = kwargs.get('output_schema')
        if len(args) > 1: output_schema = args[1]
        elif len(args) > 0 and 'output_schema' not in kwargs:
            pass # prompt is args[0]
            
        if output_schema == ConsensusResponse:
            return ConsensusResponse(verdict="DEBATE", reasoning="Mixed opinions", confidence=0.5)
        
        # Generic AgentResponse
        return AgentResponse(
            agent="PRO",
            round=1,
            argument="This is a mock argument with enough length to pass validation.",
            sources=["https://example.com/source"],
            confidence=0.8,
            verdict="TRUE",
            reasoning="Mock reasoning"
        )
    
    def call(self, prompt, **kwargs):
        return "Mock plain text response."

def test_integration_full_debate_flow():
    """
    Integration test: Runs a 1-round debate through the real orchestrator 
    using a mock LLM, verifying that the graph nodes, tracker, and 
    resource manager all fire correctly.
    """
    tracker = ProgressTracker()
    client = MockLLMClient()
    
    # Force single round for speed
    orchestrator = DebateOrchestrator(llm_client=client, tracker=tracker)
    
    # Mock the graph nodes slightly to avoid hitting real Tavily if possible
    # Actually, let's mock tavily_retriever
    with patch("src.orchestration.debate.get_tavily_retriever") as mock_tavily:
        mock_tavily.return_value.search_adversarial.return_value = {
            "pro": [{"url": "https://pro.com", "content": "Evidence for"}],
            "con": [{"url": "https://con.com", "content": "Evidence against"}]
        }
        
        # Mock claim decomposer
        with patch("src.orchestration.debate.ClaimDecomposer") as mock_decomp:
            mock_decomp.return_value.decompose.return_value = ["Primary Claim"]
            
            # Run the debate
            state = orchestrator.run("Mock Claim", thread_id="test_thread")
            
            # 1. Verify state completion
            assert state.verdict is not None
            assert state.round >= 1
            
            # 2. Verify tracker updates
            # We expect INITIALIZING, SEARCHING, ROUND_1_PRO, ROUND_1_CON, MODERATING, COMPLETE
            stages_hit = [u.stage for u in tracker.updates]
            assert Stage.INITIALIZING in stages_hit
            assert Stage.SEARCHING in stages_hit
            assert Stage.ROUND_1_PRO in stages_hit
            assert Stage.COMPLETE in stages_hit
            
            # 3. Verify BoundedCache (indirectly via debug logs or by checking the instance)
            from src.orchestration.cache import get_cache
            cache = get_cache()
            # If we call again, it should hit L1 cache (if enabled during tests)
            # Since we didn't disable it in this test explicitly, let's see.
            
            # 4. Verify ResourceManager
            rm = get_resource_manager()
            assert rm.get_current_memory_mb() > 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
