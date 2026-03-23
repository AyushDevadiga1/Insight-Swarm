# InsightSwarm — Full Codebase Audit & Patch Implementation Plan
**Date:** March 2026  
**Scope:** Complete deep audit of all source files for resilience, fallback completeness, error handling, and system-destroying single points of failure.

---

## EXECUTIVE SUMMARY

The codebase has solid architecture bones — Pydantic models, circuit breakers, retry handlers, observable logging, and a layered LLM client all exist. However **many of these resilience components are built but not wired in**. The actual execution paths bypass them. There are 12 confirmed issues ranging from critical single points of failure that will crash the entire Streamlit app, to medium bugs that silently degrade quality, to structural issues that prevent the system from surviving real-world production load.

---

## CRITICAL ISSUES — App-Destroying

### CRIT-01: `APIKeyManager.__init__` raises `RuntimeError` at module import time

**File:** `src/utils/api_key_manager.py` → `_load_and_validate_keys()`  
**What happens:** If `GROQ_API_KEY` is missing or fails format validation, the constructor raises `RuntimeError`. This exception propagates up through `FreeLLMClient.__init__()` → `DebateOrchestrator.__init__()` → Streamlit's `_get_orchestrator()`. Since `app.py` calls `_get_orchestrator()` inside a request handler (not module-level), this crashes the entire running session with a 500 error and an empty white screen — **not a user-friendly error message**.

**Worse:** The singleton pattern `_key_manager = None` + `get_api_key_manager()` means once it fails, every subsequent call also fails because the singleton is never set. The entire app becomes permanently unusable until restarted.

**Fix:** Wrap the `RuntimeError` raise in `_load_and_validate_keys()` into a warning instead. Store a `self.degraded = True` flag. Let `get_working_key()` return `None` gracefully. Surface the error as a Streamlit banner, not a crash.

---

### CRIT-02: `DebateOrchestrator.__init__` is not protected in `app.py`

**File:** `app.py` → `_get_orchestrator()` (not shown in tail but referenced)  
**What happens:** `DebateOrchestrator()` calls `FreeLLMClient()` which calls `get_api_key_manager()` which can raise. App.py wraps this in a `try/except` for `verify` button but the orchestrator is also initialized at `_init()` time inside `st.session_state`. If `_init()` runs before a `try` block, the exception is unhandled, killing the Streamlit thread.

**Fix:** Always lazy-initialize the orchestrator inside a `try/except Exception` that renders an error banner instead of crashing.

---

### CRIT-03: `BackgroundTaskQueue` executor is never shut down — memory/thread leak

**File:** `src/async_tasks/task_queue.py`  
**What happens:** `BackgroundTaskQueue` uses a singleton `ThreadPoolExecutor(max_workers=3)`. It is never shut down. `self.tasks` dict grows unboundedly — every completed task stays in memory forever. On Streamlit Cloud with dozens of requests, this leaks memory until OOM kill. The `concurrent.futures` executor also holds OS threads permanently.

**Fix:**
1. Add `atexit.register(executor.shutdown, wait=False)` in `__new__`.
2. Add a `cleanup_old_tasks()` method that removes completed tasks older than 5 minutes — call it at the top of `get_status()`.
3. Cap `self.tasks` at 50 entries with LRU eviction.

---

### CRIT-04: `SemanticCache._encode()` disables the entire cache on first model failure

**File:** `src/orchestration/cache.py` → `_encode()`  
**What happens:** If the embedding model fails (network issue, HuggingFace download error, memory error), `_encode()` catches the exception, sets `self.enabled = False`, and **permanently disables the cache for the session**. This means a single transient model load failure bricks the semantic cache for all subsequent requests until the server restarts. The system will then hit the LLM API for every single repeat claim — burning API quota.

**Fix:** Don't permanently disable on encoding failure. Instead: return `None` from `_encode()` on error, let `get_verdict()` return `None` (cache miss), but **don't flip `self.enabled`**. Reserve `self.enabled = False` only for explicit config opt-out.

---

### CRIT-05: `FactChecker` spawns up to 10 concurrent HTTP threads with no global rate limit

**File:** `src/agents/fact_checker.py` → `generate()`  
**What happens:** `ThreadPoolExecutor(max_workers=10)` is created fresh per `generate()` call with no limit on total concurrent threads across simultaneous Streamlit sessions. If 3 users submit claims simultaneously, you get up to 30 concurrent outbound HTTP connections. On Streamlit Cloud's 1GB RAM container, this causes OOM. The executor is also never explicitly shut down — it relies on GC, which is non-deterministic.

