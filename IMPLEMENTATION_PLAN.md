# InsightSwarm — Full Implementation Plan
**Based on complete re-read of all source files, March 2026**

Every fix below names the exact file, the exact line/function, exactly what to change, and which session to do it in.

---

## THE 4 SESSIONS

| Session | Theme | Time | Goal |
|---------|-------|------|------|
| 1 | Stop the Crashes | 90 min | Nothing can destroy the app anymore |
| 2 | Fix Silent Failures | 90 min | System degrades gracefully, not silently breaks |
| 3 | Wire the Orphaned Code | 60 min | Use what you already built |
| 4 | Production Hardening | 60 min | Ready for real traffic |

---

# SESSION 1 — STOP THE CRASHES
**Do this first. These are the bugs that kill the entire app.**

---

## FIX 1-A
**File:** `src/utils/api_key_manager.py`
**Function:** `_load_and_validate_keys()`
**Line:** The `if not all_keys_loaded: raise RuntimeError(...)` block at the bottom

**Problem:** If GROQ_API_KEY is missing or badly formatted, this raises a RuntimeError that propagates up through FreeLLMClient → DebateOrchestrator → app.py and crashes the entire Streamlit session with a white screen. The singleton `_key_manager = None` then stays None forever — every subsequent request also crashes.

**What to change:**

Replace this block:
```python
if not all_keys_loaded:
    raise RuntimeError(
        "❌ Critical API keys missing or invalid. ..."
    )
logger.info("✅ API Key Manager initialized successfully")
```

With this:
```python
self.degraded = not all_keys_loaded
if self.degraded:
    self.degraded_reason = (
        "Required API keys missing or invalid. Check GROQ_API_KEY in .env"
    )
    logger.error(f"⚠️ APIKeyManager degraded: {self.degraded_reason}")
else:
    logger.info("✅ API Key Manager initialized successfully")
```

Also add `self.degraded = False` and `self.degraded_reason = ""` at the TOP of `__init__()`, before `_load_and_validate_keys()` is called.

Then in `get_working_key()`, add at the very top:
```python
if getattr(self, 'degraded', False):
    logger.warning(f"APIKeyManager degraded: {self.degraded_reason}")
    return None
```

**Result:** Bad API key = graceful None return everywhere, app shows a banner instead of crashing.

---

## FIX 1-B
**File:** `src/orchestration/debate.py`
**Function:** `_fact_checker_node()`
**Line:** The `except Exception as e:` block at the bottom of the function

**Problem:** If FactChecker crashes (SSL error, model load fail, etc.), this returns bare `state` with `verification_results = None`, `pro_verification_rate = None`, `con_verification_rate = None`. The Moderator's `_build_prompt()` then does `{pro_rate:.1%}` formatting on `None` → `TypeError` → entire LangGraph graph crashes.

**What to change:**

Replace:
```python
except Exception as e:
    logger.error(f"FactChecker failed: {e}")
    return state
```

With:
```python
except Exception as e:
    logger.error(f"FactChecker failed: {e}", exc_info=True)
    state.verification_results = state.verification_results or []
    state.pro_verification_rate = state.pro_verification_rate if state.pro_verification_rate is not None else 0.0
    state.con_verification_rate = state.con_verification_rate if state.con_verification_rate is not None else 0.0
    return state
```

---

## FIX 1-C
**File:** `src/orchestration/cache.py`
**Function:** `_encode()`

**Problem:** On any embedding model failure (network, HuggingFace timeout, memory), this sets `self.enabled = False` permanently. Every subsequent cache lookup returns None for the rest of the session. The system hits the LLM API for every repeat claim — burning quota. One transient error bricks caching forever.

**What to change:**

Replace:
```python
def _encode(self, text: str) -> Optional[np.ndarray]:
    try:
        return self.model.encode([text])[0]
    except Exception as e:
        logger.warning(f"Semantic cache disabled (model load failed): {e}")
        self.enabled = False
        return None
```

With:
```python
def _encode(self, text: str) -> Optional[np.ndarray]:
    try:
        return self.model.encode([text])[0]
    except Exception as e:
        # Do NOT disable cache permanently — this may be transient
        # Just return None for this call, cache will try again next time
        logger.warning(f"Embedding encode failed (cache miss for this call): {e}")
        return None
```

