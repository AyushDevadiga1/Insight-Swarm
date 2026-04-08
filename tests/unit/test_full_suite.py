"""
InsightSwarm — Complete Unit Test Suite
Covers all current production paths, agent behaviours, and edge cases.
Written to match the current codebase (MemorySaver, preferred_provider param,
_process_content, SETTLED_TRUTHS, claim_decomposer, trust_scorer, etc.)
"""
import os
import sys
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from types import SimpleNamespace
from typing import cast

# CI-safe defaults — must come before any src import
os.environ.setdefault("ENABLE_OFFLINE_FALLBACK", "1")
os.environ.setdefault("GROQ_API_KEY",   "gsk_ci_placeholder_abcdefghijklmnopqrstuvwxyz")
os.environ.setdefault("GEMINI_API_KEY",  "AIzaSy_ci_placeholder_abcdefghijklmnopqrstuvwx")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.core.models import (
    AgentResponse, DebateState, ModeratorVerdict, SourceVerification, ConsensusResponse
)
from src.agents.pro_agent import ProAgent
from src.agents.con_agent import ConAgent
from src.agents.moderator import Moderator
from src.agents.fact_checker import FactChecker
from src.llm.client import FreeLLMClient, RateLimitError
from src.utils.trust_scorer import TrustScorer
from src.utils.temporal_verifier import TemporalVerifier
from src.utils.url_helper import URLNormalizer


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_client():
    """Generic mocked LLM client."""
    client = Mock(spec=FreeLLMClient)
    client.call_structured.return_value = AgentResponse(
        agent="PRO", round=1,
        argument="Strong evidence supports this claim.",
        sources=["https://example.com/source1"],
        confidence=0.8,
    )
    return client

@pytest.fixture
def pro_agent(mock_client):
    return ProAgent(mock_client)

@pytest.fixture
def con_agent(mock_client):
    client = Mock(spec=FreeLLMClient)
    client.call_structured.return_value = AgentResponse(
        agent="CON", round=1,
        argument="Counter-evidence refutes this claim.",
        sources=["https://example.com/source2"],
        confidence=0.7,
    )
    return ConAgent(client)

@pytest.fixture
def base_state():
    return DebateState(claim="Exercise improves mental health", round=1)

@pytest.fixture
def full_debate_state():
    """State representing a completed 3-round debate."""
    return DebateState(
        claim="Coffee prevents cancer",
        round=4,
        pro_arguments=["Pro R1", "Pro R2", "Pro R3"],
        con_arguments=["Con R1", "Con R2", "Con R3"],
        pro_sources=[["https://pubmed.gov/1"], ["https://harvard.edu/2"], ["https://nature.com/3"]],
        con_sources=[["https://cancer.org/1"], ["https://who.int/2"], ["https://cdc.gov/3"]],
        pro_verification_rate=0.8,
        con_verification_rate=0.75,
        metrics={"consensus": {"verdict": "DEBATE", "score": 0.5, "reasoning": "Contested topic"}},
    )

@pytest.fixture
def fake_fc_client():
    """Minimal client for FactChecker (deterministic — no LLM calls needed)."""
    return cast(FreeLLMClient, SimpleNamespace())


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — ProAgent
# ═══════════════════════════════════════════════════════════════════════════════

class TestProAgent:

    def test_role_is_pro(self, pro_agent):
        assert pro_agent.role == "PRO"

    def test_default_provider_is_groq(self, mock_client):
        agent = ProAgent(mock_client)
        assert agent.preferred_provider == "groq"

    def test_custom_provider_accepted(self, mock_client):
        agent = ProAgent(mock_client, preferred_provider="cerebras")
        assert agent.preferred_provider == "cerebras"

    def test_generate_returns_pro_response(self, pro_agent, base_state):
        response = pro_agent.generate(base_state)
        assert response.agent == "PRO"
        assert response.round == 1
        assert isinstance(response.argument, str)
        assert len(response.argument) > 0

    def test_generate_sets_timestamp(self, pro_agent, base_state):
        response = pro_agent.generate(base_state)
        assert response.timestamp is not None
        # Format: HH:MM:SS
        parts = response.timestamp.split(":")
        assert len(parts) == 3

    def test_generate_sanitizes_sources(self, mock_client, base_state):
        """Sources returned by LLM are sanitized before storage."""
        mock_client.call_structured.return_value = AgentResponse(
            agent="PRO", round=1,
            argument="Evidence here.",
            sources=["Stanton et al. 2020 - Journal of Science", "https://valid.com/page"],
        )
        agent = ProAgent(mock_client)
        response = agent.generate(base_state)
        # Title-like string should be dropped
        assert not any("Stanton" in s for s in response.sources)
        # Valid URL should be preserved
        assert any("valid.com" in s for s in response.sources)

    def test_generate_on_round_gt_1_includes_con_argument(self, mock_client):
        """Round 2+ prompt must reference ConAgent's previous argument."""
        state = DebateState(
            claim="Test claim", round=2,
            pro_arguments=["Pro R1"],
            con_arguments=["Con R1 — this specific phrase"],
        )
        agent = ProAgent(mock_client)
        agent.generate(state)
        prompt_used = mock_client.call_structured.call_args.kwargs.get('prompt')
        assert "Con R1 — this specific phrase" in prompt_used

    def test_api_failure_returns_fallback_response(self, mock_client, base_state):
        mock_client.call_structured.side_effect = Exception("Connection timeout")
        agent = ProAgent(mock_client)
        response = agent.generate(base_state)
        assert response.agent == "PRO"
        assert response.confidence == 0.5  # non-quota fallback
        assert response.sources == []

    def test_quota_exhausted_sets_api_failure_marker(self, mock_client, base_state):
        mock_client.call_structured.side_effect = Exception("QUOTA_EXHAUSTED: daily limit")
        agent = ProAgent(mock_client)
        response = agent.generate(base_state)
        assert "[API_FAILURE]" in response.argument
        assert response.confidence == 0.0

    def test_call_count_increments_on_success(self, pro_agent, base_state):
        initial = pro_agent.call_count
        pro_agent.generate(base_state)
        assert pro_agent.call_count == initial + 1

    def test_call_count_does_not_increment_on_failure(self, mock_client, base_state):
        mock_client.call_structured.side_effect = Exception("fail")
        agent = ProAgent(mock_client)
        initial = agent.call_count
        agent.generate(base_state)
        assert agent.call_count == initial

    def test_empty_claim_does_not_crash(self, pro_agent):
        state = DebateState(claim="", round=1)
        response = pro_agent.generate(state)
        assert hasattr(response, "argument")

    def test_evidence_sources_included_in_prompt(self, mock_client):
        state = DebateState(
            claim="Test", round=1,
            evidence_sources=[{
                "title": "UniqueTitle999",
                "url": "https://test.com",
                "content": "Some content"
            }]
        )
        agent = ProAgent(mock_client)
        agent.generate(state)
        prompt = mock_client.call_structured.call_args.kwargs.get('prompt')
        assert "UniqueTitle999" in prompt

    def test_verification_feedback_injected_in_later_rounds(self, mock_client):
        state = DebateState(
            claim="Test", round=2,
            pro_arguments=["R1"],
            con_arguments=["Con R1"],
            verification_feedback="WARNING: https://bad.com failed verification"
        )
        agent = ProAgent(mock_client)
        agent.generate(state)
        prompt = mock_client.call_structured.call_args.kwargs.get('prompt')
        assert "WARNING: https://bad.com failed verification" in prompt


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — ConAgent
# ═══════════════════════════════════════════════════════════════════════════════

