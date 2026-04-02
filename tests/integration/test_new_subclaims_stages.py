import os
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.orchestration.debate import DebateOrchestrator

class TestSSETracker:
    def __init__(self):
        self.events = []
    
    def set_stage(self, stage, message=""):
        self.events.append(str(stage))

def test_stage_event_coverage():
    orch = DebateOrchestrator()
    tracker = TestSSETracker()
    orch.set_tracker(tracker)
    
    # We just run the stream for a bit to capture stage events emitted directly by run or stream
    # Actually, let's capture from orch.stream() which is what the server uses
    events = []
    states = []
    
    # Using a claim we know won't hit consensus immediately 
    for event_type, state_data in orch.stream("Artificial intelligence will replace all software engineers by 2030", "test_thread"):
        events.append(event_type)
        states.append(state_data)
        
    # verify tracking stages were called
    st = [e for e in tracker.events]
    
    # Verify new decomposing and searching stages were emitted
    assert "Stage.DECOMPOSING" in st or "DECOMPOSING" in st
    assert "Stage.SEARCHING" in st or "SEARCHING" in st
    
    final_state = states[-1] if states else None
    assert final_state is not None
    # For a complex claim, sub_claims should be populated
    assert len(final_state.sub_claims) > 1

def test_sub_claims_in_state():
    orch = DebateOrchestrator()
    # A multi-part claim
    result = orch.run("Electric cars are better for the environment and cheaper to maintain")
    
    assert result.sub_claims is not None
    assert len(result.sub_claims) >= 2
    assert "environment" in str(result.sub_claims).lower() or "cheaper" in str(result.sub_claims).lower()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
