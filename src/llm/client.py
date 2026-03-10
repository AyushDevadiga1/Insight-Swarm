"""
FreeLLMClient - Manages LLM API calls with automatic fallback

This client tries Groq first (fast, 14,400 req/day), then falls back
to Gemini (1,500 req/day) if Groq fails or hits rate limits.
"""

import os
import threading
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class FreeLLMClient:
    """
    Unified client for multiple LLM providers with automatic fallback.
    
    Usage:
        client = FreeLLMClient()
        response = client.call("What is 2+2?")
        print(response)  # "4"
    """
    
    def __init__(self):
        """Initialize both Groq and Gemini clients"""
        
        self.groq_error = None
        self.gemini_error = None
        
        # Groq setup
        try:
            from groq import Groq
            self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
            self.groq_available = True
            print("✅ Groq client initialized")
        except Exception as e:
            self.groq_available = False
            self.groq_error = str(e)
            print(f"⚠️  Groq initialization failed: {e}")
        
        # Gemini setup
        try:
            from google.genai import Client
            # New google-genai uses Client
            self.genai_client = Client(api_key=os.getenv("GEMINI_API_KEY"))
            self.gemini_available = True
            print("✅ Gemini client initialized")
        except Exception as e:
            self.gemini_available = False
            self.gemini_error = str(e)
            print(f"⚠️  Gemini initialization failed: {e}")
        
        # Track usage with thread-safe counter lock
        self.groq_calls = 0
        self.gemini_calls = 0
        self._counter_lock = threading.Lock()
    
    def call(
        self, 
        prompt: str, 
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """
        Send prompt to LLM and get response.
        
        Tries Groq first, falls back to Gemini if Groq fails.
        
        Args:
            prompt: The prompt to send to the LLM
            temperature: Creativity level (0.0 = deterministic, 1.0 = creative)
            max_tokens: Maximum length of response
            
        Returns:
            Response text from the LLM
            
        Raises:
            Exception: If all LLM providers fail
        """
        
        groq_error = None
        gemini_error = None
        
        # Try Groq first (primary provider)
        if self.groq_available:
            try:
                response = self._call_groq(prompt, temperature, max_tokens)
                with self._counter_lock:
                    self.groq_calls += 1
                    call_count = self.groq_calls
                print(f"✅ Groq call #{call_count} successful")
                return response
            
            except Exception as e:
                groq_error = str(e)
                print(f"⚠️  Groq failed: {groq_error}")
                print("   Attempting Gemini fallback...")
        
        # Fallback to Gemini
        if self.gemini_available:
            try:
                response = self._call_gemini(prompt, temperature, max_tokens)
                with self._counter_lock:
                    self.gemini_calls += 1
                    call_count = self.gemini_calls
                print(f"✅ Gemini fallback call #{call_count} successful")
                return response
            
            except Exception as e:
                gemini_error = str(e)
                print(f"❌ Gemini also failed: {gemini_error}")
                raise Exception(
                    f"All LLM providers failed.\n"
                    f"Groq error: {groq_error if groq_error else self.groq_error if self.groq_available else 'Not available'}\n"
                    f"Gemini error: {gemini_error if gemini_error else self.gemini_error}"
                )
        
        # If we get here, both are unavailable
        raise Exception("No LLM providers available. Check your API keys in .env file")
    
    def _call_groq(
        self, 
        prompt: str, 
        temperature: float,
        max_tokens: int
    ) -> str:
        """
        Call Groq API using a current Llama model
        
        Args:
            prompt: User prompt
            temperature: Creativity parameter
            max_tokens: Max response length
            
        Returns:
            Response text
        """
        response = self.groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        if not response.choices:
            raise ValueError("Groq returned empty response")
        return response.choices[0].message.content    
    def _call_gemini(
        self, 
        prompt: str, 
        temperature: float,
        max_tokens: int
    ) -> str:
        """
        Call Gemini API using Gemini 2.0 Flash model
        
        Args:
            prompt: User prompt
            temperature: Creativity parameter
            max_tokens: Max response length
            
        Returns:
            Response text
        """
        config = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        
        response = self.genai_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=config
        )
        
        return response.text
    
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
    
    # Initialize client
    print("\n1. Initializing client...")
    client = FreeLLMClient()
    
    # Test 1: Simple question
    print("\n2. Test 1: Simple math question")
    response = client.call("What is 2+2? Answer with just the number.")
    print(f"   Response: {response}")
    
    # Test 2: Creative task
    print("\n3. Test 2: Creative task")
    response = client.call(
        "Write one sentence about why cats are interesting.",
        temperature=0.9
    )
    print(f"   Response: {response}")
    
    # Test 3: Longer response
    print("\n4. Test 3: Longer response")
    response = client.call(
        "Explain in 2 sentences what a multi-agent system is.",
        max_tokens=150
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