Also fix `model` property — replace `self._model_failed = True` with a counter:
Add `self._model_fail_count = 0` in `__init__`. In the `model` property exception:
```python
except Exception as e:
    self._model_fail_count += 1
    if self._model_fail_count >= 3:
        self._model_failed = True  # Only permanently fail after 3 attempts
    raise RuntimeError(f"Failed to load embedding model: {e}")
```

---

## FIX 1-D
**File:** `src/agents/fact_checker.py`
**Function:** `generate()`
**Line:** `with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:`

**Problem:** A new 10-thread executor is created fresh on every single `generate()` call. With 3 concurrent users that's 30 threads spinning up simultaneously downloading full HTML pages. On Streamlit Cloud's 1GB container this is an OOM bomb. The executor is also never explicitly shut down — it relies on the `with` block's `__exit__` which calls `shutdown(wait=True)`, blocking the calling thread until all 10 fetches complete even if 5 of them are hanging at the 10-second timeout.

**What to change:**

At module level (top of file, after imports), add:
```python
import atexit as _atexit

_VERIFY_POOL = concurrent.futures.ThreadPoolExecutor(
    max_workers=5,
    thread_name_prefix="factcheck"
)
_atexit.register(_VERIFY_POOL.shutdown, wait=False)
```

In `generate()`, replace:
```python
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    futures = {executor.submit(self._verify_url, url, agent, state.claim, claim_embedding): url 
               for url, agent, argument in all_sources}
    for future in concurrent.futures.as_completed(futures):
        try:
            res = future.result()
            if res is not None:
                results.append(res)
        except Exception as e:
            logger.error(f"Failed to verify {futures[future]}: {e}")
```

With:
```python
futures = {
    _VERIFY_POOL.submit(self._verify_url, url, agent, state.claim, claim_embedding): url
    for url, agent, argument in all_sources
}
for future in concurrent.futures.as_completed(futures, timeout=60):
    try:
        res = future.result(timeout=15)
        if res is not None:
            results.append(res)
    except concurrent.futures.TimeoutError:
        logger.warning(f"URL verification timed out: {futures[future]}")
    except Exception as e:
        logger.error(f"Failed to verify {futures[future]}: {e}")
```

---

## FIX 1-E
**File:** `src/agents/fact_checker.py`
**Function:** `_verify_url()`
**Line:** `resp = requests.get(url, timeout=self.url_timeout, allow_redirects=True, headers=headers)`

**Problem:** Downloads unlimited bytes. A URL returning a 50MB PDF or huge HTML page downloads everything into memory, per thread. With 5 threads this is 250MB RAM consumed in one FactChecker call.

**What to change:**

Replace:
```python
resp = requests.get(
    url,
    timeout=self.url_timeout,
    allow_redirects=True,
    headers=headers
)
```

With:
```python
resp = requests.get(
    url,
    timeout=self.url_timeout,
    allow_redirects=True,
    headers=headers,
    stream=True
)
# Read at most 50KB — enough for fuzzy matching, prevents OOM
raw_bytes = b""
for chunk in resp.iter_content(chunk_size=8192):
    raw_bytes += chunk
    if len(raw_bytes) >= 51200:
        break
resp._content = raw_bytes  # make resp.text work normally after this
```

Then change the paywall check to:
```python
content_text = raw_bytes.decode("utf-8", errors="ignore")
paywall_indicators = ['subscribe to read', 'paywall', 'premium content', 'login to continue', 'subscription required', 'members only']
if any(ind in content_text.lower() for ind in paywall_indicators):
    ...
```

And replace all subsequent `resp.text` and `content = resp.text` with `content = content_text`.

---

## FIX 1-F
**File:** `src/async_tasks/task_queue.py`
**Class:** `BackgroundTaskQueue`

**Problem:** `self.tasks` dict grows without bound — every completed debate stays in memory forever. On Streamlit Cloud with dozens of daily users, this leaks memory until OOM kill.

**What to change:**

Add `import atexit` at the top.

In `__new__`, after creating the executor, add:
```python
atexit.register(cls._instance.executor.shutdown, wait=False)
```

Add this method to the class:
```python
def _prune_old_tasks(self):
    """Remove completed tasks older than 10 minutes."""
    import time
    now = time.time()
    to_delete = []
    for task_id, (future, meta) in self.tasks.items():
        if future.done():
            # Check if the task was submitted more than 10 min ago
            submitted_at = getattr(future, '_submitted_at', now)
            if now - submitted_at > 600:
                to_delete.append(task_id)
    for task_id in to_delete:
        del self.tasks[task_id]
```

