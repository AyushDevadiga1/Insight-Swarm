"""
tests/benchmark_suite.py
=========================
InsightSwarm FEVER Benchmark Evaluation
----------------------------------------
Evaluates the full multi-agent system against the FEVER fact-verification
dataset and compares it to two baselines:
  1. Keyword-matching classifier (trivial baseline)
  2. Zero-shot LLM classifier (single-agent baseline)

Usage:
    # Run full benchmark (200 claims)
    python tests/benchmark_suite.py

    # Run with smaller sample for quick testing
    python tests/benchmark_suite.py --n 20 --quick

    # Run only the baseline comparison (no full debate)
    python tests/benchmark_suite.py --baseline-only

Output files (in outputs/):
    fever_results.json         — per-claim InsightSwarm results
    baseline_results.json      — per-claim baseline results
    benchmark_report.json      — aggregated metrics for all systems

Run scripts/download_fever.py first to get the data.
"""

import sys
import os
import json
import time
import re
import argparse
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, asdict
from pydantic import BaseModel, Field

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.WARNING)  # Suppress debug noise during benchmark
logger = logging.getLogger("benchmark")

OUTPUTS_DIR = ROOT / "outputs"
DATA_DIR    = ROOT / "data"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


# ── Label mapping ─────────────────────────────────────────────────────────────

FEVER_TO_VERDICT = {
    "SUPPORTS": "TRUE",
    "REFUTES":  "FALSE",
    "NOT ENOUGH INFO": "INSUFFICIENT EVIDENCE",
}

VERDICT_TO_FEVER = {v: k for k, v in FEVER_TO_VERDICT.items()}

# InsightSwarm verdicts that count as SUPPORTS
POSITIVE_VERDICTS   = {"TRUE"}
# InsightSwarm verdicts that count as REFUTES
NEGATIVE_VERDICTS   = {"FALSE"}
# Partially true is ambiguous — treated as partial credit in metrics
PARTIAL_VERDICTS    = {"PARTIALLY TRUE"}
# Unknown / errors → penalised
UNKNOWN_VERDICTS    = {"INSUFFICIENT EVIDENCE", "UNKNOWN", "ERROR", "RATE_LIMITED", "SYSTEM_ERROR"}


def map_verdict_to_fever(verdict: str) -> str:
    """Map InsightSwarm verdict → FEVER label for metric computation."""
    v = (verdict or "").upper().strip()
    if v in POSITIVE_VERDICTS:
        return "SUPPORTS"
    if v in NEGATIVE_VERDICTS:
        return "REFUTES"
    return "NOT ENOUGH INFO"


# ── Metric helpers ────────────────────────────────────────────────────────────

@dataclass
class ClaimResult:
    claim:            str
    fever_label:      str        # Ground truth
    expected_verdict: str        # Ground truth in InsightSwarm space
    system_verdict:   str        # What the system said
    system_confidence: float
    correct:          bool
    partial_credit:   float      # 0.0 or 0.5 for PARTIALLY TRUE on TRUE/FALSE claims
    latency_s:        float
    error:            Optional[str] = None
    metrics:          Optional[Dict] = None


