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
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, retry_if_exception  # type: ignore
    HAS_TENACITY = True
except ImportError:
    HAS_TENACITY = False
    def retry(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def stop_after_attempt(*args: Any, **kwargs: Any) -> Any: return None
    def wait_exponential(*args: Any, **kwargs: Any) -> Any: return None
    def retry_if_exception_type(*args: Any, **kwargs: Any) -> Any: return None
    def retry_if_exception(*args: Any, **kwargs: Any) -> Any: return None

import json
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    print("WARNING: requests library not installed - Cerebras/OpenRouter disabled")

load_dotenv()
logger = logging.getLogger(__name__)

from src.utils.api_key_manager import get_api_key_manager


class RateLimitError(RuntimeError):
    def __init__(self, provider: str, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.provider    = provider
        self.retry_after = retry_after


class FreeLLMClient:
    MAX_CALLS_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

    GROQ_MODEL  = os.getenv("GROQ_MODEL",  "llama-3.3-70b-versatile")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    def __init__(self):
        self.key_manager = get_api_key_manager()

        self.groq_client   = None
        self.genai_client  = None
        self.groq_available  = False
        self.gemini_available = False
        self.groq_calls   = 0
        self.gemini_calls = 0
        self.groq_last_call_times   = []
        self.gemini_last_call_times = []
        self._counter_lock      = threading.Lock()
        self.groq_error:   Optional[str] = None
        self.gemini_error: Optional[str] = None
        self._gemini_mode:   Optional[str] = None
        self._genai_types    = None
        self._gemini_legacy  = None
        self._gemini_legacy_lock = threading.Lock()
        self._preferred_provider: Optional[str] = None
        
        # Initialize providers using API key manager
        self._init_providers()

    def _init_providers(self):
        try:
            groq_key = self.key_manager.get_working_key("groq")
            if groq_key:
                from groq import Groq
                self.groq_client    = Groq(api_key=groq_key)
                self.groq_available = True
                logger.info("✅ Groq client initialised")
            else:
                self.groq_available = False
                self.groq_error     = "No working Groq API keys available"
                logger.warning("⚠️ Groq client not available")
        except Exception as e:
            self.groq_available = False
            self.groq_error     = str(e)
            logger.warning(f"⚠️ Groq init failed: {type(e).__name__}")

        try:
            gemini_key = self.key_manager.get_working_key("gemini")
            if gemini_key:
                try:
                    from google import genai
                    from google.genai import types as genai_types
                    self._genai_types  = genai_types
                    self.genai_client  = genai.Client(api_key=gemini_key)
                    self.gemini_available = True
                    self._gemini_mode  = "genai"
                    logger.info("✅ Gemini client initialised (google.genai)")
                except (ImportError, AttributeError):
                    import google.generativeai as genai
                    self._gemini_legacy = genai
                    genai.configure(api_key=gemini_key)
                    self.genai_client  = genai.GenerativeModel(self.GEMINI_MODEL)
                    self.gemini_available = True
                    self._gemini_mode  = "legacy"
                    logger.warning("⚠️ Using legacy Gemini client")
            else:
                self.gemini_available = False
                self.gemini_error     = "No working Gemini API keys available"
                logger.warning("⚠️ Gemini client not available")
        except Exception as e:
            self.gemini_available = False
            self.gemini_error = str(e)
            logger.warning(f"⚠️ Gemini initialization failed: {type(e).__name__}")
            
        if not self.groq_available and not self.gemini_available:
            offline = os.getenv("ENABLE_OFFLINE_FALLBACK", "false").lower() in ("true", "1", "yes")
            if offline:
                logger.warning("⚠️ No LLM providers — offline fallback mode.")
            else:
                raise RuntimeError(
                    "No LLM providers available. Check GROQ_API_KEY / GEMINI_API_KEY in .env.\n"
                    "Set ENABLE_OFFLINE_FALLBACK=1 to start without API keys."
                )

    # ── Utility helpers ───────────────────────────────────────────────────────

    def _is_rate_limit_error(self, error: Exception) -> bool:
        text = str(error).lower()
        return ("rate limit" in text or "rate_limit" in text
                or "resource_exhausted" in text or "429" in text)

    def _provider_order(self, preferred_provider: Optional[str] = None) -> list:
        '''Return provider priority order based on preference and availability'''
        if preferred_provider:
            if preferred_provider == "gemini":
                return ["gemini", "groq"]
            elif preferred_provider == "groq":
                return ["groq", "gemini"]
        if self._preferred_provider == "gemini":
            return ["gemini", "groq"]
        return ["groq", "gemini"]

    def _set_next_preference(self, provider: str) -> None:
        if provider == "groq" and self.gemini_available:
            self._preferred_provider = "gemini"
        elif provider == "gemini" and self.groq_available:
            self._preferred_provider = "groq"
        else:
            self._preferred_provider = provider

    def _extract_retry_after(self, message: str) -> Optional[float]:
        for pattern in (
            r"retry in\s*([0-9]+(?:\.[0-9]+)?)s",
            r"retrydelay':\s*'([0-9]+)s'",
        ):
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
            logger.warning(f"⚠️ Rate limit for {provider}: {len(call_times)} calls/min")
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

    # ── call_structured ───────────────────────────────────────────────────────

    def call_structured(
        self,
        prompt: str,
        output_schema: Type[BaseModel],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        max_retries: int = 2,
        preferred_provider: Optional[str] = None
    ) -> Any:
        """
        Call LLM and parse the response as a Pydantic model.
        Does NOT rotate the preferred provider on success — only on failure.
        Reuses the existing groq_client instead of creating a new one per attempt.
        """
        json_prompt = (
            f"{prompt}\n\nIMPORTANT: Return a valid JSON object matching:\n"
            f"{output_schema.schema_json(indent=2)}"
        )

        last_error  = None
        attempted_any = False

        for provider in self._provider_order(preferred_provider):
            if provider == "groq" and self.groq_available and self.key_manager.has_working_keys("groq"):
                attempted_any = True
                for attempt in range(max_retries + 1):
                    groq_key = self.key_manager.get_working_key("groq")
                    if not groq_key:
                        break
                    groq_key_hash = hashlib.sha256(groq_key.encode()).hexdigest()[:16]
                    try:
                        with self._counter_lock:
                            if not self._check_rate_limit("groq", self.groq_last_call_times):
                                raise RuntimeError("Groq rate limit exceeded")
                            self.groq_last_call_times.append(time.time())

                        if self.groq_client is None:
                            raise RuntimeError("Groq client not initialised")

                        # Reuse existing client — update key instead of creating new Groq()
                        self.groq_client.api_key = groq_key

                        response        = self._call_groq(json_prompt, temperature, max_tokens,
                                                          timeout=30, groq_client=self.groq_client)
                        cleaned         = self._clean_json_response(response)
                        result          = output_schema.parse_raw(cleaned)

                        self.key_manager.report_key_success("groq", groq_key_hash)
                        # ← No _set_next_preference on success — stay with Groq
                        return result

                    except Exception as e:
                        last_error = e
                        self.key_manager.report_key_failure("groq", groq_key_hash, e)
                        err = str(e).lower()
                        if any(kw in err for kw in ("429", "rate limit", "quota", "exceeded",
                                                     "limit reached", "model_decommissioned")):
                            logger.warning(f"Groq quota/limit in structured call: {e}")
                            self._mark_provider_failed("groq")   # switch on failure ✓
                            break
                        logger.warning(f"Groq structured attempt {attempt+1}: {e}")
                        if attempt < max_retries:
                            time.sleep(1)

            if provider == "gemini" and self.gemini_available and self.key_manager.has_working_keys("gemini"):
                attempted_any = True
                for attempt in range(max_retries + 1):
                    gemini_key = self.key_manager.get_working_key("gemini")
                    if not gemini_key:
                        break
                    gemini_key_hash = hashlib.sha256(gemini_key.encode()).hexdigest()[:16]
                    try:
                        with self._counter_lock:
                            if not self._check_rate_limit("gemini", self.gemini_last_call_times):
                                raise RuntimeError("Gemini rate limit exceeded")
                            self.gemini_last_call_times.append(time.time())

                        if self._gemini_mode == "genai" and self.genai_client is None:
                            raise RuntimeError("Gemini GenAI client not initialised")
                        if self._gemini_mode == "legacy" and self._gemini_legacy is None:
                            raise RuntimeError("Gemini legacy client not initialised")

                        response = self._call_gemini(
                            json_prompt, temperature, max_tokens, timeout=30, gemini_key=gemini_key
                        )
                        cleaned_response = self._clean_json_response(response)
                        result = output_schema.parse_raw(cleaned_response)
                        
                        self.key_manager.report_key_success("gemini", gemini_key_hash)
                        # ← No _set_next_preference on success
                        return result

                    except Exception as e:
                        last_error = e
                        self.key_manager.report_key_failure("gemini", gemini_key_hash, e)
                        err = str(e).lower()
                        if any(kw in err for kw in ("429", "rate limit", "quota", "exceeded", "limit reached")):
                            logger.warning(f"Gemini quota/limit in structured call: {e}")
                            self._mark_provider_failed("gemini")  # switch on failure ✓
                            break
                        logger.warning(f"Gemini structured attempt {attempt+1}: {e}")
                        if attempt < max_retries:
                            time.sleep(1)

        if not attempted_any:
            raise RuntimeError("No LLM providers available for structured call.")
        logger.error(f"All structured calls failed. Last: {last_error}")
        raise RuntimeError(f"Failed to get structured output: {last_error}")

    # ── call (plain text) ─────────────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        # Only retry on transient API/network errors — never on ValueError/TypeError
        # (which are deterministic validation failures and should fail immediately).
        retry=retry_if_exception(lambda e: not isinstance(e, (ValueError, TypeError))),
        reraise=True,
    )
    def call(self, prompt: str, temperature: float = 0.7, max_tokens: int = 1000, timeout: int = 30) -> str:
        """
        Send prompt to LLM.  Groq first, Gemini fallback.
        Provider preference rotates only on failure, never on success.
        """
        try:
            self._validate_prompt(prompt)
            if not 0.0 <= temperature <= 2.0:
                raise ValueError("Temperature must be 0.0-2.0")
            if not 1 <= max_tokens <= 4000:
                raise ValueError("max_tokens must be 1-4000")
            if not 1 <= timeout <= 300:
                raise ValueError("timeout must be 1-300 seconds")
        except ValueError as e:
            logger.error(f"❌ Input validation: {e}")
            raise

        last_error: Optional[Exception] = None
        attempted_any = False

        for provider in self._provider_order():
            if provider == "groq" and self.groq_available and self.key_manager.has_working_keys("groq"):
                groq_key = self.key_manager.get_working_key("groq")
                if not groq_key:
                    continue
                groq_key_hash = hashlib.sha256(groq_key.encode()).hexdigest()[:16]
                attempted_any = True
                try:
                    with self._counter_lock:
                        rate_limit_hit = not self._check_rate_limit("groq", self.groq_last_call_times)
                        if not rate_limit_hit:
                            self.groq_last_call_times.append(time.time())

                    if rate_limit_hit:
                        logger.info("Groq rate-limited — trying Gemini fallback...")
                    else:
                        if self.groq_client is None:
                            raise RuntimeError("Groq client not initialised")
                        response = self._call_groq(prompt, temperature, max_tokens, timeout)
                        self._validate_response(response)
                        with self._counter_lock:
                            self.groq_calls += 1
                        logger.info(f"✅ Groq call #{self.groq_calls}")
                        # ← No provider rotation on success
                        self.key_manager.report_key_success("groq", groq_key_hash)
                        return response
                except Exception as e:
                    if self._is_rate_limit_error(e):
                        self.key_manager.report_key_failure("groq", groq_key_hash, e)
                        self._mark_provider_failed("groq")   # switch on failure ✓
                        last_error = RateLimitError("groq", str(e), self._extract_retry_after(str(e)))
                        continue
                    last_error = e
                    self.key_manager.report_key_failure("groq", groq_key_hash, e)
                    self._mark_provider_failed("groq")       # switch on failure ✓
                    logger.warning(f"⚠️ Groq failed: {type(e).__name__} — trying Gemini...")

            if provider == "gemini" and self.gemini_available and self.key_manager.has_working_keys("gemini"):
                gemini_key = self.key_manager.get_working_key("gemini")
                if not gemini_key:
                    continue
                gemini_key_hash = hashlib.sha256(gemini_key.encode()).hexdigest()[:16]
                attempted_any = True
                try:
                    with self._counter_lock:
                        rate_limit_hit = not self._check_rate_limit("gemini", self.gemini_last_call_times)
                        if not rate_limit_hit:
                            self.gemini_last_call_times.append(time.time())

                    if rate_limit_hit:
                        logger.warning("❌ Gemini rate-limited too")
                    else:
                        if self._gemini_mode == "genai" and self.genai_client is None:
                            raise RuntimeError("Gemini GenAI client not initialised")
                        if self._gemini_mode == "legacy" and self._gemini_legacy is None:
                            raise RuntimeError("Gemini legacy client not initialised")
                        response = self._call_gemini(prompt, temperature, max_tokens,
                                                     timeout, gemini_key=gemini_key)
                        self._validate_response(response)
                        with self._counter_lock:
                            self.gemini_calls += 1
                        logger.info(f"✅ Gemini call #{self.gemini_calls}")
                        # ← No provider rotation on success
                        self.key_manager.report_key_success("gemini", gemini_key_hash)
                        return response
                except Exception as e:
                    if self._is_rate_limit_error(e):
                        self.key_manager.report_key_failure("gemini", gemini_key_hash, e)
                        self._mark_provider_failed("gemini")
                        last_error = RateLimitError("gemini", str(e), self._extract_retry_after(str(e)))
                        continue
                    last_error = e
                    self.key_manager.report_key_failure("gemini", gemini_key_hash, e)
                    logger.error(f"❌ Gemini also failed: {type(e).__name__}")

        if not attempted_any:
            raise RateLimitError("all", "No API keys available.")
        if isinstance(last_error, RateLimitError):
            raise last_error

        if self._try_offline_fallback():
            logger.warning("🔄 Offline fallback mode")
            return self._get_offline_fallback_text(prompt)

        raise RuntimeError("All LLM providers failed. Check API keys and network.")

    def _is_rate_limit_exception(self, e: Exception) -> bool:
        return self._is_rate_limit_error(e)

    # ── Internal API calls ────────────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception(lambda e: "rate limit" in str(e).lower()
                                 or "429" in str(e) or "exhausted" in str(e).lower()),
        reraise=True,
    )
    def _call_groq(self, prompt: str, temperature: float, max_tokens: int,
                   timeout: int, groq_client: Optional[Any] = None) -> str:
        try:
            client = groq_client or self.groq_client
            if client is None:
                raise RuntimeError("Groq client not initialised")
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
        except Exception as e:
            logger.debug(f"Groq API error: {type(e).__name__}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception(lambda e: "rate limit" in str(e).lower()
                                 or "429" in str(e) or "exhausted" in str(e).lower()),
        reraise=True,
    )
    def _call_gemini(self, prompt: str, temperature: float, max_tokens: int,
                     timeout: int, gemini_key: Optional[str] = None,
                     response_mime_type: Optional[str] = None) -> str:
        try:
            if gemini_key is None:
                gemini_key = self.key_manager.get_working_key("gemini")
            if not gemini_key:
                raise RuntimeError("No working Gemini API keys")

            if self._gemini_mode == "genai" and self._genai_types is not None:
                from google import genai
                client = genai.Client(api_key=gemini_key)
                cfg_kwargs: dict = {"temperature": temperature, "max_output_tokens": max_tokens}
                if response_mime_type:
                    cfg_kwargs["response_mime_type"] = response_mime_type
                config   = self._genai_types.GenerateContentConfig(**cfg_kwargs)
                response = client.models.generate_content(
                    model=self.GEMINI_MODEL, contents=prompt, config=config)
            else:
                if self._gemini_legacy is None:
                    raise RuntimeError("Legacy Gemini client not initialised")
                with self._gemini_legacy_lock:
                    self._gemini_legacy.configure(api_key=gemini_key)
                    model = self._gemini_legacy.GenerativeModel(self.GEMINI_MODEL)
                    gen_cfg: dict = {"temperature": temperature, "max_output_tokens": max_tokens}
                    if response_mime_type:
                        gen_cfg["response_mime_type"] = response_mime_type
                    response = model.generate_content(prompt, generation_config=gen_cfg)

            if not response or not response.text:
                raise ValueError("Gemini returned empty response")
            return response.text
        except Exception as e:
            logger.debug(f"Gemini API error: {type(e).__name__}")
            raise

    # ── Helpers ───────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        with self._counter_lock:
            groq_count = self.groq_calls
            gemini_count = self.gemini_calls
        return {
            "groq_calls": groq_count,
            "gemini_calls": gemini_count,
            "total_calls": groq_count + gemini_count
        }

    def _try_offline_fallback(self) -> bool:
        return os.getenv("ENABLE_OFFLINE_FALLBACK", "false").lower() in ("true", "1", "yes")

    def _get_offline_fallback_text(self, prompt: str) -> str:
        return ("I'm unable to complete this request due to API rate limits or outages. "
                "Please try again in a few moments.")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("FreeLLMClient test")
    print("=" * 60)
    try:
        client   = FreeLLMClient()
        response = client.call("What is 2+2? Answer with just the number.", timeout=30)
        print(f"Response: {response}")
        print(f"Stats:    {client.get_stats()}")
        print("✅ FreeLLMClient working.")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        logger.exception("Test error")
