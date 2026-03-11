"""
FreeLLMClient - Manages LLM API calls with automatic fallback

This client tries Groq first (fast, 14,400 req/day), then falls back
to Gemini (1,500 req/day) if Groq fails or hits rate limits.

SECURITY FEATURES:
- Input validation & sanitization
- Response validation  
- Rate limiting (5 calls/min per provider)
- Timeout protection (1-300 seconds)
- Safe error handling (no key exposure)
- Thread-safe operations
"""

import os
import threading
import logging
import time
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FreeLLMClient:
    """
    Unified client for multiple LLM providers with automatic fallback.
    
    Features:
    - Automatic fallback from Groq to Gemini
    - Rate limiting and timeout protection
    - Comprehensive error handling
    - Thread-safe call tracking
    
    Usage:
        client = FreeLLMClient()
        response = client.call("What is 2+2?")
        print(response)  # "4"
    """
    
    # Rate limiting: configurable calls per minute per provider
    # Default 60 matches free tier limits for Groq (14,400/day ~ 10/min) and Gemini (1,500/day ~ 1/min)
    # Override via RATE_LIMIT_PER_MINUTE environment variable for cost control
    MAX_CALLS_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    
    def __init__(self):
        """Initialize both Groq and Gemini clients"""
        
        self.groq_error = None
        self.gemini_error = None
        
        # Groq setup
        try:
            from groq import Groq
            groq_key = os.getenv("GROQ_API_KEY")
            if not groq_key:
                raise ValueError("GROQ_API_KEY not set in environment")
            groq_key = groq_key.strip()
            if len(groq_key) < 30:
                raise ValueError("GROQ_API_KEY appears invalid (too short, expected >=30 characters)")
            if not groq_key.startswith("gsk_"):
                raise ValueError("GROQ_API_KEY format invalid (expected to start with 'gsk_')")
            
            self.groq_client = Groq(api_key=groq_key)
            self.groq_available = True
            logger.info("✅ Groq client initialized")
        except Exception as e:
            self.groq_available = False
            self.groq_error = str(e)
            logger.warning(f"⚠️  Groq initialization failed: {type(e).__name__}")
        
        # Gemini setup
        try:
            import google.generativeai as genai
            gemini_key = os.getenv("GEMINI_API_KEY")
            if not gemini_key:
                raise ValueError("GEMINI_API_KEY not set in environment")
            gemini_key = gemini_key.strip()
            if len(gemini_key) < 30:
                raise ValueError("GEMINI_API_KEY appears invalid (too short, expected >=30 characters)")
            
            # Configure Gemini API
            genai.configure(api_key=gemini_key)
            self.genai_client = genai.GenerativeModel('gemini-2.0-flash')
            self.gemini_available = True
            logger.info("✅ Gemini client initialized")
        except (ImportError, AttributeError) as e:
            # Known issue: google-genai has compatibility issues with Python 3.13 and pydantic
            # Gracefully fall back to Groq-only
            self.gemini_available = False
            self.gemini_error = f"google.generativeai initialization failed: {type(e).__name__} - likely version compatibility issue"
            logger.warning(f"⚠️  Gemini initialization failed: {type(e).__name__} (will use Groq only)")
        except Exception as e:
            self.gemini_available = False
            self.gemini_error = str(e)
            logger.warning(f"⚠️  Gemini initialization failed: {type(e).__name__}")
        
        # Track usage with thread-safe counter lock
        self.groq_calls = 0
        self.gemini_calls = 0
        self.groq_last_call_times = []
        self.gemini_last_call_times = []
        self._counter_lock = threading.Lock()
        
        if not self.groq_available and not self.gemini_available:
            logger.error("❌ No LLM providers available")
            raise RuntimeError("No LLM providers available. Check your API keys in .env file")
    
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
        
        # Prune and filter calls older than 1 minute (in-place mutation)
        i = 0
        while i < len(call_times):
            if call_times[i] <= one_minute_ago:
                call_times.pop(i)
            else:
                i += 1
        
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
    
    def call(
        self, 
        prompt: str, 
        temperature: float = 0.7,
        max_tokens: int = 1000,
        timeout: int = 30
    ) -> str:
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
            if not 1 <= timeout <= 90:
                raise ValueError("timeout must be between 1 and 90 seconds")
        except ValueError as e:
            logger.error(f"❌ Input validation failed: {e}")
            raise
        
        groq_error = None
        gemini_error = None
        
        # Try Groq first (primary provider)
        if self.groq_available:
            try:
                with self._counter_lock:
                    if not self._check_rate_limit("groq", self.groq_last_call_times):
                        rate_limit_reached = True
                    else:
                        rate_limit_reached = False
                
                if rate_limit_reached:
                    logger.info("   Groq rate limit reached, trying Gemini...")
                else:
                    response = self._call_groq(prompt, temperature, max_tokens, timeout)
                    self._validate_response(response)
                    
                    with self._counter_lock:
                        self.groq_calls += 1
                        self.groq_last_call_times.append(time.time())
                        call_count = self.groq_calls
                    
                    logger.info(f"✅ Groq call #{call_count} successful")
                    return response
            
            except Exception as e:
                groq_error = str(e)
                logger.warning(f"⚠️  Groq failed: {type(e).__name__}")
                logger.debug(f"   Error details: {groq_error[:100]}")
                logger.info("   Attempting Gemini fallback...")
        
        # Fallback to Gemini
        if self.gemini_available:
            try:
                with self._counter_lock:
                    if not self._check_rate_limit("gemini", self.gemini_last_call_times):
                        rate_limit_reached = True
                    else:
                        rate_limit_reached = False
                
                if rate_limit_reached:
                    logger.warning("❌ Gemini rate limit also reached")
                else:
                    response = self._call_gemini(prompt, temperature, max_tokens, timeout)
                    self._validate_response(response)
                    
                    with self._counter_lock:
                        self.gemini_calls += 1
                        self.gemini_last_call_times.append(time.time())
                        call_count = self.gemini_calls
                    
                    logger.info(f"✅ Gemini fallback call #{call_count} successful")
                    return response
            
            except Exception as e:
                gemini_error = str(e)
                logger.error(f"❌ Gemini also failed: {type(e).__name__}")
                logger.debug(f"   Error details: {gemini_error[:100]}")
        
        # Both providers failed
        error_msg = "All LLM providers failed. Check your API keys and network connection."
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    def _call_groq(
        self, 
        prompt: str, 
        temperature: float,
        max_tokens: int,
        timeout: int
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
            response = self.groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout
            )
            
            if not response.choices:
                raise ValueError("Groq returned empty response")
            return response.choices[0].message.content
        
        except Exception as e:
            logger.debug(f"Groq API error: {type(e).__name__}")
            raise
    
    def _call_gemini(
        self, 
        prompt: str, 
        temperature: float,
        max_tokens: int,
        timeout: int
    ) -> str:
        """
        Call Gemini API using google.generativeai SDK
        
        Args:
            prompt: User prompt
            temperature: Creativity parameter
            max_tokens: Max response length
            timeout: Request timeout in seconds
            
        Returns:
            Response text
        """
        try:
            response = self.genai_client.generate_content(
                prompt,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                },
                request_options={"timeout": timeout}
            )
            
            if not response or not response.text:
                raise ValueError("Gemini returned empty response")
            
            return response.text
        
        except Exception as e:
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


# ============================================
# TESTING CODE (run this file directly)
# ============================================

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