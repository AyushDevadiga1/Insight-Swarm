"""
src/monitoring/api_status.py — Final production version.
Fixed: get_health_monitor() singleton is not thread-safe — added lock.
"""
import asyncio, time, threading
from src.utils.api_key_manager import get_api_key_manager
from src.llm.client import FreeLLMClient


class HealthMonitor:
    def __init__(self):
        self.llm = FreeLLMClient()

    async def _test_provider(self, provider: str) -> dict:
        start = time.time()
        try:
            await asyncio.to_thread(self.llm.call, prompt="Hi", max_tokens=1, timeout=5,
                                    preferred_provider=provider)
            return {"status":"healthy","latency_ms":round((time.time()-start)*1000)}
        except Exception as e:
            err = str(e).lower()
            if "rate limit" in err or "429" in err:
                return {"status":"rate_limited","error":"Quota exceeded"}
            return {"status":"invalid_key","error":str(e)[:50]}

    async def get_status(self):
        km  = get_api_key_manager()
        raw = km.get_health_status()
        tasks = {p: self._test_provider(p)
                 for p in ("groq","gemini","cerebras","openrouter")
                 if raw.get(p,{}).get("valid_keys",0) > 0}
        pings = {}
        if tasks:
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            for provider, res in zip(tasks.keys(), results):
                pings[provider] = {"status":"error","error":str(res)} if isinstance(res, Exception) else res

        result = {}
        for provider in ("groq","gemini","cerebras","openrouter","tavily"):
            info     = raw.get(provider, {})
            valid    = info.get("valid_keys", 0)
            total    = info.get("total_keys", 0)
            ping_res = pings.get(provider, {})
            if total == 0:        status = "no_key"
            elif ping_res.get("status"): status = ping_res["status"]
            elif valid > 0:       status = "healthy"
            else:                 status = "invalid_key"
            result[provider] = {"status":status,"keys_available":valid,"keys_total":total,
                                 "latency_ms":ping_res.get("latency_ms"),"error":ping_res.get("error")}
        return result


_monitor      = None
_monitor_lock = threading.Lock()

def get_health_monitor() -> HealthMonitor:
    global _monitor
    if _monitor is None:
        with _monitor_lock:
            if _monitor is None:
                _monitor = HealthMonitor()
    return _monitor
