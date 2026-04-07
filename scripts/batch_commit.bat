@echo off
REM =============================================================================
REM  InsightSwarm - Day 23 Batch Commit Script (FIXED)
REM  Runs 18 targeted commits covering all changes made today.
REM  Fixed to use valid multiline commit syntax for Windows CMD.
REM =============================================================================

echo.
echo ============================================================
echo  InsightSwarm D23 - Batch Commit (18 commits)
echo ============================================================
echo.

REM ─── 1. debate.py ─────────────────────────────────────────────────────────
REM (Already committed in previous run, but adding for completeness)
git add src\orchestration\debate.py
git commit -m "feat(orchestration): wire novelty modules + add close() to DebateOrchestrator" -m "- Added close() method with _closed flag to prevent dangling resources" -m "- Wired ArgumentationAnalyzer in _moderator_node (non-fatal try/except)" -m "- Wired AdaptiveConfidenceCalibrator after moderator response" -m "- Wired ExplainabilityEngine in _verdict_node" -m "- Wired ClaimComplexityEstimator in run() and stream()" -m "- Fixed _retry_revision_node: save/restore state.round (bug #5 from audit)" -m "- Added num_rounds param to _run_single_claim and stream()" -m "- Complexity-aware interactive prompt in run() for high/very_high claims"

REM ─── 2. moderator.py ──────────────────────────────────────────────────────
git add src\agents\moderator.py
git commit -m "fix(agents/moderator): remove double-calibration and unused import" -m "- Removed get_calibrator call inside generate() - debate.py _moderator_node already calls calibrator after generate() returns; double-calling inflated confidence values and wrote two calibration dict entries" -m "- Removed unused import: get_argumentation_analyzer was imported but never referenced anywhere in the class" -m "- Extracted trust scores with a cleaner list comprehension" -m "- Added dict() copy of result.metrics to avoid mutating the Pydantic object"

REM ─── 3. argumentation_analysis.py ────────────────────────────────────────
git add src\novelty\argumentation_analysis.py
git commit -m "fix(novelty/argumentation): move numpy import to module top - fixes NameError" -m "Critical fix: np was imported at the BOTTOM of the file inside a try/except block, but was referenced inside class methods defined ABOVE that import. Python resolves names at call-time for methods, so the first call to calculate_argument_structure_score() or compare_debate_quality() raised NameError: name 'np' is not defined." -m "Fix: moved the numpy import (with fallback shim) to the top of the module, before the class definition, so np is always in scope when methods execute."

REM ─── 4. contradiction_detection.py ───────────────────────────────────────
git add src\novelty\contradiction_detection.py
git commit -m "fix(novelty/contradiction): guard against None content_preview" -m "- Added _safe_content() helper that extracts text from both dict and SourceVerification Pydantic objects, returning '' instead of None" -m "- detect_directional_contradiction() now returns False early if either content string is falsy - prevents AttributeError on .lower()" -m "- analyze_contradiction_pair() uses _safe_content() throughout" -m "- Wrapped pairwise comparison loop in try/except so one bad source pair cannot crash the entire contradiction analysis" -m "- Added None/hasattr guards when reading url, trust_score, status"

REM ─── 5. test_deep_fixes.py ────────────────────────────────────────────────
git add tests\test_deep_fixes.py
git commit -m "fix(tests/test_deep_fixes): fix all three failing tests" -m "test_verification_rate_semantics: - Mock now returns AgentResponse (not a plain dict) - _fact_checker_node calls response.metrics which fails on dicts - Added pro_rate/con_rate keys to mock metrics to match production code" -m "test_round_counter_logic: - Updated post-increment round convention: ConAgent increments round after generating, so after Round 3 state.round == 4; 4 > 3 == 'end' is correct - Added assertion for round=3 -> 'continue' and round=2 -> 'continue'" -m "test_moderator_fallback_on_rate_limit: - Replaced deleted _parse_moderator_response test with a real one that exercises the current code path (call_structured raises RateLimitError)"

