"""
InsightSwarm Health Monitor
Run this script to verify the health of all LLM providers and API keys.
"""
import sys
import os
import logging

# Add root to sys.path
sys.path.insert(0, os.getcwd())

from src.utils.api_key_manager import get_api_key_manager
from src.llm.client import FreeLLMClient

# Suppress noisy logs during health check
logging.getLogger("src.llm.client").setLevel(logging.WARNING)

def check_health():
    print("="*50)
    print("🔍 INSIGHTSWARM SYSTEM HEALTH CHECK")
    print("="*50)
    
    # 1. API Key Manager Check
    print("\n[1] API Key Status:")
    manager = get_api_key_manager()
    health = manager.get_health_status()
    
    total_valid = 0
    for provider, status in health.items():
        valid = status['valid_keys']
        total = status['total_keys']
        symbol = "✅" if valid > 0 else "❌"
        print(f"  {symbol} {provider:12}: {valid}/{total} working")
        total_valid += valid
    
    if total_valid == 0:
        print("\n❌ CRITICAL: No valid API keys found. Check your .env file.")
        return

    # 2. LLM Provider Connectivity
    print("\n[2] Live Provider Connectivity (10-token test):")
    client = FreeLLMClient()
    
    providers_to_test = []
    if client.groq_available: providers_to_test.append('groq')
    if client.cerebras_available: providers_to_test.append('cerebras')
    if client.openrouter_available: providers_to_test.append('openrouter')
    if client.gemini_available: providers_to_test.append('gemini')
    
    if not providers_to_test:
        print("  ❌ No providers available for testing.")
    else:
        for provider in providers_to_test:
            try:
                # Simple connectivity test
                response = client.call(
                    "Say 'OK'", 
                    max_tokens=5, 
                    preferred_provider=provider
                )
                if "OK" in response.upper():
                    print(f"  ✅ {provider:12}: SUCCESS")
                else:
                    print(f"  ⚠️ {provider:12}: PARTIAL (Response: {response[:20]}...)")
            except Exception as e:
                print(f"  ❌ {provider:12}: FAILED ({str(e)[:50]})")

    # 3. Environment Check
    print("\n[3] Environment Check:")
    print(f"  ✅ Python Version: {sys.version.split()[0]}")
    print(f"  ✅ Working Dir:   {os.getcwd()}")
    
    print("\n" + "="*50)
    print("🎉 Health Check Complete")
    print("="*50 + "\n")

if __name__ == "__main__":
    check_health()
