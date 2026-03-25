"""
FIX FILE 3 — src/orchestration/debate.py  (full replacement)
Fixes:
  P0-5  Default providers changed: Pro→groq, Con→gemini (most reliable free-tier pair)
  P0-6  .json() / .parse_obj() → Pydantic v2 APIs (.model_dump_json() / .model_validate())
  P1-7  Consensus check: substring→word-boundary match; timeout guard added
  P3-3  Outer except no longer swallows all exceptions blindly
  P3-4  Removed redundant @retry on _call_groq (handled inside client now)

Drop-in replacement for src/orchestration/debate.py.
"""
import sys
import logging
import json
from pathlib import Path
from src.utils.claim_decomposer import ClaimDecomposer
from src.utils.summarizer import Summarizer
from typing import List, Dict, Optional, Literal, Any
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.models import DebateState, AgentResponse, ConsensusResponse
from src.agents.pro_agent import ProAgent
from src.agents.con_agent import ConAgent
from src.agents.fact_checker import FactChecker
from src.agents.moderator import Moderator
from src.orchestration.cache import get_cached_verdict, set_cached_verdict, get_cache
from src.utils.tavily_retriever import get_tavily_retriever
from src.llm.client import FreeLLMClient, RateLimitError
from src.utils.url_helper import URLNormalizer

logger = logging.getLogger(__name__)