class TestConAgent:

    def test_role_is_con(self, con_agent):
        assert con_agent.role == "CON"

    def test_default_provider_is_gemini(self, mock_client):
        agent = ConAgent(mock_client)
        assert agent.preferred_provider == "gemini"

    def test_custom_provider_accepted(self, mock_client):
        agent = ConAgent(mock_client, preferred_provider="openrouter")
        assert agent.preferred_provider == "openrouter"

    def test_generate_returns_con_response(self, con_agent, base_state):
        base_state.pro_arguments.append("Pro arg R1")
        response = con_agent.generate(base_state)
        assert response.agent == "CON"

    def test_generate_sets_timestamp(self, con_agent, base_state):
        response = con_agent.generate(base_state)
        assert response.timestamp is not None

    def test_round1_prompt_references_pro_argument(self, mock_client):
        state = DebateState(
            claim="Test claim", round=1,
            pro_arguments=["ProArgument_UniqueString_XYZ"],
        )
        agent = ConAgent(mock_client)
        agent.generate(state)
        prompt = mock_client.call_structured.call_args.kwargs.get('prompt')
        assert "ProArgument_UniqueString_XYZ" in prompt

    def test_api_failure_returns_fallback_not_raise(self, mock_client, base_state):
        mock_client.call_structured.side_effect = RuntimeError("API down")
        agent = ConAgent(mock_client)
        response = agent.generate(base_state)
        assert response.agent == "CON"
        assert isinstance(response.argument, str)

    def test_quota_failure_sets_api_failure_marker(self, mock_client, base_state):
        mock_client.call_structured.side_effect = Exception("QUOTA_EXHAUSTED")
        agent = ConAgent(mock_client)
        response = agent.generate(base_state)
        assert "[API_FAILURE]" in response.argument
        assert response.confidence == 0.0

    def test_argument_differs_from_pro(self, mock_client):
        pro_client = Mock(spec=FreeLLMClient)
        pro_client.call_structured.return_value = AgentResponse(
            agent="PRO", round=1, argument="PRO UNIQUE ARGUMENT", sources=[]
        )
        con_client = Mock(spec=FreeLLMClient)
        con_client.call_structured.return_value = AgentResponse(
            agent="CON", round=1, argument="CON UNIQUE REBUTTAL", sources=[]
        )
        state = DebateState(claim="Test", round=1)
        pro = ProAgent(pro_client).generate(state)
        state.pro_arguments.append(pro.argument)
        con = ConAgent(con_client).generate(state)
        assert pro.argument != con.argument


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — Moderator
# ═══════════════════════════════════════════════════════════════════════════════

