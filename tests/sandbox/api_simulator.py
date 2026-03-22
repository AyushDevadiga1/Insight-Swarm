import time
import random
import logging
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class ChaosConfig(BaseModel):
    """Configuration for the Chaos Simulator."""
    failure_rate: float = 0.2          # 0.0 to 1.0
    rate_limit_rate: float = 0.1       # 0.0 to 1.0 (simulates 429)
    min_latency: float = 0.1           # seconds
    max_latency: float = 2.0           # seconds
    provider_specific_failure: Dict[str, float] = {} # e.g. {"groq": 0.5}

class MockChaosClient:
    """
    A drop-in replacement for testing that simulates real-world instability.
    Injected into DebateOrchestrator to verify CircuitBreaker and Fallback logic.
    """
    def __init__(self, config: Optional[ChaosConfig] = None):
        self.config = config or ChaosConfig()
        self.call_history: List[Dict[str, Any]] = []
        
        # Mirror FreeLLMClient attributes for compatibility
        self.groq_available = True
        self.gemini_available = True
        self.cerebras_available = True
        self.openrouter_available = True

    def _simulate_chaos(self, provider: str):
        """Internal helper to inject delay and failures."""
        # 1. Latency
        delay = random.uniform(self.config.min_latency, self.config.max_latency)
        time.sleep(delay)

        # 2. Provider-specific failure override
        fail_prob = self.config.provider_specific_failure.get(provider, self.config.failure_rate)

        # 3. Simulate Rate Limit (429)
        if random.random() < self.config.rate_limit_rate:
            logger.warning(f"CHAOS: Simulating 429 RateLimit for {provider}")
            raise RuntimeError(f"Rate limit exceeded for {provider} (429)")

        # 4. Simulate Generic Failure (500)
        if random.random() < fail_prob:
            logger.error(f"CHAOS: Simulating 500 error for {provider}")
            raise RuntimeError(f"Internal Server Error on {provider} (500)")

    def call_structured(self, prompt: str, output_schema: Any, **kwargs):
        provider = kwargs.get("preferred_provider", "unknown")
        self.call_history.append({"method": "call_structured", "provider": provider})
        
        self._simulate_chaos(provider)
        
        # Return valid mock data if no exception raised
        fields = {}
        if hasattr(output_schema, "model_fields"):
            fields = output_schema.model_fields
        elif hasattr(output_schema, "__fields__"):
            fields = output_schema.__fields__
            
        if fields:
             # Simple heuristic to fill pydantic models
             data = {}
             for k in fields.keys():
                 if k == "metrics":
                     data[k] = {"mock_metric": 0.95}
                 elif k == "agent":
                     # Infer role from prompt or provider
                     role = "PRO"
                     if "ConAgent" in prompt or "con" in provider:
                         role = "CON"
                     data[k] = role
                 elif k == "sources":
                     data[k] = ["https://mock-source.com/research"]
                 elif k == "confidence":
                     data[k] = 0.95
                 elif k == "round":
                     data[k] = 1
                 elif k == "verdict":
                     data[k] = "TRUE"
                 elif k == "reasoning":
                     data[k] = "Automated simulation reasoning based on mock data consistency."
                 else:
                     data[k] = "Mock result"
             
             return output_schema(**data)
        return {"result": "mock"}

    def call(self, prompt: str, **kwargs):
        provider = kwargs.get("preferred_provider", "unknown")
        self.call_history.append({"method": "call", "provider": provider})
        
        self._simulate_chaos(provider)
        return "Mock plain text response."

def run_chaos_test():
    """Example usage of the simulator."""
    print("🚀 Starting Chaos Test...")
    config = ChaosConfig(failure_rate=0.5, rate_limit_rate=0.2)
    client = MockChaosClient(config)
    
    for i in range(5):
        try:
            res = client.call(f"Test {i}", preferred_provider="groq")
            print(f"✅ Success: {res}")
        except Exception as e:
            print(f"❌ Failure: {e}")

if __name__ == "__main__":
    run_chaos_test()
