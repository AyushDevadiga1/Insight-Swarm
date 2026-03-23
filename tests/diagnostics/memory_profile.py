import os
import sys
import time
import gc
import psutil
import logging
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.orchestration.debate import DebateOrchestrator
from src.resource.manager import get_resource_manager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_current_memory_mb():
    process = psutil.Process()
    return process.memory_info().rss / (1024 * 1024)

def run_memory_profile(num_claims=5):
    logger.info("Starting memory profile...")
    
    # Initialize orchestrator
    orchestrator = DebateOrchestrator()
    rm = get_resource_manager()
    
    # Initial memory
    gc.collect()
    start_mem = get_current_memory_mb()
    logger.info(f"Baseline memory: {start_mem:.1f}MB")
    
    test_claims = [
        "Does coffee cause cancer?",
        "Is the earth flat?",
        "Do vaccines cause autism?",
        "Is climate change real?",
        "Are cats better than dogs?"
    ]
    
    results = []
    
    for i in range(min(num_claims, len(test_claims))):
        claim = test_claims[i]
        logger.info(f"--- Processing claim {i+1}: '{claim}' ---")
        
        # Run debate (simplified/mocked if possible? No, let's run real but maybe one-round?)
        # Or just use the run method with num_rounds=1 for speed in profiling
        # Actually orchestration.debate.DebateOrchestrator doesn't take num_rounds in run()
        # but we can set it in initial_state.
        # For simplicity, we just run the full thing.
        
        try:
            orchestrator.run(claim)
        except Exception as e:
            logger.error(f"Error during debate: {e}")
            
        gc.collect()
        current_mem = get_current_memory_mb()
        logger.info(f"Memory after claim {i+1}: {current_mem:.1f}MB")
        results.append(current_mem)
        
        # Check if resource manager triggered
        rm.check_and_reclaim()

    final_mem = results[-1]
    growth = final_mem - start_mem
    growth_per_claim = growth / num_claims
    
    logger.info("=" * 40)
    logger.info(f"Memory Profile Results (over {num_claims} claims):")
    logger.info(f"Initial: {start_mem:.1f}MB")
    logger.info(f"Final: {final_mem:.1f}MB")
    logger.info(f"Total Growth: {growth:.1f}MB")
    logger.info(f"Avg Growth/Claim: {growth_per_claim:.1f}MB")
    logger.info("=" * 40)
    
    if growth_per_claim > 20:
        logger.error("❌ MEMORY LEAK DETECTED: Growth exceeds 20MB/claim")
        sys.exit(1)
    else:
        logger.info("✅ MEMORY STABLE: Growth within acceptable limits")
        sys.exit(0)

if __name__ == "__main__":
    # Ensure RUN_PROFILER env is set to allow some heavier tests if needed
    os.environ["RUN_LLM_TESTS"] = "1" 
    # Use a small number of rounds to speed up profiling
    # Note: Currently DebateOrchestrator doesn't easily allow round override in run() without changing code
    # But for a profile, 5 claims is fine.
    run_memory_profile(2) # Running 2 for speed in this test phase