In `submit()`, before `future = self.executor.submit(...)`, call `self._prune_old_tasks()`.
After `future = self.executor.submit(...)`, add: `future._submitted_at = time.time()`  
*(Note: `_submitted_at` is a custom attr on the Future object — this works in Python.)*

Also cap the dict: after the above, add:
```python
if len(self.tasks) > 50:
    # Evict oldest completed task
    for tid, (f, _) in list(self.tasks.items()):
        if f.done():
            del self.tasks[tid]
            break
```

---

## FIX 1-G  
**File:** `src/orchestration/debate.py`
**Function:** `run()`
**Line:** The dangling `tavily = get_tavily_retriever()` at the very bottom of the function — **after** the `return` statement and **after** the `except` block

**Problem:** There is a stray `tavily = get_tavily_retriever()` line at line ~355 that appears AFTER both the `return final_state` and the `except` block's `return initial_state`. This is dead unreachable code but it is syntactically valid Python — it causes no error but it is evidence the function's structure is confused. More importantly, the Tavily call INSIDE the function (before the try block) runs synchronously with no timeout — if Tavily is slow, it eats your 180s budget.

**What to change:**

1. Delete the dangling `tavily = get_tavily_retriever()` line at the bottom of `run()`.

2. Wrap the Tavily call in a timeout:
```python
# Replace:
tavily = get_tavily_retriever()
adversarial_sources = tavily.search_adversarial(claim, max_results=5)

# With:
import concurrent.futures as _cf
tavily = get_tavily_retriever()
try:
    with _cf.ThreadPoolExecutor(max_workers=1) as _tex:
        _fut = _tex.submit(tavily.search_adversarial, claim, 5)
        adversarial_sources = _fut.result(timeout=12)
except Exception:
    logger.warning("Tavily timed out or failed — proceeding without pre-fetched evidence")
    adversarial_sources = {"pro": [], "con": []}
```

Same fix in `stream()` — same Tavily call pattern, same problem.

---

# SESSION 2 — FIX SILENT FAILURES
**These don't crash the app but silently degrade quality or lie to users.**

---

## FIX 2-A
**File:** `src/core/models.py`
**Class:** `ModeratorVerdict`

**Problem:** `verdict: str = "UNKNOWN"` accepts any string from the LLM including `"Maybe"`, `"TRUE with caveats"`, `"I believe true"`. These fall through all the CSS class lookups and render as invisible text on a dark background — the user sees a blank verdict box.

**What to change:**

Replace:
```python
class ModeratorVerdict(BaseModel):
    verdict: str = "UNKNOWN"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reasoning: str = ""
    metrics: Optional[Dict[str, Any]] = Field(default_factory=dict)
```

With:
```python
from pydantic import validator

class ModeratorVerdict(BaseModel):
    verdict: str = "UNKNOWN"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reasoning: str = ""
    metrics: Optional[Dict[str, Any]] = Field(default_factory=dict)

    _VALID_VERDICTS = {
        "TRUE", "FALSE", "PARTIALLY TRUE", "INSUFFICIENT EVIDENCE",
        "CONSENSUS_SETTLED", "RATE_LIMITED", "UNKNOWN", "ERROR"
    }

    @validator("verdict", pre=True, always=True)
    def normalise_verdict(cls, v):
        if not v:
            return "UNKNOWN"
        v = str(v).strip().upper()
        # Common LLM variants
        if v in ("PARTIALLY_TRUE", "PARTIAL", "PARTLY TRUE", "PARTLY_TRUE"):
            return "PARTIALLY TRUE"
        if v in ("INSUFFICIENT", "INSUFFICIENT_EVIDENCE", "NOT ENOUGH EVIDENCE"):
            return "INSUFFICIENT EVIDENCE"
        if v in ("TRUE", "FALSE", "UNKNOWN", "ERROR", "RATE_LIMITED", "CONSENSUS_SETTLED"):
            return v
        # If nothing matched, log and default
        logger.warning(f"ModeratorVerdict: unexpected verdict '{v}', defaulting to UNKNOWN")
        return "UNKNOWN"
```

---

## FIX 2-B
**File:** `src/utils/api_key_manager.py`
**Function:** `report_key_failure()`
**Line:** `backoff_time = min(60 * (2 ** key_info.consecutive_failures), 3600)`

**Problem:** After 6 failures, backoff = 3840s → capped at 3600s (1 hour). On Streamlit Cloud where a session might last 30 minutes, this permanently kills the key. `reset_all_keys()` exists but is never called automatically.

