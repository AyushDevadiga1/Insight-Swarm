"""
DebateOrchestrator - Coordinates multi-round debate using LangGraph and Pydantic models.
"""
import sys
import logging
import sqlite3
from pathlib import Path
from src.utils.claim_decomposer import ClaimDecomposer
from src.utils.summarizer import Summarizer
from typing import List, Dict, Optional, Literal, Any
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

# Add parent directories to path
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
    """
    Orchestrates multi-round debate using LangGraph.
    """

    def __init__(self, llm_client=None, pro_agent=None, con_agent=None,
                 fact_checker=None, moderator=None):
        self.client = llm_client or FreeLLMClient()
        self.pro_agent = pro_agent or ProAgent(self.client)
        self.con_agent = con_agent or ConAgent(self.client)
        self.fact_checker = fact_checker or FactChecker(self.client)
        self.moderator = moderator or Moderator(self.client)
        self.summarizer = Summarizer(self.client)

        # Persistent SQLite checkpointing — single connection, thread-safe
        self.conn = sqlite3.connect("insightswarm_graph.db", check_same_thread=False)
        self.checkpointer = SqliteSaver(self.conn)
        self.graph = self._build_graph()

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

        workflow.add_conditional_edges(
            "consensus_check",
            self._should_debate,
            {"skip": "moderator", "debate": "summarizer"},
        )

        workflow.add_edge("summarizer", "pro_agent")
        workflow.add_edge("pro_agent",  "con_agent")

        workflow.add_conditional_edges(
            "con_agent",
            self._should_continue,
            {"continue": "summarizer", "end": "fact_checker"},
        )

        workflow.add_conditional_edges(
            "fact_checker",
            self._should_retry,
            {"retry": "revision", "proceed": "moderator"},
        )

        workflow.add_edge("revision",  "fact_checker")
        workflow.add_edge("moderator", "verdict")
        workflow.add_edge("verdict",   END)

        return workflow.compile(checkpointer=self.checkpointer)

    # ── Graph nodes ───────────────────────────────────────────────────────────

    def _summarize_node(self, state: DebateState) -> DebateState:
        """Compress debate history when rounds accumulate (fixes context overflow)."""
        if state.round > 2:
            logger.info("Round > 2 — generating debate summary.")
            state.summary = self.summarizer.summarize_history(state)

        # Cap argument lists to 5 rounds to prevent memory growth
        if len(state.pro_arguments) > 5:
            logger.info("Capping argument history at 5 rounds.")
            state.pro_arguments = state.pro_arguments[-5:]
            state.con_arguments = state.con_arguments[-5:]

        return state

    def _consensus_check_node(self, state: DebateState) -> DebateState:
        """Fast consensus pre-check using Gemini — skips full debate for settled facts."""
        logger.info(f"Consensus pre-check for: {state.claim}")

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
            response = self.client.call_structured(
                prompt=prompt,
                output_schema=ConsensusResponse,
                temperature=0.1,
                preferred_provider="gemini",
            )

            if response.verdict != "DEBATE" and response.confidence > 0.9:
                state.verdict = response.verdict
                state.confidence = response.confidence
                state.moderator_reasoning = f"Consensus Pre-Check: {response.reasoning}"
                logger.info(f"Consensus found: {state.verdict}")

            if state.metrics is None:
                state.metrics = {}
            state.metrics["consensus"] = {
                "verdict":   response.verdict,
                "reasoning": response.reasoning,
                "score":     response.confidence,
            }

        except Exception as e:
            logger.warning(f"Consensus check failed: {e}")

        return state

    def _should_debate(self, state: DebateState) -> Literal["skip", "debate"]:
        if state.verdict in ("TRUE", "FALSE", "NEUTRAL") and (state.confidence or 0) > 0.9:
            return "skip"
        return "debate"

    def _pro_agent_node(self, state: DebateState) -> DebateState:
        logger.info(f"ProAgent — Round {state.round}")
        response = self.pro_agent.generate(state)
        state.pro_arguments.append(response.argument)
        state.pro_sources.append(response.sources)
        return state

    def _con_agent_node(self, state: DebateState) -> DebateState:
        logger.info(f"ConAgent — Round {state.round}")
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

        # Use short, unambiguous markers that won't appear in genuine debate text
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
        state.round  = state.num_rounds  # agents build prompts for the correct round

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
            metrics  = response.metrics or {} if not isinstance(response, dict) else response

            verification_results = metrics.get("verification_results", [])
            state.verification_results = verification_results

            pro_rate = metrics.get("pro_rate")
            con_rate = metrics.get("con_rate")

            if pro_rate is None or con_rate is None:
                pro_src_count = sum(len(s) for s in (state.pro_sources or []))
                con_src_count = sum(len(s) for s in (state.con_sources or []))
                pro_verified  = sum(1 for r in verification_results
                                    if r.get("agent_source") == "PRO" and r.get("status") == "VERIFIED")
                con_verified  = sum(1 for r in verification_results
                                    if r.get("agent_source") == "CON" and r.get("status") == "VERIFIED")
                if pro_rate is None:
                    pro_rate = (pro_verified / pro_src_count) if pro_src_count else 0.0
                if con_rate is None:
                    con_rate = (con_verified / con_src_count) if con_src_count else 0.0

            state.pro_verification_rate = pro_rate
            state.con_verification_rate = con_rate
        except Exception as e:
            logger.error(f"FactChecker failed: {e}")
        return state

    def _moderator_node(self, state: DebateState) -> DebateState:
        try:
            response = self.moderator.generate(state)
            state.verdict            = response.verdict
            state.confidence         = response.confidence
            state.moderator_reasoning = response.reasoning
            state.metrics            = response.metrics
        except RateLimitError as e:
            logger.error("Moderator rate limited.")
            state.verdict    = "RATE_LIMITED"
            state.confidence = 0.0
            if not state.moderator_reasoning:
                hint = f" Retry after ~{e.retry_after:.0f}s." if e.retry_after else ""
                state.moderator_reasoning = f"Rate limit exceeded.{hint}"
            state.metrics = {}
        return state

    def _verdict_node(self, state: DebateState) -> DebateState:
        logger.info(f"Final verdict: {state.verdict} (confidence: {state.confidence})")
        return state

    # ── Public API ────────────────────────────────────────────────────────────

    def _switch_all_to_gemini(self) -> None:
        logger.warning("Switching all agents to Gemini fallback mode.")
        self.client.groq_available    = False
        self.client._preferred_provider = "gemini"

    def _safe_error_response(self, agent_name: str, round_num: int,
                             claim: str, error: str) -> AgentResponse:
        return AgentResponse(
            agent=agent_name, round=round_num,
            argument=f"Technical error while arguing '{claim}': {error}",
            sources=[], confidence=0.0,
            reasoning=f"Systemic failure: {error}", metrics={},
        )

    def run(self, claim: str, thread_id: str = "default") -> DebateState:
        logger.info(f"Running debate on: {claim}")

        # Decompose multi-part claims — process the primary atomic claim
        decomposer  = ClaimDecomposer(self.client)
        sub_claims  = decomposer.decompose(claim)
        target_claim = sub_claims[0]
        if len(sub_claims) > 1:
            logger.info(f"Multi-part claim — primary: '{target_claim}'")

        # Semantic cache check
        cache = get_cache()
        cached = cache.get_verdict(target_claim)
        if cached:
            state = DebateState.parse_obj(cached)
            state.is_cached = True
            return state

        # Pre-debate evidence retrieval (Tavily dual-sided search)
        tavily = get_tavily_retriever()
        adversarial = tavily.search_adversarial(claim, max_results=5)

        initial_state = DebateState(
            claim=claim,
            pro_evidence=adversarial["pro"],
            con_evidence=adversarial["con"],
            evidence_sources=adversarial["pro"] + adversarial["con"],
        )

        try:
            config      = {"configurable": {"thread_id": thread_id}}
            final_state = self.graph.invoke(initial_state, config=config)

            if not hasattr(final_state, "to_dict"):
                if isinstance(final_state, dict):
                    final_state = DebateState.parse_obj(final_state)
                else:
                    final_state = DebateState.parse_obj(dict(final_state))

            if not final_state.verdict:
                final_state.verdict = "ERROR"
                final_state.confidence = final_state.confidence or 0.0
                if not final_state.moderator_reasoning:
                    final_state.moderator_reasoning = "No verdict produced due to upstream errors."

            # Write to cache only for valid, confident verdicts
            if final_state.verdict not in ("ERROR", "RATE_LIMITED", "SYSTEM_ERROR", None):
                if final_state.verdict != "INSUFFICIENT EVIDENCE" or \
                        (final_state.confidence is not None and final_state.confidence > 0.1):
                    import json
                    set_cached_verdict(target_claim, json.loads(final_state.json()))
                else:
                    logger.warning("Skipping cache — low-confidence INSUFFICIENT EVIDENCE.")
            else:
                logger.warning(f"Skipping cache — invalid verdict: {final_state.verdict}")

            return final_state

        except Exception as e:
            logger.error(f"Debate failed: {e}")
            initial_state.verdict = "INSUFFICIENT EVIDENCE"
            initial_state.confidence = 0.0
            initial_state.moderator_reasoning = f"System-level error: {str(e)}"
            initial_state.metrics = {}
            return initial_state

    def stream(self, claim: str, thread_id: str = "default"):
        """Stream debate progress for real-time UI updates."""
        logger.info(f"Streaming debate on: {claim}")

        decomposer   = ClaimDecomposer(self.client)
        sub_claims   = decomposer.decompose(claim)
        target_claim = sub_claims[0]
        if len(sub_claims) > 1:
            logger.info(f"Multi-part claim (stream) — primary: '{target_claim}'")

        cache = get_cache()
        cached = cache.get_verdict(target_claim)
        if cached:
            state = DebateState.parse_obj(cached)
            state.is_cached = True
            yield "cache_hit", state
            return

        tavily = get_tavily_retriever()
        adversarial = tavily.search_adversarial(target_claim, max_results=5)

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
                last_state = DebateState.parse_obj(event) if isinstance(event, dict) else event
                yield "progress", last_state

            if last_state.verdict not in ("ERROR", "RATE_LIMITED", "SYSTEM_ERROR", None):
                if last_state.verdict != "INSUFFICIENT EVIDENCE" or \
                        (last_state.confidence is not None and last_state.confidence > 0.1):
                    import json
                    set_cached_verdict(target_claim, json.loads(last_state.json()))

            yield "complete", last_state

        except Exception as e:
            logger.error(f"Stream failed: {e}")
            last_state.verdict = "INSUFFICIENT EVIDENCE"
            last_state.confidence = 0.0
            last_state.moderator_reasoning = f"System-level error during streaming: {str(e)}"
            yield "error", last_state


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    orchestrator = DebateOrchestrator()
    res = orchestrator.run("Does coffee cause cancer?")
    print(f"VERDICT: {res.verdict}")
