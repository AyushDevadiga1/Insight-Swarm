# InsightSwarm Progress Report — Day 23

## Overview
Today's sprint wired all remaining novelty modules into the live pipeline and built
the complete evaluation infrastructure needed for paper submission.

---

## Phase 2 — Novelty Modules Wired ✅

### ArgumentationAnalyzer → live in `_moderator_node`
- Called on every pro/con argument after each debate
- Detects 10 fallacy types (ad hominem, strawman, false dichotomy, etc.)
- Scores citation quality, rhetorical intensity, argument structure
- Results stored in `state.metrics["argumentation_analysis"]`
- Surfaced in `MetricsGrid.jsx` as a dedicated "Argumentation Analysis" block
  showing pro/con quality bars, fallacy counts, debate quality tier

### AdaptiveConfidenceCalibrator → live in `_moderator_node`
- Runs immediately after ArgumentationAnalyzer on the Moderator's raw confidence
- Detects underconfidence (strong evidence + low confidence) and applies
  an evidence-strength-proportional boost
- Calibrated confidence replaces raw confidence in `state.confidence`
- Calibration metadata stored in `state.metrics["calibration"]`
- Surfaced in `MetricsGrid.jsx` as a "Confidence Calibration" block showing
  raw→calibrated flow, adjustment amount, underconfidence detection flag

Both modules are wrapped in try/except and fail gracefully — they never crash the pipeline.

---

## Phase 3 — FEVER Benchmark Infrastructure ✅

### `scripts/download_fever.py`
- Downloads 200 balanced claims (100 SUPPORTS + 100 REFUTES) from HuggingFace
- Falls back to 50-claim curated hand-labelled dataset if HuggingFace unreachable
- Saves to `data/fever_sample.json`
- Run: `python scripts/download_fever.py`

### `tests/benchmark_suite.py` (rewritten)
- Full FEVER evaluation with precision, recall, F1, accuracy, calibration MAE
- Two baselines: keyword classifier + zero-shot single-agent LLM
- Per-claim result logging + aggregated benchmark_report.json
- Run: `python tests/benchmark_suite.py [--n 20 --quick]`

### `scripts/generate_paper_metrics.py`
- Reads `outputs/benchmark_report.json` + `outputs/ablation_results.json`
- Outputs:
  - `outputs/paper_metrics.json` — all key numbers in one place
  - `outputs/table_main.tex` — LaTeX comparison table (paste-ready)
  - `outputs/table_ablation.tex` — LaTeX ablation table
- Run: `python scripts/generate_paper_metrics.py`

---

## Phase 4 — Ablation Study Runner ✅

### `scripts/run_ablation.py`
- Tests 4 configurations on a 50-claim FEVER subset:
  1. Full system (all novelty enabled)
  2. No trust-weighted scoring (Moderator uses simple count-based rate)
  3. Single-agent (no debate — just Moderator LLM)
  4. No confidence calibration (raw confidence unchanged)
- Each config produces precision/recall/F1/accuracy metrics
- ΔF1 relative to full system shows component contribution
- Saves to `outputs/ablation_results.json`
- Run: `python scripts/run_ablation.py [--n 20]`

---

## Files Changed / Created

| File | Action |
|------|--------|
| `src/orchestration/debate.py` | Modified — wired ArgumentationAnalyzer + AdaptiveConfidenceCalibrator in `_moderator_node` |
| `frontend/src/components/results/MetricsGrid.jsx` | Modified — added ArgumentationBlock + CalibrationBlock UI sections |
| `scripts/download_fever.py` | Created |
| `scripts/generate_paper_metrics.py` | Created |
| `scripts/run_ablation.py` | Created |
| `tests/benchmark_suite.py` | Rewritten — FEVER benchmark with baselines |
| `requirements.txt` | Updated — added `datasets`, `scipy`, `fastapi`, `uvicorn`, `websockets` |
| `data/` | Created directory |
| `outputs/` | Used for benchmark output |

---

## Execution Order (Next Steps)

```bash
# Step 1: Download FEVER sample
python scripts/download_fever.py

# Step 2: Run full benchmark (takes ~30 min on 200 claims)
python tests/benchmark_suite.py

# Step 3: Run ablation study (~15 min on 50 claims × 4 configs)
python scripts/run_ablation.py

# Step 4: Generate paper tables
python scripts/generate_paper_metrics.py

# Step 5: Write 4-page demo paper using outputs/paper_metrics.json
```

---

## What's Left for Submission

- [ ] Write 4-page ACL/EMNLP demo paper (paper/demo_paper.md)
- [ ] Run actual benchmarks (need API credits)
- [ ] Add architecture diagram SVG for paper figure
- [ ] Final README update with benchmark reproduction instructions
- [ ] GitHub Actions CI for benchmark reproducibility
