"""
DebateOrchestrator - Coordinates multi-round debate using LangGraph and Pydantic models.
"""
import sys
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, cast, Literal
from langgraph.graph import StateGraph, START, END

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.models import DebateState, AgentResponse
from src.agents.pro_agent import ProAgent
from src.agents.con_agent import ConAgent
from src.agents.fact_checker import FactChecker
from src.agents.moderator import Moderator
from src.orchestration.cache import get_cached_verdict, set_cached_verdict
from src.llm.client import FreeLLMClient

logger = logging.getLogger(__name__)

class DebateOrchestrator:
    """
    Orchestrates multi-round debate using LangGraph.
    """
    
    def __init__(self):
        self.client = FreeLLMClient()
        self.pro_agent = ProAgent(self.client)
        self.con_agent = ConAgent(self.client)
        self.fact_checker = FactChecker(self.client)
        self.moderator = Moderator(self.client)
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
        
        workflow.set_entry_point("pro_agent")
        workflow.add_edge("pro_agent", "con_agent")
        
        workflow.add_conditional_edges(
            "con_agent",
            self._should_continue,
            {"continue": "pro_agent", "end": "fact_checker"}
        )
        
        workflow.add_conditional_edges(
            "fact_checker",
            self._should_retry,
            {"retry": "revision", "proceed": "moderator"}
        )
        
        workflow.add_edge("revision", "moderator")
        workflow.add_edge("moderator", "verdict")
        workflow.add_edge("verdict", END)
        
        return workflow.compile()
    
    def _pro_agent_node(self, state: DebateState) -> DebateState:
        logger.info(f"ProAgent turn - Round {state.round}")
        try:
            response = self.pro_agent.generate(state)
            state.pro_arguments.append(response.argument)
            state.pro_sources.append(response.sources)
            return state
        except Exception as e:
            logger.error(f"ProAgent failed: {e}")
            raise
    
    def _con_agent_node(self, state: DebateState) -> DebateState:
        logger.info(f"ConAgent turn - Round {state.round}")
        try:
            response = self.con_agent.generate(state)
            state.con_arguments.append(response.argument)
            state.con_sources.append(response.sources)
            state.round += 1
            return state
        except Exception as e:
            logger.error(f"ConAgent failed: {e}")
            raise
    
    def _should_continue(self, state: DebateState) -> Literal["continue", "end"]:
        if state.round > state.num_rounds:
            return "end"
        return "continue"

    def _should_retry(self, state: DebateState) -> Literal["retry", "proceed"]:
        # Check for technical errors in the last round arguments
        # If we hit quota or 400 errors, don't waste more API calls in a revision loop
        last_pro = state.pro_arguments[-1] if state.pro_arguments else ""
        last_con = state.con_arguments[-1] if state.con_arguments else ""
        
        error_keywords = ["Technical error", "Quota exceeded", "429", "model_decommissioned"]
        if any(kw in last_pro or kw in last_con for kw in error_keywords):
            logger.warning("Technical failure detected in debate rounds. Short-circuiting revision loop.")
            return "proceed"
            
        pro_rate = state.pro_verification_rate or 0.0
        con_rate = state.con_verification_rate or 0.0
        if (pro_rate < 0.3 or con_rate < 0.3) and state.retry_count < 1:
            return "retry"
        return "proceed"

    def _retry_revision_node(self, state: DebateState) -> DebateState:
        logger.info("Revision loop triggered")
        state.retry_count += 1
        # In a real revision we would pass feedback, for now just rerun the agents
        state = self._pro_agent_node(state)
        state = self._con_agent_node(state)
        return state
    
    def _fact_checker_node(self, state: DebateState) -> DebateState:
        logger.info("FactChecker verifying sources...")
        try:
            response = self.fact_checker.generate(state)
            metrics = response.metrics or {}
            state.verification_results = metrics.get('verification_results', [])
            state.pro_verification_rate = metrics.get('pro_rate', 0.0)
            state.con_verification_rate = metrics.get('con_rate', 0.0)
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
        except Exception as e:
            logger.error(f"Moderator failed: {e}")
            return state

    def _verdict_node(self, state: DebateState) -> DebateState:
        logger.info(f"Final Verdict: {state.verdict} (Confidence: {state.confidence})")
        return state
    
    def run(self, claim: str, thread_id: str = "default") -> DebateState:
        logger.info(f"Running debate on: {claim}")
        
        # Check cache
        cached = get_cached_verdict(claim)
        if cached:
            # Reconstruct model from dict
            state = DebateState.parse_obj(cached)
            state.is_cached = True
            return state
            
        initial_state = DebateState(claim=claim)
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
            
            # Save to cache as dict
            set_cached_verdict(claim, final_state.to_dict())
            return final_state
        except Exception as e:
            logger.error(f"Debate failed: {e}")
            initial_state.verdict = "ERROR"
            initial_state.confidence = 0.0
            initial_state.moderator_reasoning = str(e)
            return initial_state

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    orchestrator = DebateOrchestrator()
    res = orchestrator.run("Does coffee cause cancer?")
    print(f"VERDICT: {res.verdict}")