"""
Test that Gemini fallback works when Groq fails
"""

from src.llm.client import FreeLLMClient
import os

# Temporarily break Groq by using wrong API key
original_key = os.getenv("GROQ_API_KEY")
os.environ["GROQ_API_KEY"] = "invalid_key_to_force_failure"

# Initialize client (Groq will fail, should use Gemini)
print("Testing fallback mechanism...")
print("(Groq will fail intentionally, Gemini should work)\n")

client = FreeLLMClient()

try:
    response = client.call("Say 'Fallback works!' and nothing else.")
    print(f"\n✅ Fallback successful!")
    print(f"   Response: {response}")
    
    stats = client.get_stats()
    print(f"\n   Groq calls: {stats['groq_calls']}")
    print(f"   Gemini calls: {stats['gemini_calls']}")
    
    if stats['gemini_calls'] > 0:
        print("\n🎉 Fallback mechanism is working correctly!")
    
except Exception as e:
    print(f"\n❌ Fallback failed: {e}")

# Restore original key
os.environ["GROQ_API_KEY"] = original_key