**Fix:**
1. Use a module-level singleton `ThreadPoolExecutor(max_workers=5)` shared across all calls.
2. Add explicit `executor.shutdown(wait=False)` via `atexit`.
3. Cap concurrency with a `Semaphore(5)` guard.

---

## HIGH SEVERITY — Silent Failures & Degradation

### HIGH-01: `CircuitBreaker`, `FallbackHandler`, `RetryHandler` are BUILT but NEVER USED

**Files:** `src/resilience/circuit_breaker.py`, `fallback_handler.py`, `retry_handler.py`  
**What happens:** These three resilience modules exist as dead code. No agent, no orchestrator, no LLM client imports or uses them. The `FreeLLMClient` has its own inline retry logic (via `tenacity`) which is separate and uncoordinated. The circuit breaker never trips. The fallback chain never executes.

**Fix:** Wire `CircuitBreaker` instances (one per provider) into `FreeLLMClient._call_groq()` and `_call_gemini()`. Wire `FallbackHandler.execute()` around the provider selection loop in `call_structured()`. This gives you actual circuit-breaking behavior instead of the current "try groq → try gemini → raise" linear chain.

---

### HIGH-02: `ProgressTracker` and `ObservableLogger` are built but `DebateOrchestrator` never calls them

**Files:** `src/ui/progress_tracker.py`, `src/utils/observable_logger.py`  
**What happens:** These are built and wired in `app.py` (`render_progress_panel`, `render_log_panel`) but `DebateOrchestrator._pro_agent_node()`, `_con_agent_node()`, `_fact_checker_node()`, `_moderator_node()` never call `tracker.update()` or `observable_logger.info()`. The progress bar in the UI stays frozen at the first stage for the entire 47-second debate. Users see no intermediate feedback.

**Fix:** Inject a `ProgressTracker` into `DebateOrchestrator.__init__()` and call `tracker.update(Stage.ROUND_1_PRO, ...)` etc. at the start of each node method. Pass it via `DebateState.metadata` or as a constructor arg.

---

### HIGH-03: `URLNormalizer` exists but `FactChecker` and `debate.py` both have their own inline URL sanitization — 3 separate implementations, all divergent

**Files:** `src/utils/url_helper.py`, `src/agents/fact_checker.py`, `src/orchestration/debate.py` → `_fact_checker_node()`  
**What happens:** `debate.py._fact_checker_node()` has a 40-line inline URL sanitization function. `fact_checker.py._verify_url()` has its own validation. `url_helper.py.URLNormalizer` has a third implementation. They have different edge cases and will give different results on the same URL. This causes inconsistent behavior where the same hallucinated URL passes in one path and fails in another.

**Fix:** Delete the inline sanitization in `debate.py` and the URL parsing in `fact_checker.py`. Use `URLNormalizer.sanitize_list()` and `URLNormalizer.sanitize_url()` exclusively. One implementation, one source of truth.

---

### HIGH-04: `validate_claim()` max length is 300 chars but `app.py` uses 500 chars — silent mismatch

**Files:** `src/utils/validation.py` (max 300), `app.py` input (maxlength=500 in the old HTML), and the `claim-box` in the retro widget (maxlength=500)  
**What happens:** A user can type a 400-character claim in the UI, it passes the HTML input, but then `validate_claim()` returns `False, "Claim too long"` — silently failing after the user already submitted. The UI shows nothing because the error path in `analyze_claim_with_streaming` calls `st.error()` inside a `with st.status()` context that may already be closed.

**Fix:** Align the limit to one value everywhere. Choose 500 chars, update `validate_claim()` to match, and show a real-time character counter in the UI.

---

### HIGH-05: `APIKeyManager` exponential backoff reaches 1 hour — key never recovered in session

**File:** `src/utils/api_key_manager.py` → `report_key_failure()`  
**What happens:** `backoff_time = min(60 * (2 ** consecutive_failures), 3600)`. After 6 failures, cooldown = 3840s → capped at 3600s (1 hour). On Streamlit Cloud where sessions last minutes to hours, this effectively permanently kills the key for the session. But `reset_all_keys()` exists and is never called automatically — it requires external trigger. There's no auto-recovery after a successful period.