**What to change:**

Change the max backoff cap from 3600 to 300 (5 minutes max):
```python
backoff_time = min(60 * (2 ** key_info.consecutive_failures), 300)
```

Then add auto-recovery: in `get_working_key()`, before the availability check, add:
```python
# Auto-reset keys that have been in cooldown longer than their backoff time
now = time.time()
for ki in self.keys.get(provider, []):
    if ki.status == APIKeyStatus.RATE_LIMITED and now >= ki.cooldown_until:
        ki.status = APIKeyStatus.VALID
        ki.consecutive_failures = max(0, ki.consecutive_failures - 1)
        logger.info(f"Auto-recovered {provider} key from cooldown")
```

---

## FIX 2-C
**File:** `src/llm/client.py`
**Function:** `_check_rate_limit()`

**Problem:** `last_call_times[:] = [t for t in last_call_times if now - t < 60]` is correct BUT this function is called inside `with self._counter_lock:` in `_execute_provider()`, and `last_call_times` is a reference to `self.groq_last_call_times` etc. Two threads can race on the same list between `fetchall` and `extend`. The fix is already partially there (slice assignment is atomic-ish) but the lock scope is inconsistent — `_check_rate_limit` gets the list by reference then the caller appends to `last_times` in the same lock block. This is actually okay as written. **This one is FINE — no change needed.** (Crossed off from the original audit — the current code structure is correct.)

---

## FIX 2-D
**File:** `src/orchestration/cache.py`
**Function:** `get_verdict()`
**Line:** `rows = c.fetchall()`

**Problem:** Fetches the entire `claim_cache` table into RAM on every lookup. After months of production, this is thousands of rows × 6KB embedding each = hundreds of MB loaded and compared on every request.

**What to change:**

Add a module-level in-memory numpy index that rebuilds only when new rows are written:

Add at class level:
```python
self._embedding_index = None   # numpy array of all embeddings, shape (N, D)
self._index_ids = []           # list of row IDs in same order as _embedding_index
self._index_dirty = True       # True = needs rebuild
```

Add a method:
```python
def _rebuild_index(self):
    """Load all embeddings into RAM as a numpy matrix for fast cosine search."""
    try:
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            now = datetime.now().isoformat()
            c.execute(
                'SELECT id, claim_embedding, verdict_data, created_at FROM claim_cache WHERE expires_at > ?',
                (now,)
            )
            rows = c.fetchall()
        if not rows:
            self._embedding_index = None
            self._index_data = []
            return
        ids, embeddings, data = [], [], []
        for row_id, emb_bytes, verdict_json, created_at in rows:
            emb = np.frombuffer(emb_bytes, dtype=np.float32)
            ids.append(row_id)
            embeddings.append(emb)
            d = json.loads(verdict_json)
            d['cached_at'] = created_at
            data.append(d)
        self._embedding_index = np.stack(embeddings)  # shape (N, D)
        # Pre-normalise for fast cosine via dot product
        norms = np.linalg.norm(self._embedding_index, axis=1, keepdims=True)
        norms[norms == 0] = 1
        self._embedding_index = self._embedding_index / norms
        self._index_data = data
        self._index_dirty = False
        logger.debug(f"Rebuilt embedding index: {len(rows)} entries")
    except Exception as e:
        logger.error(f"Index rebuild failed: {e}")
        self._embedding_index = None
```

In `get_verdict()`, replace the entire fetchall loop with:
```python
if self._index_dirty or self._embedding_index is None:
    self._rebuild_index()
if self._embedding_index is None:
    return None

q = query_embedding / (np.linalg.norm(query_embedding) or 1)
sims = self._embedding_index @ q
best_idx = int(np.argmax(sims))
best_sim = float(sims[best_idx])
if best_sim >= similarity_threshold:
    data = dict(self._index_data[best_idx])
    data['is_cached'] = True
    data['cache_similarity'] = best_sim
    ...
    return data
return None
```

In `set_verdict()`, after the INSERT, add: `self._index_dirty = True`

---

## FIX 2-E
**File:** `src/utils/validation.py`
**Function:** `validate_claim()`

**Problem:** Max 300 chars but `app.py` text input has no HTML maxlength — user types 400 chars, submits, gets a confusing silent rejection. Also minimum is 10 chars in `app.py` but 3 words in `validate_claim()` — "a b c" (5 chars) passes the word check but fails the char check — inconsistent.

