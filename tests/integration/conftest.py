import os

import pytest

RUN_INTEGRATION_LLM = os.getenv("RUN_INTEGRATION_LLM", "").strip().lower() in ("1", "true", "yes")


class DummyClient:
    openrouter_available = True
    groq_available = True

    def __init__(self, *args, **kwargs):
        pass

    def call_structured(self, prompt, output_schema, temperature=0.7, max_tokens=2000, max_retries=2, preferred_provider=None, **kwargs):
        fields = list(output_schema.model_fields.keys()) if hasattr(output_schema, "model_fields") else []

        if "claims" in fields:
            # ClaimDecomposer — two atomic claims so multi-claim paths are exercised
            return output_schema(
                claims=["Electric cars are better for the environment.",
                        "Electric cars are cheaper to maintain over their lifetime."]
            )
        if "metrics" in fields and "verdict" in fields:
            # ModeratorVerdict — used by Moderator.generate (final verdict path)
            return output_schema(
                verdict="INSUFFICIENT EVIDENCE",
                confidence=0.5,
                reasoning="Mock moderator reasoning for integration tests. This explanation is intentionally long to satisfy minimum length checks in integration tests.",
                metrics={"credibility": 0.5, "balance": 0.5}
            )
        if "verdict" in fields and "confidence" in fields and "reasoning" in fields:
            # ConsensusResponse — pre-check never settles, so the debate path runs
            return output_schema(
                verdict="DEBATE",
                confidence=0.4,
                reasoning="Mock consensus reasoning."
            )
        return output_schema(
            argument="Mock argument for integration tests. " * 10,
            sources=["https://example.com"],
            confidence=0.6
        )

    def call(self, prompt, temperature=0.7, max_tokens=1000, timeout=30, **kwargs):
        return "Mock response"


def _fake_get(url, timeout=None, allow_redirects=True, **kwargs):
    class DummyResponse:
        def __init__(self):
            self.status_code = 200
            self.text = "Mock response content for verification."
        def iter_content(self, chunk_size=8192):
            yield self.text.encode("utf-8")
    return DummyResponse()


@pytest.fixture(autouse=True)
def _stub_external_calls(monkeypatch):
    if RUN_INTEGRATION_LLM:
        return
    monkeypatch.setattr("src.orchestration.debate.FreeLLMClient", DummyClient)
    monkeypatch.setattr("requests.get", _fake_get)
