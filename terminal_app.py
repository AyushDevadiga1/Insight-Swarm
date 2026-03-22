import sys
# FLASH BOOT - DO NOT MOVE
print("✨ [BOOT] Terminal Engine Starting...", flush=True)

import argparse
import logging
import time
from typing import Optional

# Set up logging early
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TerminalApp")

print("✨ [IMPORTS] Loading InsightSwarm Core Components...", flush=True)
try:
    from src.orchestration.debate import DebateOrchestrator
    from src.ui.progress_tracker import ProgressTracker, Stage
    print("✨ [IMPORTS] Success.", flush=True)
except Exception as e:
    print(f"❌ [IMPORTS] Failed: {e}", flush=True)
    sys.exit(1)

class TerminalTracker(ProgressTracker):
    """A progress tracker that prints precisely to the console."""
    def update(self, stage: Stage, message: str, progress: float = 0.0, **metadata):
        super().update(stage, message, progress, **metadata)
        print(f"\n[{stage.name}] ➔ {message} ({progress*100:.0f}%)", flush=True)
        if metadata:
            print(f"   └─ Meta: {metadata}", flush=True)

def main():
    parser = argparse.ArgumentParser(description="InsightSwarm Terminal Demo")
    parser.add_argument("--claim", type=str, required=True, help="The claim to verify")
    parser.add_argument("--mode", type=str, choices=["live", "simulation"], default="live", help="Simulation or Live mode")
    args = parser.parse_args()

    print("\n" + "="*80, flush=True)
    print(f"🚀 InsightSwarm Terminal Replica - {args.mode.upper()} MODE", flush=True)
    print("="*80, flush=True)
    print(f"Claim: {args.claim}\n", flush=True)

    tracker = TerminalTracker()

    try:
        if args.mode == "simulation":
            from tests.sandbox.api_simulator import MockChaosClient, ChaosConfig
            config = ChaosConfig(failure_rate=0.0, rate_limit_rate=0.0) # Zero failure for demo
            client = MockChaosClient(config)
            orchestrator = DebateOrchestrator(llm_client=client, tracker=tracker)
        else:
            print("🔧 Initializing Live Orchestrator...", flush=True)
            orchestrator = DebateOrchestrator(tracker=tracker)

        print("🔍 Starting Debate Engine...", flush=True)
        start_time = time.time()
        # In terminal mode, we often want fresh runs for debugging
        # Let's add a small hack to ensure fresh runs if desired, 
        # or just accept that the user might want cache on.
        result = orchestrator.run(args.claim)
        end_time = time.time()

        print("\n" + "="*80, flush=True)
        print("🎯 FINAL RESULT", flush=True)
        print("="*80, flush=True)
        print(f"Verdict: {result.verdict}", flush=True)
        print(f"Confidence: {result.confidence*100:.1f}%", flush=True)
        print(f"Reasoning: {result.moderator_reasoning}", flush=True)
        print(f"Duration: {end_time - start_time:.1f}s", flush=True)
        print("="*80 + "\n", flush=True)

    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user.", flush=True)
    except Exception as e:
        logger.exception(f"❌ Critical failure: {e}")
        print(f"\n❌ FAILED: {str(e)}", flush=True)

if __name__ == "__main__":
    main()