class DebateOrchestrator:
    """Orchestrates multi-round debate using LangGraph."""

    def __init__(self, llm_client=None, pro_agent=None, con_agent=None,
                 fact_checker=None, moderator=None):
        self.client = llm_client or FreeLLMClient()

        # P0-5 fix: default to groq/gemini — the two most reliable free-tier providers.
        # Cerebras and OpenRouter are aggressively quota-limited on free plans; they remain
        # available as fallbacks inside FreeLLMClient's provider rotation logic.
        self.pro_agent    = pro_agent    or ProAgent(self.client,    preferred_provider="groq")
        self.con_agent    = con_agent    or ConAgent(self.client,    preferred_provider="gemini")
        self.fact_checker = fact_checker or FactChecker(self.client, preferred_provider="groq")
        self.moderator    = moderator    or Moderator(self.client)
        self.summarizer        = Summarizer(self.client)
        self.claim_decomposer  = ClaimDecomposer(self.client)

        self.checkpointer = MemorySaver()
        self.graph        = self._build_graph()

    # ── Graph construction ────────────────────────────────────────────────────

    def _build_graph(self) -> Any:
        workflow = StateGraph(DebateState)

        workflow.add_node("consensus_check", self._consensus_check_node)
        workflow.add_node("summarizer",      self._summarize_node)
        workflow.add_node("pro_agent",       self._pro_agent_node)
        workflow.add_node("con_agent",       self._con_agent_node)
        workflow.add_node("fact_checker",    self._fact_checker_node)
        workflow.add_node("moderator",       self._moderator_node)
        workflow.add_node("verdict",         self._verdict_node)
        workflow.add_node("revision",        self._retry_revision_node)

        workflow.add_edge(START, "consensus_check")
        workflow.add_conditional_edges("consensus_check", self._should_debate,
                                       {"skip": "moderator", "debate": "summarizer"})
        workflow.add_edge("summarizer", "pro_agent")
        workflow.add_edge("pro_agent",  "con_agent")
        workflow.add_conditional_edges("con_agent", self._should_continue,
                                       {"continue": "summarizer", "end": "fact_checker"})
        workflow.add_conditional_edges("fact_checker", self._should_retry,
                                       {"retry": "revision", "proceed": "moderator"})
        workflow.add_edge("revision",  "fact_checker")
        workflow.add_edge("moderator", "verdict")
        workflow.add_edge("verdict",   END)

        return workflow.compile(checkpointer=self.checkpointer)

    # ── Graph nodes ───────────────────────────────────────────────────────────

    def _summarize_node(self, state: DebateState) -> DebateState:
        if state.round > 2:
            logger.info("Round > 2 — generating debate summary.")
            state.summary = self.summarizer.summarize_history(state)
        if len(state.pro_arguments) > 5:
            state.pro_arguments = state.pro_arguments[-5:]
            state.con_arguments = state.con_arguments[-5:]
        return state

    def _consensus_check_node(self, state: DebateState) -> DebateState:
        """
        P1-7 fix:
        - Use word-boundary regex instead of substring match for hardcoded facts
        - Wrap Gemini call in a timeout guard
        """
        import re
        logger.info("Consensus pre-check for: %s", state.claim)
        claim_lower = state.claim.lower()

        SETTLED_TRUTHS = {
            r'\bearth is flat\b':          ('FALSE', 1.0, 'Earth is an oblate spheroid — proven by physics and satellite imagery.'),
            r'\bearth is round\b':         ('TRUE',  1.0, 'Earth is an oblate spheroid — global scientific consensus.'),
            r'\bvaccines cause autism\b':  ('FALSE', 0.99, 'Extensively debunked by global medical research (CDC, WHO).'),
            r'\bsmoking causes cancer\b':  ('TRUE',  0.99, 'Established medical consensus over decades of research.'),
            r'\bclimate change is real\b': ('TRUE',  0.98, 'Scientific consensus from IPCC and major scientific academies.'),
            r'\bwater is h2o\b':           ('TRUE',  1.0, 'Fundamental chemical composition of water.'),
            r'\bmoon landing was faked\b': ('FALSE', 1.0, 'Extensively documented historical fact with physical evidence.'),
            r'\bsun revolves around earth\b': ('FALSE', 1.0, 'Heliocentric model is a fundamental fact of astronomy.'),
        }

        for pattern, (verdict, conf, reasoning) in SETTLED_TRUTHS.items():
            if re.search(pattern, claim_lower):
                state.verdict    = verdict
                state.confidence = conf
                state.moderator_reasoning = f"Settled Science: {reasoning}"
                if state.metrics is None:
                    state.metrics = {}
                state.metrics["consensus"] = {"verdict": verdict, "reasoning": reasoning, "score": conf}
                logger.info("Hardcoded consensus: %s", verdict)
                return state

        prompt = f"""You are a Consensus Checker. Determine if there is a massive, widely accepted scientific or authoritative consensus on the following claim.
CLAIM: {state.claim}

Respond in JSON format:
{{
  "verdict": "TRUE" | "FALSE" | "NEUTRAL" | "DEBATE",
  "reasoning": "Brief explanation citing authoritative bodies (WHO, NASA, CDC, etc.)",
  "confidence": 0.0-1.0
}}

If the claim is factually settled (e.g. Earth is round), return TRUE/FALSE.
If it is controversial or requires current events analysis, return DEBATE.
"""
        try:
            import concurrent.futures as _cf
            with _cf.ThreadPoolExecutor(max_workers=1) as tex:
                fut = tex.submit(
                    self.client.call_structured,
                    prompt, ConsensusResponse, 0.1, 500, 1, "gemini"
                )
                response = fut.result(timeout=15)   # P1-7 fix: timeout guard

            if response.verdict != "DEBATE" and response.confidence > 0.9:
                state.verdict    = response.verdict
                state.confidence = response.confidence
                state.moderator_reasoning = f"Consensus Pre-Check: {response.reasoning}"
                logger.info("Consensus found: %s", state.verdict)

            if state.metrics is None:
                state.metrics = {}
            state.metrics["consensus"] = {
                "verdict":   response.verdict,
                "reasoning": response.reasoning,
                "score":     response.confidence,
            }
        except Exception as e:
            logger.warning("Consensus check failed (non-fatal): %s", e)

        return state

    def _should_debate(self, state: DebateState) -> Literal["skip", "debate"]:
        if state.verdict in ("TRUE", "FALSE", "NEUTRAL") and (state.confidence or 0) > 0.9:
            return "skip"
        return "debate"

    def _pro_agent_node(self, state: DebateState) -> DebateState:
        logger.info("ProAgent — Round %d", state.round)
        response = self.pro_agent.generate(state)
        state.pro_arguments.append(response.argument)
        state.pro_sources.append(response.sources)
        return state

    def _con_agent_node(self, state: DebateState) -> DebateState:
        logger.info("ConAgent — Round %d", state.round)
        response = self.con_agent.generate(state)
        state.con_arguments.append(response.argument)
        state.con_sources.append(response.sources)
        state.round += 1
        return state

    def _should_continue(self, state: DebateState) -> Literal["continue", "end"]:
        if isinstance(state, dict):
            return "end" if state.get("round", 1) > state.get("num_rounds", 3) else "continue"
        return "end" if state.round > state.num_rounds else "continue"

    def _should_retry(self, state: DebateState) -> Literal["retry", "proceed"]:
        last_pro = state.pro_arguments[-1] if state.pro_arguments else ""
        last_con = state.con_arguments[-1] if state.con_arguments else ""
        if "[API_FAILURE]" in last_pro or "[API_FAILURE]" in last_con:
            logger.warning("API failure marker detected — skipping revision loop.")
            return "proceed"
        pro_rate = state.pro_verification_rate or 0.0
        con_rate = state.con_verification_rate or 0.0
        if (pro_rate < 0.3 or con_rate < 0.3) and state.retry_count < 1:
            return "retry"
        return "proceed"

    def _retry_revision_node(self, state: DebateState) -> DebateState:
        logger.info("Revision loop triggered.")
        state.retry_count += 1
        saved_round  = state.round
        state.round  = state.num_rounds

        pro_resp = self.pro_agent.generate(state)
        if state.pro_arguments:
            state.pro_arguments[-1] = pro_resp.argument
        if state.pro_sources:
            state.pro_sources[-1]   = pro_resp.sources

        con_resp = self.con_agent.generate(state)
        if state.con_arguments:
            state.con_arguments[-1] = con_resp.argument
        if state.con_sources:
            state.con_sources[-1]   = con_resp.sources

        state.round = saved_round
        return state

    def _fact_checker_node(self, state: DebateState) -> DebateState:
        logger.info("FactChecker verifying sources...")
        try:
            state.pro_sources = URLNormalizer.sanitize_list(state.pro_sources)
            state.con_sources = URLNormalizer.sanitize_list(state.con_sources)

            response = self.fact_checker.generate(state)
            metrics  = response.metrics or {}

            verification_results          = metrics.get("verification_results", [])
            state.verification_results    = verification_results
            state.pro_verification_rate   = metrics.get("pro_rate", 0.0)
            state.con_verification_rate   = metrics.get("con_rate", 0.0)
        except Exception as e:
            logger.error("FactChecker failed: %s", e)
        return state

    def _moderator_node(self, state: DebateState) -> DebateState:
        try:
            response                  = self.moderator.generate(state)
            state.verdict             = response.verdict
            state.confidence          = response.confidence
            state.moderator_reasoning = response.reasoning
            state.metrics             = response.metrics
        except RateLimitError as e:
            logger.error("Moderator rate limited.")
            state.verdict    = "RATE_LIMITED"
            state.confidence = 0.0
            hint = f" Retry after ~{e.retry_after:.0f}s." if e.retry_after else ""
            state.moderator_reasoning = state.moderator_reasoning or f"Rate limit exceeded.{hint}"
            state.metrics = {}
        return state

    def _verdict_node(self, state: DebateState) -> DebateState:
        logger.info("Final verdict: %s (confidence: %s)", state.verdict, state.confidence)
        return state

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self, claim: str, thread_id: str = "default") -> DebateState:
        logger.info("Running debate on: %s", claim)

        cache  = get_cache()
        cached = cache.get_verdict(claim)
        if cached:
            state          = DebateState.model_validate(cached)   # P0-6 fix: Pydantic v2
            state.is_cached = True
            return state

        sub_claims   = self.claim_decomposer.decompose(claim)
        target_claim = sub_claims[0]
        if len(sub_claims) > 1:
            logger.info("Multi-part claim — primary: %r", target_claim)

        import concurrent.futures as _cf
        tavily = get_tavily_retriever()
        try:
            with _cf.ThreadPoolExecutor(max_workers=1) as tex:
                fut        = tex.submit(tavily.search_adversarial, target_claim, 5)
                adversarial = fut.result(timeout=12)
        except Exception:
            logger.warning("Tavily timed out or failed — proceeding without evidence")
            adversarial = {"pro": [], "con": []}

        initial_state = DebateState(
            claim=target_claim,
            pro_evidence=adversarial["pro"],
            con_evidence=adversarial["con"],
            evidence_sources=adversarial["pro"] + adversarial["con"],
        )

        final_state = initial_state  # safe default for error path
        try:
            config      = {"configurable": {"thread_id": thread_id}}
            raw_result  = self.graph.invoke(initial_state, config=config)

            if isinstance(raw_result, dict):
                final_state = DebateState.model_validate(raw_result)   # P0-6 fix
            elif hasattr(raw_result, "model_dump"):
                final_state = raw_result
            else:
                final_state = DebateState.model_validate(dict(raw_result))

            if not final_state.verdict:
                final_state.verdict    = "ERROR"
                final_state.confidence = final_state.confidence or 0.0
                if not final_state.moderator_reasoning:
                    final_state.moderator_reasoning = "No verdict produced due to upstream errors."

            # Cache only valid, confident verdicts
            if final_state.verdict not in ("ERROR", "RATE_LIMITED", "SYSTEM_ERROR", None):
                if final_state.verdict != "INSUFFICIENT EVIDENCE" or \
                        (final_state.confidence is not None and final_state.confidence > 0.1):
                    try:
                        # P0-6 fix: Pydantic v2 serialisation
                        set_cached_verdict(target_claim, json.loads(final_state.model_dump_json()))
                    except Exception as cache_err:
                        logger.warning("Cache write failed (non-fatal): %s", cache_err)

            return final_state

        except (ValueError, TypeError, AttributeError) as programming_error:
            # P3-3 fix: don't swallow programming errors — re-raise so they surface during dev
            logger.error("Programming error in debate graph: %s", programming_error)
            raise
        except Exception as e:
            # Only swallow runtime/API errors, not bugs
            logger.error("Debate failed (runtime): %s", e)
            final_state.verdict    = "INSUFFICIENT EVIDENCE"
            final_state.confidence = 0.0
            final_state.moderator_reasoning = f"Runtime error: {str(e)}"
            final_state.metrics    = {}
            return final_state

    def stream(self, claim: str, thread_id: str = "default"):
        logger.info("Streaming debate on: %s", claim)

        cache  = get_cache()
        cached = cache.get_verdict(claim)
        if cached:
            state          = DebateState.model_validate(cached)   # P0-6 fix
            state.is_cached = True
            yield "cache_hit", state
            return

        sub_claims   = self.claim_decomposer.decompose(claim)
        target_claim = sub_claims[0]

        import concurrent.futures as _cf
        tavily = get_tavily_retriever()
        try:
            with _cf.ThreadPoolExecutor(max_workers=1) as tex:
                fut        = tex.submit(tavily.search_adversarial, target_claim, 5)
                adversarial = fut.result(timeout=12)
        except Exception:
            logger.warning("Tavily timed out (stream) — proceeding without evidence")
            adversarial = {"pro": [], "con": []}

        initial_state = DebateState(
            claim=target_claim,
            pro_evidence=adversarial["pro"],
            con_evidence=adversarial["con"],
            evidence_sources=adversarial["pro"] + adversarial["con"],
        )

        config     = {"configurable": {"thread_id": thread_id}}
        last_state = initial_state

        try:
            for event in self.graph.stream(initial_state, config=config, stream_mode="values"):
                if isinstance(event, dict):
                    last_state = DebateState.model_validate(event)
                else:
                    last_state = event
                yield "progress", last_state

            if last_state.verdict not in ("ERROR", "RATE_LIMITED", "SYSTEM_ERROR", None):
                if last_state.verdict != "INSUFFICIENT EVIDENCE" or \
                        (last_state.confidence is not None and last_state.confidence > 0.1):
                    try:
                        set_cached_verdict(target_claim, json.loads(last_state.model_dump_json()))
                    except Exception as cache_err:
                        logger.warning("Stream cache write failed (non-fatal): %s", cache_err)

            yield "complete", last_state

        except (ValueError, TypeError, AttributeError) as programming_error:
            logger.error("Programming error during stream: %s", programming_error)
            raise
        except Exception as e:
            logger.error("Stream failed (runtime): %s", e)
            last_state.verdict    = "INSUFFICIENT EVIDENCE"
            last_state.confidence = 0.0
            last_state.moderator_reasoning = f"Runtime error during streaming: {str(e)}"
            yield "error", last_state
