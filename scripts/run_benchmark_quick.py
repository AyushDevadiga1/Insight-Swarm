"""
scripts/run_benchmark_quick.py
================================
Quick 10-claim sanity-check benchmark — runs in ~5 minutes.
Use this to verify the pipeline works before running the full 100-claim benchmark.

Usage:
    python scripts/run_benchmark_quick.py

Output:
    outputs/quick_benchmark_report.json
"""

import sys
import json
import time
from pathlib import Path
from dataclasses import asdict

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from benchmark_suite import (
    run_insightswarm_benchmark,
    run_baseline_benchmark,
    compute_metrics,
)

OUTPUTS_DIR = ROOT / "outputs"
DATA_DIR    = ROOT / "data"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# 10-claim quick test — 5 SUPPORTS, 5 REFUTES, all genuinely non-trivial
QUICK_CLAIMS = [
    {"claim": "Regular exercise can help reduce symptoms of depression.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE", "evidence": []},
    {"claim": "Vitamin C supplements prevent the common cold.", "fever_label": "REFUTES", "expected_verdict": "FALSE", "evidence": []},
    {"claim": "Social media use is linked to increased rates of anxiety in teenagers.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE", "evidence": []},
    {"claim": "Sugar directly causes hyperactivity in children.", "fever_label": "REFUTES", "expected_verdict": "FALSE", "evidence": []},
    {"claim": "Climate change is causing more frequent and intense hurricanes.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE", "evidence": []},
    {"claim": "5G networks cause COVID-19 or other diseases.", "fever_label": "REFUTES", "expected_verdict": "FALSE", "evidence": []},
    {"claim": "Gene editing technologies like CRISPR can correct genetic disorders.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE", "evidence": []},
    {"claim": "mRNA vaccines permanently alter human DNA.", "fever_label": "REFUTES", "expected_verdict": "FALSE", "evidence": []},
    {"claim": "Misinformation spreads faster on social media than accurate information.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE", "evidence": []},
    {"claim": "Homeopathic treatments are clinically proven to be more effective than placebos.", "fever_label": "REFUTES", "expected_verdict": "FALSE", "evidence": []},
]


def main():
    print("=" * 60)
    print("InsightSwarm Quick Benchmark (10 claims)")
    print("=" * 60)

    # Run InsightSwarm
    is_results = run_insightswarm_benchmark(QUICK_CLAIMS, n=10, quick=True)
    is_metrics = compute_metrics(is_results)

    # Run baselines
    baseline_results = run_baseline_benchmark(QUICK_CLAIMS, n=10)
    all_metrics = {"insightswarm": is_metrics}
    for name, b_results in baseline_results.items():
        all_metrics[name] = compute_metrics(b_results)

    # Save
    report = {
        "dataset": "quick_10_claims",
        "n_claims": 10,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "metrics": all_metrics,
        "per_claim": [asdict(r) for r in is_results],
    }

    out_path = OUTPUTS_DIR / "quick_benchmark_report.json"
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\n{'─' * 50}")
    print("RESULTS SUMMARY")
    print(f"{'─' * 50}")
    for sys_name, m in all_metrics.items():
        print(f"{sys_name:<22} Acc={m.get('accuracy', 0):.1%}  F1={m.get('f1', 0):.1%}")
    print(f"\nReport → {out_path}")
    print("\nNext: python tests/benchmark_suite.py --n 100 --quick")
    print("      python scripts/run_ablation.py --n 20")


if __name__ == "__main__":
    main()