def compute_metrics(results: List[ClaimResult]) -> Dict[str, Any]:
    """Compute precision, recall, F1, accuracy on binary TRUE/FALSE claims."""
    # Filter to binary (exclude NEI claims for primary metrics)
    binary = [r for r in results if r.fever_label in ("SUPPORTS", "REFUTES")]

    if not binary:
        return {"error": "No binary claims in results"}

    tp = sum(1 for r in binary if r.fever_label == "SUPPORTS" and r.system_verdict == "TRUE")
    fp = sum(1 for r in binary if r.fever_label == "REFUTES"  and r.system_verdict == "TRUE")
    fn = sum(1 for r in binary if r.fever_label == "SUPPORTS" and r.system_verdict != "TRUE")
    tn = sum(1 for r in binary if r.fever_label == "REFUTES"  and r.system_verdict != "TRUE")

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy  = (tp + tn) / len(binary) if binary else 0.0

    # Full accuracy including partial credit
    total_credit = sum(r.correct + r.partial_credit for r in binary)
    weighted_acc = total_credit / len(binary) if binary else 0.0

    # Error rate
    error_count = sum(1 for r in results if r.error is not None)

    # Average latency on successful runs
    ok_latencies = [r.latency_s for r in results if r.error is None]
    avg_latency  = sum(ok_latencies) / len(ok_latencies) if ok_latencies else 0.0

    # Confidence calibration — mean absolute error between confidence and correct
    calibration_errors = []
    for r in binary:
        expected_conf = 1.0 if r.correct else 0.0
        calibration_errors.append(abs(r.system_confidence - expected_conf))
    mae_calibration = sum(calibration_errors) / len(calibration_errors) if calibration_errors else 0.0

    return {
        "n_total":          len(results),
        "n_binary":         len(binary),
        "n_errors":         error_count,
        "accuracy":         round(accuracy, 4),
        "weighted_accuracy": round(weighted_acc, 4),
        "precision":        round(precision, 4),
        "recall":           round(recall, 4),
        "f1":               round(f1, 4),
        "true_positives":   tp,
        "false_positives":  fp,
        "false_negatives":  fn,
        "true_negatives":   tn,
        "avg_latency_s":    round(avg_latency, 2),
        "mae_calibration":  round(mae_calibration, 4),
    }


# ── Baselines ─────────────────────────────────────────────────────────────────

class KeywordBaseline:
    """
    Trivial keyword-matching classifier.
    Returns TRUE if claim contains positive-sounding words, else FALSE.
    This is the floor — any real system should beat it.
    """
    NEGATIVE_KEYWORDS = [
        "never", "not", "no ", "false", "fake", "wrong", "incorrect",
        "didn't", "wasn't", "isn't", "aren't", "can't", "won't", "failed",
        "myth", "hoax", "disproven", "debunked",
    ]

    def predict(self, claim: str) -> Tuple[str, float]:
        claim_lower = claim.lower()
        neg_hits = sum(1 for kw in self.NEGATIVE_KEYWORDS if kw in claim_lower)
        if neg_hits >= 2:
            return "FALSE", 0.6
        elif neg_hits == 1:
            return "FALSE", 0.52
        else:
            return "TRUE", 0.55


class SingleAgentBaseline:
    """
    Zero-shot single-LLM classifier — no debate, no evidence retrieval.
    Represents the 'LLM only' approach this paper argues against.
    """

    # BUG FIX: call_structured requires a Pydantic BaseModel, not bare dict.
    class _PredictSchema(BaseModel):
        verdict:    str   = Field(default="INSUFFICIENT EVIDENCE")
        confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    def __init__(self, llm_client=None):
        if llm_client is None:
            from src.llm.client import FreeLLMClient
            llm_client = FreeLLMClient()
        self.client = llm_client

    def predict(self, claim: str) -> Tuple[str, float]:
        prompt = (
            f"Is the following claim TRUE, FALSE, or PARTIALLY TRUE?\n"
            f"Claim: {claim}\n\n"
            f"Respond with ONLY a JSON object: "
            f'{{ "verdict": "TRUE"|"FALSE"|"PARTIALLY TRUE", "confidence": 0.0-1.0 }}'
        )
        try:
            result = self.client.call_structured(
                prompt,
                self._PredictSchema,
                temperature=0.1,
                preferred_provider="groq",
            )
            verdict = str(result.verdict).upper().strip()
            conf    = float(result.confidence)
            return verdict, conf
        except Exception:
            return "INSUFFICIENT EVIDENCE", 0.0


# ── InsightSwarm runner ───────────────────────────────────────────────────────