REM ─── 6. test_moderator.py ────────────────────────────────────────────────
git add tests\test_moderator.py
git commit -m "fix(tests/test_moderator): fix Pydantic ValidationError and wrong mock target" -m "- Removed verdict=None, confidence=None, moderator_reasoning=None - these fields are non-Optional in DebateState (str/float), passing None raises Pydantic ValidationError before any test logic runs" -m "- Changed client.call.return_value -> client.call_structured.return_value because Moderator.generate() calls call_structured, not call" -m "- Mock now returns ModeratorVerdict (correct output_schema) instead of a raw string that would fail model_validate_json" -m "- Added basic sanity assertions (agent, verdict, confidence range)"

REM ─── 7. models.py ────────────────────────────────────────────────────────
git add src\core\models.py
git commit -m "feat(core/models): add human_verdict_override field for HITL resume endpoint" -m "- Added Optional[str] human_verdict_override field to DebateState" -m "- Field used by /api/debate/resume/{thread_id} when a human expert sets a verdict override before the moderator runs" -m "- SourceVerification.get() already uses correct _MISSING sentinel (no val is None bug)" -m "- AgentResponse.get() also uses _MISSING sentinel correctly"

REM ─── 8. fact_checker.py ──────────────────────────────────────────────────
git add src\agents\fact_checker.py
git commit -m "feat(agents/fact_checker): integrate contradiction detection novelty module" -m "- Added import of get_contradiction_detector at module top" -m "- After computing pro/con verification rates, calls detector.detect_contradictions() on the results list (accepts both List[SourceVerification] and List[Dict])" -m "- Contradiction analysis stored in metrics['contradictions'] for API and UI" -m "- ContradictionDetector handles None content_preview gracefully after D23 fix"

REM ─── 9. conftest.py ──────────────────────────────────────────────────────
git add tests\conftest.py tests\integration\conftest.py
git commit -m "test(conftest): set ENABLE_OFFLINE_FALLBACK and placeholder API keys" -m "- os.environ.setdefault('ENABLE_OFFLINE_FALLBACK', '1') prevents FreeLLMClient from raising RuntimeError when no real API keys are present in CI" -m "- Placeholder keys have correct prefixes so format-validation passes: GROQ_API_KEY = gsk_ci_placeholder_..., GEMINI_API_KEY = AIzaSy_ci_placeholder_..." -m "- Unit tests that mock call_structured/call are unaffected by these values"

REM ─── 10. server.py (api) ─────────────────────────────────────────────────
git add api\server.py
git commit -m "fix(api/server): use model_dump() before dict() in _state_to_dict helper" -m "- state_to_dict now prefers model_dump() (Pydantic v2) over dict() (Pydantic v1) to prevent deprecation warnings and ensure nested models serialize correctly" -m "- resume_debate endpoint: replaced human_input.dict() with human_input.model_dump() for the same reason (Pydantic v2 deprecates .dict())" -m "- No functional change; pure compatibility fix"

REM ─── 11. novelty __init__.py ─────────────────────────────────────────────
git add src\novelty\__init__.py
git commit -m "chore(novelty/__init__): verify all five module exports are importable" -m "Package exports: get_calibrator, get_argumentation_analyzer, get_contradiction_detector, get_complexity_estimator, get_explainability_engine. All five are now syntactically correct after the argumentation_analysis.py numpy fix and contradiction_detection.py None-guard fix."

