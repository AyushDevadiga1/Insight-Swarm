import os
import pytest


RUN_INTEGRATION_LLM = os.getenv("RUN_INTEGRATION_LLM", "").strip().lower() in ("1", "true", "yes")


class DummyClient:
    def __init__(self, *args, **kwargs):
        pass

    def call_structured(self, prompt, output_schema, temperature=0.7, max_tokens=2000, max_retries=2):
        name = getattr(output_schema, "__name__", "")
        if name == "ModeratorVerdict":
            return output_schema(
                verdict="INSUFFICIENT EVIDENCE",
                confidence=0.5,
                reasoning="Mock moderator reasoning for integration tests. This explanation is intentionally long to satisfy minimum length checks in integration tests.",
                metrics={"credibility": 0.5, "balance": 0.5}
            )
        return output_schema(
            agent="PRO",
            round=1,
            argument="Mock argument for integration tests.",
            sources=["https://example.com"],
            confidence=0.6
        )

    def call(self, prompt, temperature=0.7, max_tokens=1000, timeout=30):
        return "Mock response"


def _fake_get(url, timeout=None, allow_redirects=True, **kwargs):
    class DummyResponse:
        def __init__(self):
            self.status_code = 200
            self.text = "Mock response content for verification."
    return DummyResponse()


@pytest.fixture(autouse=True)
def _stub_external_calls(monkeypatch):
    if RUN_INTEGRATION_LLM:
        return
    monkeypatch.setattr("src.orchestration.debate.FreeLLMClient", DummyClient)
    monkeypatch.setattr("requests.get", _fake_get)