def run_insightswarm_benchmark(
    claims: List[Dict],
    n: Optional[int] = None,
    quick: bool = False,
) -> List[ClaimResult]:
    from src.orchestration.debate import DebateOrchestrator
    from src.llm.client import FreeLLMClient

    client = FreeLLMClient()
    orch   = DebateOrchestrator(client)

    sample = claims[:n] if n else claims
    results = []

    print(f"\n{'='*60}")
    print(f"InsightSwarm FEVER Benchmark — {len(sample)} claims")
    print(f"{'='*60}")

    for i, item in enumerate(sample, 1):
        claim    = item["claim"]
        gt_label = item["fever_label"]
        gt_verdt = item["expected_verdict"]

        print(f"\n[{i:>3}/{len(sample)}] {claim[:70]}{'…' if len(claim) > 70 else ''}")
        start = time.time()

        try:
            state   = orch.run(claim)
            latency = time.time() - start

            system_v = (state.verdict or "UNKNOWN").upper().strip()
            system_c = float(state.confidence or 0.0)

            correct       = (system_v in POSITIVE_VERDICTS and gt_label == "SUPPORTS") or \
                            (system_v in NEGATIVE_VERDICTS  and gt_label == "REFUTES")
            partial_credit = 0.5 if (system_v in PARTIAL_VERDICTS and gt_label in ("SUPPORTS", "REFUTES")) else 0.0

            result = ClaimResult(
                claim=claim,
                fever_label=gt_label,
                expected_verdict=gt_verdt,
                system_verdict=system_v,
                system_confidence=system_c,
                correct=correct,
                partial_credit=partial_credit,
                latency_s=latency,
                metrics=state.metrics or {},
            )
            print(f"    → InsightSwarm: {system_v} ({system_c:.0%}) | GT: {gt_label} | {'✓' if correct else '✗'} | {latency:.1f}s")

        except Exception as e:
            latency = time.time() - start
            result = ClaimResult(
                claim=claim,
                fever_label=gt_label,
                expected_verdict=gt_verdt,
                system_verdict="ERROR",
                system_confidence=0.0,
                correct=False,
                partial_credit=0.0,
                latency_s=latency,
                error=str(e),
            )
            print(f"    → ERROR: {e} | {latency:.1f}s")

        results.append(result)

        # Quick mode: pause to avoid rate limits
        if quick and i % 5 == 0:
            print("    [quick mode] pausing 5s...")
            time.sleep(5)

    return results


# ── Baseline runner ───────────────────────────────────────────────────────────