REM ─── 12. scripts/test_api_keys.py ────────────────────────────────────────
git add scripts\test_api_keys.py
git commit -m "feat(scripts): rewrite test_api_keys.py with researched limits and token probe" -m "Realistic free-tier limits (April 2026) baked in: Groq: 30 RPM | 14 400 RPD | 6 000 TPM; Gemini: 10 RPM | 250 RPD | 250K TPM; Cerebras: 30 RPM | token-based | 60K TPM; OpenRouter: 10 RPM | ~200 RPD; Tavily: none | ~33/day." -m "New test steps: format -> liveness ping -> token budget probe (~220 tok) -> structured JSON round-trip. Each step can independently surface: Invalid key (401/403); Rate-limited NOW (429); TPM bucket exhausted (token probe); Structured output parse failure."

REM ─── 13. scripts/download_fever.py ──────────────────────────────────────
git add scripts\download_fever.py
git commit -m "feat(scripts): add download_fever.py - FEVER benchmark data download" -m "Downloads 200 balanced FEVER claims (100 SUPPORTS + 100 REFUTES) from HuggingFace datasets. Falls back to a curated 50-claim hand-labelled dataset when HuggingFace is unreachable (offline/CI environments)." -m "Usage: python scripts/download_fever.py [--n 200] [--include_nei]; Output: data/fever_sample.json"

REM ─── 14. tests/benchmark_suite.py ───────────────────────────────────────
git add tests\benchmark_suite.py
git commit -m "feat(tests): rewrite benchmark_suite.py as full FEVER evaluation harness" -m "- Full FEVER evaluation: precision, recall, F1, accuracy, calibration MAE" -m "- Two baselines: keyword classifier + zero-shot single-agent LLM" -m "- Per-claim result logging (ClaimResult dataclass) + aggregated report JSON" -m "- Verdict mapping: TRUE<->SUPPORTS, FALSE<->REFUTES, partial credit for PARTIALLY TRUE" -m "- Fixed Pydantic schema bug in SingleAgentBaseline.predict()" -m "Usage: python tests/benchmark_suite.py [--n 20 --quick] [--baseline-only]"

REM ─── 15. ablation + metrics ──────────────────────────────────────────────
git add scripts\run_ablation.py scripts\generate_paper_metrics.py
git commit -m "feat(scripts): add ablation runner and LaTeX paper metrics generator" -m "run_ablation.py: Tests 4 configurations on a 50-claim FEVER subset. Reports delta-F1 per component to prove each adds value." -m "generate_paper_metrics.py: Reads benchmark_report.json + ablation_results.json. Outputs paper_metrics.json, table_main.tex, table_ablation.tex (LaTeX tables have best values bolded)."

REM ─── 16. client.py (JSON Extraction) ─────────────────────────────────────
git add src\llm\client.py
git commit -m "fix(llm/client): add brace-balanced JSON extraction for robust parsing" -m "- Implemented _clean_json_response with brace-balancing logic to isolate the first JSON object or array." -m "- Solves 'trailing characters' errors from Cerebras/OpenRouter when LLMs append explanatory text after JSON blocks." -m "- Handles multiple nested braces and escapes correctly."

REM ─── 17. linter_configs ──────────────────────────────────────────────────
git add pyrightconfig.json .vscode\settings.json pyrefly.toml
git commit -m "chore(config): fix import root for Pyright and Pyrefly linters" -m "- Added extraPaths: ['.'] to pyrightconfig.json and settings.json." -m "- Created pyrefly.toml with search_path = ['.'] to mirror runtime import resolution." -m "- Silences all 'Cannot find module src.*' false-positive warnings."

REM ─── 18. paper + main.py ─────────────────────────────────────────────────
git add main.py paper\demo_paper_v2.md
git commit -m "docs(paper): update evaluation results and system demo sections" -m "- Added XAI and Complexity Estimation to novelty list in abstract/conclusion." -m "- Updated demo flow to include raw-vs-calibrated confidence and transparency scores." -m "- Added placeholder results for 100-claim benchmark (to be populated)." -m "- Fixed main.py to pass num_rounds=3 to avoid ambiguity."

echo.
echo ============================================================
echo  All 18 commits finished. Verify with: git log --oneline -18
echo ============================================================
echo.

git log --oneline -18
