"""
scripts/run_ablation.py
========================
Ablation study for InsightSwarm.
Tests 4 configurations on a 50-claim FEVER subset to isolate the contribution
of each novel component.

Configurations:
  1. full_system       — everything enabled (baseline for comparison)
  2. no_trust_weighting — disable trust-weighted scoring in Moderator
  3. single_agent       — skip debate entirely, use only Moderator LLM
  4. no_calibration     — disable AdaptiveConfidenceCalibrator

Usage:
    python scripts/run_ablation.py
    python scripts/run_ablation.py --n 20 --configs full_system,no_calibration

Output:
    outputs/ablation_results.json
"""

import argparse
import json
import sys
import time
from copy import deepcopy
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, List, Optional

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

OUTPUTS_DIR = ROOT / "outputs"
DATA_DIR    = ROOT / "data"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# Reuse metric helpers from benchmark_suite
sys.path.insert(0, str(ROOT / "tests"))
from benchmark_suite import (
    compute_metrics, ClaimResult,
    POSITIVE_VERDICTS, NEGATIVE_VERDICTS, PARTIAL_VERDICTS,
)


# ── Config patches ────────────────────────────────────────────────────────────

def patch_no_trust_weighting():
    """
    Monkey-patch Moderator._calculate_weighted_score to return an unweighted
    (simple count-based) score, disabling trust-weighting.
    """
    from src.agents.moderator import Moderator

    def _simple_rate(self, results, agent):
        agent_results = [r for r in results if isinstance(r, dict) and r.get("agent_source") == agent]
        if not agent_results:
            return 0.0
        verified = sum(1 for r in agent_results if r.get("status") == "VERIFIED")
        return verified / len(agent_results)

    Moderator._calculate_weighted_score = _simple_rate


def patch_no_calibration():
    """
    Monkey-patch confidence_calibration so calibrate() always returns
    the raw confidence unchanged. Simulates removing the calibration module.
    """
    import src.novelty.confidence_calibration as cc

    class _NoopCalibrator:
        def calibrate(self, raw_confidence, **kwargs):
            return raw_confidence, {
                "adjustment_type":        "disabled",
                "raw_confidence":         raw_confidence,
                "calibrated_confidence":  raw_confidence,
                "adjustment":             0.0,
                "underconfidence_detected": False,
            }

    cc._calibrator = _NoopCalibrator()


class SingleAgentOrchestrator:
    """
    Stripped-down orchestrator that skips the full debate and uses only
    the Moderator LLM with zero debate context. Represents 'no multi-agent'.
    """
    def __init__(self, llm_client):
        from src.agents.moderator import Moderator
        from src.core.models import DebateState
        self.moderator  = Moderator(llm_client)
        self.DebateState = DebateState

    def run(self, claim: str, thread_id: str = "sa-default"):
        state = self.DebateState(
            claim=claim,
            pro_arguments=["The claim may be true based on general knowledge."],
            con_arguments=["The claim may be false based on general knowledge."],
            pro_sources=[[]], con_sources=[[]],
            verification_results=[], pro_verification_rate=0.0, con_verification_rate=0.0,
        )
        try:
            response         = self.moderator.generate(state)
            state.verdict    = response.verdict
            state.confidence = response.confidence
            state.moderator_reasoning = response.reasoning
            state.metrics    = response.metrics or {}
        except Exception as e:
            state.verdict    = "ERROR"
            state.confidence = 0.0
        return state


# ── Run a single config ───────────────────────────────────────────────────────

def run_config(
    config_name: str,
    config_label: str,
    claims: List[Dict],
    n: int,
) -> List[ClaimResult]:
    from src.llm.client import FreeLLMClient

    client = FreeLLMClient()

    if config_name == "single_agent":
        orch = SingleAgentOrchestrator(client)
    else:
        from src.orchestration.debate import DebateOrchestrator
        orch = DebateOrchestrator(client)

    sample  = claims[:n]
    results = []

    print(f"\n  Running: {config_label} ({len(sample)} claims)")

    for i, item in enumerate(sample, 1):
        claim    = item["claim"]
        gt_label = item["fever_label"]
        start    = time.time()

        try:
            state   = orch.run(claim)
            latency = time.time() - start
            sv      = (state.verdict or "UNKNOWN").upper().strip()
            sc      = float(state.confidence or 0.0)
            correct = (sv in POSITIVE_VERDICTS and gt_label == "SUPPORTS") or \
                      (sv in NEGATIVE_VERDICTS  and gt_label == "REFUTES")
            partial = 0.5 if (sv in PARTIAL_VERDICTS and gt_label in ("SUPPORTS","REFUTES")) else 0.0

            result = ClaimResult(
                claim=claim, fever_label=gt_label,
                expected_verdict=item["expected_verdict"],
                system_verdict=sv, system_confidence=sc,
                correct=correct, partial_credit=partial,
                latency_s=latency,
            )
            mark = "✓" if correct else "✗"
            print(f"    [{i:>2}/{len(sample)}] {sv:<25} GT:{gt_label:<12} {mark} {latency:.1f}s")

        except Exception as e:
            latency = time.time() - start
            result = ClaimResult(
                claim=claim, fever_label=gt_label,
                expected_verdict=item["expected_verdict"],
                system_verdict="ERROR", system_confidence=0.0,
                correct=False, partial_credit=0.0, latency_s=latency, error=str(e),
            )
            print(f"    [{i:>2}/{len(sample)}] ERROR: {e}")

        results.append(result)

    return results


