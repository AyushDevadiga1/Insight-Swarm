import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.orchestration.debate import DebateOrchestrator

def main():
    orch = DebateOrchestrator()
    print("Testing 'water is h2o'...")
    for event_type, state in orch.stream("water is h2o", "test_thread2"):
        if hasattr(state, "model_dump"):
            state = state.model_dump()
        print(f"[{event_type}]")
        if event_type == "progress":
            print("  Pro arguments:", len(state.get("pro_arguments", [])))
            for pa in state.get("pro_arguments", []):
                print(f"    - {pa[:60]}...")
            print("  Pro sources:", len(state.get("pro_sources", [])))
        elif event_type == "complete":
            print("Verdict:", state.get("verdict"))
            print("Reasoning:", state.get("moderator_reasoning"))
            for pa in state.get("pro_arguments", []):
                print(f"  PA: {pa}")
            for ca in state.get("con_arguments", []):
                print(f"  CA: {ca}")
if __name__ == "__main__":
    main()