class TestModerator:

    @pytest.fixture
    def moderator_client(self):
        client = Mock(spec=FreeLLMClient)
        client.call_structured.return_value = ModeratorVerdict(
            verdict="TRUE",
            confidence=0.9,
            reasoning="Evidence strongly supports the claim.",
            metrics={"argument_quality": 0.9, "logical_fallacies": [], "credibility_score": 0.85}
        )
        return client

    @pytest.fixture
    def moderator(self, moderator_client):
        return Moderator(moderator_client)

    def test_role_is_moderator(self, moderator):
        assert moderator.role == "MODERATOR"

    def test_generates_verdict(self, moderator, full_debate_state):
        result = moderator.generate(full_debate_state)
        assert result.agent == "MODERATOR"
        assert result.verdict == "TRUE"

    def test_composite_confidence_formula(self, moderator, full_debate_state):
        """
        Formula: (arg_quality*0.3) + (avg_ver*0.3) + (avg_trust*0.2) + (consensus*0.2)
        With metrics={"argument_quality":0.9}, ver_rates=0.8/0.75, no trust scores,
        consensus verdict=DEBATE → score=0.5.
        avg_ver = (0.8+0.75)/2 = 0.775
        composite = (0.9*0.3) + (0.775*0.3) + (0.5*0.2) + (0.5*0.2)
                  = 0.27 + 0.2325 + 0.1 + 0.1 = 0.7025
        """
        result = moderator.generate(full_debate_state)
        assert result.confidence == pytest.approx(0.7025, abs=0.01)

    def test_trust_score_from_verification_results(self, moderator_client):
        """Trust scores in verification_results must influence composite confidence."""
        state = DebateState(
            claim="Test", round=4,
            pro_arguments=["A"], con_arguments=["B"],
            pro_verification_rate=0.9, con_verification_rate=0.9,
            metrics={
                "argument_quality": 0.9,
                "consensus": {"verdict": "TRUE", "score": 0.95, "reasoning": ""},
                "verification_results": [
                    {"status": "VERIFIED", "trust_score": 1.0},  # WHO
                    {"status": "VERIFIED", "trust_score": 0.8},  # Reuters
                ]
            }
        )
        moderator = Moderator(moderator_client)
        result = moderator.generate(state)
        # avg_trust = (1.0 + 0.8) / 2 = 0.9
        # consensus: verdict=TRUE matches result.verdict=TRUE → score=0.95
        # composite = (0.9*0.3)+(0.9*0.3)+(0.9*0.2)+(0.95*0.2)
        #           = 0.27 + 0.27 + 0.18 + 0.19 = 0.91
        assert result.confidence > 0.85  # High trust pushes confidence up

    def test_confidence_breakdown_in_metrics(self, moderator, full_debate_state):
        result = moderator.generate(full_debate_state)
        assert "confidence_breakdown" in result.metrics
        bd = result.metrics["confidence_breakdown"]
        assert "argument_quality_score" in bd
        assert "verification_score" in bd
        assert "trust_score" in bd
        assert "consensus_score" in bd

    def test_fallback_on_rate_limit(self):
        client = Mock(spec=FreeLLMClient)
        client.call_structured.side_effect = RateLimitError("groq", "rate limited", 45.0)
        moderator = Moderator(client)
        state = DebateState(claim="Test", round=3)
        result = moderator.generate(state)
        assert result.verdict == "RATE_LIMITED"
        assert result.confidence == 0.0

    def test_fallback_on_generic_exception(self):
        client = Mock(spec=FreeLLMClient)
        client.call_structured.side_effect = Exception("Connection error")
        moderator = Moderator(client)
        state = DebateState(claim="Test", round=3)
        result = moderator.generate(state)
        assert result.verdict == "SYSTEM_ERROR"
        assert result.confidence == 0.0

    def test_fallback_verdict_set_includes_all_valid_verdicts(self, moderator, full_debate_state):
        fallback = moderator._fallback_verdict(full_debate_state)
        valid = {"TRUE", "FALSE", "PARTIALLY TRUE", "INSUFFICIENT EVIDENCE",
                 "SYSTEM_ERROR", "RATE_LIMITED", "UNKNOWN", "ERROR", "CONSENSUS_SETTLED"}
        assert fallback.verdict in valid

    def test_summary_used_when_available(self, moderator_client):
        """When state.summary is populated, it must appear in the Moderator prompt."""
        state = DebateState(
            claim="Test claim", round=4,
            pro_arguments=["R1", "R2", "R3"],
            con_arguments=["R1", "R2", "R3"],
            summary="UNIQUE_SUMMARY_STRING_XYZ123"
        )
        moderator = Moderator(moderator_client)
        moderator.generate(state)
        prompt = moderator_client.call_structured.call_args.kwargs.get('prompt')
        assert "UNIQUE_SUMMARY_STRING_XYZ123" in prompt

    def test_full_args_used_when_no_summary(self, moderator_client):
        """Without summary, full argument text should appear in prompt."""
        state = DebateState(
            claim="Test", round=2,
            pro_arguments=["SPECIFIC_PRO_ROUND1", "SPECIFIC_PRO_ROUND2"],
            con_arguments=["SPECIFIC_CON_ROUND1", "SPECIFIC_CON_ROUND2"],
            summary="",
        )
        moderator = Moderator(moderator_client)
        moderator.generate(state)
        prompt = moderator_client.call_structured.call_args.kwargs.get('prompt')
        assert "SPECIFIC_PRO_ROUND1" in prompt

    def test_health_claim_adds_safety_note_instruction(self, moderator_client):
        """Safety note instruction must be present in every Moderator prompt."""
        state = DebateState(
            claim="Drinking bleach cures infections",
            round=3,
            pro_arguments=["R1", "R2", "R3"],
            con_arguments=["R1", "R2", "R3"],
        )
        moderator = Moderator(moderator_client)
        moderator.generate(state)
        prompt = moderator_client.call_structured.call_args.kwargs.get('prompt')
        assert "SAFETY NOTE" in prompt

    def test_verification_rates_in_prompt(self, moderator_client):
        state = DebateState(
            claim="Test", round=4,
            pro_arguments=["A", "B", "C"], con_arguments=["A", "B", "C"],
            pro_verification_rate=0.88, con_verification_rate=0.72,
        )
        Moderator(moderator_client).generate(state)
        prompt = moderator_client.call_structured.call_args.kwargs.get('prompt')
        assert "88.0%" in prompt or "88%" in prompt
        assert "72.0%" in prompt or "72%" in prompt


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — FactChecker
# ═══════════════════════════════════════════════════════════════════════════════