# ── Main ──────────────────────────────────────────────────────────────────────

CONFIGS = {
    "full_system":        "Full system (all novelty enabled)",
    "no_trust_weighting": "No trust-weighted scoring",
    "single_agent":       "Single-agent (no debate)",
    "no_calibration":     "No confidence calibration",
}

def main():
    parser = argparse.ArgumentParser(description="InsightSwarm Ablation Study")
    parser.add_argument("--n",       type=int,  default=50, help="Claims per config (default: 50)")
    parser.add_argument("--data",    type=str,  default=None, help="Path to fever_sample.json")
    parser.add_argument("--configs", type=str,  default=None,
                        help="Comma-separated subset of configs to run (default: all)")
    args = parser.parse_args()

    data_path = Path(args.data) if args.data else DATA_DIR / "fever_sample.json"
    if not data_path.exists():
        print(f"ERROR: {data_path} not found.")
        print("Run: python scripts/download_fever.py")
        sys.exit(1)

    with open(data_path, encoding="utf-8") as f:
        all_claims = json.load(f)

    # Use a fixed balanced sub-sample for ablation reproducibility
    supports = [c for c in all_claims if c["fever_label"] == "SUPPORTS"][:args.n // 2]
    refutes  = [c for c in all_claims if c["fever_label"] == "REFUTES"][:args.n // 2]
    claims   = supports + refutes

    configs_to_run = args.configs.split(",") if args.configs else list(CONFIGS.keys())

    print(f"\n{'='*60}")
    print(f"InsightSwarm Ablation Study — {len(claims)} claims × {len(configs_to_run)} configs")
    print(f"{'='*60}")

    ablation_results = []

    for config_name in configs_to_run:
        if config_name not in CONFIGS:
            print(f"WARNING: Unknown config '{config_name}' — skipping")
            continue

        config_label = CONFIGS[config_name]

        # Apply patches (must be done before creating orchestrator)
        if config_name == "no_trust_weighting":
            patch_no_trust_weighting()
        elif config_name == "no_calibration":
            patch_no_calibration()

        results = run_config(config_name, config_label, claims, n=len(claims))
        metrics = compute_metrics(results)
        metrics.update({
            "config":       config_name,
            "config_label": config_label,
        })
        ablation_results.append(metrics)

        print(f"\n  {config_label}:")
        print(f"    Accuracy: {metrics['accuracy']:.1%}  F1: {metrics['f1']:.1%}")

        # Reset patches by reimporting (simple but effective for sequential configs)
        if config_name in ("no_trust_weighting", "no_calibration"):
            import importlib
            import src.agents.moderator
            import src.novelty.confidence_calibration
            importlib.reload(src.agents.moderator)
            importlib.reload(src.novelty.confidence_calibration)

    # ── Save ──────────────────────────────────────────────────────────────────
    output = {
        "n_per_config": len(claims),
        "timestamp":    time.strftime("%Y-%m-%d %H:%M:%S"),
        "results":      ablation_results,
    }

    out_path = OUTPUTS_DIR / "ablation_results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Ablation results → {out_path}")
    print(f"\nΔF1 relative to full system:")
    full_f1 = next((r["f1"] for r in ablation_results if r["config"] == "full_system"), None)
    if full_f1 is not None:
        for r in ablation_results:
            delta = (r["f1"] - full_f1) * 100
            sign  = "+" if delta >= 0 else ""
            print(f"  {r['config_label']:<42} {sign}{delta:.1f}% ΔF1")
    print(f"{'='*60}")

    # Tip: run generate_paper_metrics.py after this
    print("\nNext: python scripts/generate_paper_metrics.py --ablation outputs/ablation_results.json")


if __name__ == "__main__":
    main()
