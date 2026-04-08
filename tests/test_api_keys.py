"""
tests/test_api_keys.py — RENAMED from old Cerebras-only script.

This file is intentionally minimal. The real API key test suite lives at:
    scripts/test_api_keys.py

Keeping this file here (but as a non-test module) caused a pytest collection
error due to a module name collision with scripts/test_api_keys.py.

Resolution: this file no longer defines any test_ functions.
To run the API key test suite, use:
    python scripts/test_api_keys.py
    python scripts/test_api_keys.py --format-only
    python scripts/test_api_keys.py --verbose
"""

# This file is intentionally left without test functions.
# The old content (a bare Cerebras API call script with no test functions)
# was causing pytest to try to collect it as a test module, resulting in:
#   ERROR: import file mismatch — scripts/test_api_keys.py vs tests/test_api_keys.py