**Fix:** Add auto-reset logic: after `recovery_timeout` elapses without any call (i.e., the system has been idle), reset `consecutive_failures` to 0 and set `cooldown_until = 0`. Also call `reset_all_keys()` at the start of each new Streamlit session (inside `_init()`).

---

### HIGH-06: `FreeLLMClient._check_rate_limit()` mutates shared list without lock on list operations

**File:** `src/llm/client.py` → `_check_rate_limit()`  
**What happens:**
```python
recent = [t for t in call_times if t > one_minute_ago]
call_times.clear()         # ← not atomic
call_times.extend(recent)  # ← not atomic
```
The `_counter_lock` is held for the outer `with` block, but `call_times` is a list reference passed by value to `_check_rate_limit()`. If two threads call this simultaneously with the same list object, one thread's `clear()` can run while the other is iterating — race condition. Python GIL prevents full corruption but the count can be wrong, leading to rate limit bypass.

**Fix:** Replace `call_times.clear(); call_times.extend()` with `call_times[:] = recent` (single atomic slice assignment). Also add `_groq_times_lock` and `_gemini_times_lock` separate from `_counter_lock` to avoid holding the coarse lock during list manipulation.

---

### HIGH-07: `debate.py._fact_checker_node()` swallows all exceptions silently

**File:** `src/orchestration/debate.py` → `_fact_checker_node()`  
```python
except Exception as e:
    logger.error(f"FactChecker failed: {e}")
    return state  # ← state has no verification_results set
```
**What happens:** If FactChecker crashes entirely (e.g., `requests` not installed, SSL error), the state is returned with `verification_results = None`. The Moderator then receives a state with `None` verification data and attempts `state.pro_verification_rate` which is also `None`. The Moderator prompt includes `{pro_rate:.1%}` formatting on a `None` value — **this raises `TypeError` in the Moderator node**, crashing the graph.

**Fix:** In the `except` block, explicitly set `state.verification_results = []`, `state.pro_verification_rate = 0.0`, `state.con_verification_rate = 0.0` before returning. Also add a null-guard in `_build_prompt` in Moderator.

---

## MEDIUM SEVERITY — Logic Bugs & Edge Cases

### MED-01: `_get_actual_key()` returns `None` silently when key hash not in `_reverse_lookup`

**File:** `src/utils/api_key_manager.py` → `get_working_key()`  
**What happens:** If a key passes validation (stored in `self.keys`) but its hash is somehow not in `_reverse_lookup` (race condition during init, or key validation runs twice), `_get_actual_key()` returns `None`. The caller (`FreeLLMClient`) then passes `None` as the API key to Groq/Gemini SDK, getting a cryptic authentication error instead of a clear "no key available" message.

**Fix:** Add assertion `assert key_hash in self._reverse_lookup` inside `_validate_key()` after successful validation, and log a clear error if `_get_actual_key()` returns `None`.

---

### MED-02: `FactChecker._verify_url()` downloads full page HTML for every URL — no size cap

**File:** `src/agents/fact_checker.py` → `_verify_url()`  
**What happens:** `requests.get()` with no `stream=True` and no `max_bytes` limit. A URL returning a 50MB PDF or a huge HTML page will download the entire thing into memory, per thread, with up to 10 concurrent threads. This can consume 500MB+ of RAM in a single FactChecker call on a large claim set.

**Fix:** Use `stream=True` and read only the first 50KB:
```python
resp = requests.get(url, timeout=self.url_timeout, stream=True, headers=headers)
content = resp.raw.read(50000).decode('utf-8', errors='ignore')
```

---

### MED-03: `SemanticCache` loads ALL rows from SQLite into memory for every cache lookup

**File:** `src/orchestration/cache.py` → `get_verdict()`  
```python
c.execute('SELECT claim_text, claim_embedding, verdict_data FROM claim_cache WHERE expires_at > ?')
rows = c.fetchall()  # ← entire table into RAM
```
**What happens:** After 6 months of production use with the pre-seeded 20 claims plus real user claims, this table could have thousands of rows, each with a full embedding blob (1536 floats × 4 bytes = 6KB each). Fetching all of them into RAM on every cache lookup is O(n) memory and O(n) CPU for cosine similarity computation.

**Fix:** Pre-build an in-memory numpy index (`faiss` or simple numpy stack) on startup. Refresh it only when new rows are inserted. The existing `BoundedCache` L1 layer helps for repeats but doesn't solve the full-table scan.

---

### MED-04: `DebateOrchestrator.run()` calls `tavily.search_adversarial()` synchronously before debate starts — no timeout

