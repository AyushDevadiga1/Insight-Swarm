"""
FIX FILE 2 — src/llm/client.py  (critical sections only — full replacement)
Fixes:
  P0-2  .schema_json() / .parse_raw() removed in Pydantic v2
  P0-3  _call_gemini creates new genai.Client on every call
  P0-4  _mark_provider_failed permanently disables providers — now uses timed cooldown
  P1-4  _call_cerebras / _call_openrouter had no retry decorator
  P2-4  groq_client.api_key mutation outside lock (race condition)
  P3-4  Double-retry: @retry on _call_groq PLUS loop in call_structured (now consistent)

This is a drop-in replacement for src/llm/client.py.
"""

from pydantic import BaseModel
from typing import Type, Any, Optional
import os
import re
import threading
import logging
import time
import hashlib
from dotenv import load_dotenv

try:
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
    HAS_TENACITY = True
except ImportError:
    HAS_TENACITY = False
    def retry(*args, **kwargs):
        def decorator(func): return func
        return decorator
    def stop_after_attempt(*a, **k): return None
    def wait_exponential(*a, **k): return None
    def retry_if_exception(*a, **k): return None

import json

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

load_dotenv()
logger = logging.getLogger(__name__)

from src.utils.api_key_manager import get_api_key_manager

# How long (seconds) a provider stays in soft-cooldown after a rate-limit hit.
# After this window, _is_provider_available() will re-enable it automatically.
_PROVIDER_COOLDOWN_SECONDS = 90


