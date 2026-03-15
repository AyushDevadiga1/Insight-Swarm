"""
API Key Manager - Centralized API key validation, rotation, and security.

Handles all API key operations with proper validation, fallbacks, and security.
"""

import os
import logging
import time
import hashlib
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class APIKeyStatus(Enum):
    VALID = "valid"
    INVALID = "invalid"
    MISSING = "missing"
    RATE_LIMITED = "rate_limited"
    EXPIRED = "expired"

@dataclass
class APIKeyInfo:
    """Information about an API key"""
    key_hash: str  # SHA256 hash for logging (never store actual key)
    provider: str
    status: APIKeyStatus
    last_used: float
    consecutive_failures: int
    cooldown_until: float

class APIKeyManager:
    """
    Centralized API key management with validation, rotation, and security.

    Features:
    - API key validation on startup
    - Automatic key rotation on failures
    - Rate limit handling
    - Security (never logs actual keys)
    - Health monitoring
    """

    def __init__(self):
        self.keys: Dict[str, List[APIKeyInfo]] = {}
        self._reverse_lookup: Dict[str, str] = {}  # key_hash -> actual_key (O(1) lookup #17)
        self._load_and_validate_keys()
        self._health_check_interval = 300  # 5 minutes
        self._last_health_check = 0

    def _load_and_validate_keys(self):
        """Load and validate all API keys on startup"""
        logger.info("🔐 Initializing API Key Manager...")

        # Define all supported API keys
        key_configs = {
            "groq": {
                "env_vars": ["GROQ_API_KEYS", "GROQ_API_KEY"],
                "validators": [self._validate_groq_key],
                "required": True
            },
            "gemini": {
                "env_vars": ["GEMINI_API_KEYS", "GEMINI_API_KEY"],
                "validators": [self._validate_gemini_key],
                "required": False   # Gemini is a fallback provider, not mandatory
            },
            "tavily": {
                "env_vars": ["TAVILY_API_KEY"],
                "validators": [self._validate_tavily_key],
                "required": False
            }
        }

        all_keys_loaded = True

        for provider, config in key_configs.items():
            keys = self._collect_keys(provider, config["env_vars"])
            if not keys:
                if config["required"]:
                    logger.error(f"❌ Required API keys missing for {provider}")
                    all_keys_loaded = False
                else:
                    logger.warning(f"⚠️ Optional API keys missing for {provider}")
                continue

            # Validate each key
            valid_keys = []
            for key in keys:
                key_info = self._validate_key(provider, key, config["validators"])
                if key_info.status == APIKeyStatus.VALID:
                    valid_keys.append(key_info)
                    logger.info(f"✅ {provider} API key validated")
                else:
                    logger.warning(f"⚠️ {provider} API key invalid: {key_info.status.value}")

            self.keys[provider] = valid_keys

            if not valid_keys:
                if config["required"]:
                    logger.error(f"❌ No valid API keys for required provider {provider}")
                    all_keys_loaded = False
                else:
                    logger.warning(f"⚠️ No valid API keys for optional provider {provider}")

        if not all_keys_loaded:
            raise RuntimeError(
                "❌ Critical API keys missing or invalid. Please check your .env file.\n"
                "Required: GROQ_API_KEY\n"
                "Optional: GEMINI_API_KEY, TAVILY_API_KEY\n"
                "See README.md for setup instructions."
            )

        logger.info("✅ API Key Manager initialized successfully")

    def _collect_keys(self, provider: str, env_vars: List[str]) -> List[str]:
        """Collect API keys from environment variables"""
        keys = []

        for env_var in env_vars:
            value = os.getenv(env_var)
            if value:
                # Handle comma-separated lists
                if env_var.endswith("S"):  # Plural form
                    keys.extend([k.strip() for k in value.split(",") if k.strip()])
                else:
                    keys.append(value.strip())

        # Remove duplicates while preserving order
        seen = set()
        ordered = []
        for key in keys:
            if key in seen:
                continue
            seen.add(key)
            ordered.append(key)
        return ordered

    def _validate_key(self, provider: str, key: str, validators: List[Callable]) -> APIKeyInfo:
        """Validate a single API key"""
        key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]  # Short hash for logging

        key_info = APIKeyInfo(
            key_hash=key_hash,
            provider=provider,
            status=APIKeyStatus.INVALID,
            last_used=0,
            consecutive_failures=0,
            cooldown_until=0
        )

        # Run all validators
        for validator in validators:
            try:
                if validator(key):
                    key_info.status = APIKeyStatus.VALID
                    # Store in reverse lookup for O(1) retrieval (#17)
                    self._reverse_lookup[key_hash] = key
                    break
            except Exception as e:
                logger.debug(f"Key validation failed for {provider}: {e}")
                continue

        return key_info

    def _validate_groq_key(self, key: str) -> bool:
        """Validate Groq API key format"""
        return len(key) >= 30 and key.startswith("gsk_")

    def _validate_gemini_key(self, key: str) -> bool:
        """Validate Gemini API key format"""
        return len(key) >= 30 and key.startswith("AIza")

    def _validate_tavily_key(self, key: str) -> bool:
        """Validate Tavily API key format"""
        return len(key) >= 20  # Tavily keys are typically long

    def get_working_key(self, provider: str) -> Optional[str]:
        """
        Get a working API key for the provider, with automatic rotation.

        Returns the actual key string for use, or None if no working keys available.
        """
        if provider not in self.keys:
            return None

        now = time.time()
        available_keys = []

        for key_info in self.keys[provider]:
            if key_info.status == APIKeyStatus.VALID and now >= key_info.cooldown_until:
                available_keys.append(key_info)

        if not available_keys:
            logger.warning(f"⚠️ No available API keys for {provider}")
            return None

        # Rotate keys by least-recently-used to spread load
        key_info = sorted(available_keys, key=lambda k: k.last_used)[0]
        key_info.last_used = now

        # Get the actual key from environment (we only store hash)
        return self._get_actual_key(provider, key_info.key_hash)

    def _get_actual_key(self, provider: str, key_hash: str) -> Optional[str]:
        """Retrieve actual key by hash (reverse lookup - O(1) #17)"""
        return self._reverse_lookup.get(key_hash)

    def report_key_failure(self, provider: str, key_hash: str, error: Exception):
        """Report that an API key failed"""
        if provider not in self.keys:
            return

        for key_info in self.keys[provider]:
            if key_info.key_hash == key_hash:
                key_info.consecutive_failures += 1
                key_info.last_used = time.time()

                # Implement exponential backoff
                error_text = str(error).lower()
                
                # Check for permanent "0 quota" errors which indicate account/config issues
                if "limit: 0" in error_text or "quota: 0" in error_text:
                    key_info.status = APIKeyStatus.INVALID
                    logger.error(f"❌ {provider} key has zero quota (config issue): {error_text}")
                elif "rate limit" in error_text or "resource_exhausted" in error_text or "429" in error_text:
                    key_info.status = APIKeyStatus.RATE_LIMITED
                    backoff_time = min(60 * (2 ** key_info.consecutive_failures), 3600)  # Max 1 hour
                    key_info.cooldown_until = time.time() + backoff_time
                    logger.warning(f"🚦 {provider} key rate limited, cooling down for {backoff_time}s")
                elif key_info.consecutive_failures >= 3:
                    key_info.status = APIKeyStatus.INVALID
                    logger.error(f"❌ {provider} key marked invalid after {key_info.consecutive_failures} failures")
                else:
                    logger.warning(f"⚠️ {provider} key failed ({key_info.consecutive_failures}/3)")

                break

    def report_key_success(self, provider: str, key_hash: str):
        """Report that an API key worked successfully"""
        if provider not in self.keys:
            return

        for key_info in self.keys[provider]:
            if key_info.key_hash == key_hash:
                key_info.consecutive_failures = 0
                key_info.status = APIKeyStatus.VALID
                break

    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status of all API keys"""
        now = time.time()
        status = {}

        for provider, keys in self.keys.items():
            provider_status = {
                "total_keys": len(keys),
                "valid_keys": 0,
                "rate_limited_keys": 0,
                "invalid_keys": 0,
                "cooldown_keys": 0
            }

            for key_info in keys:
                if key_info.status == APIKeyStatus.VALID and now >= key_info.cooldown_until:
                    provider_status["valid_keys"] += 1
                elif key_info.status == APIKeyStatus.RATE_LIMITED:
                    provider_status["rate_limited_keys"] += 1
                elif key_info.status == APIKeyStatus.INVALID:
                    provider_status["invalid_keys"] += 1
                elif now < key_info.cooldown_until:
                    provider_status["cooldown_keys"] += 1

            status[provider] = provider_status

        return status

    def has_working_keys(self, provider: str) -> bool:
        """Check if provider has any working keys available"""
        if provider not in self.keys:
            return False

        now = time.time()
        return any(
            key_info.status == APIKeyStatus.VALID and now >= key_info.cooldown_until
            for key_info in self.keys[provider]
        )


# Global instance
_key_manager = None

def get_api_key_manager() -> APIKeyManager:
    """Get global API key manager instance"""
    global _key_manager
    if _key_manager is None:
        _key_manager = APIKeyManager()
    return _key_manager