class TestFactChecker:

    @pytest.fixture
    def fc(self, fake_fc_client):
        return FactChecker(llm_client=fake_fc_client)

    @pytest.fixture
    def state_with_sources(self):
        return DebateState(
            claim="Coffee reduces cancer risk",
            pro_sources=[["https://pubmed.ncbi.nlm.nih.gov/12345"]],
            con_sources=[["https://cancer.org/research"]],
        )

    # ── _verify_url: invalid / non-string inputs ──────────────────────────────

    def test_non_string_url_returns_invalid(self, fc):
        result = fc._verify_url(12345, "PRO", "claim", None, None)
        assert result.status == "INVALID_URL"

    def test_none_url_returns_invalid(self, fc):
        result = fc._verify_url(None, "PRO", "claim", None, None)
        assert result.status == "INVALID_URL"

    def test_bare_domain_no_scheme_returns_invalid(self, fc):
        result = fc._verify_url("www.example.com", "PRO", "claim", None, None)
        assert result.status == "INVALID_URL"

    def test_title_string_returns_invalid(self, fc):
        result = fc._verify_url(
            "Stanton et al. 2020 — Exercise and neuroplasticity", "PRO", "claim", None, None
        )
        assert result.status == "INVALID_URL"

    def test_empty_string_returns_invalid(self, fc):
        result = fc._verify_url("", "PRO", "claim", None, None)
        assert result.status == "INVALID_URL"

    # ── _verify_url: HTTP status codes ───────────────────────────────────────

    def test_404_returns_not_found(self, fc, monkeypatch):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.iter_content.return_value = iter([b"Not found"])
        monkeypatch.setattr("requests.get", lambda *a, **kw: mock_resp)
        result = fc._verify_url("https://example.com/missing", "PRO", "claim", None, None)
        assert result.status == "NOT_FOUND"

    def test_timeout_returns_timeout_status(self, fc, monkeypatch):
        import requests as req_mod
        monkeypatch.setattr(
            "requests.get", lambda *a, **kw: (_ for _ in ()).throw(req_mod.Timeout())
        )
        result = fc._verify_url("https://example.com/slow", "PRO", "claim", None, None)
        assert result.status == "TIMEOUT"

    def test_connection_error_returns_error_status(self, fc, monkeypatch):
        import requests as req_mod
        monkeypatch.setattr(
            "requests.get",
            lambda *a, **kw: (_ for _ in ()).throw(req_mod.ConnectionError("failed"))
        )
        result = fc._verify_url("https://example.com/down", "PRO", "claim", None, None)
        assert result.status == "ERROR"

    # ── _verify_url: paywall detection ───────────────────────────────────────

    def test_paywall_content_returns_paywall_restricted(self, fc, monkeypatch):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_content.return_value = iter(
            [b"Please subscribe to read this premium content."]
        )
        monkeypatch.setattr("requests.get", lambda *a, **kw: mock_resp)
        result = fc._verify_url("https://wsj.com/article", "PRO", "claim", None, None)
        assert result.status == "PAYWALL_RESTRICTED"

    # ── _verify_url: pre-fetched content bypass ───────────────────────────────

    def test_prefetched_content_bypasses_http(self, fc, monkeypatch):
        """If content already in evidence_sources, HTTP should not be called."""
        http_calls = []
        monkeypatch.setattr("requests.get", lambda *a, **kw: http_calls.append(1) or MagicMock())

        state = DebateState(
            claim="Test", round=1,
            evidence_sources=[{
                "url": "https://prefetched.com/page",
                "content": "Test claim is supported by evidence."
            }]
        )
        fc._verify_url("https://prefetched.com/page", "PRO", "Test", None, state)
        # HTTP should not be called if content was pre-fetched
        assert len(http_calls) == 0

    # ── _verify_url: agent_source label ──────────────────────────────────────

    def test_agent_source_label_set_correctly(self, fc, monkeypatch):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.iter_content.return_value = iter([b""])
        monkeypatch.setattr("requests.get", lambda *a, **kw: mock_resp)
        result = fc._verify_url("https://example.com/x", "CON", "claim", None, None)
        assert result.agent_source == "CON"

    # ── generate: metrics structure ───────────────────────────────────────────

    def test_generate_returns_agent_response(self, fc, monkeypatch, state_with_sources):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.iter_content.return_value = iter([b""])
        monkeypatch.setattr("requests.get", lambda *a, **kw: mock_resp)
        response = fc.generate(state_with_sources)
        assert response.agent == "FACT_CHECKER"
        assert "verification_results" in response.metrics
        assert "pro_rate" in response.metrics
        assert "con_rate" in response.metrics

    def test_generate_counts_pro_and_con_separately(self, fc, monkeypatch):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_content.return_value = iter([b"coffee cancer research antioxidants reduce"])
        monkeypatch.setattr("requests.get", lambda *a, **kw: mock_resp)
        state = DebateState(
            claim="coffee cancer",
            pro_sources=[["https://a.com"], ["https://b.com"]],
            con_sources=[["https://c.com"]],
        )
        response = fc.generate(state)
        pro_results = [r for r in response.metrics["verification_results"]
                       if r["agent_source"] == "PRO"]
        con_results = [r for r in response.metrics["verification_results"]
                       if r["agent_source"] == "CON"]
        assert len(pro_results) == 2
        assert len(con_results) == 1

    def test_generate_handles_empty_sources_gracefully(self, fc):
        state = DebateState(claim="Test", pro_sources=[], con_sources=[])
        response = fc.generate(state)
        assert response.agent == "FACT_CHECKER"
        assert response.metrics["verification_results"] == []
        assert response.metrics["pro_rate"] == 0.0
        assert response.metrics["con_rate"] == 0.0

    def test_generate_handles_all_sources_invalid(self, fc):
        state = DebateState(
            claim="Test",
            pro_sources=[["Title without URL", "another title"]],
            con_sources=[["Not a URL at all"]],
        )
        response = fc.generate(state)
        for r in response.metrics["verification_results"]:
            assert r["status"] == "INVALID_URL"

    # ── _process_content: trust scoring ──────────────────────────────────────

    def test_verified_source_gets_trust_score(self, fc, monkeypatch):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        # Content without model → falls through to plain VERIFIED
        mock_resp.iter_content.return_value = iter([b"exercise improves mental health benefits"])
        monkeypatch.setattr("requests.get", lambda *a, **kw: mock_resp)
        # Disable model so we hit the plain-VERIFIED path with trust scoring
        fc.model = None
        result = fc._verify_url("https://who.int/health/exercise", "PRO", "exercise", None, None)
        # Should be VERIFIED and have trust_score
        assert result.status == "VERIFIED"
        assert result.trust_score == 1.0  # WHO is AUTHORITATIVE
        assert result.trust_tier == "AUTHORITATIVE"

    def test_unreliable_source_gets_low_trust_score(self, fc, monkeypatch):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_content.return_value = iter([b"some content"])
        monkeypatch.setattr("requests.get", lambda *a, **kw: mock_resp)
        fc.model = None
        result = fc._verify_url("https://infowars.com/article", "CON", "claim", None, None)
        assert result.trust_score == 0.1
        assert result.trust_tier == "UNRELIABLE"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — TrustScorer
# ═══════════════════════════════════════════════════════════════════════════════