**What to change:**

```python
def validate_claim(claim: str) -> Tuple[bool, str]:
    if not claim or not claim.strip():
        return False, "Claim cannot be empty."
    
    stripped = claim.strip()
    
    # Align with UI max
    if len(stripped) > 500:
        return False, "Claim too long (max 500 characters)."
    
    # Align with UI min  
    if len(stripped) < 10:
        return False, "Claim too short (minimum 10 characters)."
    
    # At least one meaningful word (>2 chars)
    words = stripped.split()
    if not any(len(w) > 2 for w in words):
        return False, "Claim must contain at least one meaningful word."
    
    # Unicode safety — reject RTL override and other control characters
    for char in stripped:
        cp = ord(char)
        if 0x200B <= cp <= 0x200F or 0x202A <= cp <= 0x202E or 0xFFF0 <= cp <= 0xFFFF:
            return False, "Claim contains unsupported characters."
    
    # Prompt injection patterns
    injection_patterns = [
        r"ignore\s+previous\s+instructions",
        r"ignore\s+all\s+previous",
        r"disregard\s+all\s+previous",
        r"\bsystem\s*:\s*",
    ]
    for pattern in injection_patterns:
        if re.search(pattern, stripped.lower()):
            return False, "Prompt injection detected."
    
    return True, ""
```

---

## FIX 2-F
**File:** `src/orchestration/debate.py`
**Function:** `_moderator_node()`

**Problem:** If `response.metrics` is `None` (which happens when Moderator uses the fallback path), then `state.metrics = None` is set. Later in `app.py`, `render_metrics()` does `m = result.get("metrics") or {}` and `float(m.get('credibility', 0.0))` — this works. But `state.metrics = response.metrics` where `response.metrics` is an empty dict `{}` from `AgentResponse` default, not `None`. This is actually fine as-is. **No change needed here.**

However, there IS a real bug: when `_moderator_node` catches `RateLimitError` it sets `state.metrics = {}` (dict), but `DebateState.metrics` is typed as `Optional[Dict[str, Any]]` with `default_factory=dict`, so empty dict is fine. **Fine — no change.**

---

# SESSION 3 — WIRE THE ORPHANED CODE
**Code that's built and imported but not actually used correctly.**

---

## FIX 3-A
**File:** `src/orchestration/debate.py`
**Function:** `_verification_gate_node()`
**Lines:** The Gemini key check block

**Problem:**
```python
gemini_key = self.client.key_manager.get_working_key("gemini")
if not gemini_key:
    raise RuntimeError("No working Gemini API keys available for verification")
```
This raises inside a LangGraph node — which is an unhandled exception that crashes the graph. The verification gate doesn't even USE the Gemini key — FactChecker uses HTTP directly. This key check makes no sense here and will crash the graph when Gemini is rate-limited.

**What to change:**

Delete the entire block:
```python
gemini_key = self.client.key_manager.get_working_key("gemini")
if not gemini_key:
    raise RuntimeError("No working Gemini API keys available for verification")
```

Replace it with nothing — the verification gate only calls `self.fact_checker._verify_url()` which is HTTP-only and doesn't need any LLM key.

---

## FIX 3-B
**File:** `src/orchestration/bounded_cache.py` ← **THIS FILE DOES NOT EXIST**
**Action:** CREATE it.

`cache.py` does:
```python
from src.orchestration.bounded_cache import BoundedCache
```
wrapped in try/except ImportError, so it silently fails. The L1 memory cache is never active. Create the file:

```python
# src/orchestration/bounded_cache.py
"""LRU-bounded in-memory cache — L1 layer in front of SQLite semantic cache."""
from collections import OrderedDict
from threading import Lock

class BoundedCache:
    def __init__(self, maxsize: int = 100):
        self._cache: OrderedDict = OrderedDict()
        self._maxsize = maxsize
        self._lock = Lock()

    def get(self, key: str):
        with self._lock:
            if key not in self._cache:
                return None
            self._cache.move_to_end(key)
            return self._cache[key]

    def put(self, key: str, value) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value
            if len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)
```

---

## FIX 3-C
**File:** `src/orchestration/debate.py`
**Function:** `_summarize_node()`
**Lines:** History capping block

