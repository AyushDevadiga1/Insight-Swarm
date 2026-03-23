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
from src.resilience.circuit_breaker import CircuitBreaker
from src.resilience.fallback_handler import FallbackHandler
from src.resilience.retry_handler import with_retry


class RateLimitError(RuntimeError):
    def __init__(self, provider: str, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.provider = provider
        self.retry_after = retry_after

class FreeLLMClient:
    MAX_CALLS_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    
    # Configurable model names
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    
    def __init__(self):
        # Initialize API key manager first
        self.key_manager = get_api_key_manager()
        
        self.groq_client = None
        self.genai_client = None
        self.groq_calls = 0
        self.gemini_calls = 0
        self.groq_last_call_times = []
        self.gemini_last_call_times = []
        self._counter_lock = threading.Lock()
        self.groq_error: Optional[str] = None
        self.gemini_error: Optional[str] = None
        self._gemini_mode: Optional[str] = None
        self._genai_types = None
        self._gemini_legacy = None
        self._gemini_legacy_lock = threading.Lock()
        self._preferred_provider: Optional[str] = None
        
        self.cerebras_client = None
        self.openrouter_client = None
        self.cerebras_calls = 0
        self.openrouter_calls = 0
        self.cerebras_last_call_times = []
        self.openrouter_last_call_times = []

        self.cerebras_error: Optional[str] = None
        self.openrouter_error: Optional[str] = None
    
        # Resilience components
        self.circuit_breakers = {
            "cerebras": CircuitBreaker("cerebras", failure_threshold=3, recovery_timeout=60.0),
            "openrouter": CircuitBreaker("openrouter", failure_threshold=3, recovery_timeout=60.0),
            "groq": CircuitBreaker("groq", failure_threshold=3, recovery_timeout=60.0),
            "gemini": CircuitBreaker("gemini", failure_threshold=3, recovery_timeout=60.0),
        }

    
        # We no longer initialize providers upfront.
        # They are initialized on first use via properties.
        pass

    @property
    def groq_available(self) -> bool:
        return self.key_manager.has_working_keys("groq")

    @property
    def gemini_available(self) -> bool:
        return self.key_manager.has_working_keys("gemini")

    @property
    def cerebras_available(self) -> bool:
        return HAS_REQUESTS and self.key_manager.has_working_keys("cerebras")

    @property
    def openrouter_available(self) -> bool:
        return HAS_REQUESTS and self.key_manager.has_working_keys("openrouter")

    def _get_groq_client(self, api_key: str):
        if not self.groq_client:
            from groq import Groq
            self.groq_client = Groq(api_key=api_key)
            logger.debug("✅ Groq client lazily initialized")
        else:
            self.groq_client.api_key = api_key
        return self.groq_client

    def _get_gemini_client(self, api_key: str):
        if self.genai_client:
            return self.genai_client
            
        # Try modern SDK first
        try:
            from google import genai
            from google.genai import types as genai_types
            self._genai_types = genai_types
            self.genai_client = genai.Client(api_key=api_key)
            self._gemini_mode = "genai"
            logger.debug("✅ Gemini client initialized (google.genai)")
            return self.genai_client
        except (ImportError, Exception) as e:
            logger.warning(f"Modern google.genai SDK failed, trying legacy fallback: {e}")
            
        # Fallback to legacy SDK
        try:
            import google.generativeai as genai_legacy
            self._gemini_legacy = genai_legacy
            self._gemini_mode = "legacy"
            logger.debug("✅ Gemini client initialized (google.generativeai legacy)")
            # we don't return a 'client' object here as legacy is module-level
            return genai_legacy
        except ImportError:
            logger.error("No Gemini SDKs found (tried genai and generativeai)")
            raise RuntimeError("Gemini SDK not installed")

    def _is_rate_limit_error(self, error: Exception) -> bool:
        text = str(error).lower()
        return (
            "rate limit" in text
            or "rate_limit" in text
            or "resource_exhausted" in text
            or "429" in text
        )

    def _provider_order(self, preferred_provider: Optional[str] = None) -> list:
        '''Return provider priority order based on preference and availability'''
        if preferred_provider:
            if preferred_provider == "cerebras":
                return ["cerebras", "openrouter", "groq", "gemini"]
            elif preferred_provider == "openrouter":
                return ["openrouter", "cerebras", "groq", "gemini"]
            elif preferred_provider == "groq":
                return ["groq", "cerebras", "openrouter", "gemini"]
            elif preferred_provider == "gemini":
                return ["gemini", "openrouter", "cerebras", "groq"]
        
        # Default: Cerebras first (fastest), then OpenRouter (diverse), then fallbacks
        if self._preferred_provider == "cerebras":
            return ["cerebras", "openrouter", "groq", "gemini"]
        elif self._preferred_provider == "openrouter":
            return ["openrouter", "cerebras", "groq", "gemini"]
        
        # Cerebras has DNS issues, OpenRouter has no credits — put working providers first
        return ["groq", "gemini", "cerebras", "openrouter"]

    def _set_next_preference(self, provider: str) -> None:
        # Round robin / priority shift
        providers = ["cerebras", "openrouter", "groq", "gemini"]
        try:
            current_idx = providers.index(provider)
            next_idx = (current_idx + 1) % len(providers)
            self._preferred_provider = providers[next_idx]
        except ValueError:
            self._preferred_provider = "cerebras"

    def _extract_retry_after(self, message: str) -> Optional[float]:
        match = re.search(r"retry in\s*([0-9]+(?:\.[0-9]+)?)s", message, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        match = re.search(r"retrydelay':\s*'([0-9]+)s'", message, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        return None

    def _check_rate_limit(self, provider: str, last_call_times: list) -> bool:
        """Helper to enforce rate limits per provider."""
        now = time.time()
        # Clean up timestamps older than 60s
        last_call_times[:] = [t for t in last_call_times if now - t < 60]
        return len(last_call_times) < self.MAX_CALLS_PER_MINUTE

    def _validate_prompt(self, prompt: str) -> None:
        """Basic prompt safety/integrity check."""
        if not prompt or len(prompt.strip()) < 5:
            raise ValueError("Prompt too short or empty")
        if len(prompt) > 50000: # Safety cap
            raise ValueError("Prompt exceeds maximum allowed length (50k chars)")

    def _validate_response(self, response: str) -> None:
        """Basic response integrity check."""
        if not response or len(response.strip()) < 2:
            raise ValueError("Empty or trivial response received from provider")

    def _clean_json_response(self, raw_text: str) -> str:
        """Strip markdown code blocks and garbage from LLM JSON responses."""
        if not raw_text:
            return "{}"
        # Remove triple backticks
        cleaned = re.sub(r'```json\s*', '', raw_text)
        cleaned = re.sub(r'```\s*', '', cleaned)
        # Find first { and last }
        first = cleaned.find('{')
        last = cleaned.rfind('}')
        if first != -1 and last != -1:
            return cleaned[first:last+1]
        return cleaned.strip()

    def _execute_provider(
        self,
        provider: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
        timeout: int,
        is_structured: bool = False,
        output_schema: Optional[Type[BaseModel]] = None,
        model: Optional[str] = None
    ) -> Any:
        cb = self.circuit_breakers[provider]
        if not cb.is_allowed():
            raise RuntimeError(f"Circuit Breaker for {provider} is OPEN")

        if not getattr(self, f"{provider}_available"):
            raise RuntimeError(f"Provider {provider} is not available")

        api_key = self.key_manager.get_working_key(provider)
        if not api_key:
            raise RuntimeError(f"No working key for {provider}")

        key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]

        try:
            with self._counter_lock:
                last_times = getattr(self, f"{provider}_last_call_times")
                if not self._check_rate_limit(provider, last_times):
                    # Fail gracefully so fallback catches it
                    raise RateLimitError(provider, f"{provider} rate limit hit")
                last_times.append(time.time())

            if is_structured:
                if provider == "cerebras":
                    response = self._call_cerebras(prompt, temperature, max_tokens, timeout=30, cerebras_key=api_key)
                elif provider == "openrouter":
                    target_model = model if model else "meta-llama/llama-3.1-70b-instruct"
                    response = self._call_openrouter(prompt, temperature, max_tokens, timeout=30, openrouter_key=api_key, model=target_model)
                elif provider == "groq":
                    client = self._get_groq_client(api_key)
                    response = self._call_groq(prompt, temperature, max_tokens, timeout=30, groq_client=client)
                elif provider == "gemini":
                    self._get_gemini_client(api_key)
                    response = self._call_gemini(prompt, temperature, max_tokens, timeout=30, gemini_key=api_key, response_mime_type="application/json")
                else:
                    raise ValueError("Unknown provider")
                
                cleaned = self._clean_json_response(response)
                result = output_schema.parse_raw(cleaned)
            else:
                if provider == "cerebras":
                    response = self._call_cerebras(prompt, temperature, max_tokens, timeout, cerebras_key=api_key)
                elif provider == "openrouter":
                    response = self._call_openrouter(prompt, temperature, max_tokens, timeout, openrouter_key=api_key)
                elif provider == "groq":
                    client = self._get_groq_client(api_key)
                    response = self._call_groq(prompt, temperature, max_tokens, timeout, groq_client=client)
                elif provider == "gemini":
                    self._get_gemini_client(api_key)
                    response = self._call_gemini(prompt, temperature, max_tokens, timeout, gemini_key=api_key)
                else:
                    raise ValueError("Unknown provider")
                    
                self._validate_response(response)
                result = response

            with self._counter_lock:
                calls_attr = f"{provider}_calls"
                setattr(self, calls_attr, getattr(self, calls_attr) + 1)
                
            self.key_manager.report_key_success(provider, key_hash)
            self._set_next_preference(provider)
            cb.record_success()
            return result

        except Exception as e:
            err_msg = str(e).lower()
            if "402" in err_msg or "payment" in err_msg or "credits" in err_msg:
                logger.error(f"❌ Provider {provider} failed with 402 (no credits). Marking key as invalid.")
                # Cannot set @property directly — mark key permanently invalid via key_manager instead
                # has_working_keys() will then return False, making the property return False naturally
                for ki in self.key_manager.keys.get(provider, []):
                    if ki.key_hash == key_hash:
                        from src.utils.api_key_manager import APIKeyStatus
                        ki.status = APIKeyStatus.INVALID
                        break
                self.key_manager.report_key_failure(provider, key_hash, e)
            
            if self._is_rate_limit_error(e):
                self.key_manager.report_key_failure(provider, key_hash, e)
                raise RateLimitError(provider, str(e), self._extract_retry_after(str(e)))
                
            self.key_manager.report_key_failure(provider, key_hash, e)
            logger.warning(f"⚠️ {provider.title()} failed execution: {type(e).__name__} - {e}")
            cb.record_failure()
            raise

    def call_structured(
        self,
        prompt: str,
        output_schema: Type[BaseModel],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        max_retries: int = 2,
        preferred_provider: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 60
    ) -> Any:
        json_prompt = f"{prompt}\n\nIMPORTANT: You MUST return a valid JSON object matching this schema:\n{output_schema.schema_json(indent=2)}"
        
        operations = []
        for provider in self._provider_order(preferred_provider):
            operations.append(
                lambda p=provider: self._execute_provider(p, json_prompt, temperature, max_tokens, timeout, is_structured=True, output_schema=output_schema, model=model)
            )
            
        return FallbackHandler.execute(operations)

    def call(self, prompt: str, temperature: float = 0.7, max_tokens: int = 1000, timeout: int = 30, preferred_provider: Optional[str] = None) -> str:
        try:
            self._validate_prompt(prompt)
            if not 0.0 <= temperature <= 2.0:
                raise ValueError("Temperature must be between 0.0 and 2.0")
            if not 1 <= max_tokens <= 4000:
                raise ValueError("max_tokens must be between 1 and 4000")
            if not 1 <= timeout <= 300:
                raise ValueError("timeout must be between 1 and 300 seconds")
        except ValueError as e:
            logger.error(f"❌ Input validation failed: {e}")
            raise
            
        operations = []
        for provider in self._provider_order(preferred_provider):
            operations.append(
                lambda p=provider: self._execute_provider(p, prompt, temperature, max_tokens, timeout, is_structured=False)
            )
            
        def offline_fb():
            if self._try_offline_fallback():
                logger.warning("🔄 Using offline fallback mode")
                return self._get_offline_fallback_text(prompt)
            raise RuntimeError("All LLM providers failed. Check your API keys and network connection.")
            
        return FallbackHandler.execute(operations, graceful_fallback=offline_fb)
    def _is_rate_limit_exception(self, e: Exception) -> bool:
        return self._is_rate_limit_error(e)

    @with_retry(max_retries=2, base_delay=1.0, exceptions=(Exception,))
    
    def _call_groq(
        self, 
        prompt: str, 
        temperature: float,
        max_tokens: int,
        timeout: int,
        groq_client: Optional[Any] = None
    ) -> str:
        """
        Call Groq API using current Llama model
        
        Args:
            prompt: User prompt
            temperature: Creativity parameter
            max_tokens: Max response length
            timeout: Request timeout in seconds
            
        Returns:
            Response text
        """
        try:
            client = groq_client or self.groq_client
            if client is None:
                raise RuntimeError("Groq client not initialized")
            response = client.chat.completions.create(
                model=self.GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout
            )
            
            if not response.choices:
                raise ValueError("Groq returned empty response")
            return response.choices[0].message.content or ""
        
        except Exception as e: # Catching general Exception for API call issues
            logger.debug(f"Groq API error: {type(e).__name__}")
            raise
    
    @with_retry(max_retries=2, base_delay=1.0, exceptions=(Exception,))
    
    def _call_cerebras(
        self, 
        prompt: str, 
        temperature: float,
        max_tokens: int,
        timeout: int,
        cerebras_key: Optional[str] = None
    ) -> str:
        '''
        Call Cerebras API (ultra-fast 2000+ tok/s inference)
        
        API Docs: https://inference-docs.cerebras.ai/api-reference/chat-completions
        '''
        try:
            if cerebras_key is None:
                cerebras_key = self.key_manager.get_working_key("cerebras")
            if not cerebras_key:
                raise RuntimeError("No working Cerebras API keys available")
            if not HAS_REQUESTS:
                raise RuntimeError("requests library not installed")
            
            headers = {
                "Authorization": f"Bearer {cerebras_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "llama3.1-8b",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False
            }
            
            response = requests.post(
                "https://api.cerebras.ai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"] or ""
            else:
                error_msg = f"Cerebras API error: {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg += f" - {error_data.get('error', {}).get('message', response.text)}"
                except:
                    error_msg += f" - {response.text[:200]}"
                raise RuntimeError(error_msg)
                
        except Exception as e:
            logger.error(f"Cerebras detailed error: {str(e)}")
            logger.debug(f"Cerebras API error: {type(e).__name__}")
            raise

    @with_retry(max_retries=2, base_delay=1.0, exceptions=(Exception,))
    
    def _call_openrouter(
        self, 
        prompt: str, 
        temperature: float,
        max_tokens: int,
        timeout: int,
        openrouter_key: Optional[str] = None,
        model: str = "meta-llama/llama-3.1-70b-instruct"
    ) -> str:
        '''
        Call OpenRouter API (access to 100+ models)
        
        Default model: meta-llama/llama-3.1-70b-instruct (free tier)
        Alternative: anthropic/claude-3.5-sonnet (for reasoning)
        
        API Docs: https://openrouter.ai/docs
        '''
        try:
            if openrouter_key is None:
                openrouter_key = self.key_manager.get_working_key("openrouter")
            if not openrouter_key:
                raise RuntimeError("No working OpenRouter API keys available")
            if not HAS_REQUESTS:
                raise RuntimeError("requests library not installed")
            
            headers = {
                "Authorization": f"Bearer {openrouter_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/InsightSwarm",  # Optional
                "X-Title": "InsightSwarm"  # Optional
            }
            
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"] or ""
            else:
                error_msg = f"OpenRouter API error: {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg += f" - {error_data.get('error', {}).get('message', response.text)}"
                except:
                    error_msg += f" - {response.text[:200]}"
                raise RuntimeError(error_msg)
                
        except Exception as e:
            logger.error(f"OpenRouter detailed error: {str(e)}")
            logger.debug(f"OpenRouter API error: {type(e).__name__}")
            raise
    
    @with_retry(max_retries=2, base_delay=1.0, exceptions=(Exception,))
    
    def _call_gemini(
        self, 
        prompt: str, 
        temperature: float,
        max_tokens: int,
        timeout: int,
        gemini_key: Optional[str] = None,
        response_mime_type: Optional[str] = None
    ) -> str:
        """
        Call Gemini API using google.genai (preferred) or google.generativeai (legacy) SDK
        
        Args:
            prompt: User prompt
            temperature: Creativity parameter
            max_tokens: Max response length
            timeout: Request timeout in seconds
            
        Returns:
            Response text
        """
        try:
            if gemini_key is None:
                gemini_key = self.key_manager.get_working_key("gemini")
            if not gemini_key:
                raise RuntimeError("No working Gemini API keys available")

            if self._gemini_mode == "genai" and self._genai_types is not None:
                from google import genai
                client = genai.Client(api_key=gemini_key)
                config_kwargs = {
                    "temperature": temperature,
                    "max_output_tokens": max_tokens
                }
                if response_mime_type:
                    config_kwargs["response_mime_type"] = response_mime_type
                config = self._genai_types.GenerateContentConfig(**config_kwargs)
                response = client.models.generate_content(
                    model=self.GEMINI_MODEL,
                    contents=prompt,
                    config=config,
                )
            else:
                if self._gemini_legacy is None:
                    try:
                        import google.generativeai as genai_legacy
                        self._gemini_legacy = genai_legacy
                    except ImportError:
                        raise RuntimeError("No Gemini SDK found. Run: pip install google-generativeai")
                with self._gemini_legacy_lock:
                    self._gemini_legacy.configure(api_key=gemini_key)
                    model = self._gemini_legacy.GenerativeModel(self.GEMINI_MODEL)
                    generation_config = {
                        "temperature": temperature,
                        "max_output_tokens": max_tokens,
                    }
                    if response_mime_type:
                        generation_config["response_mime_type"] = response_mime_type
                    response = model.generate_content(
                        prompt,
                        generation_config=generation_config,
                    )
            
            if not response or not response.text:
                raise ValueError("Gemini returned empty response")
            
            return response.text
        
        except Exception as e: # Catching general Exception for API call issues
            logger.debug(f"Gemini API error: {type(e).__name__}")
            raise
    
    def get_stats(self) -> dict:
        """
        Get usage statistics
        
        Returns:
            Dictionary with call counts (thread-safe snapshot)
        """
        with self._counter_lock:
            groq_count = self.groq_calls
            gemini_count = self.gemini_calls
        return {
            "groq_calls": groq_count,
            "gemini_calls": gemini_count,
            "cerebras_calls": self.cerebras_calls,
            "openrouter_calls": self.openrouter_calls,
            "total_calls": groq_count + gemini_count + self.cerebras_calls + self.openrouter_calls
        }

    def _try_offline_fallback(self) -> bool:
        """Check if offline fallback should be enabled"""
        return os.getenv("ENABLE_OFFLINE_FALLBACK", "false").lower() in ("true", "1", "yes")

    def _get_offline_fallback_text(self, prompt: str) -> str:
        """Return a safe text fallback when all providers fail."""
        return (
            "I'm currently unable to complete this request due to API rate limits "
            "or temporary outages. Please try again in a few moments."
        )

if __name__ == "__main__":
    print("\n" + "="*60)
    print("FreeLLMClient Test Suite")
    print("="*60)
    
    try:
        # Initialize client
        print("\n1. Initializing client...")
        client = FreeLLMClient()
        
        # Test 1: Simple question
        print("\n2. Test 1: Simple math question")
        response = client.call("What is 2+2? Answer with just the number.", timeout=30)
        print(f"   Response: {response}")
        
        # Test 2: Creative task
        print("\n3. Test 2: Creative task")
        response = client.call(
            "Write one sentence about why cats are interesting.",
            temperature=0.9,
            timeout=30
        )
        print(f"   Response: {response}")
        
        # Test 3: Longer response
        print("\n4. Test 3: Longer response")
        response = client.call(
            "Explain in 2 sentences what a multi-agent system is.",
            max_tokens=150,
            timeout=30
        )
        print(f"   Response: {response}")
        
        # Show stats
        print("\n5. Usage Statistics:")
        stats = client.get_stats()
        print(f"   Groq calls: {stats['groq_calls']}")
        print(f"   Gemini calls: {stats['gemini_calls']}")
        print(f"   Total calls: {stats['total_calls']}")
        
        print("\n" + "="*60)
        print("✅ All tests passed! FreeLLMClient is working.")
        print("="*60 + "\n")
    
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        logger.exception("Test suite error")
