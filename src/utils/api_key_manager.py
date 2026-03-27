"""
src/utils/api_key_manager.py — Final production version. All batches applied.
"""
import os, logging, time, hashlib, threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
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
    def __init__(self):
        self.degraded        = False
        self.degraded_reason = ""
        self.keys: Dict[str, List[APIKeyInfo]] = {}
        self._reverse_lookup: Dict[str, str]   = {}
        self._load_and_validate_keys()

    def _load_and_validate_keys(self):
        logger.info("Initializing API Key Manager...")
        key_configs = {
            "groq":       {"env_vars":["GROQ_API_KEYS","GROQ_API_KEY"],       "validators":[self._validate_groq_key],       "required":True},
            "gemini":     {"env_vars":["GEMINI_API_KEYS","GEMINI_API_KEY"],   "validators":[self._validate_gemini_key],     "required":False},
            "tavily":     {"env_vars":["TAVILY_API_KEY"],                      "validators":[self._validate_tavily_key],     "required":False},
            "cerebras":   {"env_vars":["CEREBRAS_API_KEY"],                    "validators":[self._validate_cerebras_key],   "required":False},
            "openrouter": {"env_vars":["OPENROUTER_API_KEY"],                  "validators":[self._validate_openrouter_key], "required":False},
        }
        missing_required = []
        for provider, cfg in key_configs.items():
            raw_keys = self._collect_keys(provider, cfg["env_vars"])
            if not raw_keys:
                if cfg["required"]: missing_required.append(provider)
                self.keys[provider] = []
                continue
            valid_keys = []
            for key in raw_keys:
                ki = self._validate_key(provider, key, cfg["validators"])
                if ki.status == APIKeyStatus.VALID:
                    valid_keys.append(ki)
                    logger.info("%s API key validated", provider)
                else:
                    logger.warning("%s API key invalid: %s", provider, ki.status.value)
            self.keys[provider] = valid_keys
            if not valid_keys and cfg["required"]:
                missing_required.append(provider)

        if missing_required:
            self.degraded        = True
            self.degraded_reason = f"Required providers missing: {missing_required}. Check .env."
            logger.warning("APIKeyManager degraded (informational): %s", self.degraded_reason)
        else:
            logger.info("API Key Manager initialized successfully")

    def _collect_keys(self, provider: str, env_vars: List[str]) -> List[str]:
        keys = []
        for ev in env_vars:
            val = os.getenv(ev)
            if val:
                keys.extend(p.strip().strip("\"'") for p in val.split(",") if p.strip())
        seen, unique = set(), []
        for k in keys:
            if k not in seen: seen.add(k); unique.append(k)
        return unique

    def _validate_key(self, provider: str, key: str, validators: List[Callable]) -> APIKeyInfo:
        key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
        ki = APIKeyInfo(key_hash=key_hash, provider=provider, status=APIKeyStatus.INVALID,
                        last_used=0, consecutive_failures=0, cooldown_until=0)
        for v in validators:
            try:
                if v(key):
                    ki.status = APIKeyStatus.VALID
                    self._reverse_lookup[key_hash] = key
                    break
            except Exception as e:
                logger.debug("Key validation failed for %s: %s", provider, e)
        return ki

    def _validate_groq_key(self, key: str) -> bool:
        if not (len(key) >= 30 and key.startswith("gsk_")): return False
        if os.getenv("ENABLE_API_LIVENESS_PROBES","false").lower() == "true":
            try:
                import requests
                return requests.get("https://api.groq.com/openai/v1/models",
                                    headers={"Authorization": f"Bearer {key}"}, timeout=5).status_code == 200
            except Exception: return False
        return True

    def _validate_gemini_key(self, key: str) -> bool:
        if not (len(key) >= 30 and key.startswith("AIza")): return False
        if os.getenv("ENABLE_API_LIVENESS_PROBES","false").lower() == "true":
            try:
                import requests
                return requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={key}", timeout=5).status_code == 200
            except Exception: return False
        return True

    def _validate_tavily_key(self, key: str) -> bool:   return len(key) >= 20
    def _validate_cerebras_key(self, key: str) -> bool: return len(key) >= 30 and key.startswith("csk-")
    def _validate_openrouter_key(self, key: str) -> bool: return len(key) >= 30 and key.startswith("sk-or-")

    def get_working_key(self, provider: str) -> Optional[str]:
        if provider not in self.keys: return None
        now = time.time()
        for ki in self.keys[provider]:
            if ki.status == APIKeyStatus.RATE_LIMITED and now >= ki.cooldown_until:
                ki.status = APIKeyStatus.VALID
                ki.consecutive_failures = max(0, ki.consecutive_failures - 1)
                logger.info("Auto-recovered %s key from cooldown", provider)
        available = [ki for ki in self.keys[provider] if ki.status == APIKeyStatus.VALID and now >= ki.cooldown_until]
        if not available:
            logger.warning("No available API keys for %s", provider)
            return None
        ki = sorted(available, key=lambda k: k.last_used)[0]
        ki.last_used = now
        return self._reverse_lookup.get(ki.key_hash)

    def report_key_failure(self, provider: str, key_hash: str, error: Exception):
        if provider not in self.keys: return
        for ki in self.keys[provider]:
            if ki.key_hash != key_hash: continue
            ki.consecutive_failures += 1
            ki.last_used = time.time()
            err = str(error).lower()
            if "limit: 0" in err or "quota: 0" in err:
                ki.status = APIKeyStatus.INVALID
                logger.error("%s key has zero quota", provider)
            elif any(kw in err for kw in ("rate limit","resource_exhausted","429","quota")):
                ki.status         = APIKeyStatus.RATE_LIMITED
                ki.cooldown_until = time.time() + min(30 * (2 ** ki.consecutive_failures), 300)
                logger.warning("%s key rate limited, cooling down", provider)
            elif ki.consecutive_failures >= 5:
                ki.status         = APIKeyStatus.RATE_LIMITED
                ki.cooldown_until = time.time() + 600
                logger.warning("%s key cooling down 600s after repeated failures", provider)
            else:
                logger.warning("%s key failed (%d/5)", provider, ki.consecutive_failures)
            break

    def report_key_success(self, provider: str, key_hash: str):
        if provider not in self.keys: return
        for ki in self.keys[provider]:
            if ki.key_hash == key_hash:
                ki.consecutive_failures = 0
                ki.status = APIKeyStatus.VALID
                break

    def has_working_keys(self, provider: str) -> bool:
        if provider not in self.keys: return False
        now = time.time()
        return any(ki.status == APIKeyStatus.VALID and now >= ki.cooldown_until for ki in self.keys[provider])

    def reset_all_keys(self) -> None:
        for keys in self.keys.values():
            for ki in keys:
                if ki.status == APIKeyStatus.RATE_LIMITED:
                    ki.status = APIKeyStatus.VALID; ki.cooldown_until = 0; ki.consecutive_failures = 0
        logger.info("All rate-limited keys reset")

    def get_health_status(self) -> Dict[str, Any]:
        now, status = time.time(), {}
        for provider, keys in self.keys.items():
            ps = {"total_keys":len(keys),"valid_keys":0,"rate_limited_keys":0,"invalid_keys":0,"cooldown_keys":0}
            for ki in keys:
                if ki.status == APIKeyStatus.VALID and now >= ki.cooldown_until: ps["valid_keys"] += 1
                elif ki.status == APIKeyStatus.RATE_LIMITED: ps["rate_limited_keys"] += 1
                elif ki.status == APIKeyStatus.INVALID: ps["invalid_keys"] += 1
                elif now < ki.cooldown_until: ps["cooldown_keys"] += 1
            status[provider] = ps
        return status


_key_manager      = None
_key_manager_lock = threading.Lock()

def get_api_key_manager() -> APIKeyManager:
    global _key_manager
    if _key_manager is None:
        with _key_manager_lock:
            if _key_manager is None:
                _key_manager = APIKeyManager()
    return _key_manager
