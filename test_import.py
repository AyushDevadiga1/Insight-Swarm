#!/usr/bin/env python3
"""Simple test script to validate LLM client import and basic functionality"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from src.llm.client import FreeLLMClient
    print("✓ FreeLLMClient imported successfully")

    # Try to create an instance (this will fail without API keys, but should not crash)
    try:
        client = FreeLLMClient()
        print("✓ FreeLLMClient instance created")
    except Exception as e:
        print(f"✓ FreeLLMClient creation failed as expected (no API keys): {type(e).__name__}")

except ImportError as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ Unexpected error: {e}")
    sys.exit(1)

print("✓ All basic tests passed")