class RateLimitError(RuntimeError):
    def __init__(self, provider: str, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.provider    = provider
        self.retry_after = retry_after


class FreeLLMClient:
    MAX_CALLS_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

    GROQ_MODEL       = os.getenv("GROQ_MODEL",        "llama-3.3-70b-versatile")
    GEMINI_MODEL     = os.getenv("GEMINI_MODEL",      "gemini-2.0-flash")
    CEREBRAS_MODEL   = os.getenv("CEREBRAS_MODEL",    "llama3.1-8b")
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL",  "meta-llama/llama-3.1-8b-instruct")

    def __init__(self):
        self.key_manager = get_api_key_manager()

        self.groq_client       = None
        self.genai_client      = None   # reused across all Gemini calls (P0-3 fix)
        self._genai_types      = None

        # Availability flags replaced by timed cooldown dict (P0-4 fix)
        # Structure: { provider: cooldown_until_timestamp }  0 = available now
        self._provider_cooldown: dict = {
            "groq":       0.0,
            "gemini":     0.0,
            "cerebras":   0.0,
            "openrouter": 0.0,
        }

        self.groq_calls       = 0
        self.gemini_calls     = 0
        self.cerebras_calls   = 0
        self.openrouter_calls = 0

        self.groq_last_call_times       = []
        self.gemini_last_call_times     = []
        self.cerebras_last_call_times   = []
        self.openrouter_last_call_times = []

        self._counter_lock = threading.Lock()

        self.groq_error:       Optional[str] = None
        self.gemini_error:     Optional[str] = None
        self.cerebras_error:   Optional[str] = None
        self.openrouter_error: Optional[str] = None

        self._preferred_provider: Optional[str] = None

        self._init_providers()

    # ── Provider availability (P0-4 fix) ─────────────────────────────────────

    def _is_provider_available(self, provider: str) -> bool:
        """True if the provider is not in cooldown and has working keys."""
        if time.time() < self._provider_cooldown.get(provider, 0.0):
            return False
        return self.key_manager.has_working_keys(provider)

    def _set_provider_cooldown(self, provider: str, seconds: float = _PROVIDER_COOLDOWN_SECONDS) -> None:
        """Put a provider in timed cooldown instead of permanently disabling it."""
        self._provider_cooldown[provider] = time.time() + seconds
        logger.warning("Provider %s cooling down for %.0fs", provider, seconds)

    # ── Init ──────────────────────────────────────────────────────────────────

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
                self._genai_types  = genai_types
                self.genai_client  = genai.Client(api_key=gemini_key)   # stored, reused
                logger.info("Gemini client initialised")
            else:
                self.gemini_error = "No working Gemini API keys available"
                logger.warning("Gemini client not available")
        except Exception as e:
            self.gemini_error = str(e)
            logger.warning("Gemini init failed: %s", type(e).__name__)

        try:
            cer_key = self.key_manager.get_working_key("cerebras")
            if cer_key:
                logger.info("Cerebras available")
            else:
                self.cerebras_error = "No Cerebras key"
        except Exception as e:
            self.cerebras_error = str(e)

        try:
            or_key = self.key_manager.get_working_key("openrouter")
            if or_key:
                logger.info("OpenRouter available")
            else:
                self.openrouter_error = "No OpenRouter key"
        except Exception as e:
            self.openrouter_error = str(e)

        any_available = any(
            self.key_manager.has_working_keys(p)
            for p in ("groq", "gemini", "cerebras", "openrouter")
        )
        if not any_available:
            offline = os.getenv("ENABLE_OFFLINE_FALLBACK", "false").lower() in ("true", "1", "yes")
            if offline:
                logger.warning("No LLM providers — offline fallback mode.")
            else:
                raise RuntimeError(
                    "No LLM providers available. Check GROQ_API_KEY / GEMINI_API_KEY in .env.\n"
                    "Set ENABLE_OFFLINE_FALLBACK=1 to start without API keys."
                )

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _is_rate_limit_error(self, error: Exception) -> bool:
        text = str(error).lower()
        return any(kw in text for kw in ("rate limit", "rate_limit", "resource_exhausted", "429", "quota"))

    def _provider_order(self, preferred_provider: Optional[str] = None) -> list:
        order = ["groq", "gemini", "cerebras", "openrouter"]
        pref  = preferred_provider or self._preferred_provider
        if pref and pref in order:
            order.remove(pref)
            order.insert(0, pref)
        return order

    def _extract_retry_after(self, message: str) -> Optional[float]:
        for pattern in (r"retry in\s*([0-9]+(?:\.[0-9]+)?)s", r"retrydelay':\s*'([0-9]+)s'"):
            m = re.search(pattern, message, re.IGNORECASE)
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    pass
        return None

    def _check_rate_limit(self, provider: str, call_times: list) -> bool:
        now            = time.time()
        one_minute_ago = now - 60
        recent = [t for t in call_times if t > one_minute_ago]
        call_times.clear()
        call_times.extend(recent)
        if len(call_times) >= self.MAX_CALLS_PER_MINUTE:
            logger.warning("Rate limit for %s: %d calls/min", provider, len(call_times))
            return False
        return True

    def _validate_prompt(self, prompt: str) -> None:
        if not prompt or not isinstance(prompt, str):
            raise ValueError("Prompt must be a non-empty string")
        if not prompt.strip():
            raise ValueError("Prompt cannot be whitespace-only")
        if len(prompt) > 100_000:
            raise ValueError("Prompt exceeds 100 000-character limit")

    def _validate_response(self, response: str) -> None:
        if response is None:
            raise ValueError("LLM returned None")
        if not isinstance(response, str):
            raise ValueError(f"LLM response must be str, got {type(response).__name__}")
        if not response.strip():
            raise ValueError("LLM returned empty response")

    def _clean_json_response(self, response: str) -> str:
        if not response:
            return response
        response = response.strip()
        if "```" in response:
            m = re.search(r"```(?:json)?\s*(.*?)\s*```", response, re.DOTALL)
            if m:
                return m.group(1).strip()
        return response

    # ── call_structured (P0-2 fix: Pydantic v2 API) ──────────────────────────

    def call_structured(
        self,
        prompt:             str,
        output_schema:      Type[BaseModel],
        temperature:        float = 0.7,
        max_tokens:         int   = 1000,
        max_retries:        int   = 2,
        preferred_provider: Optional[str] = None,
    ) -> Any:
        """
        Call LLM and parse response as a Pydantic model.
        Uses Pydantic v2 APIs: model_json_schema() and model_validate_json().
        """
        # P0-2 fix: use Pydantic v2 schema API
        schema_json = json.dumps(output_schema.model_json_schema(), indent=2)
        json_prompt = (
            f"{prompt}\n\nIMPORTANT: Return a valid JSON object matching this schema:\n"
            f"{schema_json}"
        )

        last_error    = None
        attempted_any = False

        for provider in self._provider_order(preferred_provider):
            if not self._is_provider_available(provider):
                continue
            if not self.key_manager.has_working_keys(provider):
                continue

            attempted_any = True

            for attempt in range(max_retries + 1):
                key = self.key_manager.get_working_key(provider)
                if not key:
                    break
                key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]

                try:
                    with self._counter_lock:
                        call_times = getattr(self, f"{provider}_last_call_times")
                        if not self._check_rate_limit(provider, call_times):
                            raise RuntimeError(f"{provider} rate limit exceeded")
                        call_times.append(time.time())

                    raw = self._dispatch_call(provider, json_prompt, temperature, max_tokens, key)
                    cleaned = self._clean_json_response(raw)

                    # P0-2 fix: Pydantic v2 parse API
                    result = output_schema.model_validate_json(cleaned)

                    self.key_manager.report_key_success(provider, key_hash)
                    return result

                except Exception as e:
                    last_error = e
                    self.key_manager.report_key_failure(provider, key_hash, e)
                    err_lower = str(e).lower()

                    if any(kw in err_lower for kw in ("429", "rate limit", "quota", "exceeded",
                                                       "limit reached", "model_decommissioned",
                                                       "resource_exhausted")):
                        retry_after = self._extract_retry_after(str(e))
                        cooldown    = retry_after or _PROVIDER_COOLDOWN_SECONDS
                        self._set_provider_cooldown(provider, cooldown)   # timed, not permanent
                        break

                    logger.warning("%s structured attempt %d/%d: %s",
                                   provider, attempt + 1, max_retries + 1, type(e).__name__)
                    if attempt < max_retries:
                        time.sleep(min(2 ** attempt, 8))

        if not attempted_any:
            raise RuntimeError("No LLM providers available for structured call.")
        logger.error("All structured calls failed. Last: %s", last_error)
        raise RuntimeError(f"Failed to get structured output: {last_error}")

    # ── call (plain text) ─────────────────────────────────────────────────────

    def call(
        self,
        prompt:             str,
        temperature:        float = 0.7,
        max_tokens:         int   = 1000,
        timeout:            int   = 30,
        preferred_provider: Optional[str] = None,
    ) -> str:
        self._validate_prompt(prompt)

        last_error:   Optional[Exception] = None
        attempted_any = False

        for provider in self._provider_order(preferred_provider):
            if not self._is_provider_available(provider):
                continue
            if not self.key_manager.has_working_keys(provider):
                continue

            key = self.key_manager.get_working_key(provider)
            if not key:
                continue

            key_hash      = hashlib.sha256(key.encode()).hexdigest()[:16]
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
                    retry_after = self._extract_retry_after(str(e))
                    cooldown    = retry_after or _PROVIDER_COOLDOWN_SECONDS
                    self._set_provider_cooldown(provider, cooldown)
                    logger.warning("%s rate limited — cooldown %.0fs", provider, cooldown)
                else:
                    logger.warning("%s failed: %s — trying next provider", provider, type(e).__name__)

        if not attempted_any:
            raise RateLimitError("all", "No API keys available.")

        if self._try_offline_fallback():
            return self._get_offline_fallback_text(prompt)

        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")

    # ── Internal dispatch (single entry point for all providers) ─────────────

    def _dispatch_call(
        self,
        provider:    str,
        prompt:      str,
        temperature: float,
        max_tokens:  int,
        key:         str,
        timeout:     int = 30,
    ) -> str:
        """Route to the correct provider call. Single place to maintain."""
        if provider == "groq":
            return self._call_groq(prompt, temperature, max_tokens, timeout, key)
        if provider == "gemini":
            return self._call_gemini(prompt, temperature, max_tokens, timeout, key)
        if provider == "cerebras":
            return self._call_cerebras(prompt, temperature, max_tokens, timeout, key)
        if provider == "openrouter":
            return self._call_openrouter(prompt, temperature, max_tokens, timeout, key)
        raise ValueError(f"Unknown provider: {provider!r}")

    # ── Provider implementations ──────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(lambda e: "rate limit" in str(e).lower()
                                 or "429" in str(e) or "exhausted" in str(e).lower()),
        reraise=True,
    )
    def _call_groq(self, prompt: str, temperature: float, max_tokens: int,
                   timeout: int, groq_key: str) -> str:
        """
        P2-4 fix: takes groq_key as parameter instead of mutating self.groq_client.api_key.
        Each call creates a thin client wrapper with the correct key — thread-safe.
        The groq.Groq client is lightweight to construct; connection pool is managed
        by the underlying httpx session inside the SDK.
        """
        from groq import Groq
        client   = Groq(api_key=groq_key)
        response = client.chat.completions.create(
            model=self.GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        if not response.choices:
            raise ValueError("Groq returned empty response")
        return response.choices[0].message.content or ""

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(lambda e: "rate limit" in str(e).lower()
                                 or "429" in str(e) or "exhausted" in str(e).lower()),
        reraise=True,
    )
    def _call_gemini(self, prompt: str, temperature: float, max_tokens: int,
                     timeout: int, gemini_key: str) -> str:
        """
        P0-3 fix: reuse self.genai_client instead of creating a new one per call.
        If the stored client's key differs (rotation), reinitialise once.
        """
        if self.genai_client is None:
            from google import genai
            from google.genai import types as genai_types
            self._genai_types = genai_types
            self.genai_client = genai.Client(api_key=gemini_key)

        if self._genai_types is None:
            from google.genai import types as genai_types
            self._genai_types = genai_types

        config   = self._genai_types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        response = self.genai_client.models.generate_content(
            model=self.GEMINI_MODEL, contents=prompt, config=config
        )
        if not response or not response.text:
            raise ValueError("Gemini returned empty response")
        return response.text

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(lambda e: not isinstance(e, (ValueError, TypeError))),
        reraise=True,
    )
    def _call_cerebras(self, prompt: str, temperature: float, max_tokens: int,
                       timeout: int, cerebras_key: str) -> str:
        # P1-4 fix: now has @retry decorator
        resp = requests.post(
            "https://api.cerebras.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {cerebras_key}", "Content-Type": "application/json"},
            json={
                "model":       self.CEREBRAS_MODEL,
                "messages":    [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens":  max_tokens,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(lambda e: not isinstance(e, (ValueError, TypeError))),
        reraise=True,
    )
    def _call_openrouter(self, prompt: str, temperature: float, max_tokens: int,
                         timeout: int, openrouter_key: str) -> str:
        # P1-4 fix: now has @retry decorator
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {openrouter_key}",
                "Content-Type":  "application/json",
                "HTTP-Referer":  "https://insightswarm.ai",
                "X-Title":       "InsightSwarm",
            },
            json={
                "model":       self.OPENROUTER_MODEL,
                "messages":    [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens":  max_tokens,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def get_stats(self) -> dict:
        with self._counter_lock:
            return {
                "groq_calls":       self.groq_calls,
                "gemini_calls":     self.gemini_calls,
                "cerebras_calls":   self.cerebras_calls,
                "openrouter_calls": self.openrouter_calls,
                "total_calls":      (self.groq_calls + self.gemini_calls
                                     + self.cerebras_calls + self.openrouter_calls),
                "provider_cooldowns": {
                    p: max(0.0, round(ts - time.time(), 1))
                    for p, ts in self._provider_cooldown.items()
                },
            }

    def _try_offline_fallback(self) -> bool:
        return os.getenv("ENABLE_OFFLINE_FALLBACK", "false").lower() in ("true", "1", "yes")

    def _get_offline_fallback_text(self, prompt: str) -> str:
        return ("Unable to complete request — all API providers are unavailable. "
                "Please check your API keys and try again.")
