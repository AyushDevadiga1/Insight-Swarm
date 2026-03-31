import logging
from types import SimpleNamespace
from typing import cast, List

import pytest

from src.agents.fact_checker import FactChecker
from src.core.models import DebateState
from src.llm.client import FreeLLMClient


class DummyResponse:
    def __init__(self, status_code=200, text="ok"):
        self.status_code = status_code
        self.text = text
    def iter_content(self, chunk_size=8192):
        yield self.text.encode("utf-8")


def test_factchecker_avoids_fetching_invalid_titles(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)

    calls = []

    def fake_get(url, timeout=None, allow_redirects=True, **kwargs):
        calls.append(url)
        return DummyResponse(status_code=200, text="response content")

    monkeypatch.setattr("requests.get", fake_get)

    fake_client = cast(FreeLLMClient, SimpleNamespace())
    fc = FactChecker(llm_client=fake_client)

    state = DebateState(
        claim="Does exercise help mental health?",
        pro_sources=[["Stanton et al. (2020) - Exercise and neuroplasticity: a review of the evidence", "https://example.com"]],
        con_sources=[["Journal of Clinical Psychology", "www.example.org"]],
    )

    resp = fc.generate(state)
    metrics = resp.metrics or {}
    results = metrics.get("verification_results", [])

    # Titles without schemes should be marked INVALID_URL and not trigger requests.get
    invalids = [r for r in results if r["status"] == "INVALID_URL"]
    assert any("Stanton et al." in r["url"] for r in invalids)

    # Bare domain 'www.example.org' should be considered INVALID_URL by FactChecker (no scheme)
    # but our upstream sanitizers may add http://; ensure at least the https://example.com was fetched
    assert any(r["url"].startswith("https://example.com") or r["url"].startswith("http://example.com") for r in results)

    # Ensure requests.get was called only for the explicit URL (https://example.com)
    assert any("example.com" in c for c in calls)
    # And not called for the long title strings
    assert not any("Stanton et al." in c for c in calls)


def test_factchecker_handles_non_string_sources(monkeypatch):
    calls = []

    def fake_get(url, timeout=None, allow_redirects=True, **kwargs):
        calls.append(url)
        return DummyResponse(status_code=200, text="ok")

    monkeypatch.setattr("requests.get", fake_get)

    fake_client = cast(FreeLLMClient, SimpleNamespace())
    fc = FactChecker(llm_client=fake_client)

    # Cast to satisfy static typing while exercising runtime handling of non-string values
    # Create a valid DebateState then inject non-string sources without Pydantic re-validation
    state = DebateState(claim="Test non-string sources", pro_sources=[[]], con_sources=[])
    object.__setattr__(state, "pro_sources", [[12345, None, "https://valid.example.net"]])

    resp = fc.generate(state)
    metrics = resp.metrics or {}
    results = metrics.get("verification_results", [])

    # Non-string inputs should be converted to strings and classified as INVALID_URL
    assert any(r["status"] == "INVALID_URL" for r in results)
    # The valid URL should trigger a fetch
    assert any("valid.example.net" in c for c in calls)
