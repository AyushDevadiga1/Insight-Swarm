"""
src/llm/client.py — All batches applied. Final production version.
"""
from pydantic import BaseModel
from typing import Type, Any, Optional
import os, re, threading, logging, time, hashlib, json
from dotenv import load_dotenv

try:
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
    HAS_TENACITY = True
except ImportError:
    HAS_TENACITY = False
    def retry(*a, **k):
        def d(f): return f
        return d
    def stop_after_attempt(*a, **k): return None
    def wait_exponential(*a, **k):   return None
    def retry_if_exception(*a, **k): return None

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

load_dotenv()
logger = logging.getLogger(__name__)

# Module-level schema cache — generate schema JSON once per type, never per call
_SCHEMA_CACHE: dict = {}

def _get_schema_json(output_schema) -> str:
    key = id(output_schema)
    if key not in _SCHEMA_CACHE:
        _SCHEMA_CACHE[key] = json.dumps(output_schema.model_json_schema(), indent=2)
    return _SCHEMA_CACHE[key]

from src.utils.api_key_manager import get_api_key_manager
from src.resilience.circuit_breaker import CircuitBreaker

_PROVIDER_COOLDOWN_SECONDS = 90

_circuit_breakers = {
    "groq": CircuitBreaker("groq", failure_threshold=3, recovery_timeout=60.0),
    "gemini": CircuitBreaker("gemini", failure_threshold=3, recovery_timeout=60.0),
    "cerebras": CircuitBreaker("cerebras", failure_threshold=3, recovery_timeout=60.0),
    "openrouter": CircuitBreaker("openrouter", failure_threshold=3, recovery_timeout=60.0),
}


