import sys
import re

client_path = r"c:\Users\hp\Desktop\InsightSwarm\src\llm\client.py"
with open(client_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
skip = False

for idx, line in enumerate(lines):
    # Locate where `call` currently has its decorators or `call_structured` starts.
    # Actually wait. `call_structured` doesn't have a decorator.
    if line.startswith("    def call_structured("):
        skip = True
        
        # INSERT the new unified methods
        new_methods = """    def _execute_provider(
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
        json_prompt = f"{prompt}\\n\\nIMPORTANT: You MUST return a valid JSON object matching this schema:\\n{output_schema.schema_json(indent=2)}"
        
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
"""
        new_lines.append(new_methods)
        continue

    if skip:
        # We need to skip `call()` which has a decorator. So let's look for `def _is_rate_limit_exception`.
        # However, `call()` starts right above `_is_rate_limit_exception`. The decorator would have been skipped because we started skipping AT `call_structured`.
        # Wait, what if `call` had decorators BEFORE `call_structured`? No, `call_structured` is defined before `call`. So the `@retry` above `call` is skipped automatically!
        if line.startswith("    def _is_rate_limit_exception("):
            skip = False
        else:
            continue

    # Clean up the `@retry` on `call` if there was an stray one. In our case `call_structured()` precedes `call()`, 
    # and wait! Above `call()` there's a `@retry(stop=stop_after_attempt...)`. Does our skip catch it?
    # Yes, because `skip` becomes `True` at `call_structured(` and remains `True` over `call` and its decorators, until `_is_rate_limit_exception`.

    new_lines.append(line)

code = "".join(new_lines)

# 1. Add resilient imports
imports_addition = """
from src.utils.api_key_manager import get_api_key_manager
from src.resilience.circuit_breaker import CircuitBreaker
from src.resilience.fallback_handler import FallbackHandler
from src.resilience.retry_handler import with_retry
"""
code = code.replace("from src.utils.api_key_manager import get_api_key_manager", imports_addition)

# 2. Add circuit breakers to __init__
init_addition = """
        self.cerebras_error: Optional[str] = None
        self.openrouter_error: Optional[str] = None
    
        # Resilience components
        self.circuit_breakers = {
            "cerebras": CircuitBreaker("cerebras", failure_threshold=3, recovery_timeout=60.0),
            "openrouter": CircuitBreaker("openrouter", failure_threshold=3, recovery_timeout=60.0),
            "groq": CircuitBreaker("groq", failure_threshold=3, recovery_timeout=60.0),
            "gemini": CircuitBreaker("gemini", failure_threshold=3, recovery_timeout=60.0),
        }
"""
code = code.replace("""        self.cerebras_error: Optional[str] = None
        self.openrouter_error: Optional[str] = None""", init_addition)

# Remove the `@retry` blocks and replace with `@with_retry`
# Current decorators look like:
# @retry(
#     stop=stop_after_attempt(3),
#     wait=wait_exponential(multiplier=1, min=2, max=30),
#     retry=retry_if_exception(lambda e: "rate limit" in str(e).lower() or "429" in str(e)),
#     reraise=True
# )
code = re.sub(
    r"@retry\([\s\S]*?reraise=True\n\s*\)",
    "@with_retry(max_retries=2, base_delay=1.0, exceptions=(Exception,))\n    ",
    code
)

with open(client_path, "w", encoding="utf-8") as f:
    f.write(code)

print("done")
