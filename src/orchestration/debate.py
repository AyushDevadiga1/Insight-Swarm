"""
DebateOrchestrator - Coordinates multi-round debate using LangGraph and Pydantic models.
"""
import sys
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, cast, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.models import DebateState, AgentResponse
from src.agents.pro_agent import ProAgent
from src.agents.con_agent import ConAgent
from src.agents.fact_checker import FactChecker
from src.agents.moderator import Moderator
from src.orchestration.cache import get_cached_verdict, set_cached_verdict, get_cache
from src.utils.tavily_retriever import get_tavily_retriever
from src.llm.client import FreeLLMClient, RateLimitError

logger = logging.getLogger(__name__)

class DebateOrchestrator:
    """
    Orchestrates multi-round debate using LangGraph.
    """
    
    def __init__(self, llm_client=None, pro_agent=None, con_agent=None, 
                 fact_checker=None, moderator=None):
        """
        Initialize DebateOrchestrator with dependency injection for better testability.
        
        Args:
            llm_client: LLM client instance (defaults to FreeLLMClient)
            pro_agent: ProAgent instance (defaults to ProAgent)
            con_agent: ConAgent instance (defaults to ConAgent)  
            fact_checker: FactChecker instance (defaults to FactChecker)
            moderator: Moderator instance (defaults to Moderator)
        """
        self.client = llm_client or FreeLLMClient()
        self.pro_agent = pro_agent or ProAgent(self.client)
        self.con_agent = con_agent or ConAgent(self.client)
        self.fact_checker = fact_checker or FactChecker(self.client)
        self.moderator = moderator or Moderator(self.client)
        self.checkpointer = MemorySaver()
        self.graph = self._build_graph()
    
    def _build_graph(self) -> Any:
        # We use the Pydantic model as the state schema
        # LangGraph works with Pydantic models by using their field annotations
        workflow = StateGraph(DebateState)
        
        workflow.add_node("pro_agent", self._pro_agent_node)
        workflow.add_node("con_agent", self._con_agent_node)
        workflow.add_node("fact_checker", self._fact_checker_node)
        workflow.add_node("moderator", self._moderator_node)
        workflow.add_node("verdict", self._verdict_node)
        workflow.add_node("revision", self._retry_revision_node)
        workflow.add_node("verification_gate", self._verification_gate_node)
        
        workflow.set_entry_point("pro_agent")
        workflow.add_edge("pro_agent", "con_agent")
        
        # Insert mid-debate verification gate after ConAgent
        workflow.add_edge("con_agent", "verification_gate")
        
        workflow.add_conditional_edges(
            "verification_gate",
            self._should_continue,
            {"continue": "pro_agent", "end": "fact_checker"}
        )
        
        workflow.add_conditional_edges(
            "fact_checker",
            self._should_retry,
            {"retry": "revision", "proceed": "moderator"}
        )
        
        workflow.add_edge("revision", "fact_checker")
        workflow.add_edge("moderator", "verdict")
        workflow.add_edge("verdict", END)
        
        return workflow.compile(checkpointer=self.checkpointer)

    def _switch_all_to_gemini(self) -> None:
        """Force all agents to prefer Gemini and stop attempting Groq."""
        logger.warning("Switching all agents to Gemini fallback mode due to consistent errors.")
        self.client.groq_available = False
        self.client._preferred_provider = "gemini"

    def _safe_error_response(self, agent_name: str, round_num: int, claim: str, error: str) -> AgentResponse:
        """Return a safe fallback structured response to prevent app crashes."""
        return AgentResponse(
            agent=agent_name,
            round=round_num,
            argument=f"I encountered a technical error while arguing '{claim}'. Error details: {error}",
            sources=[],
            confidence=0.0,
            verdict=None,
            reasoning=f"Systemic failure: {error}",
            metrics={}
        )
    
    def _pro_agent_node(self, state: DebateState) -> DebateState:
        logger.info(f"ProAgent turn - Round {state.round}")
        response = self.pro_agent.generate(state)   # No try/except needed anymore
        state.pro_arguments.append(response.argument)
        state.pro_sources.append(response.sources)
        return state

    def _con_agent_node(self, state: DebateState) -> DebateState:
        logger.info(f"ConAgent turn - Round {state.round}")
        response = self.con_agent.generate(state)
        state.con_arguments.append(response.argument)
        state.con_sources.append(response.sources)
        state.round += 1
        return state
    
    def _should_continue(self, state: DebateState) -> Literal["continue", "end"]:
        if isinstance(state, dict):
            round_num = state.get("round", 1)
            num_rounds = state.get("num_rounds", 3)
            return "end" if round_num > num_rounds else "continue"
        if state.round > state.num_rounds:
            return "end"
        return "continue"

    def _should_retry(self, state: DebateState) -> Literal["retry", "proceed"]:
        last_pro = state.pro_arguments[-1] if state.pro_arguments else ""
        last_con = state.con_arguments[-1] if state.con_arguments else ""
        
        if any(phrase in last_pro or phrase in last_con for phrase in ["QUOTA EXHAUSTED", "API ERROR FALLBACK", "LLM call failed"]):
            logger.warning("API failure detected in debate. Skipping revision loop.")
            return "proceed"
        
        # existing rate checks...
        pro_rate = state.pro_verification_rate or 0.0
        con_rate = state.con_verification_rate or 0.0
        if (pro_rate < 0.3 or con_rate < 0.3) and state.retry_count < 1:
            return "retry"
        return "proceed"

    def _verification_gate_node(self, state: DebateState) -> DebateState:
        # round_idx is 0-based index of the round just completed.
        # len(state.pro_sources) equals the number of completed rounds.
        round_idx = len(state.pro_sources) - 1

        # Do not run on the very first entry (no sources yet) or on the
        # final round (verification feedback would never be used by any agent).
        if round_idx < 0 or round_idx >= state.num_rounds - 1:
            return state

        logger.info("Running mid-debate verification gate for round %d...", round_idx + 1)

        sources_to_check = []
        if len(state.pro_sources) > round_idx:
            argument = state.pro_arguments[round_idx] if len(state.pro_arguments) > round_idx else ""
            for url in state.pro_sources[round_idx]:
                sources_to_check.append((url, "PRO", argument))
        if len(state.con_sources) > round_idx:
            argument = state.con_arguments[round_idx] if len(state.con_arguments) > round_idx else ""
            for url in state.con_sources[round_idx]:
                sources_to_check.append((url, "CON", argument))

        failed_sources = []
        for url, agent, argument in sources_to_check:
            try:
                verification = self.fact_checker._verify_url(url, agent, argument)
                if verification.status != "VERIFIED":
                    failed_sources.append(url)
            except Exception as e:
                logger.warning(f"Verification gate failed for {url}: {e}")
                failed_sources.append(url)

        if failed_sources:
            state.verification_feedback = (
                "WARNING: The following sources failed verification:\n" +
                "\n".join(f"- {url}" for url in failed_sources) +
                "\n\nYou must revise your argument without these sources."
            )
            logger.info(f"Verification gate caught {len(failed_sources)} failed sources.")

        return state

    def _retry_revision_node(self, state: DebateState) -> DebateState:
        logger.info("Revision loop triggered")
        state.retry_count += 1

        # Temporarily set round to the last real debate round so agents build
        # prompts for the correct context (not round 4 which does not exist).
        saved_round = state.round
        state.round = state.num_rounds  # = 3

        pro_resp = self.pro_agent.generate(state)
        if state.pro_arguments:
            state.pro_arguments[-1] = pro_resp.argument
        if state.pro_sources:
            state.pro_sources[-1] = pro_resp.sources

        con_resp = self.con_agent.generate(state)
        if state.con_arguments:
            state.con_arguments[-1] = con_resp.argument
        if state.con_sources:
            state.con_sources[-1] = con_resp.sources

        # Restore the post-increment round value so the rest of the graph
        # sees the correct state.
        state.round = saved_round
        return state
    
    def _fact_checker_node(self, state: DebateState) -> DebateState:
        logger.info("FactChecker verifying sources...")
        try:
            # Sanitize sources before handing to FactChecker to reduce noisy fetch attempts.
            def _sanitize_list_of_sources(list_of_lists):
                import re
                from urllib.parse import urlparse

                URL_RE = re.compile(r"(https?://[^\s\)\]\}<>\"']+)")
                BARE_DOMAIN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-\.]+\.[A-Za-z]{2,}([/?#].*)?$")

                sanitized = []
                skipped = 0
                for round_sources in list_of_lists:
                    new_round = []
                    for s in round_sources:
                        try:
                            if not isinstance(s, str):
                                s = str(s)
                            original = s.strip()
                            if not original:
                                skipped += 1
                                continue

                            # Extract embedded URLs like "Source Name - https://example.com"
                            match = URL_RE.search(original)
                            if match:
                                new_round.append(match.group(1))
                                continue

                            parsed = urlparse(original)
                            if parsed.scheme in ("http", "https") and parsed.netloc:
                                new_round.append(original)
                                continue

                            # Heuristic: bare domains like 'www.example.com' -> add https://
                            if " " not in original and BARE_DOMAIN_RE.match(original):
                                new_round.append("https://" + original)
                                continue

                            # Otherwise treat as a non-URL citation/title and skip
                            skipped += 1
                        except Exception:
                            skipped += 1
                    sanitized.append(new_round)
                if skipped:
                    logger.info("Skipped %d non-URL sources during sanitization", skipped)
                return sanitized

            state.pro_sources = _sanitize_list_of_sources(state.pro_sources)
            state.con_sources = _sanitize_list_of_sources(state.con_sources)

            response = self.fact_checker.generate(state)
            if isinstance(response, dict):
                metrics = response
            else:
                metrics = response.metrics or {}
            verification_results = metrics.get('verification_results', [])
            state.verification_results = verification_results

            pro_rate = metrics.get('pro_rate', None)
            con_rate = metrics.get('con_rate', None)

            if pro_rate is None or con_rate is None:
                pro_sources_count = sum(len(s) for s in (state.pro_sources or []))
                con_sources_count = sum(len(s) for s in (state.con_sources or []))
                pro_verified = sum(
                    1 for r in verification_results
                    if r.get('agent_source') == 'PRO' and r.get('status') == 'VERIFIED'
                )
                con_verified = sum(
                    1 for r in verification_results
                    if r.get('agent_source') == 'CON' and r.get('status') == 'VERIFIED'
                )
                if pro_rate is None:
                    pro_rate = (pro_verified / pro_sources_count) if pro_sources_count else 0.0
                if con_rate is None:
                    con_rate = (con_verified / con_sources_count) if con_sources_count else 0.0

            state.pro_verification_rate = pro_rate
            state.con_verification_rate = con_rate
            return state
        except Exception as e:
            logger.error(f"FactChecker failed: {e}")
            return state
    
    def _moderator_node(self, state: DebateState) -> DebateState:
        try:
            response = self.moderator.generate(state)
            state.verdict = response.verdict
            state.confidence = response.confidence
            state.moderator_reasoning = response.reasoning
            state.metrics = response.metrics
            return state
        except RateLimitError as e:
            # Only reachable if generate() re-raises instead of falling back.
            logger.error("Moderator rate limited; aborting debate run.")
            state.verdict = "RATE_LIMITED"
            state.confidence = 0.0
            if not state.moderator_reasoning:
                retry_hint = f" Retry after ~{e.retry_after:.0f}s." if e.retry_after else ""
                state.moderator_reasoning = f"Rate limit exceeded.{retry_hint}"
            state.metrics = {}
            return state

    def _verdict_node(self, state: DebateState) -> DebateState:
        logger.info(f"Final Verdict: {state.verdict} (Confidence: {state.confidence})")
        return state
    
    def run(self, claim: str, thread_id: str = "default") -> DebateState:
        logger.info(f"Running debate on: {claim}")
        
        # Check unified semantic cache first
        cache = get_cache()
        cached_result = cache.get_verdict(claim)
        if cached_result:
            # Reconstruct state from cached result
            state = DebateState.parse_obj(cached_result)
            state.is_cached = True
            return state
        
        # Retrieve dual-sided evidence before debate for balanced analysis
        tavily = get_tavily_retriever()
        adversarial_sources = tavily.search_adversarial(claim, max_results=5)
        
        initial_state = DebateState(
            claim=claim, 
            pro_evidence=adversarial_sources["pro"],
            con_evidence=adversarial_sources["con"]
        )
        try:
            config = {"configurable": {"thread_id": thread_id}}
            final_state = self.graph.invoke(initial_state, config=config)
            
            # Ensure final_state is a DebateState model
            if not hasattr(final_state, 'to_dict'):
                if isinstance(final_state, dict):
                    final_state = DebateState.parse_obj(final_state)
                else:
                    # Fallback for unexpected types
                    logger.warning(f"Unexpected final_state type: {type(final_state)}. Attempting conversion.")
                    final_state = DebateState.parse_obj(dict(final_state))

            if not final_state.verdict:
                final_state.verdict = "ERROR"
                final_state.confidence = final_state.confidence or 0.0
                if not final_state.moderator_reasoning:
                    final_state.moderator_reasoning = "No verdict was produced due to upstream errors."
            
            # Save to cache only when verdict is valid and confidence is high enough to be meaningful
            # This prevents technical failures (INSUFFICIENT EVIDENCE with 0.0 confidence)
            # from being poisoned into the semantic cache.
            # Serialization uses recursive json parsing to avoid losing nested models (#08)
            if final_state.verdict and final_state.verdict not in ("ERROR", "RATE_LIMITED", "SYSTEM_ERROR"):
                if final_state.verdict != "INSUFFICIENT EVIDENCE" or final_state.confidence > 0.1:
                    import json
                    state_json = json.loads(final_state.json())
                    set_cached_verdict(claim, state_json)
                else:
                    logger.warning("Skipping cache write for low-confidence Insufficient Evidence.")
            else:
                logger.warning(f"Skipping cache write due to invalid verdict: {final_state.verdict}")
            return final_state
        except Exception as e:
            logger.error(f"Debate failed: {e}")
            initial_state.verdict = "INSUFFICIENT EVIDENCE"
            initial_state.confidence = 0.0
            initial_state.moderator_reasoning = f"System-level error (likely API quota): {str(e)}"
            return initial_state

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    orchestrator = DebateOrchestrator()
    res = orchestrator.run("Does coffee cause cancer?")
    print(f"VERDICT: {res.verdict}")
