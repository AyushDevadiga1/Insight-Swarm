"""
Pytest configuration and fixtures

Provides:
- Test isolation
- Proper setup/teardown
- Environment cleanup
- Fixture management
"""

import os
os.environ.setdefault("ENABLE_OFFLINE_FALLBACK", "1")
os.environ.setdefault("GROQ_API_KEY",   "gsk_ci_placeholder_not_real_key_abcdefgh")
os.environ.setdefault("GEMINI_API_KEY",  "AIzaSy_ci_placeholder_not_real_key_xyz")

import pytest
import logging
from typing import Generator


# Configure logging for tests
logging.basicConfig(
    level=logging.WARNING,
    format='%(name)s - %(levelname)s - %(message)s'
)


@pytest.fixture(scope="session")
def env_vars():
    """
    Verify environment variables are set properly.
    Store original values to restore after tests.
    """
    original_groq = os.getenv("GROQ_API_KEY")
    original_gemini = os.getenv("GEMINI_API_KEY")
    
    yield {
        "GROQ_API_KEY": original_groq,
        "GEMINI_API_KEY": original_gemini
    }
    
    # Cleanup (restore originals)
    if original_groq is not None:
        os.environ["GROQ_API_KEY"] = original_groq
    elif "GROQ_API_KEY" in os.environ:
        del os.environ["GROQ_API_KEY"]
    
    if original_gemini is not None:
        os.environ["GEMINI_API_KEY"] = original_gemini
    elif "GEMINI_API_KEY" in os.environ:
        del os.environ["GEMINI_API_KEY"]


@pytest.fixture(autouse=True)
def cleanup_environment():
    """
    Ensure environment is clean before and after each test.
    Prevents test pollution.
    """
    yield
    # No cleanup needed as we use try/finally in tests


def pytest_configure(config):
    """
    Configure pytest with custom markers.
    """
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (slow)"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test (fast)"
    )
    config.addinivalue_line(
        "markers", "security: mark test as security-focused test"
    )


def pytest_collection_modifyitems(config, items):
    """
    Automatically mark tests based on their location.
    """
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
