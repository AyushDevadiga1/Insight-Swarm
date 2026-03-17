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

load_dotenv()
logger = logging.getLogger(__name__)

from src.utils.api_key_manager import get_api_key_manager

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
        self.groq_available = False
        self.gemini_available = False
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
        
        # Initialize providers using API key manager
        self._init_providers()
    
    def _init_providers(self):
        """Initialize LLM providers using API key manager"""
        try:
            # Initialize Groq
            groq_key = self.key_manager.get_working_key("groq")
            if groq_key:
                from groq import Groq
                self.groq_client = Groq(api_key=groq_key)
                self.groq_available = True
                logger.info("✅ Groq client initialized")
            else:
                self.groq_available = False
                self.groq_error = "No working Groq API keys available"
                logger.warning("⚠️ Groq client not available")
                
        except Exception as e: # Catching general Exception for initialization issues
            self.groq_available = False
            self.groq_error = str(e)
            logger.warning(f"⚠️ Groq initialization failed: {type(e).__name__}")
            
        try:
            # Initialize Gemini
            gemini_key = self.key_manager.get_working_key("gemini")
            if gemini_key:
                try:
                    from google import genai
                    from google.genai import types as genai_types
                    self._genai_types = genai_types
                    self.genai_client = genai.Client(api_key=gemini_key)
                    self.gemini_available = True
                    self._gemini_mode = "genai"
                    logger.info("✅ Gemini client initialized (google.genai)")
                except (ImportError, AttributeError):
                    import google.generativeai as genai
                    self._gemini_legacy = genai
                    genai.configure(api_key=gemini_key)
                    self.genai_client = genai.GenerativeModel(self.GEMINI_MODEL)
                    self.gemini_available = True
                    self._gemini_mode = "legacy"
                    logger.warning("⚠️ Using legacy Gemini client")
            else:
                self.gemini_available = False
                self.gemini_error = "No working Gemini API keys available"
                logger.warning("⚠️ Gemini client not available")
                
        except Exception as e: # Catching general Exception for initialization issues
            self.gemini_available = False
            self.gemini_error = str(e)
            logger.warning(f"⚠️ Gemini initialization failed: {type(e).__name__}")
            
        if not self.groq_available and not self.gemini_available:
            offline = os.getenv("ENABLE_OFFLINE_FALLBACK", "false").lower() in ("true", "1", "yes")
            if offline:
                logger.warning("⚠️ No LLM providers available — running in offline fallback mode.")
            else:
                raise RuntimeError(
                    "No LLM providers available. Check GROQ_API_KEY / GEMINI_API_KEY in .env file.\n"
                    "Set ENABLE_OFFLINE_FALLBACK=1 to start without API keys."
                )

    def _is_rate_limit_error(self, error: Exception) -> bool:
        text = str(error).lower()
        return (
            "rate limit" in text
            or "rate_limit" in text
            or "resource_exhausted" in text
            or "429" in text
        )

    def _provider_order(self, preferred_provider: Optional[str] = None) -> list:
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

    def call_structured(
        self,
        prompt: str,
        output_schema: Type[BaseModel],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        max_retries: int = 2,
        preferred_provider: Optional[str] = None
    ) -> Any:
        """
        Calls LLM with mandatory JSON output.
        ENFORCES rate limits and respects preferred provider order.
        """
        json_prompt = f"{prompt}\n\nIMPORTANT: You MUST return a valid JSON object matching this schema:\n{output_schema.schema_json(indent=2)}"
        
        last_error = None
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
                            # #4: Atomic timestamp append before the call
                            self.groq_last_call_times.append(time.time())

                        # #15: Guard fast fail if Groq client not initialised
                        if self.groq_client is None:
                            raise RuntimeError("Groq client not initialized")

                        # Update client with current working key
                        from groq import Groq
                        current_client = Groq(api_key=groq_key)

                        response = self._call_groq(
                            json_prompt, temperature, max_tokens, timeout=30, groq_client=current_client
                        )
                        cleaned_response = self._clean_json_response(response)
                        result = output_schema.parse_raw(cleaned_response)
                        
                        self.key_manager.report_key_success("groq", groq_key_hash)
                        self._set_next_preference("groq")
                        return result

                    except Exception as e:
                        last_error = e
                        self.key_manager.report_key_failure("groq", groq_key_hash, e)
                        
                        err_str = str(e).lower()
                        if any(kw in err_str for kw in ["429", "rate limit", "quota", "exceeded",
                                                         "limit reached", "model_decommissioned"]):
                            logger.warning(f"Groq quota/limit error in structured call: {e}")
                            break # Try next provider
                        
                        logger.warning(f"Groq structured attempt {attempt+1} failed: {e}")
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
                            # #4: Atomic timestamp append before the call
                            self.gemini_last_call_times.append(time.time())

                        # #15: Guard fast fail if Gemini client not initialised
                        if self._gemini_mode == "genai" and self.genai_client is None:
                            raise RuntimeError("Gemini GenAI client not initialized")
                        if self._gemini_mode == "legacy" and self._gemini_legacy is None:
                            raise RuntimeError("Gemini legacy client not initialized")

                        response = self._call_gemini(
                            json_prompt, temperature, max_tokens, timeout=30, gemini_key=gemini_key
                        )
                        cleaned_response = self._clean_json_response(response)
                        result = output_schema.parse_raw(cleaned_response)
                        
                        self.key_manager.report_key_success("gemini", gemini_key_hash)
                        self._set_next_preference("gemini")
                        return result

                    except Exception as e:
                        last_error = e
                        self.key_manager.report_key_failure("gemini", gemini_key_hash, e)
                        
                        err_str = str(e).lower()
                        if any(kw in err_str for kw in ["429", "rate limit", "quota", "exceeded", "limit reached"]):
                            logger.warning(f"Gemini quota/limit error in structured call: {e}")
                            break # Try next provider
                            
                        logger.warning(f"Gemini structured attempt {attempt+1} failed: {e}")
                        if attempt < max_retries:
                            time.sleep(1)

        if not attempted_any:
            raise RuntimeError("No LLM providers available for structured call.")
            
        logger.error(f"All LLM structured calls failed. Last error: {last_error}")
        raise RuntimeError(f"Failed to get structured output from LLM: {last_error}")
    
    def _check_rate_limit(self, provider: str, call_times: list) -> bool:
        """
        Check if rate limit exceeded for provider
        
        Args:
            provider: "groq" or "gemini"
            call_times: List of recent call timestamps
            
        Returns:
            True if within rate limit, False otherwise
        """
        now = time.time()
        one_minute_ago = now - 60
        
        # Filter and update list to keep only recent calls (thread-safe replacement)
        recent = [t for t in call_times if t > one_minute_ago]
        call_times.clear()
        call_times.extend(recent)
        
        recent_calls = len(call_times)
        
        if recent_calls >= self.MAX_CALLS_PER_MINUTE:
            logger.warning(f"⚠️  Rate limit approaching for {provider}: {recent_calls} calls in last minute")
            return False
        
        return True
    
    def _validate_prompt(self, prompt: str) -> None:
        """
        Validate prompt before sending to LLM
        
        Args:
            prompt: User prompt
            
        Raises:
            ValueError: If prompt is invalid
        """
        if not prompt or not isinstance(prompt, str):
            raise ValueError("Prompt must be a non-empty string")
        
        if len(prompt.strip()) == 0:
            raise ValueError("Prompt cannot be empty or whitespace-only")
        
        if len(prompt) > 100000:
            raise ValueError("Prompt exceeds maximum length of 100,000 characters")
    
    def _validate_response(self, response: str) -> None:
        """
        Validate LLM response
        
        Args:
            response: Response text from LLM
            
        Raises:
            ValueError: If response is invalid
        """
        if response is None:
            raise ValueError("LLM returned None response")
        
        if not isinstance(response, str):
            raise ValueError(f"LLM response must be string, got {type(response).__name__}")
        
        if len(response.strip()) == 0:
            raise ValueError("LLM returned empty response")
    
    def _clean_json_response(self, response: str) -> str:
        """Extract JSON from markdown code blocks if present."""
        if not response:
            return response
            
        # Clean up common LLM garbage
        response = response.strip()
        
        # Remove markdown code blocks
        if "```" in response:
            # Handle ```json ... ``` or just ``` ... ```
            match = re.search(r"```(?:json)?\s*(.*?)\s*```", response, re.DOTALL)
            if match:
                return match.group(1).strip()
        
        return response
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((Exception,)),
        reraise=True
    )
    def call(self, prompt: str, temperature: float = 0.7, max_tokens: int = 1000, timeout: int = 30) -> str:
        """
        Send prompt to LLM and get response.
        Tries Groq first, falls back to Gemini if Groq fails.
        
        Args:
            prompt: The prompt to send to the LLM
            temperature: Creativity level (0.0-2.0, default 0.7)
            max_tokens: Maximum length of response (1-4000, default 1000)
            timeout: Request timeout in seconds (1-300, default 30)
            
        Returns:
            Response text from the LLM
            
        Raises:
            ValueError: If inputs are invalid
            RuntimeError: If all LLM providers fail
        """
        # Validate inputs
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
        
        groq_error = None
        gemini_error = None
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
                        rate_limit_reached = not self._check_rate_limit("groq", self.groq_last_call_times)
                        if not rate_limit_reached:
                            # #4: Atomic timestamp append before the call
                            self.groq_last_call_times.append(time.time())
                            
                    if rate_limit_reached:
                        logger.info("   Groq rate limit reached, trying Gemini fallback...")
                    else:
                        if self.groq_client is None:
                            raise RuntimeError("Groq client not initialized")
                        response = self._call_groq(prompt, temperature, max_tokens, timeout)
                        self._validate_response(response)
                        with self._counter_lock:
                            self.groq_calls += 1
                            call_count = self.groq_calls
                        logger.info(f"✅ Groq call #{call_count} successful")
                        self._set_next_preference("groq")
                        self.key_manager.report_key_success("groq", groq_key_hash)
                        return response
                except Exception as e: # Catching general Exception for API call issues
                    if self._is_rate_limit_error(e):
                        retry_after = self._extract_retry_after(str(e))
                        self.key_manager.report_key_failure("groq", groq_key_hash, e)
                        last_error = RateLimitError("groq", str(e), retry_after)
                        continue
                    groq_error = str(e)
                    last_error = e
                    self.key_manager.report_key_failure("groq", groq_key_hash, e)
                    logger.warning(f"⚠️  Groq failed: {type(e).__name__}")
                    logger.debug(f"   Error details: {groq_error[:100]}")
                    logger.info("   Attempting Gemini fallback...")

            if provider == "gemini" and self.gemini_available and self.key_manager.has_working_keys("gemini"):
                gemini_key = self.key_manager.get_working_key("gemini")
                if not gemini_key:
                    continue
                gemini_key_hash = hashlib.sha256(gemini_key.encode()).hexdigest()[:16]
                attempted_any = True
                try:
                    with self._counter_lock:
                        rate_limit_reached = not self._check_rate_limit("gemini", self.gemini_last_call_times)
                        if not rate_limit_reached:
                            # #4: Atomic timestamp append before the call
                            self.gemini_last_call_times.append(time.time())
                            
                    if rate_limit_reached:
                        logger.warning("❌ Gemini rate limit also reached")
                    else:
                        # #15: Guard fast fail if Gemini client not initialised
                        if self._gemini_mode == "genai" and self.genai_client is None:
                            raise RuntimeError("Gemini GenAI client not initialized")
                        if self._gemini_mode == "legacy" and self._gemini_legacy is None:
                            raise RuntimeError("Gemini legacy client not initialized")
                            
                        response = self._call_gemini(
                            prompt,
                            temperature,
                            max_tokens,
                            timeout,
                            gemini_key=gemini_key
                        )
                        self._validate_response(response)
                        with self._counter_lock:
                            self.gemini_calls += 1
                            call_count = self.gemini_calls
                        logger.info(f"✅ Gemini call #{call_count} successful")
                        self._set_next_preference("gemini")
                        self.key_manager.report_key_success("gemini", gemini_key_hash)
                        return response
                except Exception as e: # Catching general Exception for API call issues
                    if self._is_rate_limit_error(e):
                        retry_after = self._extract_retry_after(str(e))
                        self.key_manager.report_key_failure("gemini", gemini_key_hash, e)
                        last_error = RateLimitError("gemini", str(e), retry_after)
                        continue
                    gemini_error = str(e)
                    last_error = e
                    self.key_manager.report_key_failure("gemini", gemini_key_hash, e)
                    logger.error(f"❌ Gemini also failed: {type(e).__name__}")
                    logger.debug(f"   Error details: {gemini_error[:100]}")

        if not attempted_any:
            raise RateLimitError("all", "No available API keys (all providers rate limited).")
        if isinstance(last_error, RateLimitError):
            raise last_error
        
        # Both providers failed - try offline fallback
        if self._try_offline_fallback():
            logger.warning("🔄 Using offline fallback mode")
            return self._get_offline_fallback_text(prompt)
        
        # Both providers failed
        error_msg = "All LLM providers failed. Check your API keys and network connection."
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    def _is_rate_limit_exception(self, e: Exception) -> bool:
        return self._is_rate_limit_error(e)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        # Using lambda since we don't have self in the decorator scope easily, wait, 
        # tenacity retry_if_exception needs a boolean returning callable.
        # It's better to just catch the RateLimitError bubbled up or check string:
        retry=retry_if_exception(lambda e: "rate limit" in str(e).lower() or "429" in str(e) or "exhausted" in str(e).lower()),
        reraise=True
    )
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
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception(lambda e: "rate limit" in str(e).lower() or "429" in str(e) or "exhausted" in str(e).lower()),
        reraise=True
    )
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
                    raise RuntimeError("Legacy Gemini client not initialized")
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
            "total_calls": groq_count + gemini_count
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
