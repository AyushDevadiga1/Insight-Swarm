import sys
import os
import json
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestration.debate import DebateOrchestrator
from src.llm.client import FreeLLMClient

BENCHMARK_CLAIMS = [
    "Climate change is a hoax created by scientists.",
    "BPA in plastic is safe for human consumption.",
    "Drinking 8 glasses of water a day is a medical requirement.",
    "The Great Wall of China is visible from the moon.",
    "Aspirin can prevent heart attacks in everyone."
]

def run_benchmark():
    print("--- Starting InsightSwarm Benchmark Suite ---")
    client = FreeLLMClient()
    orchestrator = DebateOrchestrator(client)
    results = []

    for claim in BENCHMARK_CLAIMS:
        print(f"\nEvaluating Claim: '{claim}'")
        start_time = time.time()
        try:
            state = orchestrator.run(claim)
            duration = time.time() - start_time
            
            # Simple Hallucination Check: Do agents use URLs not in source list?
            # (Heuristic: extract URLs from arguments and compare with source list)
            import re
            url_pattern = re.compile(r'https?://\S+')
            found_urls = set()
            for arg in state.pro_arguments + state.con_arguments:
                found_urls.update(url_pattern.findall(arg))
            
            source_urls = {s.get('url') for s in state.evidence_sources if s.get('url')}
            hallucinated_urls = [u for u in found_urls if u not in source_urls]
            
            # Use LLM as Judge for Quality (Audit #24)
            judge_prompt = f"""Evaluate the following debate result for accuracy, grounding, and neutrality.
CLAIM: {state.claim}
VERDICT: {state.verdict}
REASONING: {state.moderator_reasoning}
PRO ARGUMENTS: {state.pro_arguments}
CON ARGUMENTS: {state.con_arguments}

Respond in JSON:
{{
  "hallucination_risk": 0.0-1.0,
  "accuracy_score": 0.0-1.0,
  "grounding_score": 0.0-1.0,
  "feedback": "Short critique"
}}
"""
            eval_res = client.call_structured(judge_prompt, dict, preferred_provider="gemini")
            
            result_item = {
                "claim": claim,
                "verdict": state.verdict,
                "confidence": state.confidence,
                "duration_s": duration,
                "hallucinated_urls_count": len(hallucinated_urls),
                "evaluation": eval_res
            }
            results.append(result_item)
            print(f"--- Success: {state.verdict} ({state.confidence:.2%}) in {duration:.1f}s")
            print(f"--- Quality: Accuracy={eval_res.get('accuracy_score')}, Grounding={eval_res.get('grounding_score')}")
            
        except Exception as e:
            print(f"--- Failed: {e}")
            results.append({"claim": claim, "status": "failed", "error": str(e)})

    # Save report
    report_path = Path("tests/benchmark_report.json")
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n--- Benchmark Complete. Report saved to {report_path}")

if __name__ == "__main__":
    run_benchmark()