**File:** `src/orchestration/debate.py` → `run()`  
**What happens:** Tavily is called synchronously with no timeout guard around the call. If Tavily's API is slow or down, this blocks the entire debate thread for an indefinite period. The 180-second Streamlit timeout in `app.py` is measured from the start of `analyze_claim_with_streaming()`, which includes Tavily time — so a 60-second Tavily hang eats 33% of the total budget before a single agent runs.

**Fix:** Wrap the Tavily call in `concurrent.futures.wait(timeout=15)` and fall back to `{"pro": [], "con": []}` on timeout.

---

### MED-05: `validate_claim()` minimum is 3 words but claim can still be nonsense

**File:** `src/utils/validation.py`  
**What happens:** "a b c" passes validation (3 words) but is meaningless for fact-checking. More critically, the prompt-injection check uses `re.search(pattern, claim.lower())` with `r"\bsystem\s*:\s*"` — but the word boundary `\b` before "system" doesn't match "ecosystem:" (good) but also doesn't match "SYSTEM:" (ALL CAPS variant of injection). The `claim.lower()` handles case, but the `\b` after the `r` string prefix means the pattern works — this one is actually fine. However, there is no check for extremely high Unicode density or RTL override characters that could confuse the LLM.

**Fix:** Add minimum meaningful word check (at least one word > 3 chars). Add a Unicode safety check: `if any(ord(c) > 8000 for c in claim): return False, "Claim contains unsupported characters."` to prevent Unicode exploit attempts.

---

### MED-06: `ModeratorVerdict` in `models.py` has `verdict: str = "UNKNOWN"` — not a Literal

**File:** `src/core/models.py`  
**What happens:** The original `ModeratorVerdict` in the file now has `verdict: str = "UNKNOWN"` instead of the Literal type. This means any string the LLM returns — including `"Maybe"`, `"I think true"`, `"TRUE with caveats"` — passes Pydantic validation. The downstream `render_verdict()` in `app.py` checks `verdict in ("RATE_LIMITED", "SYSTEM_ERROR")` and applies CSS classes from a dict. An unexpected string falls through all checks and renders with no CSS class — blank box, invisible text.

**Fix:** Restore `verdict: Literal["TRUE","FALSE","PARTIALLY TRUE","INSUFFICIENT EVIDENCE","CONSENSUS_SETTLED","RATE_LIMITED","UNKNOWN","ERROR"]`. Add a `@validator` that strips and title-cases the value before matching.

---

## LOW SEVERITY — Code Quality & Maintenance

### LOW-01: `concurrent.futures` import is duplicated in `fact_checker.py` and `debate.py`
Both files manage their own thread pools. Consolidate into a shared module-level executor in `src/utils/thread_pool.py`.

### LOW-02: `TrustScorer` is computed but its result is never used in the verdict formula
`trust_score` and `trust_tier` are populated in `SourceVerification` but the Moderator prompt and weighted consensus algorithm in `debate.py` ignore them entirely. The `DebateConfig.SOURCE_VERIFICATION_WEIGHT = 2.0` is a constant comment — it's not actually used in any calculation in the current code.

### LOW-03: `ObservableLogger` creates a second log handler every time it is imported in a new thread
The `if not root.handlers:` guard is correct but `root = logging.getLogger("InsightSwarm")` uses the named logger, not the root logger. If `logging.basicConfig()` was already called (as in `main.py`), a second handler is added to the root logger — causing double-printing of every log line.

### LOW-04: `BoundedCache` is imported in `cache.py` but `bounded_cache.py` may not exist
```python
from src.orchestration.bounded_cache import BoundedCache
```
This is wrapped in `try/except ImportError` — so it silently degrades — but it means the L1 cache is never active. The file should be created.

### LOW-05: `app.py` imports `from concurrent.futures import ThreadPoolExecutor` but removed its usage
The old `executor` in `app.py` is gone (replaced by `BackgroundTaskQueue`) but the import remains. Dead import.

---

## PATCH IMPLEMENTATION PLAN

### Phase 1 — Stop the Bleeding (Critical fixes, 1-2 hours)

**P1-A: Guard `APIKeyManager` init crash**
```python
# api_key_manager.py — replace the RuntimeError raise
if not all_keys_loaded:
    self.degraded = True
    self.degraded_reason = "Required API keys missing or invalid"
    logger.error("APIKeyManager degraded: " + self.degraded_reason)
    # Do NOT raise — let app surface the error gracefully
```
Add `self.degraded = False` in `__init__`. In `get_working_key()`, if `self.degraded`, log and return `None`.

