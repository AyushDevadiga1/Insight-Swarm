# InsightSwarm — Post-Change Codebase Status
**Fresh audit after your changes, March 2026**

---

## Overall: Strong Progress — Sessions 1 and 2 Fully Done, 3 and 4 Partial

| Session | Status | Detail |
|---------|--------|--------|
| Session 1 — Stop the Crashes | ✅ Complete | All 7 fixes applied correctly |
| Session 2 — Fix Silent Failures | ✅ Complete | All 4 fixes applied correctly |
| Session 3 — Wire the Orphaned Code | ⚠️ 5/6 done | Fix 3-E applied in wrong place |
| Session 4 — Production Hardening | ⚠️ 3/4 done | Fix 4-B partial, 4-D guard still present |

One **new bug was introduced** during the fixes. Three **original issues remain unfixed**. All documented below with exact file, function, and replacement code.

---

## What Was Done Correctly

### Session 1 — All 7 correct

| Fix | File | What Was Done |
|-----|------|---------------|
| 1-A | `api_key_manager.py` | `degraded` flag added, no RuntimeError raise, guard in `get_working_key()` |
| 1-B | `debate.py` | `_fact_checker_node()` safe exit with defaults for all None fields |
| 1-C | `cache.py` | `_encode()` returns None on error without disabling cache, 3-failure threshold |
| 1-D | `fact_checker.py` | Module-level `_VERIFY_POOL` singleton with `atexit`, `as_completed(timeout=60)` |
| 1-E | `fact_checker.py` | `stream=True`, 50KB cap, `content_text` used throughout `_verify_url()` |
| 1-F | `task_queue.py` | `atexit` shutdown, `_prune_old_tasks()`, `_submitted_at` timestamp |
| 1-G | `debate.py` | Tavily wrapped in 12s timeout, dangling line deleted from `run()` and `stream()` |

### Session 2 — All 4 correct

| Fix | File | What Was Done |
|-----|------|---------------|
| 2-A | `models.py` | `ModeratorVerdict` validator normalises LLM variants to canonical verdicts |
| 2-B | `api_key_manager.py` | Max backoff `min(30 * 2^n, 300)`, auto-recovery loop in `get_working_key()` |
| 2-C | `cache.py` | `_rebuild_index()`, vectorised numpy search, `_index_dirty = True` on write |
| 2-D | `validation.py` | Limits aligned (10/500), Unicode safety, meaningful word check |

### Session 3 — 5 of 6 correct

| Fix | File | Status |
|-----|------|--------|
| 3-A | `debate.py` | ✅ Bad Gemini key RuntimeError deleted from `_verification_gate_node()` |
| 3-B | `bounded_cache.py` | ✅ File created correctly with thread-safe LRU |
| 3-C | `debate.py` | ✅ `pro_sources` and `con_sources` capped in sync with arguments in `_summarize_node()` |
| 3-D | `debate.py` | ✅ `MemorySaver` imported and used, SQLite singleton code deleted, `close()` is no-op |
| 3-E | `app.py` | ⚠️ Applied but in wrong location — see Issue 2 below |
| 3-F | `app.py` | ✅ `debate_error` written to session state instead of `st.error()` |

### Session 4 — 3 of 4 correct

| Fix | File | Status |
|-----|------|--------|
| 4-A | `debate.py` | ✅ `RATE_LIMITED` vs `SYSTEM_ERROR` classification in `run()` except block |
| 4-B | `debate.py` | ✅ Cache check moved before decomposition |
| 4-B | `claim_decomposer.py` | ❌ Still uses `preferred_provider="cerebras"` — not changed |
| 4-C | `debate.py` | ⚠️ LLM consensus path fixed in `_should_debate()`, SETTLED_TRUTHS path not fixed |
| 4-D | `client.py` | ⚠️ `_get_gemini_client()` now sets legacy correctly, but old guard still in `_call_gemini()` |

---

---

# Remaining Fixes — Exact Code

## NEW BUG — Delete `_verification_gate_node()` from `debate.py`

**File:** `src/orchestration/debate.py`
**Severity:** Not currently firing (method is not connected to the graph), but contains a crash bug if ever called

During fix 3-A, the bad Gemini key raise was deleted but a new bug was left behind. The method builds `sources_to_check` as a list of `(url, agent, arg)` tuples, then immediately overwrites it with a flat concatenation of URL strings, then tries to unpack those strings as 3-tuples:

```python
# THE BUG — two consecutive conflicting assignments:
sources_to_check = []
# ... correctly builds list of (url, agent, argument) tuples ...

failed_sources = []
sources_to_check = (state.pro_sources[-1] if state.pro_sources else []) + \
                   (state.con_sources[-1] if state.con_sources else [])
# ↑ overwrites sources_to_check with a flat list of URL strings

for url, agent, argument in sources_to_check:
# ↑ tries to unpack each URL string as three values → ValueError at runtime
```

The method is not in the graph (`_build_graph()` has no `workflow.add_node("verification_gate", ...)` line) so it never executes. The safest fix is to delete the entire method.

**What to do:** Find `_verification_gate_node()` in `debate.py` and delete the entire method. It begins with:
```python
def _verification_gate_node(self, state: DebateState) -> DebateState:
    # round_idx is 0-based index of the round just completed.
```
and ends just before `def _retry_revision_node(`. Delete everything between those two method definitions.

---

## Issue 2 — `reset_all_keys()` fires on every click instead of once per session

**File:** `app.py`
**Function:** `analyze_claim_async()`

Keys are reset on every verification button press, not once per session. If Groq just gave a 429 and set a 60-second cooldown, the user clicks Verify again — `reset_all_keys()` wipes the cooldown — Groq gets hit again immediately — another 429. This will hammer rate-limited providers on rapid re-submissions.

**Step 1 — Remove from `analyze_claim_async()`.** Delete these lines:

```python
# DELETE these 3 lines from analyze_claim_async():
# Fix 3-E: Reset keys on session start to clear transient cooldowns
if not use_sim:
    orchestrator.client.key_manager.reset_all_keys()
```

**Step 2 — Add to `_init()`, at the very end of the function after all the `setdefault` calls:**

```python
# ADD to the bottom of _init():
if not st.session_state.get("_api_keys_reset"):
    try:
        from src.utils.api_key_manager import get_api_key_manager
        get_api_key_manager().reset_all_keys()
        logger.info("API keys reset for new browser session")
    except Exception as e:
        logger.warning(f"Could not reset API keys on session start: {e}")
    st.session_state._api_keys_reset = True
```

---

## Issue 3 — SETTLED_TRUTHS path leaves blank debate tab

**File:** `src/orchestration/debate.py`
**Function:** `_consensus_check_node()`

Fix 4-C was applied in `_should_debate()` which covers the LLM-based consensus path. But the hardcoded `SETTLED_TRUTHS` dict (earth is flat, vaccines cause autism, etc.) does an early `return state` with `pro_arguments = []` and `con_arguments = []`. `render_debate()` in `app.py` computes `rounds = min(len(pros), len(cons))` which is 0 — blank debate tab.

**Find the SETTLED_TRUTHS `return state` line inside `_consensus_check_node()` and add synthetic arguments before it:**

```python
# FIND this block:
        if state.metrics is None: state.metrics = {}
        state.metrics["consensus"] = {
            "verdict": verdict,
            "reasoning": reasoning,
            "score": conf
        }
        return state       # ← pro_arguments and con_arguments are still []

# REPLACE with:
        if state.metrics is None: state.metrics = {}
        state.metrics["consensus"] = {
            "verdict": verdict,
            "reasoning": reasoning,
            "score": conf
        }
        # Populate synthetic debate entries so the UI debate tab is not blank
        if not state.pro_arguments:
            state.pro_arguments = [f"[Settled science — no debate needed] {reasoning}"]
        if not state.con_arguments:
            state.con_arguments = [f"[Consensus verdict: {verdict} ({conf:.0%} confidence) — debate skipped]"]
        if not state.pro_sources:
            state.pro_sources = [[]]
        if not state.con_sources:
            state.con_sources = [[]]
        return state
```

---

## Issue 4 — `claim_decomposer.py` still uses Cerebras

**File:** `src/utils/claim_decomposer.py`
**Function:** `decompose()`

`debate.py` itself has a comment: *"We are moving away from OpenRouter (Credits) and Cerebras (DNS)"*. But `claim_decomposer.py` was not updated:

```python
# CURRENT (wrong):
response = self.client.call_structured(
    prompt=prompt,
    output_schema=ClaimsOutput,
    temperature=0.1,
    preferred_provider="cerebras"
)

# CHANGE TO:
response = self.client.call_structured(
    prompt=prompt,
    output_schema=ClaimsOutput,
    temperature=0.1,
    preferred_provider="groq"
)
```

---

## Issue 5 — Legacy Gemini guard still raises RuntimeError (low risk)

**File:** `src/llm/client.py`
**Function:** `_call_gemini()` — the `else` branch

`_get_gemini_client()` was correctly updated to set `self._gemini_legacy` when legacy mode is needed. Since `_execute_provider()` always calls `_get_gemini_client()` before `_call_gemini()`, the guard below will not normally fire. But it's still misleading and will fail if `_call_gemini()` is ever called directly:

```python
# CURRENT (still raises RuntimeError even though _get_gemini_client now sets it):
else:
    if self._gemini_legacy is None:
        raise RuntimeError("Legacy Gemini client not initialized")

# CHANGE TO (lazy-init as fallback):
else:
    if self._gemini_legacy is None:
        try:
            import google.generativeai as genai_legacy
            self._gemini_legacy = genai_legacy
        except ImportError:
            raise RuntimeError(
                "No Gemini SDK found. Run: pip install google-generativeai"
            )
    with self._gemini_legacy_lock:
        self._gemini_legacy.configure(api_key=gemini_key)
        model_obj = self._gemini_legacy.GenerativeModel(self.GEMINI_MODEL)
        generation_config = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        if response_mime_type:
            generation_config["response_mime_type"] = response_mime_type
        response = model_obj.generate_content(
            prompt,
            generation_config=generation_config,
        )
```

---

## Minor Cleanup (optional, not bugs)

### Duplicate import in `fact_checker.py`

Lines 5–6 import `AgentResponse` twice. The second silently shadows the first:

```python
# CURRENT:
from src.agents.base import BaseAgent, AgentResponse, DebateState
from src.core.models import SourceVerification, AgentResponse        # duplicate

# CHANGE TO:
from src.agents.base import BaseAgent, AgentResponse, DebateState
from src.core.models import SourceVerification
```

### Dead `_get_orchestrator()` in `app.py`

```python
@st.cache_resource(show_spinner=False)
def _get_orchestrator() -> DebateOrchestrator:
    return DebateOrchestrator()
```

This function is never called — `analyze_claim_async()` creates `DebateOrchestrator(tracker=tracker)` directly. Safe to delete.

### `ModeratorVerdict._VALID_VERDICTS` defined but not used in validator

The `_VALID_VERDICTS` set is defined in the class body but the validator does a separate hardcoded list check instead of using it. Change the validator to use the set:

```python
# CHANGE this line in the @validator:
if v in ["TRUE", "FALSE", "PARTIALLY TRUE", "INSUFFICIENT EVIDENCE", "CONSENSUS_SETTLED", "RATE_LIMITED", "UNKNOWN", "ERROR"]:

# TO:
if v in cls._VALID_VERDICTS:
```

---

## Execution Order for Remaining Work

These 5 changes take about 20 minutes total. Do them in this order:

```
[ ] 1. Delete _verification_gate_node() from debate.py          (new bug, dead code)
[ ] 2. Move reset_all_keys() from analyze_claim_async() to _init()  (wrong placement)
[ ] 3. Add synthetic args to SETTLED_TRUTHS block in debate.py   (blank UI tab)
[ ] 4. Change claim_decomposer.py to preferred_provider="groq"   (DNS issues)
[ ] 5. Fix legacy Gemini guard in client.py                      (low risk, still misleading)
[ ] 6. Remove duplicate AgentResponse import in fact_checker.py  (cosmetic)
```

---

## Final State After All Fixes

Once the above 6 items are done, the full status is:

- **No startup crash possible** — APIKeyManager is fully degraded-state aware
- **No graph crash possible** — FactChecker and Moderator both have safe fallback states
- **Cache is resilient** — single encoding failure does not disable it permanently
- **Memory is bounded** — thread pools are singletons, task dict is pruned, HTTP downloads capped
- **All verdicts render** — ModeratorVerdict normalises any LLM string to a known value
- **UI debate tab always populated** — both consensus paths produce synthetic arguments
- **Keys recover automatically** — 5-minute max backoff with auto-recovery on cooldown expiry
- **Cache lookups are fast** — vectorised numpy index instead of Python loop over full table
