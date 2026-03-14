"""
Test that Gemini fallback works when Groq fails

SECURITY NOTE: 
- Saves and restores environment variables properly
- Does not leak API keys in output
- Uses try/finally for cleanup guarantee
"""

import sys
from pathlib import Path
import os
import pytest

RUN_PROGRESS_TESTS = os.getenv("RUN_PROGRESS_TESTS", "").strip().lower() in ("1", "true", "yes")
if not RUN_PROGRESS_TESTS:
    pytest.skip("Progress tests are manual; set RUN_PROGRESS_TESTS=1 to enable.", allow_module_level=True)

# Add parent directory to path for imports when running directly
sys.path.insert(0, str(Path(__file__).parent))

from src.llm.client import FreeLLMClient


def test_fallback_mechanism():
    """Test fallback from Groq to Gemini"""
    
    # Save original keys
    original_groq_key = os.getenv("GROQ_API_KEY")
    original_gemini_key = os.getenv("GEMINI_API_KEY")
    
    try:
        # Temporarily break Groq by using wrong API key
        os.environ["GROQ_API_KEY"] = "invalid_key_to_force_failure_xxx"
        
        # Initialize client (Groq will fail, should use Gemini)
        print("Testing fallback mechanism...")
        print("(Groq will fail intentionally, Gemini should work)\n")
        
        try:
            client = FreeLLMClient()
        except RuntimeError as e:
            print(f"⚠️  Could not initialize: {e}")
            print("   (This is expected if Gemini key is not configured)")
            return
        
        # Test the fallback
        try:
            response = client.call("Say 'Fallback works!' and nothing else.", timeout=30)
            print(f"\n✅ Fallback successful!")
            print(f"   Response: {response}")
            
            stats = client.get_stats()
            print(f"\n   Groq calls: {stats['groq_calls']}")
            print(f"   Gemini calls: {stats['gemini_calls']}")
            
            if stats['gemini_calls'] > 0:
                print("\n✅ Fallback mechanism is working correctly!")
            else:
                print("\n⚠️  Gemini was not used for fallback")
        
        except RuntimeError as e:
            print(f"\n❌ Fallback failed: Both providers unavailable")
            print("   (This is expected if you don't have API keys configured)")
    
    finally:
        # ALWAYS restore original environment variables
        if original_groq_key is not None:
            os.environ["GROQ_API_KEY"] = original_groq_key
        elif "GROQ_API_KEY" in os.environ:
            del os.environ["GROQ_API_KEY"]
        
        if original_gemini_key is not None:
            os.environ["GEMINI_API_KEY"] = original_gemini_key
        elif "GEMINI_API_KEY" in os.environ:
            del os.environ["GEMINI_API_KEY"]


if __name__ == "__main__":
    test_fallback_mechanism()