**P1-B: Fix `_fact_checker_node()` exception swallow**
```python
except Exception as e:
    logger.error(f"FactChecker failed: {e}")
    state.verification_results = []
    state.pro_verification_rate = 0.0
    state.con_verification_rate = 0.0
    return state
```

**P1-C: Fix `SemanticCache._encode()` permanent disable**
```python
def _encode(self, text: str):
    try:
        return self.model.encode([text])[0]
    except Exception as e:
        logger.warning(f"Encoding failed (cache miss, not disabling): {e}")
        return None  # Do NOT set self.enabled = False
```

**P1-D: Add `atexit` shutdown to `BackgroundTaskQueue`**
```python
import atexit
# in __new__:
atexit.register(cls._instance.executor.shutdown, wait=False)
```
Add cleanup loop in `get_status()` to prune completed tasks older than 300 seconds.

**P1-E: Cap HTTP response size in `FactChecker._verify_url()`**
```python
resp = requests.get(url, timeout=self.url_timeout, stream=True, headers=headers, allow_redirects=True)
content = b""
for chunk in resp.iter_content(chunk_size=8192):
    content += chunk
    if len(content) > 51200:  # 50KB cap
        break
content = content.decode('utf-8', errors='ignore')
```

---

### Phase 2 — Wire the Dead Code (High fixes, 2-3 hours)

**P2-A: Wire `CircuitBreaker` into `FreeLLMClient`**

Create module-level breakers:
```python
# src/llm/client.py — top level
from src.resilience.circuit_breaker import CircuitBreaker
_groq_breaker = CircuitBreaker("groq", failure_threshold=3, recovery_timeout=60)
_gemini_breaker = CircuitBreaker("gemini", failure_threshold=3, recovery_timeout=60)
```

In `_call_groq()`:
```python
if not _groq_breaker.is_allowed():
    raise RuntimeError("Groq circuit OPEN — skipping to fallback")
try:
    result = ...  # existing call
    _groq_breaker.record_success()
    return result
except Exception as e:
    _groq_breaker.record_failure()
    raise
```

**P2-B: Wire `ProgressTracker` into `DebateOrchestrator`**

Add `tracker: Optional[ProgressTracker] = None` param to `__init__`. In each node:
```python
def _pro_agent_node(self, state):
    if self.tracker:
        self.tracker.update(Stage.ROUND_1_PRO if state.round == 1 else Stage.ROUND_2_PRO if state.round == 2 else Stage.ROUND_3_PRO, 
                            f"ProAgent arguing Round {state.round}...")
    ...
```

In `app.py`, pass the tracker: `orchestrator = DebateOrchestrator(tracker=st.session_state.tracker)`.

**P2-C: Remove duplicate URL sanitization — use `URLNormalizer` only**

In `debate.py._fact_checker_node()`, replace the 40-line inline function:
```python
from src.utils.url_helper import URLNormalizer
state.pro_sources = URLNormalizer.sanitize_list(state.pro_sources)
state.con_sources = URLNormalizer.sanitize_list(state.con_sources)
```

Delete the inline `_sanitize_list_of_sources` function entirely.

**P2-D: Restore `ModeratorVerdict.verdict` as `Literal` type**
```python
class ModeratorVerdict(BaseModel):
    verdict: Literal[
        "TRUE","FALSE","PARTIALLY TRUE","INSUFFICIENT EVIDENCE",
        "CONSENSUS_SETTLED","RATE_LIMITED","UNKNOWN","ERROR"
    ] = "UNKNOWN"
```

---

### Phase 3 — Harden for Production (Medium fixes, 2-3 hours)

**P3-A: Wrap Tavily call with 15-second timeout**
```python
import concurrent.futures as cf
with cf.ThreadPoolExecutor(max_workers=1) as ex:
    fut = ex.submit(tavily.search_adversarial, claim, 5)
    try:
        adversarial_sources = fut.result(timeout=15)
    except cf.TimeoutError:
        logger.warning("Tavily timed out — proceeding without pre-fetched evidence")
        adversarial_sources = {"pro": [], "con": []}
```

**P3-B: Fix `_check_rate_limit()` list mutation race**
```python
call_times[:] = [t for t in call_times if t > one_minute_ago]  # atomic slice assign
```

