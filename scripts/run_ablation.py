"""
scripts/run_ablation.py
========================
Ablation study for InsightSwarm.
Tests 5 configurations on a 50-claim FEVER subset to isolate the contribution
of each novel component.

Configurations:
  1. full_system        — everything enabled (baseline for comparison)
  2. no_trust_weighting — disable trust-weighted scoring in Moderator
  3. single_agent       — skip debate, use only Moderator LLM
  4. no_calibration     — disable AdaptiveConfidenceCalibrator
  5. no_complexity      — disable ClaimComplexityEstimator (fixed 3 rounds)

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
from pathlib import Path
from typing import Dict, Any, List, Optional

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

OUTPUTS_DIR = ROOT / "outputs"
DATA_DIR    = ROOT / "data"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

from benchmark_suite import (
    compute_metrics, ClaimResult,
    POSITIVE_VERDICTS, NEGATIVE_VERDICTS, PARTIAL_VERDICTS,
)


# ── Config patches ─────────────────────────────────────────────────────────────

def patch_no_trust_weighting():
    """Replace trust-weighted rate with simple unweighted count-based rate."""
    from src.agents.moderator import Moderator

    def _simple_rate(self, results, agent):
        agent_results = [r for r in results if isinstance(r, dict) and r.get("agent_source") == agent]
        if not agent_results:
            return 0.0
        verified = sum(1 for r in agent_results if r.get("status") == "VERIFIED")
        return verified / len(agent_results)

    Moderator._calculate_weighted_score = _simple_rate


def patch_no_calibration():
    """Replace calibrator with a no-op that returns raw confidence unchanged."""
    import src.novelty.confidence_calibration as cc

    class _NoopCalibrator:
        def calibrate(self, raw_confidence, **kwargs):
            return raw_confidence, {
                "adjustment_type": "disabled",
                "raw_confidence": raw_confidence,
                "calibrated_confidence": raw_confidence,
                "adjustment": 0.0,
                "underconfidence_detected": False,
            }

    cc._calibrator = _NoopCalibrator()


def patch_no_complexity():
    """
    Replace ClaimComplexityEstimator with a no-op that always returns
    medium complexity → 3 rounds, 4 sources (default behaviour).
    """
    import src.novelty.claim_complexity as cc

    class _NoopEstimator:
        def estimate_complexity(self, claim: str) -> dict:
            return {
                "overall_complexity": 0.4,
                "complexity_tier": "medium",
                "recommended_debate_rounds": 3,
                "recommended_min_sources": 4,
                "requires_expert_review": False,
            }

        def adjust_debate_parameters(self, base_rounds: int, base_sources: int, profile: dict) -> dict:
            return {"adjusted_rounds": base_rounds, "adjusted_min_sources": base_sources,
                    "reasoning": "complexity estimation disabled"}

    cc._estimator = _NoopEstimator()


class SingleAgentOrchestrator:
    """
    Stripped orchestrator — no debate, no evidence retrieval.
    Represents the single-LLM baseline used in the paper.
    """
    def __init__(self, llm_client):
        from src.agents.moderator import Moderator
        from src.core.models import DebateState
        self.moderator   = Moderator(llm_client)
        self.DebateState = DebateState

    def run(self, claim: str, thread_id: str = "sa-default"):
        state = self.DebateState(
            claim=claim,
            pro_arguments=["The claim may be true based on general knowledge."],
            con_arguments=["The claim may be false based on general knowledge."],
            pro_sources=[[]], con_sources=[[]],
            verification_results=[],
            pro_verification_rate=0.0, con_verification_rate=0.0,
        )
        try:
            response              = self.moderator.generate(state)
            state.verdict         = response.verdict
            state.confidence      = response.confidence
            state.moderator_reasoning = response.reasoning
            state.metrics         = response.metrics or {}
        except Exception as e:
            state.verdict    = "ERROR"
            state.confidence = 0.0
        return state

    def close(self):
        pass


# ── Run one config ─────────────────────────────────────────────────────────────

def run_config(config_name: str, config_label: str, claims: List[Dict], n: int) -> List[ClaimResult]:
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
            correct = ((sv in POSITIVE_VERDICTS and gt_label == "SUPPORTS") or
                       (sv in NEGATIVE_VERDICTS  and gt_label == "REFUTES"))
            partial = 0.5 if (sv in PARTIAL_VERDICTS and gt_label in ("SUPPORTS", "REFUTES")) else 0.0
            result  = ClaimResult(
                claim=claim, fever_label=gt_label,
                expected_verdict=item["expected_verdict"],
                system_verdict=sv, system_confidence=sc,
                correct=correct, partial_credit=partial, latency_s=latency,
            )
            print(f"    [{i:>2}/{len(sample)}] {sv:<25} GT:{gt_label:<12} {'✓' if correct else '✗'} {latency:.1f}s")
        except Exception as e:
            latency = time.time() - start
            result  = ClaimResult(
                claim=claim, fever_label=gt_label,
                expected_verdict=item["expected_verdict"],
                system_verdict="ERROR", system_confidence=0.0,
                correct=False, partial_credit=0.0, latency_s=latency, error=str(e),
            )
            print(f"    [{i:>2}/{len(sample)}] ERROR: {e}")
        results.append(result)

    if hasattr(orch, "close"):
        orch.close()
    return results


# ── Config registry ────────────────────────────────────────────────────────────

CONFIGS: Dict[str, Dict] = {
    "full_system": {
        "label": "Full system (all contributions enabled)",
        "patch": None,
    },
    "no_trust_weighting": {
        "label": "No trust-weighted scoring",
        "patch": patch_no_trust_weighting,
    },
    "single_agent": {
        "label": "Single-agent LLM (no debate)",
        "patch": None,
    },
    "no_calibration": {
        "label": "No confidence calibration",
        "patch": patch_no_calibration,
    },
    "no_complexity": {
        "label": "No claim complexity estimation",
        "patch": patch_no_complexity,
    },
}

RESET_MODULES = {
    "no_trust_weighting": ["src.agents.moderator"],
    "no_calibration":     ["src.novelty.confidence_calibration"],
    "no_complexity":      ["src.novelty.claim_complexity"],
}


def main():
    parser = argparse.ArgumentParser(description="InsightSwarm Ablation Study")
    parser.add_argument("--n",       type=int,  default=50)
    parser.add_argument("--data",    type=str,  default=None)
    parser.add_argument("--configs", type=str,  default=None,
                        help="Comma-separated configs (default: all)")
    args = parser.parse_args()

    data_path = Path(args.data) if args.data else DATA_DIR / "fever_sample.json"
    if not data_path.exists():
        print(f"ERROR: {data_path} not found. Run: python scripts/download_fever.py")
        sys.exit(1)

    with open(data_path, encoding="utf-8") as f:
        all_claims = json.load(f)

    half     = args.n // 2
    supports = [c for c in all_claims if c["fever_label"] == "SUPPORTS"][:half]
    refutes  = [c for c in all_claims if c["fever_label"] == "REFUTES"][:half]
    claims   = supports + refutes

    configs_to_run = (
        [c.strip() for c in args.configs.split(",")]
        if args.configs else list(CONFIGS.keys())
    )

    print(f"\n{'='*60}")
    print(f"InsightSwarm Ablation Study — {len(claims)} claims × {len(configs_to_run)} configs")
    print(f"{'='*60}")

    ablation_results = []

    for config_name in configs_to_run:
        if config_name not in CONFIGS:
            print(f"WARNING: unknown config '{config_name}' — skipping")
            continue

        cfg = CONFIGS[config_name]
        if cfg["patch"]:
            cfg["patch"]()

        raw_results = run_config(config_name, cfg["label"], claims, n=len(claims))
        metrics     = compute_metrics(raw_results)
        metrics.update({"config": config_name, "config_label": cfg["label"]})
        ablation_results.append(metrics)

        print(f"\n  {cfg['label']}:")
        print(f"    Accuracy={metrics['accuracy']:.1%}  F1={metrics['f1']:.1%}  "
              f"Precision={metrics['precision']:.1%}  Recall={metrics['recall']:.1%}")

        # Reload patched modules to restore original state for next config
        if config_name in RESET_MODULES:
            import importlib
            for mod_name in RESET_MODULES[config_name]:
                try:
                    mod = sys.modules.get(mod_name)
                    if mod:
                        importlib.reload(mod)
                except Exception as e:
                    print(f"    Warning: could not reload {mod_name}: {e}")

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
    print(f"Results → {out_path}")

    full_f1 = next((r["f1"] for r in ablation_results if r["config"] == "full_system"), None)
    if full_f1 is not None:
        print(f"\nΔF1 relative to full system:")
        for r in ablation_results:
            delta = (r["f1"] - full_f1) * 100
            sign  = "+" if delta >= 0 else ""
            print(f"  {r['config_label']:<44} {sign}{delta:+.1f}% ΔF1")

    print(f"\nNext: python scripts/generate_paper_metrics.py --ablation {out_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