class TestTrustScorer:

    @pytest.mark.parametrize("url,expected_score", [
        ("https://www.who.int/news",        1.0),
        ("https://cdc.gov/report",          1.0),
        ("https://nasa.gov/missions",       1.0),
        ("https://nih.gov/research",        1.0),
        ("https://harvard.edu/study",       1.0),
        ("https://nature.com/articles",     1.0),
        ("https://reuters.com/article",     0.8),
        ("https://apnews.com/story",        0.8),
        ("https://bbc.co.uk/news",          0.8),
        ("https://twitter.com/user/123",    0.3),
        ("https://x.com/status/456",        0.3),
        ("https://reddit.com/r/science",    0.3),
        ("https://medium.com/post",         0.3),
        ("https://infowars.com/article",    0.1),
        ("https://naturalnews.com/post",    0.1),
        ("https://breitbart.com/politics",  0.1),
        ("https://myblog.com/post",         0.5),   # GENERAL fallback
    ])
    def test_known_domains(self, url, expected_score):
        assert TrustScorer.get_score(url) == expected_score

    def test_unreliable_checked_first(self):
        """UNRELIABLE check must override any other tier match."""
        score = TrustScorer.get_score("https://infowars.com/some/path")
        assert score == 0.1

    def test_malformed_url_returns_general(self):
        assert TrustScorer.get_score("not_a_url") == 0.5

    def test_empty_url_returns_general(self):
        assert TrustScorer.get_score("") == 0.5

    def test_get_tier_label_authoritative(self):
        assert TrustScorer.get_tier_label(1.0) == "AUTHORITATIVE"

    def test_get_tier_label_credible(self):
        assert TrustScorer.get_tier_label(0.8) == "CREDIBLE"

    def test_get_tier_label_undirected(self):
        assert TrustScorer.get_tier_label(0.3) == "UNDIRECTED"

    def test_www_prefix_stripped(self):
        assert TrustScorer.get_score("https://www.reuters.com/world") == 0.8


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — TemporalVerifier
# ═══════════════════════════════════════════════════════════════════════════════

class TestTemporalVerifier:

    @pytest.fixture
    def tv(self):
        return TemporalVerifier()

    def test_matching_year_returns_aligned(self, tv):
        ok, msg = tv.verify_alignment(
            "Stock market crashed in 2008",
            "The financial crisis of 2008 began in autumn."
        )
        assert ok is True

    def test_missing_year_returns_misaligned(self, tv):
        ok, msg = tv.verify_alignment(
            "Study from 2019 proved X",
            "Research in the late 2010s has shown Y."  # No '2019'
        )
        assert ok is False
        assert "2019" in msg

    def test_no_year_in_claim_always_aligned(self, tv):
        ok, _ = tv.verify_alignment(
            "Coffee is good for you",
            "Some article without any year mention."
        )
        assert ok is True

    def test_no_year_in_content_waived(self, tv):
        """If content has no years at all, alignment is waived (not failed)."""
        ok, msg = tv.verify_alignment(
            "Study from 2022 showed X",
            "Content without any year."
        )
        assert ok is True
        assert "waived" in msg.lower()

    def test_empty_claim_returns_true(self, tv):
        ok, _ = tv.verify_alignment("", "Some content 2020")
        assert ok is True

    def test_empty_content_returns_true(self, tv):
        ok, _ = tv.verify_alignment("Claim from 2020", "")
        assert ok is True

    def test_multiple_years_partial_match(self, tv):
        """Claim cites 2018 and 2019; content has 2019 only → aligned."""
        ok, _ = tv.verify_alignment(
            "Studies from 2018 and 2019 confirmed X",
            "Research published in 2019 found Y."
        )
        assert ok is True

    def test_extract_years_returns_set(self, tv):
        years = tv.extract_years("Events in 2001, 2010, and 2023 were significant.")
        assert years == {"2001", "2010", "2023"}

    def test_extract_years_empty_string(self, tv):
        assert tv.extract_years("") == set()

    def test_years_outside_range_not_extracted(self, tv):
        """Years before 1900 or after 2099 should not be extracted."""
        years = tv.extract_years("Events in 1899 and 2100 were notable.")
        assert "1899" not in years
        assert "2100" not in years


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — URLNormalizer
# ═══════════════════════════════════════════════════════════════════════════════

class TestURLNormalizer:

    @pytest.mark.parametrize("raw,expected", [
        ("https://example.com/page",    "https://example.com/page"),
        ("http://example.com/page",     "http://example.com/page"),
        ("www.example.com",             "https://www.example.com"),
        ("example.com/page",            "https://example.com/page"),
        ("Source: https://example.com", "https://example.com"),
        ("",                            None),
        ("Title of paper",              None),
        ("Stanton et al. 2020",         None),
    ])
    def test_sanitize_url(self, raw, expected):
        assert URLNormalizer.sanitize_url(raw) == expected

    def test_sanitize_list_drops_titles(self):
        result = URLNormalizer.sanitize_list([
            ["Stanton et al. 2020 - Exercise review", "https://valid.com/1"],
            ["https://valid.com/2", "Another title string"],
        ])
        assert result[0] == ["https://valid.com/1"]
        assert result[1] == ["https://valid.com/2"]

    def test_sanitize_list_preserves_structure(self):
        """Output must have same number of rounds as input."""
        inp = [["https://a.com"], [], ["https://b.com", "https://c.com"]]
        out = URLNormalizer.sanitize_list(inp)
        assert len(out) == 3
        assert out[1] == []

    def test_sanitize_list_handles_empty_input(self):
        assert URLNormalizer.sanitize_list([]) == []

    def test_embedded_url_extracted_from_longer_string(self):
        raw = "See also: https://pubmed.ncbi.nlm.nih.gov/article?id=12345 for details"
        url = URLNormalizer.sanitize_url(raw)
        assert url is not None
        assert "pubmed" in url

    def test_non_string_input_coerced(self):
        # Should not crash on non-string input
        result = URLNormalizer.sanitize_url(12345)
        assert result is None or isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8 — DebateState Model