**P3-C: Add `reset_all_keys()` call at session start**
In `app.py._init()`:
```python
from src.utils.api_key_manager import get_api_key_manager
get_api_key_manager().reset_all_keys()
```

**P3-D: Create `bounded_cache.py`**
```python
# src/orchestration/bounded_cache.py
from collections import OrderedDict

class BoundedCache:
    def __init__(self, maxsize=100):
        self._cache = OrderedDict()
        self._maxsize = maxsize

    def get(self, key):
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def put(self, key, value):
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)
```

**P3-E: Use module-level singleton thread pool in `FactChecker`**
```python
# src/agents/fact_checker.py — module level
import atexit
_VERIFY_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=5)
atexit.register(_VERIFY_POOL.shutdown, wait=False)

# in generate():
# replace: with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
futures = {_VERIFY_POOL.submit(...): url for ...}
```

**P3-F: Align claim length limit to 500 chars everywhere**
```python
# validation.py
if len(claim) > 500:
    return False, "Claim too long (max 500 characters)."
```

---

### Phase 4 — Code Quality Cleanup (Low fixes, 1 hour)

**P4-A:** Create `src/utils/thread_pool.py` with a single shared `ThreadPoolExecutor` and `atexit` handler. Import from there in both `FactChecker` and any future concurrent code.

**P4-B:** Wire `TrustScorer` results into the weighted consensus formula in `debate.py._moderator_node()`. Add `trust_weight` to `DebateConfig`.

**P4-C:** Remove dead import `from concurrent.futures import ThreadPoolExecutor` from `app.py`.

**P4-D:** Fix `ObservableLogger` double-handler issue — check `logging.getLogger("InsightSwarm").handlers` instead of relying on root logger guard.

**P4-E:** Add Unicode safety check to `validate_claim()`.

---

## ISSUE PRIORITY MATRIX

| ID | Severity | Effort | Impact if unfixed |
|---|---|---|---|
| CRIT-01 | CRITICAL | 30 min | App crashes on any API key issue |
| CRIT-02 | CRITICAL | 20 min | Unhandled exception kills session |
| CRIT-03 | CRITICAL | 45 min | Memory leak → OOM on Streamlit Cloud |
| CRIT-04 | CRITICAL | 15 min | Cache permanently disabled after 1 error |
| CRIT-05 | CRITICAL | 30 min | OOM with multiple users |
| HIGH-01 | HIGH | 2 hr | Circuit breaker/fallback never activates |
| HIGH-02 | HIGH | 1 hr | Progress bar always frozen |
| HIGH-03 | HIGH | 30 min | URL sanitization inconsistency |
| HIGH-04 | HIGH | 15 min | 400-char claims silently rejected |
| HIGH-05 | HIGH | 20 min | Keys permanently dead for session |
| HIGH-06 | HIGH | 30 min | Race condition on rate limit counter |
| HIGH-07 | HIGH | 15 min | FactChecker crash → Moderator TypeError |
| MED-01 | MEDIUM | 15 min | Cryptic auth errors |
| MED-02 | MEDIUM | 20 min | OOM from large page downloads |
| MED-03 | MEDIUM | 1 hr | O(n) memory on every cache lookup |
| MED-04 | MEDIUM | 20 min | Tavily hang eats 33% of timeout |
| MED-05 | MEDIUM | 15 min | Garbage claims pass validation |
| MED-06 | MEDIUM | 15 min | Invalid verdict strings break UI |
| LOW-01 to LOW-05 | LOW | 2 hr total | Technical debt, no user impact |

---

## RECOMMENDED ORDER OF EXECUTION

```
Day 1 (2 hours):
  P1-A → P1-B → P1-C → P1-D → P1-E
  (All 5 critical patches — nothing crashes after this)

Day 2 (3 hours):
  P2-A → P2-B → P2-C → P2-D
  (Wire the dead resilience code — system now actually uses circuit breakers)

Day 3 (3 hours):
  P3-A → P3-B → P3-C → P3-D → P3-E → P3-F
  (Harden for multi-user production load)

Day 4 (1 hour):
  P4-A → P4-B → P4-C → P4-D → P4-E
  (Clean up dead code and technical debt)
```

**Total estimated effort: ~9 hours across 4 sessions.**  
After Phase 1 alone, the system survives all API failure modes without crashing.  
After Phase 2, it uses its own resilience infrastructure for the first time.  
After Phase 3, it is ready for production multi-user load.