class RateLimitError(RuntimeError):
    def __init__(self, provider: str, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.provider    = provider
        self.retry_after = retry_after


class FreeLLMClient:
    # Accurate per-provider free-tier rate limits (requests per minute)
    # Previous code used a single MAX_CALLS_PER_MINUTE=60 which is 2-4x too high
    # for Groq (30/min) and Gemini (15/min) free tiers.
    PROVIDER_RATE_LIMITS = {
        "groq":       int(os.getenv("RATE_LIMIT_GROQ",       "28")),  # actual: 30 — buffer of 2
        "gemini":     int(os.getenv("RATE_LIMIT_GEMINI",     "13")),  # actual: 15 — buffer of 2
        "cerebras":   int(os.getenv("RATE_LIMIT_CEREBRAS",   "28")),  # actual: 30
        "openrouter": int(os.getenv("RATE_LIMIT_OPENROUTER", "18")),  # actual: 20
    }
    GROQ_MODEL       = os.getenv("GROQ_MODEL",        "llama-3.3-70b-versatile")
    GEMINI_MODEL     = os.getenv("GEMINI_MODEL",       "gemini-2.0-flash")
    CEREBRAS_MODEL   = os.getenv("CEREBRAS_MODEL",     "llama3.1-8b")
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL",   "meta-llama/llama-3.1-8b-instruct")

    def __init__(self):
        self.key_manager   = get_api_key_manager()
        self.groq_client   = None
        self.genai_client  = None
        self._genai_types  = None

        self._provider_cooldown: dict = {"groq":0.0,"gemini":0.0,"cerebras":0.0,"openrouter":0.0}
        self.groq_calls = self.gemini_calls = self.cerebras_calls = self.openrouter_calls = 0
        self.groq_last_call_times     = []
        self.gemini_last_call_times   = []
        self.cerebras_last_call_times = []
        self.openrouter_last_call_times = []
        self._counter_lock = threading.Lock()
        self.groq_error = self.gemini_error = self.cerebras_error = self.openrouter_error = None
        self._preferred_provider: Optional[str] = None
        self._init_providers()

    # ── Provider availability ─────────────────────────────────────────────────

    def _is_provider_available(self, provider: str) -> bool:
        if not _circuit_breakers[provider].is_allowed():
            return False
        if time.time() < self._provider_cooldown.get(provider, 0.0):
            return False
        return self.key_manager.has_working_keys(provider)

    def _set_provider_cooldown(self, provider: str, seconds: float = _PROVIDER_COOLDOWN_SECONDS) -> None:
        self._provider_cooldown[provider] = time.time() + seconds
        logger.warning("Provider %s cooling down for %.0fs", provider, seconds)

    def _init_providers(self):
        try:
            groq_key = self.key_manager.get_working_key("groq")
            if groq_key:
                from groq import Groq
                self.groq_client = Groq(api_key=groq_key)
                logger.info("Groq client initialised")
            else:
                self.groq_error = "No working Groq API keys available"
                logger.warning("Groq client not available")
        except Exception as e:
            self.groq_error = str(e)
            logger.warning("Groq init failed: %s", type(e).__name__)

        try:
            gemini_key = self.key_manager.get_working_key("gemini")
            if gemini_key:
                from google import genai
                from google.genai import types as genai_types
                self._genai_types = genai_types
                self.genai_client = genai.Client(api_key=gemini_key)
                logger.info("Gemini client initialised")
            else:
                self.gemini_error = "No working Gemini API keys available"
                logger.warning("Gemini client not available")
        except Exception as e:
            self.gemini_error = str(e)
            logger.warning("Gemini init failed: %s", type(e).__name__)

        for provider in ("cerebras", "openrouter"):
            try:
                if self.key_manager.get_working_key(provider):
                    logger.info("%s available", provider)
                else:
                    setattr(self, f"{provider}_error", f"No {provider} key")
            except Exception as e:
                setattr(self, f"{provider}_error", str(e))

        if not any(self.key_manager.has_working_keys(p) for p in ("groq","gemini","cerebras","openrouter")):
            offline = os.getenv("ENABLE_OFFLINE_FALLBACK","false").lower() in ("true","1","yes")
            if offline:
                logger.warning("No LLM providers — offline fallback mode.")
            else:
                raise RuntimeError("No LLM providers available. Check GROQ_API_KEY / GEMINI_API_KEY in .env.")

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _is_rate_limit_error(self, error: Exception) -> bool:
        text = str(error).lower()
        return any(kw in text for kw in ("rate limit","rate_limit","resource_exhausted","429","quota"))

    def _provider_order(self, preferred_provider: Optional[str] = None) -> list:
        order = ["groq","gemini","cerebras","openrouter"]
        pref  = preferred_provider or self._preferred_provider
        if pref and pref in order:
            order.remove(pref); order.insert(0, pref)
        return order

    def _extract_retry_after(self, message: str) -> Optional[float]:
        for pattern in (r"retry in\s*([0-9]+(?:\.[0-9]+)?)s", r"retrydelay':\s*'([0-9]+)s'"):
            m = re.search(pattern, message, re.IGNORECASE)
            if m:
                try: return float(m.group(1))
                except ValueError: pass
        return None

    def _check_rate_limit(self, provider: str, call_times: list) -> bool:
        """Returns False if provider is at its per-minute rate limit."""
        limit = self.PROVIDER_RATE_LIMITS.get(provider, 20)
        now   = time.time()
        recent = [t for t in call_times if t > now - 60]
        call_times.clear(); call_times.extend(recent)
        if len(call_times) >= limit:
            logger.warning(
                "Rate limit hit for %s: %d/%d calls/min",
                provider, len(call_times), limit
            )
            return False
        return True

    def _validate_prompt(self, prompt: str) -> None:
        if not prompt or not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt must be a non-empty string")
        if len(prompt) > 100_000:
            raise ValueError("Prompt exceeds 100 000-character limit")

    def _validate_response(self, response: str) -> None:
        if not response or not isinstance(response, str) or not response.strip():
            raise ValueError("LLM returned empty or invalid response")

    def _clean_json_response(self, response: str) -> str:
        if not response: return response
        response = response.strip()
        if "```" in response:
            m = re.search(r"```(?:json)?\s*(.*?)\s*```", response, re.DOTALL)
            if m: return m.group(1).strip()
        return response

    # ── call_structured ───────────────────────────────────────────────────────

    def call_structured(self, prompt: str, output_schema: Type[BaseModel],
                        temperature: float = 0.7, max_tokens: int = 1000,
                        max_retries: int = 2, preferred_provider: Optional[str] = None) -> Any:
        from pydantic import ValidationError as PydanticValidationError

        schema_json = _get_schema_json(output_schema)
        json_prompt = (
            f"{prompt}\n\nIMPORTANT: Return a valid JSON object matching this schema:\n{schema_json}"
        )
        last_error = None; attempted_any = False

        for provider in self._provider_order(preferred_provider):
            if not self._is_provider_available(provider): continue
            if not self.key_manager.has_working_keys(provider): continue
            attempted_any = True

            for attempt in range(max_retries + 1):
                key = self.key_manager.get_working_key(provider)
                if not key: break
                key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]

                try:
                    with self._counter_lock:
                        call_times = getattr(self, f"{provider}_last_call_times")
                        if not self._check_rate_limit(provider, call_times):
                            raise RuntimeError(f"{provider} rate limit exceeded")
                        call_times.append(time.time())

                    raw     = self._dispatch_call(provider, json_prompt, temperature, max_tokens, key)
                    cleaned = self._clean_json_response(raw)
                    result  = output_schema.model_validate_json(cleaned)
                    self.key_manager.report_key_success(provider, key_hash)
                    return result

                except PydanticValidationError as ve:
                    last_error = ve
                    logger.warning("%s parse error attempt %d/%d: %s", provider, attempt+1, max_retries+1, ve)
                    if attempt < max_retries: time.sleep(1)
                    continue

                except json.JSONDecodeError as je:
                    last_error = je
                    logger.warning("%s malformed JSON attempt %d/%d: %s", provider, attempt+1, max_retries+1, je)
                    if attempt < max_retries: time.sleep(1)
                    continue

                except Exception as e:
                    last_error = e
                    self.key_manager.report_key_failure(provider, key_hash, e)
                    err_lower = str(e).lower()
                    if any(kw in err_lower for kw in ("429","rate limit","quota","limit reached",
                                                       "model_decommissioned","resource_exhausted")):
                        cooldown = self._extract_retry_after(str(e)) or _PROVIDER_COOLDOWN_SECONDS
                        self._set_provider_cooldown(provider, cooldown)
                        break
                    logger.warning("%s structured attempt %d/%d: %s", provider, attempt+1, max_retries+1, type(e).__name__)
                    if attempt < max_retries: time.sleep(min(2 ** attempt, 8))

        if not attempted_any:
            raise RuntimeError("No LLM providers available for structured call.")
        raise RuntimeError(f"Failed to get structured output: {last_error}")

    # ── call (plain text) ─────────────────────────────────────────────────────

    def call(self, prompt: str, temperature: float = 0.7, max_tokens: int = 1000,
             timeout: int = 30, preferred_provider: Optional[str] = None) -> str:
        self._validate_prompt(prompt)
        last_error = None; attempted_any = False

        for provider in self._provider_order(preferred_provider):
            if not self._is_provider_available(provider): continue
            key = self.key_manager.get_working_key(provider)
            if not key: continue
            key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
            attempted_any = True

            try:
                with self._counter_lock:
                    call_times = getattr(self, f"{provider}_last_call_times")
                    if not self._check_rate_limit(provider, call_times):
                        logger.info("%s rate-limited — trying next provider", provider)
                        continue
                    call_times.append(time.time())

                response = self._dispatch_call(provider, prompt, temperature, max_tokens, key, timeout)
                self._validate_response(response)
                with self._counter_lock:
                    setattr(self, f"{provider}_calls", getattr(self, f"{provider}_calls") + 1)
                self.key_manager.report_key_success(provider, key_hash)
                logger.info("%s call #%d", provider, getattr(self, f"{provider}_calls"))
                return response

            except Exception as e:
                last_error = e
                self.key_manager.report_key_failure(provider, key_hash, e)
                if self._is_rate_limit_error(e):
                    cooldown = self._extract_retry_after(str(e)) or _PROVIDER_COOLDOWN_SECONDS
                    self._set_provider_cooldown(provider, cooldown)
                    logger.warning("%s rate limited — cooldown %.0fs", provider, cooldown)
                else:
                    logger.warning("%s failed: %s — trying next provider", provider, type(e).__name__)

        if not attempted_any:
            raise RateLimitError("all", "No API keys available.")
        if self._try_offline_fallback():
            return self._get_offline_fallback_text(prompt)
        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")

    # ── Dispatch ──────────────────────────────────────────────────────────────

    def _dispatch_call(self, provider: str, prompt: str, temperature: float,
                       max_tokens: int, key: str, timeout: int = 30) -> str:
        breaker = _circuit_breakers[provider]
        if not breaker.is_allowed():
            raise RuntimeError(f"Circuit OPEN for {provider}")
        try:
            if provider == "groq":       res = self._call_groq(prompt, temperature, max_tokens, timeout, key)
            elif provider == "gemini":     res = self._call_gemini(prompt, temperature, max_tokens, timeout, key)
            elif provider == "cerebras":   res = self._call_cerebras(prompt, temperature, max_tokens, timeout, key)
            elif provider == "openrouter": res = self._call_openrouter(prompt, temperature, max_tokens, timeout, key)
            else: raise ValueError(f"Unknown provider: {provider!r}")
            breaker.record_success()
            return res
        except Exception as e:
            if not self._is_rate_limit_error(e):
                breaker.record_failure()
            raise

    # ── Provider implementations ──────────────────────────────────────────────

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10),
           retry=retry_if_exception(lambda e: "rate limit" in str(e).lower() or "429" in str(e) or "exhausted" in str(e).lower()), reraise=True)
    def _call_groq(self, prompt, temperature, max_tokens, timeout, groq_key) -> str:
        from groq import Groq
        resp = Groq(api_key=groq_key).chat.completions.create(
            model=self.GROQ_MODEL,
            messages=[{"role":"user","content":prompt}],
            temperature=temperature, max_tokens=max_tokens, timeout=timeout,
        )
        if not resp.choices: raise ValueError("Groq returned empty response")
        return resp.choices[0].message.content or ""

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10),
           retry=retry_if_exception(lambda e: "rate limit" in str(e).lower() or "429" in str(e) or "exhausted" in str(e).lower()), reraise=True)
    def _call_gemini(self, prompt, temperature, max_tokens, timeout, gemini_key) -> str:
        if self.genai_client is None:
            with self._counter_lock:
                if self.genai_client is None:
                    from google import genai
                    from google.genai import types as genai_types
                    self._genai_types = genai_types
                    self.genai_client = genai.Client(api_key=gemini_key)
        if self._genai_types is None:
            from google.genai import types as genai_types
            self._genai_types = genai_types
        config = self._genai_types.GenerateContentConfig(temperature=temperature, max_output_tokens=max_tokens)
        resp   = self.genai_client.models.generate_content(model=self.GEMINI_MODEL, contents=prompt, config=config)
        if not resp or not resp.text: raise ValueError("Gemini returned empty response")
        return resp.text

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10),
           retry=retry_if_exception(lambda e: not isinstance(e, (ValueError, TypeError))), reraise=True)
    def _call_cerebras(self, prompt, temperature, max_tokens, timeout, cerebras_key) -> str:
        resp = requests.post("https://api.cerebras.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {cerebras_key}", "Content-Type": "application/json"},
            json={"model": self.CEREBRAS_MODEL, "messages":[{"role":"user","content":prompt}],
                  "temperature": temperature, "max_tokens": max_tokens}, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("choices"):
            raise ValueError("Cerebras returned empty response")
        return data["choices"][0].get("message", {}).get("content") or ""
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10),
           retry=retry_if_exception(lambda e: not isinstance(e, (ValueError, TypeError))), reraise=True)
    def _call_openrouter(self, prompt, temperature, max_tokens, timeout, openrouter_key) -> str:
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {openrouter_key}", "Content-Type": "application/json",
                     "HTTP-Referer": "https://insightswarm.ai", "X-Title": "InsightSwarm"},
            json={"model": self.OPENROUTER_MODEL, "messages":[{"role":"user","content":prompt}],
                  "temperature": temperature, "max_tokens": max_tokens}, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("choices"):
            raise ValueError("OpenRouter returned empty response")
        return data["choices"][0].get("message", {}).get("content") or ""
    def get_stats(self) -> dict:
        with self._counter_lock:
            return {
                "groq_calls": self.groq_calls, "gemini_calls": self.gemini_calls,
                "cerebras_calls": self.cerebras_calls, "openrouter_calls": self.openrouter_calls,
                "total_calls": self.groq_calls + self.gemini_calls + self.cerebras_calls + self.openrouter_calls,
                "provider_cooldowns": {p: max(0.0, round(ts - time.time(), 1)) for p, ts in self._provider_cooldown.items()},
            }

    def _try_offline_fallback(self) -> bool:
        return os.getenv("ENABLE_OFFLINE_FALLBACK","false").lower() in ("true","1","yes")

    def _get_offline_fallback_text(self, prompt: str) -> str:
        return "Unable to complete request — all API providers are unavailable. Please check your API keys and try again."
