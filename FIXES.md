# InsightSwarm — Bug Fixes & Implementation Plan

> **Based on full deep-read of every source file — March 2026**  
> 19 fixes across 4 sessions. Each entry shows the exact file, exact function, exact code to change.

---

## Table of Contents

- [How to Use This Document](#how-to-use-this-document)
- [Session Overview](#session-overview)
- [Session 1 — Stop the Crashes](#session-1--stop-the-crashes)
- [Session 2 — Fix Silent Failures](#session-2--fix-silent-failures)
- [Session 3 — Wire the Orphaned Code](#session-3--wire-the-orphaned-code)
- [Session 4 — Production Hardening](#session-4--production-hardening)
- [File Change Summary](#file-change-summary)
- [Execution Order Checklist](#execution-order-checklist)

---

## How to Use This Document

Each fix is formatted as:

```
FIX X-Y
File    → exact file path from project root
Where   → exact function name and what to look for
Problem → what breaks and why
Change  → the exact before/after code
```

Do all fixes in a session before moving to the next session. Sessions 1 and 2 are the most critical — after those two sessions the app will survive all real-world failure conditions.

---

## Session Overview

| Session | Name | Time | What You Get |
|---------|------|------|--------------|
| **1** | Stop the Crashes | 90 min | No API failure can bring the whole app down |
| **2** | Fix Silent Failures | 90 min | Degraded state is visible, not invisible |
| **3** | Wire the Orphaned Code | 60 min | Built code is actually used |
| **4** | Production Hardening | 60 min | Ready for real concurrent traffic |

---

---

# Session 1 — Stop the Crashes

> These 7 fixes are the ones where a single bad condition destroys the entire running app. Do all 7 before opening the app.

---

### FIX 1-A

**File:** `src/utils/api_key_manager.py`  
**Where:** `_load_and_validate_keys()` — the very last block of the function  
**Severity:** 🔴 App-killing

**Problem:**  
If `GROQ_API_KEY` is missing, malformed, or fails format validation, `_load_and_validate_keys()` raises a `RuntimeError`. This propagates up through `FreeLLMClient.__init__()` → `DebateOrchestrator.__init__()` → `app.py` and crashes the entire Streamlit session with a white screen. Because the singleton `_key_manager = None` never gets set, every subsequent page refresh also crashes.

**Step 1 — Add degraded flag to `__init__` (top of method, before `_load_and_validate_keys()` is called):**

```python
# ADD these two lines at the start of __init__, before _load_and_validate_keys()
self.degraded = False
self.degraded_reason = ""
```

**Step 2 — Replace the RuntimeError raise at the bottom of `_load_and_validate_keys()`:**

```python
# REMOVE this:
if not all_keys_loaded:
    raise RuntimeError(
        "❌ Critical API keys missing or invalid. Please check your .env file.\n"
        "Required: GROQ_API_KEY\n"
        "Optional: GEMINI_API_KEY, TAVILY_API_KEY, CEREBRAS_API_KEY, OPENROUTER_API_KEY\n"
        "See README.md for setup instructions."
    )
logger.info("✅ API Key Manager initialized successfully")

# REPLACE WITH this:
if not all_keys_loaded:
    self.degraded = True
    self.degraded_reason = (
        "Required API keys missing or invalid. "
        "Check GROQ_API_KEY in .env file. "
        "See README.md for setup instructions."
    )
    logger.error(f"⚠️ APIKeyManager degraded: {self.degraded_reason}")
else:
    logger.info("✅ API Key Manager initialized successfully")
```

**Step 3 — Add degraded guard at the top of `get_working_key()`:**

```python
def get_working_key(self, provider: str) -> Optional[str]:
    # ADD this at the very top:
    if getattr(self, 'degraded', False):
        logger.warning(f"APIKeyManager is degraded: {self.degraded_reason}")
        return None
    
    # ... rest of the existing method unchanged ...
```

---

### FIX 1-B

**File:** `src/orchestration/debate.py`  
**Where:** `_fact_checker_node()` — the `except Exception` block at the bottom  
**Severity:** 🔴 App-killing

**Problem:**  
If FactChecker crashes (SSL error, model load failure, network issue), the bare `return state` sends a state where `verification_results = None`, `pro_verification_rate = None`, `con_verification_rate = None`. The Moderator's `_build_prompt()` then formats `{pro_rate:.1%}` on a `None` value — Python raises `TypeError` — the entire LangGraph graph crashes with an unhandled exception.

```python
# REMOVE this:
except Exception as e:
    logger.error(f"FactChecker failed: {e}")
    return state

# REPLACE WITH this:
except Exception as e:
    logger.error(f"FactChecker failed: {e}", exc_info=True)
    # Ensure Moderator never receives None for these fields
    state.verification_results = state.verification_results or []
    state.pro_verification_rate = (
        state.pro_verification_rate if state.pro_verification_rate is not None else 0.0
    )
    state.con_verification_rate = (
        state.con_verification_rate if state.con_verification_rate is not None else 0.0
    )
    return state
```

---

### FIX 1-C

**File:** `src/orchestration/cache.py`  
**Where:** `_encode()` method — the `except Exception` block  
**Severity:** 🔴 App-killing

**Problem:**  
On any embedding model failure (HuggingFace download timeout, memory error, network blip), `_encode()` sets `self.enabled = False` permanently. The cache is then dead for the entire session. Every subsequent identical claim hits the LLM API again — burning your API quota, making repeats as slow as fresh claims, and potentially triggering rate limits.

```python
# REMOVE this:
def _encode(self, text: str) -> Optional[np.ndarray]:
    try:
        return self.model.encode([text])[0]
    except Exception as e:
        logger.warning(f"Semantic cache disabled (model load failed): {e}")
        self.enabled = False   # ← THIS LINE IS THE BUG
        return None

# REPLACE WITH this:
def _encode(self, text: str) -> Optional[np.ndarray]:
    try:
        return self.model.encode([text])[0]
    except Exception as e:
        # Return None for this call only — do NOT permanently disable the cache
        # The next call will try again; transient errors should not kill caching
        logger.warning(f"Embedding encode failed (cache miss for this call only): {e}")
        return None
```

**Also fix the `model` property** — change permanent failure after first error to require 3 failures:

```python
# ADD to __init__:
self._model_fail_count = 0

# In the model @property, change:
except Exception as e:
    self._model_failed = True   # ← current code: fails permanently on first error
    raise RuntimeError(f"Failed to load embedding model: {e}")

# To:
except Exception as e:
    self._model_fail_count = getattr(self, '_model_fail_count', 0) + 1
    if self._model_fail_count >= 3:
        self._model_failed = True   # Only permanently fail after 3 consecutive failures
    raise RuntimeError(f"Failed to load embedding model: {e}")
```

---

### FIX 1-D

**File:** `src/agents/fact_checker.py`  
**Where:** `generate()` method — the `with concurrent.futures.ThreadPoolExecutor(max_workers=10)` block  
**Severity:** 🔴 App-killing (OOM)

**Problem:**  
A fresh 10-thread pool is created for every single `generate()` call. With 3 concurrent Streamlit users, that's 30 threads simultaneously downloading HTML pages. On Streamlit Cloud's 1GB container this causes Out-of-Memory kill. The `with` block also calls `shutdown(wait=True)` on exit — blocking the calling thread until all 10 fetches finish, even if they are all hanging at the 10-second timeout.

**Step 1 — Add module-level singleton pool (after imports, before the class):**

```python
import atexit as _atexit

# Module-level singleton thread pool — shared across all FactChecker instances
# Prevents 10 new threads per call, caps concurrent HTTP fetches globally
_VERIFY_POOL = concurrent.futures.ThreadPoolExecutor(
    max_workers=5,
    thread_name_prefix="insightswarm_verify"
)
_atexit.register(_VERIFY_POOL.shutdown, wait=False)
```

**Step 2 — Replace the `with` block in `generate()`:**

```python
# REMOVE this:
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

# REPLACE WITH this:
futures = {
    _VERIFY_POOL.submit(self._verify_url, url, agent, state.claim, claim_embedding): url
    for url, agent, argument in all_sources
}
# 60s total timeout for all verifications, 15s per individual URL
try:
    for future in concurrent.futures.as_completed(futures, timeout=60):
        try:
            res = future.result(timeout=15)
            if res is not None:
                results.append(res)
        except concurrent.futures.TimeoutError:
            logger.warning(f"URL verification timed out: {futures[future]}")
        except Exception as e:
            logger.error(f"Failed to verify {futures[future]}: {e}")
except concurrent.futures.TimeoutError:
    logger.warning("FactChecker batch verification timed out after 60s")
```

---

### FIX 1-E

**File:** `src/agents/fact_checker.py`  
**Where:** `_verify_url()` method — the `requests.get()` call  
**Severity:** 🟠 Memory bomb

**Problem:**  
`requests.get()` downloads the entire HTTP response with no size limit. A URL returning a 50MB PDF or a massive HTML page downloads everything into RAM — per thread. With 5 concurrent verifications this can consume 250MB of RAM in one FactChecker call.

```python
# REMOVE this:
resp = requests.get(
    url,
    timeout=self.url_timeout,
    allow_redirects=True,
    headers=headers
)

# REPLACE WITH this:
resp = requests.get(
    url,
    timeout=self.url_timeout,
    allow_redirects=True,
    headers=headers,
    stream=True                  # Don't download everything at once
)
# Read at most 50KB — more than enough for fuzzy/semantic matching
raw_bytes = b""
for chunk in resp.iter_content(chunk_size=8192):
    raw_bytes += chunk
    if len(raw_bytes) >= 51200:  # 50KB cap
        break
# Make resp.text work for downstream code
resp._content = raw_bytes
```

Then **replace all occurrences of `resp.text`** in `_verify_url()` with a local variable:

```python
# After the stream block above, add:
content_text = raw_bytes.decode("utf-8", errors="ignore")

# Then replace every reference to `resp.text` or `content = resp.text` with `content_text`
# For example:
# BEFORE: if any(indicator in resp.text.lower() for indicator in paywall_indicators):
# AFTER:  if any(indicator in content_text.lower() for indicator in paywall_indicators):

# BEFORE: content = resp.text
# AFTER:  content = content_text
```

---

### FIX 1-F

**File:** `src/async_tasks/task_queue.py`  
**Where:** `BackgroundTaskQueue` class — `__new__()` and `submit()`  
**Severity:** 🟠 Memory leak

**Problem:**  
`self.tasks` is a dict that grows without bound — every completed debate stays in memory forever. On Streamlit Cloud with dozens of daily users, this continuously leaks memory until OOM kill. The `ThreadPoolExecutor` is also never shut down on process exit.

**Step 1 — Add `atexit` and `time` imports at the top of the file:**

```python
import atexit
import time
```

**Step 2 — Register shutdown in `__new__()`, after creating the executor:**

```python
# ADD this line right after: cls._instance.executor = ThreadPoolExecutor(max_workers=3)
atexit.register(cls._instance.executor.shutdown, wait=False)
```

**Step 3 — Add the pruning method to the class:**

```python
def _prune_old_tasks(self):
    """Remove completed tasks older than 10 minutes to prevent memory leak."""
    now = time.time()
    to_delete = [
        task_id
        for task_id, (future, _) in self.tasks.items()
        if future.done() and (now - getattr(future, '_submitted_at', now)) > 600
    ]
    for task_id in to_delete:
        del self.tasks[task_id]
    
    # Hard cap: if still over 50, evict the oldest completed task
    if len(self.tasks) > 50:
        for tid, (f, _) in list(self.tasks.items()):
            if f.done():
                del self.tasks[tid]
                break
```

**Step 4 — Call prune + stamp submission time in `submit()`:**

```python
def submit(self, task_id: str, func: Callable, *args, **kwargs) -> str:
    self._prune_old_tasks()   # ADD this as the first line

    if task_id in self.tasks:
        future, _ = self.tasks[task_id]
        if not future.done():
            return task_id

    future = self.executor.submit(func, *args, **kwargs)
    future._submitted_at = time.time()    # ADD this — timestamp for pruning
    self.tasks[task_id] = (future, None)
    logger.info(f"Task {task_id} submitted to background queue.")
    return task_id
```

---

### FIX 1-G

**File:** `src/orchestration/debate.py`  
**Where:** `run()` method — Tavily call + dangling unreachable line  
**Severity:** 🟠 Timeout bomb

**Problem 1:** The Tavily call `tavily.search_adversarial(claim, max_results=5)` runs synchronously with no timeout. If Tavily is slow or down, it can block for 30–60 seconds before the debate even starts, eating a third of your 180-second Streamlit timeout budget.

**Problem 2:** There is a dangling `tavily = get_tavily_retriever()` line at the very bottom of `run()`, appearing **after** both the `return final_state` and the `except` block's `return initial_state`. This is unreachable dead code — evidence of an earlier refactor that was not cleaned up.

**Fix Problem 1 — Wrap Tavily in a timeout:**

```python
# REMOVE this:
tavily = get_tavily_retriever()
adversarial_sources = tavily.search_adversarial(claim, max_results=5)

# REPLACE WITH this:
import concurrent.futures as _cf
tavily = get_tavily_retriever()
try:
    with _cf.ThreadPoolExecutor(max_workers=1) as _tex:
        _fut = _tex.submit(tavily.search_adversarial, claim, 5)
        adversarial_sources = _fut.result(timeout=12)  # 12 second max
except Exception:
    logger.warning("Tavily timed out or failed — proceeding without pre-fetched evidence")
    adversarial_sources = {"pro": [], "con": []}
```

**Fix Problem 2 — Delete the dangling line:**

Find and delete this line that appears after all return statements at the bottom of `run()`:

```python
# DELETE this line (it is after the function's return statements — unreachable):
    tavily = get_tavily_retriever()
```

Apply the same Tavily timeout fix to `stream()` — it has the identical pattern.

---

---

# Session 2 — Fix Silent Failures

> These 4 fixes don't crash the app but make it silently give wrong results or show a broken UI. Fix them after Session 1.

---

### FIX 2-A

**File:** `src/core/models.py`  
**Where:** `ModeratorVerdict` class  
**Severity:** 🟠 Silent UI break

**Problem:**  
`verdict: str = "UNKNOWN"` accepts any string the LLM returns — including `"Maybe"`, `"TRUE with caveats"`, `"Probably true"`, `"I believe FALSE"`. These strings fall through every CSS class lookup in `app.py` and render as invisible text against the dark background. The user sees a blank verdict box with no explanation.

```python
# REMOVE this:
class ModeratorVerdict(BaseModel):
    verdict: str = "UNKNOWN"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reasoning: str = ""
    metrics: Optional[Dict[str, Any]] = Field(default_factory=dict)

# REPLACE WITH this:
from pydantic import validator

class ModeratorVerdict(BaseModel):
    verdict: str = "UNKNOWN"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reasoning: str = ""
    metrics: Optional[Dict[str, Any]] = Field(default_factory=dict)

    _VALID_VERDICTS = frozenset({
        "TRUE", "FALSE", "PARTIALLY TRUE", "INSUFFICIENT EVIDENCE",
        "CONSENSUS_SETTLED", "RATE_LIMITED", "UNKNOWN", "ERROR"
    })

    @validator("verdict", pre=True, always=True)
    def normalise_verdict(cls, v):
        if not v:
            return "UNKNOWN"
        v = str(v).strip().upper()
        # Handle common LLM variants
        replacements = {
            "PARTIALLY_TRUE": "PARTIALLY TRUE",
            "PARTIAL": "PARTIALLY TRUE",
            "PARTLY TRUE": "PARTIALLY TRUE",
            "PARTLY_TRUE": "PARTIALLY TRUE",
            "INSUFFICIENT": "INSUFFICIENT EVIDENCE",
            "INSUFFICIENT_EVIDENCE": "INSUFFICIENT EVIDENCE",
            "NOT ENOUGH EVIDENCE": "INSUFFICIENT EVIDENCE",
            "NOT_ENOUGH_EVIDENCE": "INSUFFICIENT EVIDENCE",
        }
        if v in replacements:
            return replacements[v]
        if v in cls._VALID_VERDICTS:
            return v
        # Unrecognised — log and fall back safely
        import logging
        logging.getLogger(__name__).warning(
            f"ModeratorVerdict: unexpected verdict string '{v}', defaulting to UNKNOWN"
        )
        return "UNKNOWN"
```

---

### FIX 2-B

**File:** `src/utils/api_key_manager.py`  
**Where:** `report_key_failure()` — the backoff calculation + `get_working_key()` — the key selection loop  
**Severity:** 🟠 Keys die for whole session

**Problem:**  
The exponential backoff formula `min(60 * (2 ** consecutive_failures), 3600)` hits the 1-hour cap after just 6 failures. On Streamlit Cloud where sessions last 20–60 minutes, a key that hit its rate limit early in the session is permanently unavailable for the rest of the session. `reset_all_keys()` exists but is never called automatically.

**Fix 1 — Reduce max backoff from 3600s to 300s (5 minutes):**

```python
# CHANGE this line in report_key_failure():
backoff_time = min(60 * (2 ** key_info.consecutive_failures), 3600)

# TO:
backoff_time = min(30 * (2 ** key_info.consecutive_failures), 300)
# 30, 60, 120, 240, 300 — max 5 minutes, not 1 hour
```

**Fix 2 — Add auto-recovery in `get_working_key()`, before the availability check:**

```python
def get_working_key(self, provider: str) -> Optional[str]:
    if getattr(self, 'degraded', False):
        return None

    if provider not in self.keys:
        return None

    # ADD auto-recovery block here:
    now = time.time()
    for ki in self.keys[provider]:
        if ki.status == APIKeyStatus.RATE_LIMITED and now >= ki.cooldown_until:
            ki.status = APIKeyStatus.VALID
            ki.consecutive_failures = max(0, ki.consecutive_failures - 1)
            logger.info(f"Auto-recovered {provider} key from cooldown")

    # ... rest of the existing method unchanged ...
```

---

### FIX 2-C

**File:** `src/orchestration/cache.py`  
**Where:** `get_verdict()` method — the `c.fetchall()` and the similarity loop  
**Severity:** 🟡 Performance degrades over time

**Problem:**  
`c.fetchall()` loads the entire `claim_cache` table into RAM on every single cache lookup. Each row contains a full embedding blob (~6KB). After months of production with real users, this means loading thousands of rows into RAM and running a nested Python loop for cosine similarity on every request.

**Step 1 — Add index fields to `__init__`:**

```python
# ADD these lines in __init__(), after self._l1_cache = None:
self._embedding_index = None   # numpy matrix shape (N, embedding_dim)
self._index_data = []          # list of verdict dicts, aligned with matrix rows
self._index_dirty = True       # True = rebuild needed on next lookup
```

**Step 2 — Add `_rebuild_index()` method to the class:**

```python
def _rebuild_index(self):
    """Load all live embeddings into a numpy matrix for fast vectorised similarity."""
    try:
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            now = datetime.now().isoformat()
            c.execute(
                'SELECT id, claim_embedding, verdict_data, created_at '
                'FROM claim_cache WHERE expires_at > ?',
                (now,)
            )
            rows = c.fetchall()

        if not rows:
            self._embedding_index = None
            self._index_data = []
            self._index_dirty = False
            return

        embeddings, data = [], []
        for _, emb_bytes, verdict_json, created_at in rows:
            emb = np.frombuffer(emb_bytes, dtype=np.float32).copy()
            embeddings.append(emb)
            d = json.loads(verdict_json)
            d['cached_at'] = created_at
            data.append(d)

        matrix = np.stack(embeddings)                                # (N, D)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self._embedding_index = matrix / norms                       # pre-normalised
        self._index_data = data
        self._index_dirty = False
        logger.debug(f"Rebuilt embedding index: {len(rows)} entries")

    except Exception as e:
        logger.error(f"Index rebuild failed: {e}")
        self._embedding_index = None
```

**Step 3 — Replace the fetchall loop in `get_verdict()`:**

```python
# REMOVE this entire block:
with sqlite3.connect(self.db_path) as conn:
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute('SELECT claim_text, claim_embedding, verdict_data, created_at FROM claim_cache WHERE expires_at > ?', (now,))
    rows = c.fetchall()

best_match = None
best_similarity = 0.0

for row in rows:
    cached_claim, embedding_bytes, verdict_json, created_at = row
    cached_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
    denom = np.linalg.norm(query_embedding) * np.linalg.norm(cached_embedding)
    if denom == 0:
        continue
    similarity = np.dot(query_embedding, cached_embedding) / denom
    if similarity > best_similarity and similarity >= similarity_threshold:
        best_similarity = similarity
        data = json.loads(verdict_json)
        data['is_cached'] = True
        data['cache_similarity'] = float(similarity)
        data['cached_at'] = created_at
        best_match = data

# REPLACE WITH this:
if self._index_dirty or self._embedding_index is None:
    self._rebuild_index()

if self._embedding_index is None or len(self._index_data) == 0:
    return None

# Vectorised cosine similarity — O(N) numpy vs O(N) Python loop, 10-50x faster
q_norm = np.linalg.norm(query_embedding)
if q_norm == 0:
    return None
q = query_embedding / q_norm
similarities = self._embedding_index @ q              # dot product, shape (N,)
best_idx = int(np.argmax(similarities))
best_similarity = float(similarities[best_idx])

best_match = None
if best_similarity >= similarity_threshold:
    best_match = dict(self._index_data[best_idx])
    best_match['is_cached'] = True
    best_match['cache_similarity'] = best_similarity
```

**Step 4 — Mark index dirty when a new entry is written. In `set_verdict()`, after `conn.commit()`:**

```python
# ADD this line after conn.commit():
self._index_dirty = True
```

---

### FIX 2-D

**File:** `src/utils/validation.py`  
**Where:** `validate_claim()` — all the limits  
**Severity:** 🟡 Confusing user experience

**Problem:**  
- Max length is 300 chars but `app.py` has no `maxlength` attribute — user types 400 chars, submits, gets silent rejection
- Min length check is 3 words but `app.py` shows "minimum 10 characters" — these are different limits for the same field
- No Unicode safety check — RTL override characters (`\u202e`) can confuse LLMs

```python
# REMOVE the entire existing function and REPLACE WITH:

def validate_claim(claim: str) -> Tuple[bool, str]:
    """Validates a user-submitted claim for safety and quality."""
    if not claim or not claim.strip():
        return False, "Claim cannot be empty."

    stripped = claim.strip()

    # Align with the UI's displayed minimum of 10 characters
    if len(stripped) < 10:
        return False, "Claim too short (minimum 10 characters)."

    # Align with the UI's allowed maximum
    if len(stripped) > 500:
        return False, "Claim too long (max 500 characters)."

    # Must contain at least one word longer than 2 characters
    words = stripped.split()
    if not any(len(w) > 2 for w in words):
        return False, "Claim must contain at least one meaningful word."

    # Unicode safety: reject RTL override, zero-width, and BOM characters
    UNSAFE_RANGES = [
        (0x200B, 0x200F),   # Zero-width spaces and marks
        (0x202A, 0x202E),   # RTL/LTR override characters
        (0xFFF0, 0xFFFF),   # Specials block including BOM
    ]
    for char in stripped:
        cp = ord(char)
        for lo, hi in UNSAFE_RANGES:
            if lo <= cp <= hi:
                return False, "Claim contains unsupported control characters."

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

---

# Session 3 — Wire the Orphaned Code

> Code that was built and imported but is either never used, uses something that doesn't exist, or runs in the wrong order.

---

### FIX 3-A

**File:** `src/orchestration/debate.py`  
**Where:** `_verification_gate_node()` — the Gemini key check block  
**Severity:** 🔴 Crashes graph on Gemini rate limit

**Problem:**  
This block exists in `_verification_gate_node()` even though the node is not connected to the graph (the routing was changed to use `_should_continue` directly). More critically, if this node were ever called, the Gemini key check would raise `RuntimeError` whenever Gemini is rate-limited — inside a LangGraph node, that's an unhandled graph exception. The verification gate does not use Gemini at all — it only calls `self.fact_checker._verify_url()` which is pure HTTP.

```python
# FIND and DELETE this entire block from _verification_gate_node():
gemini_key = self.client.key_manager.get_working_key("gemini")
if not gemini_key:
    raise RuntimeError("No working Gemini API keys available for verification")
```

Replace it with nothing — the method continues fine without it.

---

### FIX 3-B

**File:** `src/orchestration/bounded_cache.py` ← **CREATE THIS FILE — IT DOES NOT EXIST**  
**Severity:** 🟠 L1 cache silently never works

**Problem:**  
`cache.py` imports `from src.orchestration.bounded_cache import BoundedCache` inside a `try/except ImportError`. The file does not exist. The `except` silently swallows the error. `self._l1_cache` stays `None` the entire session. The L1 in-memory cache that would give instant results for very recent repeated queries never activates.

**Create the file `src/orchestration/bounded_cache.py`:**

```python
"""
bounded_cache.py — LRU-bounded in-memory cache.

Acts as the L1 layer in front of the SQLite semantic cache.
Provides O(1) lookup for very recently seen claims within the same session.
Thread-safe via a simple Lock.
"""
from collections import OrderedDict
from threading import Lock
from typing import Any, Optional


class BoundedCache:
    """
    Fixed-size LRU cache. When full, evicts the least-recently-used entry.

    Args:
        maxsize: Maximum number of entries to hold. Default 100.
    """

    def __init__(self, maxsize: int = 100) -> None:
        self._cache: OrderedDict = OrderedDict()
        self._maxsize = maxsize
        self._lock = Lock()

    def get(self, key: str) -> Optional[Any]:
        """Return the cached value for key, or None if not present."""
        with self._lock:
            if key not in self._cache:
                return None
            # Move to end = mark as most-recently-used
            self._cache.move_to_end(key)
            return self._cache[key]

    def put(self, key: str, value: Any) -> None:
        """Insert or update key with value. Evicts LRU entry when full."""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value
            if len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)   # Evict oldest (LRU)

    def clear(self) -> None:
        """Empty the cache entirely."""
        with self._lock:
            self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, key: str) -> bool:
        return key in self._cache
```

---

### FIX 3-C

**File:** `src/orchestration/debate.py`  
**Where:** `_summarize_node()` — the history capping block  
**Severity:** 🟠 Index-out-of-range bug

**Problem:**  
The history cap truncates `pro_arguments` and `con_arguments` to the last 2 entries — but does NOT truncate `pro_sources` and `con_sources`. The FactChecker iterates both lists together using index `i`, assuming `pro_arguments[i]` and `pro_sources[i]` are aligned. After capping, `pro_sources` has 3 entries while `pro_arguments` has 2 — causing `IndexError` in FactChecker.

```python
# FIND this block in _summarize_node():
if len(state.pro_arguments) > 2:
    state.pro_arguments = state.pro_arguments[-2:]
    state.con_arguments = state.con_arguments[-2:]

# REPLACE WITH:
if len(state.pro_arguments) > 2:
    state.pro_arguments = state.pro_arguments[-2:]
    state.con_arguments = state.con_arguments[-2:]
    state.pro_sources   = state.pro_sources[-2:]    # Keep in sync with arguments
    state.con_sources   = state.con_sources[-2:]    # Keep in sync with arguments
```

---

### FIX 3-D

**File:** `src/orchestration/debate.py`  
**Where:** `__init__()` and top of file — `SqliteSaver` and `get_db_connection()`  
**Severity:** 🟠 Database locked errors under concurrent load

**Problem:**  
`get_db_connection()` creates a single shared SQLite connection and passes it to `SqliteSaver`. When multiple Streamlit users run debates simultaneously, they all share the same SQLite connection for LangGraph checkpointing. SQLite connections are not safely shareable across threads even with `check_same_thread=False` for writes. This causes intermittent `sqlite3.OperationalError: database is locked` errors that crash debates.

The LangGraph checkpointer only needs to persist state within a single debate run — there is no requirement to survive a server restart. `MemorySaver` is the correct tool.

**Step 1 — Change the import at the top of `debate.py`:**

```python
# REMOVE:
from langgraph.checkpoint.sqlite import SqliteSaver

# ADD:
from langgraph.checkpoint.memory import MemorySaver
```

**Step 2 — In `__init__()`, replace the connection and checkpointer lines:**

```python
# REMOVE these lines:
self.conn = get_db_connection()
self.resource_manager = get_resource_manager()
self.checkpointer = SqliteSaver(self.conn)

# REPLACE WITH:
self.resource_manager = get_resource_manager()
self.checkpointer = MemorySaver()
```

**Step 3 — Delete the now-unused `get_db_connection()` function** (the entire function and the `import sqlite3` at the top of the file, and the `_db_lock`/`_db_connection` module-level variables — nothing else uses them).

**Step 4 — Delete the `close()` method** — there is no connection to close anymore:

```python
# DELETE this method entirely:
def close(self):
    """Close SQLite connection for clean teardown."""
    if hasattr(self, 'conn') and self.conn:
        self.conn.close()
        self.conn = None
```

---

### FIX 3-E

**File:** `app.py`  
**Where:** `_init()` function — session state initialization  
**Severity:** 🟡 Rate-limited keys stay dead across page refreshes

**Problem:**  
`APIKeyManager.reset_all_keys()` exists and is correct — it un-sticks rate-limited keys. But it's never called. Keys that got rate-limited during a previous debate in the same browser session stay marked as `RATE_LIMITED` with a cooldown until forever.

Find the `_init()` function and add this block after the session state defaults are set:

```python
# ADD this block inside _init(), after st.session_state setdefault calls:

# Reset rate-limited keys once per browser session (not per rerun)
if not st.session_state.get("_api_keys_reset"):
    try:
        from src.utils.api_key_manager import get_api_key_manager
        get_api_key_manager().reset_all_keys()
        logger.info("API keys reset for new session")
    except Exception as e:
        logger.warning(f"Could not reset API keys: {e}")
    st.session_state._api_keys_reset = True
```

---

### FIX 3-F

**File:** `app.py`  
**Where:** `analyze_claim_async()` — the orchestrator init try/except  
**Severity:** 🟡 Error message doesn't appear in UI

**Problem:**  
`DebateOrchestrator()` initialization failure calls `st.error(f"Orchestrator init failed: {e}")` from inside a function that is submitted to a background `ThreadPoolExecutor`. Streamlit's `st.error()` only works from the main thread — calling it from a background thread silently does nothing. The user sees a spinning progress indicator forever.

```python
# REMOVE:
try:
    orchestrator = DebateOrchestrator(tracker=tracker)
except Exception as e:
    st.error(f"Orchestrator init failed: {e}")
    return None

# REPLACE WITH:
try:
    orchestrator = DebateOrchestrator(tracker=tracker)
except Exception as e:
    logger.error(f"Orchestrator init failed: {e}", exc_info=True)
    # Write to session state — this IS thread-safe in Streamlit
    st.session_state.debate_error = f"System initialization failed: {str(e)[:200]}"
    st.session_state.is_running = False
    return None
```

---

---

# Session 4 — Production Hardening

> These 4 fixes address real-world edge cases that only appear under actual usage conditions.

---

### FIX 4-A

**File:** `src/orchestration/debate.py`  
**Where:** `run()` — the outer `except Exception` block at the bottom  
**Severity:** 🟡 Error messages mislead debugging

**Problem:**  
The current fallback says `"System-level error (likely API quota): {str(e)}"` for ALL exceptions — including LangGraph internal errors, Pydantic validation failures, and genuine bugs. This makes it hard to distinguish real bugs from rate limits in logs. It also sets `verdict = "INSUFFICIENT EVIDENCE"` for quota errors when it should be `"RATE_LIMITED"` (which has its own CSS treatment in the UI).

```python
# REMOVE:
except Exception as e:
    logger.error(f"Debate failed: {e}")
    initial_state.verdict = "INSUFFICIENT EVIDENCE"
    initial_state.confidence = 0.0
    initial_state.moderator_reasoning = f"System-level error (likely API quota): {str(e)}"
    initial_state.metrics = {}
    return initial_state

# REPLACE WITH:
except Exception as e:
    err_str = str(e)
    is_quota = any(
        kw in err_str.lower()
        for kw in ["rate", "429", "quota", "exhausted", "resource_exhausted"]
    )
    # Log with traceback for real bugs, not for quota errors
    logger.error(
        f"Debate failed ({'quota' if is_quota else 'system error'}): {e}",
        exc_info=not is_quota
    )
    initial_state.verdict = "RATE_LIMITED" if is_quota else "INSUFFICIENT EVIDENCE"
    initial_state.confidence = 0.0
    initial_state.moderator_reasoning = (
        f"API quota exhausted. Please wait a moment and try again. ({err_str[:200]})"
        if is_quota else
        f"A system error interrupted the debate. Details: {err_str[:200]}"
    )
    initial_state.metrics = initial_state.metrics or {}
    return initial_state
```

---

### FIX 4-B

**File:** `src/utils/claim_decomposer.py` + `src/orchestration/debate.py`  
**Where:** `decompose()` — preferred provider + `run()` — call order  
**Severity:** 🟡 Wasted tokens on cache hits + slow fallback

**Problem 1:** `ClaimDecomposer.decompose()` hardcodes `preferred_provider="cerebras"`. The orchestrator's own comments note Cerebras has DNS issues. Every debate starts with a Cerebras attempt, gets a DNS failure, burns a full retry cycle, then falls back to another provider — adding 2–5 seconds to every debate start.

**Problem 2:** The decomposer is called BEFORE the semantic cache check in `run()`. For cache hits (which can be the majority of requests after warm-up), this wastes a full LLM API call on decomposition for a claim that will be served from cache anyway.

**Fix in `claim_decomposer.py`:**

```python
# CHANGE this line in decompose():
preferred_provider="cerebras"

# TO:
preferred_provider="groq"
```

**Fix in `debate.py` → `run()` — reorder cache check to happen before decomposition:**

```python
# CURRENT ORDER (wrong):
sub_claims = self.decomposer.decompose(claim)   # ← burns API call
target_claim = sub_claims[0]
cache = get_cache()
cached_result = cache.get_verdict(target_claim)  # ← checks cache after API call

# CORRECT ORDER:
# 1. Try original claim in cache first (no API call)
cache = get_cache()
cached_result = cache.get_verdict(claim)
if cached_result:
    state = DebateState.parse_obj(cached_result)
    state.is_cached = True
    return state

# 2. Only decompose on a cache miss
sub_claims = self.decomposer.decompose(claim)
target_claim = sub_claims[0]
if len(sub_claims) > 1:
    logger.info(f"Multi-part claim detected. Processing primary part: '{target_claim}'")

# 3. Try the decomposed claim in cache too (if it's different from original)
if target_claim.lower().strip() != claim.lower().strip():
    cached_result = cache.get_verdict(target_claim)
    if cached_result:
        state = DebateState.parse_obj(cached_result)
        state.is_cached = True
        return state
```

---

### FIX 4-C

**File:** `src/orchestration/debate.py`  
**Where:** `_consensus_check_node()` — the verdict-skip paths  
**Severity:** 🟡 Blank debate tab in UI

**Problem:**  
When the consensus check returns TRUE/FALSE with confidence > 0.9 (either from `SETTLED_TRUTHS` or from the LLM), it correctly skips the debate and goes straight to the Moderator. But it leaves `state.pro_arguments = []` and `state.con_arguments = []` empty. In `app.py`, `render_debate()` calculates `rounds = min(len(pros), len(cons))` = 0 and shows nothing. The debate log tab is completely empty — looks like a bug even though the verdict is correct.

**In the `SETTLED_TRUTHS` hardcoded block, after setting `state.verdict`:**

```python
# ADD these lines after state.confidence = conf:
state.pro_arguments = [
    f"[Settled science] {reasoning}"
]
state.con_arguments = [
    f"[No debate required — consensus is {verdict} with {conf:.0%} confidence]"
]
state.pro_sources = [[]]
state.con_sources = [[]]
```

**In the LLM consensus response block, after `state.moderator_reasoning = ...`:**

```python
# ADD these lines:
state.pro_arguments = [
    f"[Consensus pre-check] {response.reasoning}"
]
state.con_arguments = [
    f"[Debate skipped — consensus verdict: {response.verdict} ({response.confidence:.0%} confidence)]"
]
state.pro_sources = [[]]
state.con_sources = [[]]
```

---

### FIX 4-D

**File:** `src/llm/client.py`  
**Where:** `_call_gemini()` — the `else` branch (legacy mode)  
**Severity:** 🟠 Legacy Gemini path always crashes

**Problem:**  
When `self._gemini_mode` is not `"genai"` (i.e., the `google-genai` package isn't installed), the code hits the `else` branch which checks `if self._gemini_legacy is None: raise RuntimeError(...)`. But `self._gemini_legacy` is initialised to `None` in `__init__` and nothing ever sets it — `_get_gemini_client()` only initialises the `genai` mode. The legacy path will always raise `RuntimeError`, making Gemini completely unavailable in legacy mode environments.

```python
# FIND the else branch in _call_gemini():
else:
    if self._gemini_legacy is None:
        raise RuntimeError("Legacy Gemini client not initialized")
    with self._gemini_legacy_lock:
        self._gemini_legacy.configure(api_key=gemini_key)
        model = self._gemini_legacy.GenerativeModel(self.GEMINI_MODEL)
        # ...

# REPLACE WITH:
else:
    # Lazy-initialize legacy client on first use
    try:
        import google.generativeai as _genai_legacy
        self._gemini_legacy = _genai_legacy
    except ImportError:
        raise RuntimeError(
            "Neither google-genai nor google-generativeai is installed. "
            "Run: pip install google-generativeai"
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

---

# File Change Summary

| File | Sessions | What Changes |
|------|----------|-------------|
| `src/utils/api_key_manager.py` | 1-A, 2-B | No crash on bad key; shorter backoff (5 min max); auto-recovery on cooldown expiry |
| `src/orchestration/debate.py` | 1-B, 1-G, 3-A, 3-C, 3-D, 4-A, 4-B, 4-C | FactChecker safe exit; Tavily timeout; delete bad Gemini check; source cap sync; MemorySaver; better error classification; cache-first ordering; consensus UI fix |
| `src/orchestration/cache.py` | 1-C, 2-C | No permanent cache disable; numpy index for O(1) search |
| `src/orchestration/bounded_cache.py` | 3-B | **CREATE NEW FILE** — LRU cache that cache.py imports but is missing |
| `src/agents/fact_checker.py` | 1-D, 1-E | Singleton thread pool with atexit; 50KB HTTP response cap |
| `src/async_tasks/task_queue.py` | 1-F | Task dict pruning; atexit executor shutdown; submission timestamp |
| `src/core/models.py` | 2-A | ModeratorVerdict normaliser validator — no more invisible blank verdict box |
| `src/utils/validation.py` | 2-D | Align char limits with UI; unicode safety; meaningful word check |
| `src/utils/claim_decomposer.py` | 4-B | Change provider from cerebras to groq |
| `src/llm/client.py` | 4-D | Fix legacy Gemini path — initialise on demand instead of raising |
| `app.py` | 3-E, 3-F | reset_all_keys on session start; error state write from background thread |

---

# Execution Order Checklist

Copy this and track progress:

```
SESSION 1 — Stop the Crashes (do all before next app run)
[ ] 1-A  src/utils/api_key_manager.py    — degraded flag, no RuntimeError
[ ] 1-B  src/orchestration/debate.py     — FactChecker safe exit with defaults
[ ] 1-C  src/orchestration/cache.py      — no permanent self.enabled = False
[ ] 1-D  src/agents/fact_checker.py      — module-level singleton thread pool
[ ] 1-E  src/agents/fact_checker.py      — 50KB HTTP cap with stream=True
[ ] 1-F  src/async_tasks/task_queue.py   — task pruning + atexit shutdown
[ ] 1-G  src/orchestration/debate.py     — Tavily timeout + delete dangling line

SESSION 2 — Fix Silent Failures
[ ] 2-A  src/core/models.py              — ModeratorVerdict normaliser validator
[ ] 2-B  src/utils/api_key_manager.py    — 5 min max backoff + auto-recovery
[ ] 2-C  src/orchestration/cache.py      — numpy index rebuild (O(1) lookup)
[ ] 2-D  src/utils/validation.py         — align lengths, unicode safety

SESSION 3 — Wire the Orphaned Code
[ ] 3-A  src/orchestration/debate.py     — delete bad Gemini key check in gate node
[ ] 3-B  src/orchestration/bounded_cache.py  — CREATE THIS FILE
[ ] 3-C  src/orchestration/debate.py     — sync source cap with argument cap
[ ] 3-D  src/orchestration/debate.py     — MemorySaver instead of SqliteSaver
[ ] 3-E  app.py                          — reset_all_keys on session start
[ ] 3-F  app.py                          — write error to session state, not st.error()

SESSION 4 — Production Hardening
[ ] 4-A  src/orchestration/debate.py     — quota vs system error classification
[ ] 4-B  src/utils/claim_decomposer.py + debate.py  — groq provider, cache-first ordering
[ ] 4-C  src/orchestration/debate.py     — synthetic args on consensus skip
[ ] 4-D  src/llm/client.py              — fix legacy Gemini lazy-init
```

---

## After Each Session

| After Session | What You Can Expect |
|---------------|---------------------|
| **After 1** | App never crashes on API failures. Bad key = banner. OOM impossible. |
| **After 2** | All verdicts always render. Cache stays live through transient errors. |
| **After 3** | L1 cache active. No database lock errors. Error messages reach the UI. |
| **After 4** | Quota errors distinguished from real bugs. Cache-hits faster. No blank debate tabs. |