# ═══════════════════════════════════════════════════════════════════════════════

class TestDebateState:

    def test_default_round_is_1(self):
        state = DebateState(claim="Test")
        assert state.round == 1

    def test_default_num_rounds_is_3(self):
        state = DebateState(claim="Test")
        assert state.num_rounds == 3

    def test_get_returns_field_value(self):
        state = DebateState(claim="Test claim")
        assert state.get("claim") == "Test claim"

    def test_get_returns_default_for_missing(self):
        state = DebateState(claim="Test")
        assert state.get("nonexistent_key", "default") == "default"

    def test_get_returns_default_verdict_when_unset(self):
        """verdict defaults to 'UNKNOWN' (non-optional); .get() should return it."""
        state = DebateState(claim="Test")
        assert state.get("verdict", "FALLBACK") == "UNKNOWN"

    def test_dict_style_access(self):
        state = DebateState(claim="Test", round=2)
        assert state["round"] == 2

    def test_dict_style_set(self):
        state = DebateState(claim="Test")
        state["round"] = 3
        assert state.round == 3

    def test_contains_known_field(self):
        state = DebateState(claim="Test")
        assert "claim" in state
        assert "verdict" in state

    def test_contains_unknown_field(self):
        state = DebateState(claim="Test")
        assert "nonexistent" not in state

    def test_api_failure_not_in_base_state(self):
        """api_failure_detected was planned but not yet added — verify no crash."""
        state = DebateState(claim="Test")
        assert state.get("api_failure_detected", False) is False

    def test_summary_field_defaults_empty(self):
        state = DebateState(claim="Test")
        assert state.summary == ""

    def test_is_cached_defaults_false(self):
        state = DebateState(claim="Test")
        assert state.is_cached is False

    def test_parse_obj_from_dict(self):
        data = {
            "claim": "Test",
            "verdict": "TRUE",
            "confidence": 0.9,
            "pro_arguments": ["arg1"],
            "con_arguments": ["arg2"],
            "pro_sources": [["https://example.com"]],
            "con_sources": [["https://counter.com"]],
        }
        state = DebateState.parse_obj(data)
        assert state.claim == "Test"
        assert state.verdict == "TRUE"
        assert state.pro_sources == [["https://example.com"]]


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 9 — Orchestrator Logic (unit — no live graph)
# ═══════════════════════════════════════════════════════════════════════════════