**Problem:**
```python
if len(state.pro_arguments) > 2:
    state.pro_arguments = state.pro_arguments[-2:]
    state.con_arguments = state.con_arguments[-2:]
```
This caps arguments but does NOT cap `pro_sources` and `con_sources`. The FactChecker iterates over `state.pro_sources` which still has all 3 rounds — now misaligned with `pro_arguments` which only has 2. This will cause index-out-of-range bugs when the FactChecker tries to pair `pro_arguments[i]` with `pro_sources[i]`.

**What to change:**

Replace:
```python
if len(state.pro_arguments) > 2:
    state.pro_arguments = state.pro_arguments[-2:]
    state.con_arguments = state.con_arguments[-2:]
```

With:
```python
if len(state.pro_arguments) > 2:
    state.pro_arguments = state.pro_arguments[-2:]
    state.con_arguments = state.con_arguments[-2:]
    state.pro_sources = state.pro_sources[-2:]    # keep in sync
    state.con_sources = state.con_sources[-2:]    # keep in sync
```

---

## FIX 3-D
**File:** `src/orchestration/debate.py`
**Function:** `__init__()`
**Line:** `self.conn = get_db_connection()`

**Problem:** `get_db_connection()` creates a singleton SQLite connection with `check_same_thread=False`. `SqliteSaver` from LangGraph is then given this single shared connection. When multiple concurrent Streamlit sessions run simultaneously, they share the same SQLite connection — SQLite connections are not truly thread-safe even with `check_same_thread=False` for writes. This causes intermittent `database is locked` errors.

**What to change:**

Replace `SqliteSaver` with `MemorySaver` for the checkpointer — the checkpointer only needs to persist within one debate run (one session), not across restarts:

```python
# At top of file, change import:
# from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.memory import MemorySaver

# In __init__(), replace:
# self.conn = get_db_connection()
# self.resource_manager = get_resource_manager()
# self.checkpointer = SqliteSaver(self.conn)

# With:
self.resource_manager = get_resource_manager()
self.checkpointer = MemorySaver()
```