def run_baseline_benchmark(
    claims: List[Dict],
    n: Optional[int] = None,
) -> Dict[str, List[ClaimResult]]:

    sample   = claims[:n] if n else claims
    keyword  = KeywordBaseline()
    sa       = SingleAgentBaseline()

    kw_results = []
    sa_results = []

    print(f"\n{'='*60}")
    print(f"Baseline Evaluation — {len(sample)} claims")
    print(f"{'='*60}")

    for i, item in enumerate(sample, 1):
        claim    = item["claim"]
        gt_label = item["fever_label"]

        # Keyword baseline
        kw_v, kw_c = keyword.predict(claim)
        kw_correct  = (kw_v == "TRUE" and gt_label == "SUPPORTS") or \
                      (kw_v == "FALSE" and gt_label == "REFUTES")
        kw_results.append(ClaimResult(
            claim=claim, fever_label=gt_label,
            expected_verdict=item["expected_verdict"],
            system_verdict=kw_v, system_confidence=kw_c,
            correct=kw_correct, partial_credit=0.0, latency_s=0.001,
        ))

        # Single-agent baseline
        start  = time.time()
        sa_v, sa_c = sa.predict(claim)
        latency = time.time() - start
        sa_correct = (sa_v == "TRUE" and gt_label == "SUPPORTS") or \
                     (sa_v == "FALSE" and gt_label == "REFUTES")
        sa_results.append(ClaimResult(
            claim=claim, fever_label=gt_label,
            expected_verdict=item["expected_verdict"],
            system_verdict=sa_v, system_confidence=sa_c,
            correct=sa_correct, partial_credit=0.0, latency_s=latency,
        ))

        if i % 10 == 0 or i == len(sample):
            print(f"  [{i}/{len(sample)}] baseline batch done")

    return {"keyword": kw_results, "single_agent": sa_results}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="InsightSwarm FEVER Benchmark")
    parser.add_argument("--n",             type=int,  default=None, help="Number of claims (default: all)")
    parser.add_argument("--quick",         action="store_true",     help="Quick mode with rate-limit pauses")
    parser.add_argument("--baseline-only", action="store_true",     help="Run only baselines (skip InsightSwarm)")
    parser.add_argument("--no-baseline",   action="store_true",     help="Skip baseline evaluation")
    parser.add_argument("--data",          type=str,  default=None, help="Path to fever_sample.json")
    args = parser.parse_args()

    # Load data
    data_path = Path(args.data) if args.data else DATA_DIR / "fever_sample.json"
    if not data_path.exists():
        print(f"ERROR: FEVER sample not found at {data_path}")
        print("Run: python scripts/download_fever.py")
        sys.exit(1)

    with open(data_path, encoding="utf-8") as f:
        claims = json.load(f)

    print(f"Loaded {len(claims)} claims from {data_path}")

    all_metrics = {}

    # ── InsightSwarm ──────────────────────────────────────────────────────────
    if not args.baseline_only:
        is_results = run_insightswarm_benchmark(claims, n=args.n, quick=args.quick)
        is_metrics = compute_metrics(is_results)
        all_metrics["insightswarm"] = is_metrics

        # Save raw results
        with open(OUTPUTS_DIR / "fever_results.json", "w") as f:
            json.dump([asdict(r) for r in is_results], f, indent=2)

        print(f"\n{'─'*40}")
        print("InsightSwarm Results:")
        print(f"  Accuracy:  {is_metrics['accuracy']:.1%}")
        print(f"  Precision: {is_metrics['precision']:.1%}")
        print(f"  Recall:    {is_metrics['recall']:.1%}")
        print(f"  F1:        {is_metrics['f1']:.1%}")
        print(f"  Avg latency: {is_metrics['avg_latency_s']:.1f}s")
        print(f"  Calibration MAE: {is_metrics['mae_calibration']:.3f}")

    # ── Baselines ─────────────────────────────────────────────────────────────
    if not args.no_baseline:
        baseline_results = run_baseline_benchmark(claims, n=args.n)

        with open(OUTPUTS_DIR / "baseline_results.json", "w") as f:
            json.dump({
                k: [asdict(r) for r in v]
                for k, v in baseline_results.items()
            }, f, indent=2)

        for name, b_results in baseline_results.items():
            b_metrics = compute_metrics(b_results)
            all_metrics[name] = b_metrics
            print(f"\n{name.title()} Baseline:")
            print(f"  Accuracy:  {b_metrics['accuracy']:.1%}")
            print(f"  F1:        {b_metrics['f1']:.1%}")

    # ── Save aggregated report ────────────────────────────────────────────────
    report = {
        "dataset": str(data_path),
        "n_claims": args.n or len(claims),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "metrics": all_metrics,
    }

    with open(OUTPUTS_DIR / "benchmark_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Report saved → {OUTPUTS_DIR / 'benchmark_report.json'}")
    print(f"{'='*60}")

    # ── Print comparison table ─────────────────────────────────────────────────
    if len(all_metrics) > 1:
        print("\nSystem Comparison:")
        header = f"{'System':<20} {'Accuracy':>9} {'Precision':>10} {'Recall':>8} {'F1':>8}"
        print(header)
        print("─" * len(header))
        for sys_name, m in all_metrics.items():
            print(f"{sys_name:<20} {m.get('accuracy',0):>9.1%} {m.get('precision',0):>10.1%} "
                  f"{m.get('recall',0):>8.1%} {m.get('f1',0):>8.1%}")


if __name__ == "__main__":
    main()