class TestOrchestratorLogic:
    """
    Tests orchestrator's decision functions in isolation (no LangGraph invocation,
    no live API calls, no SQLite/MemorySaver I/O).
    """

    @pytest.fixture
    def orch(self, monkeypatch):
        """
        Build a real DebateOrchestrator but monkeypatch expensive init.
        We patch FreeLLMClient so no API keys are needed.
        """
        from unittest.mock import MagicMock
        import src.orchestration.debate as debate_mod

        fake_client = MagicMock(spec=FreeLLMClient)
        monkeypatch.setattr(debate_mod, "FreeLLMClient", lambda: fake_client)

        from src.orchestration.debate import DebateOrchestrator
        orch = DebateOrchestrator()
        return orch

    # ── _should_continue ─────────────────────────────────────────────────────

    def test_should_continue_after_round_3_con(self, orch):
        """ConAgent increments round from 3 → 4; should_continue receives 4 > 3 → end."""
        state = DebateState(claim="T", round=4, num_rounds=3)
        assert orch._should_continue(state) == "end"

    def test_should_continue_during_round_3(self, orch):
        """During round 3 (not yet incremented), should continue."""
        state = DebateState(claim="T", round=3, num_rounds=3)
        assert orch._should_continue(state) == "continue"

    def test_should_continue_rounds_1_and_2(self, orch):
        for r in [1, 2]:
            state = DebateState(claim="T", round=r, num_rounds=3)
            assert orch._should_continue(state) == "continue"

    def test_should_continue_dict_state(self, orch):
        assert orch._should_continue({"round": 4, "num_rounds": 3}) == "end"
        assert orch._should_continue({"round": 2, "num_rounds": 3}) == "continue"

    # ── _should_retry ─────────────────────────────────────────────────────────

    def test_should_retry_on_low_pro_rate(self, orch):
        state = DebateState(
            claim="T", pro_arguments=["arg"], con_arguments=["arg"],
            pro_verification_rate=0.1, con_verification_rate=0.9,
            retry_count=0,
        )
        assert orch._should_retry(state) == "retry"

    def test_should_proceed_on_low_con_rate_after_retry(self, orch):
        """retry_count >= 1 → don't retry again."""
        state = DebateState(
            claim="T", pro_arguments=["arg"], con_arguments=["arg"],
            pro_verification_rate=0.1, con_verification_rate=0.1,
            retry_count=1,
        )
        assert orch._should_retry(state) == "proceed"

    def test_api_failure_marker_forces_proceed(self, orch):
        """[API_FAILURE] in argument must always return proceed, even with 0% rate."""
        state = DebateState(
            claim="T",
            pro_arguments=["[API_FAILURE] Quota exhausted."],
            con_arguments=["Normal arg"],
            pro_verification_rate=0.0, con_verification_rate=0.0,
            retry_count=0,
        )
        assert orch._should_retry(state) == "proceed"

    def test_api_failure_marker_in_con_forces_proceed(self, orch):
        state = DebateState(
            claim="T",
            pro_arguments=["Normal arg"],
            con_arguments=["[API_FAILURE] Gemini quota hit."],
            pro_verification_rate=0.0, con_verification_rate=0.0,
            retry_count=0,
        )
        assert orch._should_retry(state) == "proceed"

    def test_legitimate_debate_about_api_quota_does_not_trigger_marker(self, orch):
        """Real debate text about 'API' management must NOT trigger the failure marker."""
        state = DebateState(
            claim="API quota management policies are effective",
            pro_arguments=["APIs have quota systems that prevent abuse."],
            con_arguments=["Quota limits harm small developers."],
            pro_verification_rate=0.8, con_verification_rate=0.8,
            retry_count=0,
        )
        # No [API_FAILURE] marker → should not proceed due to marker
        # Rates are high → no retry needed
        assert orch._should_retry(state) == "proceed"

    # ── _should_debate ────────────────────────────────────────────────────────

    def test_should_skip_when_high_confidence_settled(self, orch):
        state = DebateState(claim="T", verdict="FALSE", confidence=0.99)
        assert orch._should_debate(state) == "skip"

    def test_should_debate_when_no_verdict(self, orch):
        state = DebateState(claim="T")  # verdict="UNKNOWN", confidence=0.0 by default
        assert orch._should_debate(state) == "debate"

    def test_should_debate_when_low_confidence(self, orch):
        state = DebateState(claim="T", verdict="TRUE", confidence=0.6)
        assert orch._should_debate(state) == "debate"

    # ── Consensus pre-check: hardcoded SETTLED_TRUTHS ─────────────────────────

    def test_settled_truth_earth_is_flat(self, orch):
        state = DebateState(claim="The earth is flat, not round")
        orch._consensus_check_node(state)
        assert state.verdict == "FALSE"
        assert state.confidence == 1.0

    def test_settled_truth_vaccines_autism(self, orch):
        state = DebateState(claim="Vaccines cause autism in children")
        orch._consensus_check_node(state)
        assert state.verdict == "FALSE"
        assert state.confidence >= 0.99

    def test_settled_truth_climate_change(self, orch):
        state = DebateState(claim="Climate change is real and happening")
        orch._consensus_check_node(state)
        assert state.verdict == "TRUE"
        assert state.confidence >= 0.95

    def test_non_settled_claim_keeps_unknown_verdict(self, orch):
        """A novel claim should not get a verdict from hardcoded dict."""
        state = DebateState(claim="Drinking green tea extends lifespan by 10 years")
        # Mute the LLM call so it doesn't fail without keys
        orch.client.call_structured.side_effect = Exception("no keys")
        orch._consensus_check_node(state)
        # Verdict should still be UNKNOWN (hardcoded didn't match, LLM failed gracefully)
        assert state.verdict == "UNKNOWN"

    def test_consensus_metrics_populated(self, orch):
        """Consensus check must always populate state.metrics['consensus']."""
        state = DebateState(claim="The moon landing was faked")
        orch._consensus_check_node(state)
        assert state.metrics is not None
        assert "consensus" in state.metrics

    # ── _fact_checker_node: URL sanitization ─────────────────────────────────

    def test_fact_checker_node_sanitizes_bare_domains(self, orch, monkeypatch):
        state = DebateState(
            claim="Test",
            pro_sources=[["www.example.com", "TitleString"]],
            con_sources=[],
        )
        orch.fact_checker.generate = MagicMock(
            return_value=AgentResponse(
                agent="FACT_CHECKER", round=1,
                argument="done", sources=[],
                metrics={"verification_results": [], "pro_rate": 0.0, "con_rate": 0.0}
            )
        )
        updated = orch._fact_checker_node(state)
        # Bare domain should be converted to https://
        assert any("https://www.example.com" in url
                   for sources in updated.pro_sources for url in sources)
        # Title string should be dropped
        assert not any("TitleString" in url
                       for sources in updated.pro_sources for url in sources)

    def test_fact_checker_node_sets_verification_rates(self, orch):
        state = DebateState(
            claim="Test",
            pro_sources=[["https://a.com"]],
            con_sources=[["https://b.com"]],
        )
        orch.fact_checker.generate = MagicMock(
            return_value=AgentResponse(
                agent="FACT_CHECKER", round=1, argument="", sources=[],
                metrics={
                    "verification_results": [
                        {"agent_source": "PRO", "status": "VERIFIED"},
                        {"agent_source": "CON", "status": "NOT_FOUND"},
                    ],
                    "pro_rate": 1.0,
                    "con_rate": 0.0,
                }
            )
        )
        updated = orch._fact_checker_node(state)
        assert updated.pro_verification_rate == 1.0
        assert updated.con_verification_rate == 0.0

    # ── _summarize_node ───────────────────────────────────────────────────────

    def test_summarize_node_no_op_on_round_2(self, orch):
        state = DebateState(claim="Test", round=2)
        orch.summarizer.summarize_history = MagicMock(return_value="SUMMARY")
        orch._summarize_node(state)
        orch.summarizer.summarize_history.assert_not_called()

    def test_summarize_node_triggers_on_round_3(self, orch):
        state = DebateState(
            claim="Test", round=3,
            pro_arguments=["R1", "R2"],
            con_arguments=["R1", "R2"],
        )
        orch.summarizer.summarize_history = MagicMock(return_value="UNIQUE_SUMMARY_TEXT")
        orch._summarize_node(state)
        orch.summarizer.summarize_history.assert_called_once()
        assert state.summary == "UNIQUE_SUMMARY_TEXT"

    def test_summarize_node_caps_history_at_5(self, orch):
        state = DebateState(
            claim="Test", round=6,
            pro_arguments=["A"] * 7,
            con_arguments=["B"] * 7,
        )
        orch.summarizer.summarize_history = MagicMock(return_value="s")
        orch._summarize_node(state)
        assert len(state.pro_arguments) == 5
        assert len(state.con_arguments) == 5

    # ── _retry_revision_node ─────────────────────────────────────────────────

    def test_retry_revision_increments_retry_count(self, orch):
        state = DebateState(
            claim="Test", round=4, num_rounds=3,
            pro_arguments=["old pro"],
            con_arguments=["old con"],
            pro_sources=[["https://a.com"]],
            con_sources=[["https://b.com"]],
            retry_count=0,
        )
        orch.pro_agent.generate = MagicMock(
            return_value=AgentResponse(agent="PRO", round=3, argument="new pro", sources=[])
        )
        orch.con_agent.generate = MagicMock(
            return_value=AgentResponse(agent="CON", round=3, argument="new con", sources=[])
        )
        orch._retry_revision_node(state)
        assert state.retry_count == 1

    def test_retry_revision_replaces_last_argument(self, orch):
        state = DebateState(
            claim="Test", round=4, num_rounds=3,
            pro_arguments=["old pro arg"],
            con_arguments=["old con arg"],
            pro_sources=[["https://a.com"]],
            con_sources=[["https://b.com"]],
            retry_count=0,
        )
        orch.pro_agent.generate = MagicMock(
            return_value=AgentResponse(agent="PRO", round=3, argument="REVISED PRO", sources=[])
        )
        orch.con_agent.generate = MagicMock(
            return_value=AgentResponse(agent="CON", round=3, argument="REVISED CON", sources=[])
        )
        orch._retry_revision_node(state)
        assert state.pro_arguments[-1] == "REVISED PRO"
        assert state.con_arguments[-1] == "REVISED CON"

    def test_retry_revision_restores_round_number(self, orch):
        state = DebateState(
            claim="Test", round=4, num_rounds=3,
            pro_arguments=["old"],
            con_arguments=["old"],
            pro_sources=[["https://a.com"]],
            con_sources=[["https://b.com"]],
            retry_count=0,
        )
        orch.pro_agent.generate = MagicMock(
            return_value=AgentResponse(agent="PRO", round=3, argument="new", sources=[])
        )
        orch.con_agent.generate = MagicMock(
            return_value=AgentResponse(agent="CON", round=3, argument="new", sources=[])
        )
        orch._retry_revision_node(state)
        assert state.round == 4   # must be restored to post-increment value


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 10 — ClaimDecomposer (unit)
# ═══════════════════════════════════════════════════════════════════════════════

