"""
FIX FILE 5 — src/utils/api_key_manager.py  (full replacement)
Fixes:
  P1-2  degraded=True blocked ALL providers — removed; degraded is now informational only
  P1-3  _collect_keys only split plural env var names — now always tries comma-split
  P3-1  get_api_key_manager() singleton TOCTOU race — fixed with module-level lock
  P3-6  Keys with surrounding quotes rejected — now strips quotes

Drop-in replacement for src/utils/api_key_manager.py.
"""

import os
import logging
import time
import hashlib
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class APIKeyStatus(Enum):
    VALID        = "valid"
    INVALID      = "invalid"
    MISSING      = "missing"
    RATE_LIMITED = "rate_limited"
    EXPIRED      = "expired"


@dataclass
class APIKeyInfo:
    key_hash:             str
    provider:             str
    status:               APIKeyStatus
    last_used:            float
    consecutive_failures: int
    cooldown_until:       float


class APIKeyManager:
    """
    Centralized API key management with validation, rotation, and security.
    P1-2 fix: degraded flag is purely informational; get_working_key() always
              tries per-provider instead of returning None for everything.
    P3-1 fix: singleton creation protected by module-level lock in get_api_key_manager().
    """

    def __init__(self):
        self.degraded        = False
        self.degraded_reason = ""
        self.keys: Dict[str, List[APIKeyInfo]] = {}
        self._reverse_lookup: Dict[str, str]   = {}
        self._load_and_validate_keys()

    def _load_and_validate_keys(self):
        logger.info("Initializing API Key Manager...")

        key_configs = {
            "groq": {
                "env_vars":   ["GROQ_API_KEYS", "GROQ_API_KEY"],
                "validators": [self._validate_groq_key],
                "required":   True,
            },
            "gemini": {
                "env_vars":   ["GEMINI_API_KEYS", "GEMINI_API_KEY"],
                "validators": [self._validate_gemini_key],
                "required":   False,
            },
            "tavily": {
                "env_vars":   ["TAVILY_API_KEY"],
                "validators": [self._validate_tavily_key],
                "required":   False,
            },
            "cerebras": {
                "env_vars":   ["CEREBRAS_API_KEY"],
                "validators": [self._validate_cerebras_key],
                "required":   False,
            },
            "openrouter": {
                "env_vars":   ["OPENROUTER_API_KEY"],
                "validators": [self._validate_openrouter_key],
                "required":   False,
            },
        }

        missing_required = []

        for provider, config in key_configs.items():
            raw_keys = self._collect_keys(provider, config["env_vars"])
            if not raw_keys:
                if config["required"]:
                    logger.error("Required API keys missing for %s", provider)
                    missing_required.append(provider)
                else:
                    logger.warning("Optional API keys missing for %s", provider)
                self.keys[provider] = []
                continue

            valid_keys = []
            for key in raw_keys:
                key_info = self._validate_key(provider, key, config["validators"])
                if key_info.status == APIKeyStatus.VALID:
                    valid_keys.append(key_info)
                    logger.info("%s API key validated", provider)
                else:
                    logger.warning("%s API key invalid: %s", provider, key_info.status.value)

            self.keys[provider] = valid_keys

            if not valid_keys and config["required"]:
                logger.error("No valid API keys for required provider %s", provider)
                missing_required.append(provider)

        if missing_required:
            # P1-2 fix: mark degraded for logging, but do NOT block providers that are available
            self.degraded        = True
            self.degraded_reason = (
                f"Required providers missing or invalid: {missing_required}. "
                "Check .env file. See README for setup."
            )
            logger.warning("APIKeyManager degraded (informational): %s", self.degraded_reason)
        else:
            logger.info("API Key Manager initialized successfully")

    def _collect_keys(self, provider: str, env_vars: List[str]) -> List[str]:
        """
        P1-3 fix: always attempt comma-split regardless of env var name.
        P3-6 fix: strip surrounding quotes that Windows sometimes adds.
        """
        keys = []
        for env_var in env_vars:
            value = os.getenv(env_var)
            if not value:
                continue
            # Always try comma-split (handles both GROQ_API_KEY and GROQ_API_KEYS)
            parts = [p.strip().strip("\"'") for p in value.split(",")]   # P3-6 fix
            keys.extend(p for p in parts if p)

        # Deduplicate, preserve order
        seen: set = set()
        unique = []
        for k in keys:
            if k not in seen:
                seen.add(k)
                unique.append(k)
        return unique

    def _validate_key(self, provider: str, key: str, validators: List[Callable]) -> APIKeyInfo:
        key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
        key_info = APIKeyInfo(
            key_hash=key_hash, provider=provider, status=APIKeyStatus.INVALID,
            last_used=0, consecutive_failures=0, cooldown_until=0,
        )
        for validator in validators:
            try:
                if validator(key):
                    key_info.status = APIKeyStatus.VALID
                    self._reverse_lookup[key_hash] = key
                    break
            except Exception as e:
                logger.debug("Key validation failed for %s: %s", provider, e)
        return key_info

    # ── Validators ────────────────────────────────────────────────────────────

    def _validate_groq_key(self, key: str) -> bool:
        valid_format = len(key) >= 30 and key.startswith("gsk_")
        if not valid_format:
            return False
        if os.getenv("ENABLE_API_LIVENESS_PROBES", "false").lower() == "true":
            try:
                import requests
                r = requests.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {key}"}, timeout=5,
                )
                return r.status_code == 200
            except Exception:
                return False
        return True

    def _validate_gemini_key(self, key: str) -> bool:
        valid_format = len(key) >= 30 and key.startswith("AIza")
        if not valid_format:
            return False
        if os.getenv("ENABLE_API_LIVENESS_PROBES", "false").lower() == "true":
            try:
                import requests
                r = requests.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={key}",
                    timeout=5,
                )
                return r.status_code == 200
            except Exception:
                return False
        return True

    def _validate_tavily_key(self, key: str) -> bool:
        return len(key) >= 20

    def _validate_cerebras_key(self, key: str) -> bool:
        return len(key) >= 30 and key.startswith("csk-")

    def _validate_openrouter_key(self, key: str) -> bool:
        return len(key) >= 30 and key.startswith("sk-or-")

    # ── Key retrieval ─────────────────────────────────────────────────────────

    def get_working_key(self, provider: str) -> Optional[str]:
        """
        P1-2 fix: no longer returns None just because self.degraded is True.
        Each provider is evaluated independently.
        """
        if provider not in self.keys:
            return None

        now = time.time()

        # Auto-recover rate-limited keys whose cooldown has expired
        for ki in self.keys[provider]:
            if ki.status == APIKeyStatus.RATE_LIMITED and now >= ki.cooldown_until:
                ki.status = APIKeyStatus.VALID
                ki.consecutive_failures = max(0, ki.consecutive_failures - 1)
                logger.info("Auto-recovered %s key from cooldown", provider)

        available = [
            ki for ki in self.keys[provider]
            if ki.status == APIKeyStatus.VALID and now >= ki.cooldown_until
        ]

        if not available:
            logger.warning("No available API keys for %s", provider)
            return None

        # Least-recently-used rotation
        key_info          = sorted(available, key=lambda k: k.last_used)[0]
        key_info.last_used = now
        return self._get_actual_key(provider, key_info.key_hash)

    def _get_actual_key(self, provider: str, key_hash: str) -> Optional[str]:
        return self._reverse_lookup.get(key_hash)

    def report_key_failure(self, provider: str, key_hash: str, error: Exception):
        if provider not in self.keys:
            return
        for key_info in self.keys[provider]:
            if key_info.key_hash != key_hash:
                continue
            key_info.consecutive_failures += 1
            key_info.last_used = time.time()

            error_text     = str(error).lower()
            is_rate_limit  = any(kw in error_text for kw in
                                 ("rate limit", "resource_exhausted", "429", "quota"))
            is_zero_quota  = "limit: 0" in error_text or "quota: 0" in error_text

            if is_zero_quota:
                key_info.status = APIKeyStatus.INVALID
                logger.error("%s key has zero quota (account config issue)", provider)
            elif is_rate_limit:
                key_info.status         = APIKeyStatus.RATE_LIMITED
                backoff                 = min(30 * (2 ** key_info.consecutive_failures), 300)
                key_info.cooldown_until = time.time() + backoff
                logger.warning("%s key rate limited, cooling down for %ds", provider, backoff)
            elif key_info.consecutive_failures >= 5:
                key_info.status         = APIKeyStatus.RATE_LIMITED
                key_info.cooldown_until = time.time() + 600
                logger.warning("%s key cooling down 600s after repeated failures", provider)
            else:
                logger.warning("%s key failed (%d/5)", provider, key_info.consecutive_failures)
            break

    def report_key_success(self, provider: str, key_hash: str):
        if provider not in self.keys:
            return
        for key_info in self.keys[provider]:
            if key_info.key_hash == key_hash:
                key_info.consecutive_failures = 0
                key_info.status               = APIKeyStatus.VALID
                break

    def has_working_keys(self, provider: str) -> bool:
        if provider not in self.keys:
            return False
        now = time.time()
        return any(
            ki.status == APIKeyStatus.VALID and now >= ki.cooldown_until
            for ki in self.keys[provider]
        )

    def reset_all_keys(self) -> None:
        for keys in self.keys.values():
            for ki in keys:
                if ki.status == APIKeyStatus.RATE_LIMITED:
                    ki.status               = APIKeyStatus.VALID
                    ki.cooldown_until       = 0
                    ki.consecutive_failures = 0
        logger.info("All rate-limited keys reset")

    def get_health_status(self) -> Dict[str, Any]:
        now    = time.time()
        status = {}
        for provider, keys in self.keys.items():
            ps = {"total_keys": len(keys), "valid_keys": 0,
                  "rate_limited_keys": 0, "invalid_keys": 0, "cooldown_keys": 0}
            for ki in keys:
                if ki.status == APIKeyStatus.VALID and now >= ki.cooldown_until:
                    ps["valid_keys"] += 1
                elif ki.status == APIKeyStatus.RATE_LIMITED:
                    ps["rate_limited_keys"] += 1
                elif ki.status == APIKeyStatus.INVALID:
                    ps["invalid_keys"] += 1
                elif now < ki.cooldown_until:
                    ps["cooldown_keys"] += 1
            status[provider] = ps
        return status


# ── Singleton (P3-1 fix: double-checked locking) ─────────────────────────────
_key_manager      = None
_key_manager_lock = threading.Lock()   # module-level lock — created once safely


def get_api_key_manager() -> APIKeyManager:
    global _key_manager
    if _key_manager is None:
        with _key_manager_lock:
            if _key_manager is None:   # second check inside lock
                _key_manager = APIKeyManager()
    return _key_manager
