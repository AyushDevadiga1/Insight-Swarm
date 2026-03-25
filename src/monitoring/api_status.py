import asyncio
import time
from src.utils.api_key_manager import get_api_key_manager
from src.llm.client import FreeLLMClient

class HealthMonitor:
    def __init__(self):
        self.llm = FreeLLMClient()

    async def _test_provider(self, provider: str) -> dict:
        """Perform a live ping to the provider."""
        start = time.time()
        try:
            # Minimal token call
            await asyncio.to_thread(
                self.llm.call, 
                prompt="Hi", 
                max_tokens=1, 
                timeout=5,
                preferred_provider=provider
            )
            latency = (time.time() - start) * 1000
            return {"status": "healthy", "latency_ms": round(latency)}
        except Exception as e:
            err = str(e).lower()
            if "rate limit" in err or "429" in err:
                return {"status": "rate_limited", "error": "Quota exceeded"}
            return {"status": "invalid_key", "error": str(e)[:50]}

    async def get_status(self):
        km = get_api_key_manager()
        raw = km.get_health_status()
        
        # We'll ping all providers that have valid keys in parallel
        tasks = {}
        for provider in ["groq", "gemini", "cerebras", "openrouter"]:
            info = raw.get(provider, {})
            if info.get("valid_keys", 0) > 0:
                tasks[provider] = self._test_provider(provider)
        
        pings = {}
        if tasks:
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            for provider, res in zip(tasks.keys(), results):
                if isinstance(res, Exception):
                    pings[provider] = {"status": "error", "error": str(res)}
                else:
                    pings[provider] = res

        result = {}
        # Merge key manager info with ping results
        for provider in ["groq", "gemini", "cerebras", "openrouter", "tavily"]:
            info = raw.get(provider, {})
            valid = info.get("valid_keys", 0)
            total = info.get("total_keys", 0)
            
            ping_res = pings.get(provider, {})
            
            if total == 0:
                status = "no_key"
            elif ping_res.get("status"):
                status = ping_res["status"]
            elif valid > 0:
                status = "healthy"
            else:
                status = "invalid_key"
                
            result[provider] = {
                "status": status,
                "keys_available": valid,
                "keys_total": total,
                "latency_ms": ping_res.get("latency_ms"),
                "error": ping_res.get("error")
            }
        return result

_monitor = None
def get_health_monitor():
    global _monitor
    if _monitor is None:
        _monitor = HealthMonitor()
    return _monitor