class TestClaimDecomposer:

    from pydantic import BaseModel as _BM

    @pytest.fixture
    def decomposer_client(self):
        from pydantic import BaseModel
        class _Out(BaseModel):
            claims: list
        client = Mock(spec=FreeLLMClient)
        # Default: return original claim (simulate trivial decomposition)
        client.call_structured.return_value = type("R", (), {"claims": ["atomic part 1", "atomic part 2"]})()
        return client

    def test_short_claim_bypasses_llm(self, decomposer_client):
        """Claims under 10 words with no 'and'/comma skip the LLM call."""
        from src.utils.claim_decomposer import ClaimDecomposer
        d = ClaimDecomposer(decomposer_client)
        result = d.decompose("Exercise is good")
        decomposer_client.call_structured.assert_not_called()
        assert result == ["Exercise is good"]

    def test_complex_claim_calls_llm(self, decomposer_client):
        from src.utils.claim_decomposer import ClaimDecomposer
        d = ClaimDecomposer(decomposer_client)
        long_claim = "Climate change is real and it is caused by human activity and renewable energy can solve it"
        result = d.decompose(long_claim)
        decomposer_client.call_structured.assert_called_once()
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_llm_failure_returns_original(self, decomposer_client):
        from src.utils.claim_decomposer import ClaimDecomposer
        decomposer_client.call_structured.side_effect = Exception("API error")
        d = ClaimDecomposer(decomposer_client)
        original = "Complex claim with and in it that is longer than ten words total"
        result = d.decompose(original)
        assert result == [original]

    def test_empty_llm_response_returns_original(self, decomposer_client):
        from src.utils.claim_decomposer import ClaimDecomposer
        decomposer_client.call_structured.return_value = type("R", (), {"claims": []})()
        d = ClaimDecomposer(decomposer_client)
        original = "Complex claim with and keyword spanning over ten words total here"
        result = d.decompose(original)
        assert result == [original]

    def test_claim_with_comma_triggers_llm(self, decomposer_client):
        from src.utils.claim_decomposer import ClaimDecomposer
        d = ClaimDecomposer(decomposer_client)
        claim = "AI is powerful, and it can replace jobs"
        d.decompose(claim)
        decomposer_client.call_structured.assert_called_once()

    def test_claim_with_and_triggers_llm(self, decomposer_client):
        from src.utils.claim_decomposer import ClaimDecomposer
        d = ClaimDecomposer(decomposer_client)
        claim = "vaccines cause autism and 5G causes cancer and the moon is fake"
        d.decompose(claim)
        decomposer_client.call_structured.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 11 — Summarizer (unit)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSummarizer:

    def test_returns_empty_for_round_le_2(self):
        from src.utils.summarizer import Summarizer
        client = Mock(spec=FreeLLMClient)
        s = Summarizer(client)
        state = DebateState(claim="Test", round=2)
        result = s.summarize_history(state)
        assert result == ""
        client.call.assert_not_called()

    def test_calls_llm_for_round_gt_2(self):
        from src.utils.summarizer import Summarizer
        client = Mock(spec=FreeLLMClient)
        client.call.return_value = "SUMMARY TEXT"
        s = Summarizer(client)
        state = DebateState(
            claim="Test", round=3,
            pro_arguments=["Pro arg 1", "Pro arg 2"],
            con_arguments=["Con arg 1", "Con arg 2"],
        )
        result = s.summarize_history(state)
        client.call.assert_called_once()
        assert result == "SUMMARY TEXT"

    def test_llm_failure_returns_unavailable(self):
        from src.utils.summarizer import Summarizer
        client = Mock(spec=FreeLLMClient)
        client.call.side_effect = Exception("timeout")
        s = Summarizer(client)
        state = DebateState(claim="Test", round=4,
                            pro_arguments=["A"], con_arguments=["B"])
        result = s.summarize_history(state)
        assert "unavailable" in result.lower()

    def test_prompt_contains_pro_and_con_args(self):
        from src.utils.summarizer import Summarizer
        client = Mock(spec=FreeLLMClient)
        client.call.return_value = "ok"
        s = Summarizer(client)
        state = DebateState(
            claim="Test debate",
            round=3,
            pro_arguments=["UNIQUE_PRO_STRING"],
            con_arguments=["UNIQUE_CON_STRING"],
        )
        s.summarize_history(state)
        prompt = client.call.call_args.kwargs.get('prompt')
        assert "UNIQUE_PRO_STRING" in prompt
        assert "UNIQUE_CON_STRING" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