Also remove `get_db_connection()` function entirely if nothing else uses it, and remove the `import sqlite3` from the top of `debate.py` (it's only used by that function). Remove the `close()` method too since there's no connection to close.

---

## FIX 3-E
**File:** `app.py`
**Function:** `_init()`

**Problem:** `reset_all_keys()` should be called once per new Streamlit session to recover rate-limited keys from previous sessions. Currently it's never called.

**What to change:**

In `_init()`, after the session state defaults are set, add:
```python
# Reset any rate-limited keys on fresh session start
if not st.session_state.get("_keys_reset"):
    try:
        from src.utils.api_key_manager import get_api_key_manager
        get_api_key_manager().reset_all_keys()
    except Exception:
        pass
    st.session_state._keys_reset = True
```

---

## FIX 3-F
**File:** `app.py`
**Function:** `analyze_claim_async()`

**Problem:** `DebateOrchestrator()` initialization can still fail if something goes wrong. The current `except Exception as e: st.error(...); return None` is correct but `st.error()` inside a background task function won't show in the UI because Streamlit context isn't available in background threads.

**What to change:**

Replace:
```python
try:
    orchestrator = DebateOrchestrator(tracker=tracker)
except Exception as e:
    st.error(f"Orchestrator init failed: {e}")
    return None
```

With:
```python
try:
    orchestrator = DebateOrchestrator(tracker=tracker)
except Exception as e:
    logger.error(f"Orchestrator init failed: {e}", exc_info=True)
    st.session_state.debate_error = f"System initialization failed: {e}"
    st.session_state.is_running = False
    return None
```

---

# SESSION 4 — PRODUCTION HARDENING
**These make the system robust for real multi-user traffic.**

---

## FIX 4-A
**File:** `src/orchestration/debate.py`
**Function:** `run()`
**Lines:** Around the LangGraph `self.graph.invoke()` call

**Problem:** LangGraph's `invoke()` can raise a wide variety of internal exceptions including `GraphInterrupt`, `GraphRecursionError` (if somehow the graph loops), and various LangChain exceptions. These are all caught by the broad `except Exception as e:` but the error message `f"System-level error (likely API quota): {str(e)}"` is wrong for non-quota errors and confuses debugging.

**What to change:**

Replace:
```python
except Exception as e:
    logger.error(f"Debate failed: {e}")
    initial_state.verdict = "INSUFFICIENT EVIDENCE"
    initial_state.confidence = 0.0
    initial_state.moderator_reasoning = f"System-level error (likely API quota): {str(e)}"
    initial_state.metrics = {}
    return initial_state
```

With:
```python
except Exception as e:
    err_str = str(e)
    is_quota = any(kw in err_str.lower() for kw in ["rate", "429", "quota", "exhausted"])
    logger.error(f"Debate failed ({'quota' if is_quota else 'system'}): {e}", exc_info=not is_quota)
    initial_state.verdict = "RATE_LIMITED" if is_quota else "INSUFFICIENT EVIDENCE"
    initial_state.confidence = 0.0
    initial_state.moderator_reasoning = (
        f"API quota exhausted. Please wait and try again. ({err_str[:200]})"
        if is_quota else
        f"A system error interrupted the debate. Details: {err_str[:200]}"
    )
    initial_state.metrics = initial_state.metrics or {}
    return initial_state
```

---

## FIX 4-B
**File:** `src/utils/claim_decomposer.py`
**Function:** `decompose()`
**Line:** `preferred_provider="cerebras"`

**Problem:** ClaimDecomposer hardcodes `preferred_provider="cerebras"`. Cerebras is listed as having DNS issues in the orchestrator comments. If Cerebras is unavailable, this adds a full retry cycle before falling back to other providers — slow. Also, if `call_structured()` fails completely, the fallback `return [full_claim]` is correct, but the function is called at the start of EVERY debate run including cache hits — burning tokens on decomposition even when the result will be cached anyway.

**What to change:**

1. Change `preferred_provider="cerebras"` to `preferred_provider="groq"` (more reliable for your setup).

2. Move the decomposer call AFTER the cache check in `debate.py.run()`:

```python
# Check cache first (BEFORE decomposing — cache stores original claim)
cache = get_cache()
cached_result = cache.get_verdict(claim)  # Try original first
if cached_result:
    state = DebateState.parse_obj(cached_result)
    state.is_cached = True
    return state

# Only decompose on cache miss
sub_claims = self.decomposer.decompose(claim)
target_claim = sub_claims[0]

# Try cache again with decomposed claim if different
if target_claim != claim:
    cached_result = cache.get_verdict(target_claim)
    if cached_result:
        state = DebateState.parse_obj(cached_result)
        state.is_cached = True
        return state
```

---

## FIX 4-C
**File:** `src/orchestration/debate.py`
**Function:** `_consensus_check_node()`
**Lines:** The `response.verdict != "DEBATE"` skip-debate path

**Problem:** When consensus check returns TRUE/FALSE with confidence > 0.9, it sets `state.verdict` and skips to Moderator directly. BUT it leaves `state.pro_arguments = []` and `state.con_arguments = []` empty. Then in `app.py`, `render_debate()` does `rounds = min(len(pros), len(cons))` which is 0 — the debate log tab shows nothing. The UI looks broken even though the answer is correct.

**What to change:**

In `_consensus_check_node()`, after setting `state.verdict`, add synthetic arguments so the UI has something to display:
```python
if response.verdict != "DEBATE" and response.confidence > 0.9:
    state.verdict = response.verdict
    state.confidence = response.confidence
    state.moderator_reasoning = f"Consensus Pre-Check: {response.reasoning}"
    # Add synthetic arguments so UI debate log isn't empty
    state.pro_arguments = [f"[Consensus settled — no debate needed] {response.reasoning}"]
    state.con_arguments = [f"[Consensus settled — verdict: {response.verdict} with {response.confidence:.0%} confidence]"]
    state.pro_sources = [[]]
    state.con_sources = [[]]
```

Same fix for the `SETTLED_TRUTHS` hardcoded path.

---

## FIX 4-D
**File:** `src/llm/client.py`
**Function:** `_call_gemini()`
**Lines:** The `else` branch (legacy Gemini mode)

**Problem:** When `self._gemini_mode` is not `"genai"` (i.e., legacy mode), the code does:
```python
if self._gemini_legacy is None:
    raise RuntimeError("Legacy Gemini client not initialized")
```
But `_gemini_legacy` is initialized lazily in `_get_gemini_client()` — but `_get_gemini_client()` only initializes the `genai` mode. The legacy mode path (`self._gemini_legacy`) is NEVER initialized anywhere in the current code. The `__init__()` sets `self._gemini_legacy = None` and nothing ever changes it. So the legacy path always raises RuntimeError.

**What to change:**

In `_call_gemini()`, replace the entire `else` branch:
```python
else:
    # Legacy fallback: initialize on demand
    try:
        import google.generativeai as genai_legacy
        self._gemini_legacy = genai_legacy
    except ImportError:
        raise RuntimeError("google-generativeai not installed")
    
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

## FIX 4-E
**File:** `src/orchestration/debate.py` 
**Duplicate code cleanup**

**Problem:** `_verification_gate_node()` is defined in the class but is NEVER added to the graph. The graph uses `_should_continue` as a conditional edge from `con_agent` that goes directly to either `pro_agent` (continue) or `fact_checker` (end). The `verification_gate` node from the comment `# Insert mid-debate verification gate after ConAgent` was replaced with inline logic inside `_should_continue`. The class still has the method but it's dead code called by no one.

The mid-round URL checking now happens only in `_summarize_node` (indirectly) and `_should_retry`. The original design intent was to check sources after EACH round, not just at the end. The current implementation only checks sources once at the end via `_fact_checker_node`.

**What to change:**

Either:
- Keep `_verification_gate_node()` and add it back into the graph:
  - Add `workflow.add_node("verification_gate", self._verification_gate_node)` in `_build_graph()`
  - Change the `con_agent` conditional edge to go through `verification_gate` first
  
OR (simpler for now):
- Delete `_verification_gate_node()` from the class since it's dead code and confusing.

**Recommended:** Delete it. The FactChecker at the end already catches all hallucinations. Mid-round verification adds latency without major accuracy gain and the current routing doesn't use it.

---

# FILE-BY-FILE SUMMARY

## Quick reference — what changes in each file

| File | Session | Fixes |
|------|---------|-------|
| `src/utils/api_key_manager.py` | 1-A, 2-B | No crash on bad key, shorter backoff, auto-recovery |
| `src/orchestration/debate.py` | 1-B, 1-G, 3-A, 3-C, 3-D, 3-E, 4-A, 4-C, 4-E | FactChecker exception, Tavily timeout, bad Gemini check, source cap alignment, MemorySaver, better error messages, consensus UI fix, dead code removal |
| `src/orchestration/cache.py` | 1-C, 2-D | No permanent disable, numpy index for O(1) search |
| `src/orchestration/bounded_cache.py` | 3-B | **CREATE THIS FILE** — it doesn't exist |
| `src/agents/fact_checker.py` | 1-D, 1-E | Singleton thread pool, HTTP size cap |
| `src/async_tasks/task_queue.py` | 1-F | Task pruning, atexit shutdown |
| `src/core/models.py` | 2-A | ModeratorVerdict normaliser validator |
| `src/utils/validation.py` | 2-E | Align lengths, unicode safety, word check |
| `src/utils/claim_decomposer.py` | 4-B | Change provider, move after cache check |
| `src/llm/client.py` | 4-D | Fix legacy Gemini path |
| `app.py` | 3-E, 3-F | reset_all_keys on session start, error state write |

---

# DO THIS ORDER — EXACTLY

```
SESSION 1 (90 min) — do all of these before running the app again:
  1-A  api_key_manager.py     — no crash on bad key
  1-B  debate.py              — FactChecker exception safe exit
  1-C  cache.py               — no permanent cache disable
  1-D  fact_checker.py        — singleton thread pool
  1-E  fact_checker.py        — 50KB HTTP cap
  1-F  task_queue.py          — task pruning + atexit
  1-G  debate.py              — Tavily timeout + delete dangling line

SESSION 2 (90 min):
  2-A  models.py              — ModeratorVerdict validator
  2-B  api_key_manager.py     — 5min max backoff + auto-recover
  2-D  cache.py               — numpy index rebuild
  2-E  validation.py          — align limits, unicode safety

SESSION 3 (60 min):
  3-A  debate.py              — delete bad Gemini key check in gate
  3-B  bounded_cache.py       — CREATE THE FILE
  3-C  debate.py              — cap sources in sync with arguments
  3-D  debate.py              — MemorySaver instead of SqliteSaver
  3-E  app.py                 — reset_all_keys on session start
  3-F  app.py                 — error state write fix

SESSION 4 (60 min):
  4-A  debate.py              — better error classification
  4-B  claim_decomposer.py    — move after cache, use groq
  4-C  debate.py              — consensus UI fix (synthetic args)
  4-D  client.py              — fix legacy Gemini path
  4-E  debate.py              — delete dead _verification_gate_node
```

**After Session 1:** App no longer crashes on any API failure.
**After Session 2:** App degrades gracefully, verdict always renders correctly.
**After Session 3:** All orphaned code is either wired or removed.
**After Session 4:** Production-ready for real concurrent users.
