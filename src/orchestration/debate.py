"""
DebateOrchestrator - Coordinates multi-round debate using LangGraph and Pydantic models.
"""
import sys
import logging
from pathlib import Path
from src.utils.claim_decomposer import ClaimDecomposer
from src.utils.summarizer import Summarizer
from typing import TypedDict, List, Dict, Optional, Annotated, Literal, Any
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

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
from src.resource.manager import get_resource_manager
from src.ui.progress_tracker import ProgressTracker, Stage

logger = logging.getLogger(__name__)

# Observable logger — streams to debug.log + UI log panel
try:
    from src.utils.observable_logger import get_observable_logger as _get_obs_log
    _obs = _get_obs_log()
except Exception:
    _obs = None  # graceful degradation if not yet installed

def _olog(level: str, msg: str, **kw) -> None:
    """Emit to observable logger if available (never raises)."""
    try:
        if _obs:
            _obs.log(level, "Orchestrator", msg, **kw)
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════════

class DebateOrchestrator:
    """
    Orchestrates multi-round debate using LangGraph.
    """
    
    def __init__(self, llm_client=None, pro_agent=None, con_agent=None, 
                 fact_checker=None, moderator=None, tracker=None):
        """
        Initialize DebateOrchestrator with dependency injection for better testability.
        
        Args:
            llm_client: LLM client instance (defaults to FreeLLMClient)
            pro_agent: ProAgent instance (defaults to ProAgent)
            con_agent: ConAgent instance (defaults to ConAgent)  
            fact_checker: FactChecker instance (defaults to FactChecker)
            moderator: Moderator instance (defaults to Moderator)
        """
        _olog("INFO", "🔧 Initializing DebateOrchestrator...")
        self.client = llm_client or FreeLLMClient()
        self.tracker = tracker or ProgressTracker()
        
        # Dynamic Model Pairing based on current availability (TEMPORARY OVERRIDE)
        # We are moving away from OpenRouter (Credits) and Cerebras (DNS) 
        # to ensure the app remains functional for the user.
        
        self.pro_agent = pro_agent or ProAgent(self.client, preferred_provider="groq")
        self.con_agent = con_agent or ConAgent(self.client, preferred_provider="groq")
        self.fact_checker = fact_checker or FactChecker(self.client, preferred_provider="gemini")
        self.moderator = moderator or Moderator(self.client, preferred_provider="gemini")
        self.summarizer = Summarizer(self.client)
        self.decomposer = ClaimDecomposer(self.client)
        
        self.resource_manager = get_resource_manager()
        
        # Register cache evictors so memory is actually reclaimed under pressure
        def _evict_caches():
            try:
                cache = get_cache()
                if cache._l1_cache:
                    cache._l1_cache.clear()
                cache._embedding_index = None
                cache._index_dirty = True
                logger.info("Memory evictor: cleared L1 cache and embedding index")
            except Exception as ex:
                logger.warning(f"Cache eviction failed: {ex}")
        
        self.resource_manager.register_evictor(_evict_caches)
        
        self.checkpointer = MemorySaver()
        self.graph = self._build_graph()
        _olog("INFO", "✅ DebateOrchestrator ready")
    
    def _build_graph(self) -> Any:
        # We use the Pydantic model as the state schema
        # LangGraph works with Pydantic models by using their field annotations
        workflow = StateGraph(DebateState)
        
        workflow.add_node("consensus_check", self._consensus_check_node)
        workflow.add_node("pro_agent", self._pro_agent_node)
        workflow.add_node("con_agent", self._con_agent_node)
        workflow.add_node("fact_checker", self._fact_checker_node)
        workflow.add_node("moderator", self._moderator_node)
        workflow.add_node("verdict", self._verdict_node)
        workflow.add_node("revision", self._retry_revision_node)
        workflow.add_node("summarizer", self._summarize_node)
        
        # Define edges
        workflow.add_edge(START, "consensus_check")
        
        workflow.add_conditional_edges(
            "consensus_check",
            self._should_debate,
            {
                "skip": "moderator",
                "debate": "summarizer"
            }
        )
        
        workflow.add_edge("summarizer", "pro_agent")
        
        workflow.add_edge("pro_agent", "con_agent")
        
        # Insert mid-debate verification gate after ConAgent
        workflow.add_conditional_edges(
            "con_agent",
            self._should_continue,
            {"continue": "summarizer", "end": "fact_checker"}
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

    def _summarize_node(self, state: DebateState) -> DebateState:
        """NEW: Phase 5 Context Management (#20, #29)."""
        self.tracker.update(Stage.INITIALIZING, "Summarizing context for current round...")
        if state['round'] > 2:
            logger.info("Debate round > 2, generating summary of history.")
            state['summary'] = self.summarizer.summarize_history(state)
        
        # Phase 5: History Capping (Optimized to 2 rounds to save tokens)
        if len(state['pro_arguments']) > 2:
            logger.info("History exceeds 2 rounds, capping to save tokens.")
            state['pro_arguments'] = state['pro_arguments'][-2:]
            state['con_arguments'] = state['con_arguments'][-2:]
            state['pro_sources'] = state['pro_sources'][-2:]
            state['con_sources'] = state['con_sources'][-2:]
            
        # Phase 3: Resource Management
        self.resource_manager.check_and_reclaim()
        
        return state

    def _consensus_check_node(self, state: DebateState) -> DebateState:
        """NEW: Phase 3 Consensus Pre-Check Node using LLM and settled science."""
        self.tracker.update(Stage.SEARCHING, f"Consensus pre-check for claim: {state['claim'][:30]}...")
        logger.info(f"Consensus pre-check for claim: {state['claim']}")
        
        # Initialize verification rates to prevent TypeError in Moderator if debate is skipped
        if state['pro_verification_rate'] is None:
            state['pro_verification_rate'] = 0.0
        if state['con_verification_rate'] is None:
            state['con_verification_rate'] = 0.0
        
        claim_lower = state['claim'].lower()
        
        # Hardcoded settled science (proven facts, skip expensive LLM call)
        SETTLED_TRUTHS = {
            'earth is flat': ('FALSE', 1.0, 'Earth is an oblate spheroid - proven by physics and satellite imagery.'),
            'earth is round': ('TRUE', 1.0, 'Earth is an oblate spheroid - global scientific consensus.'),
            'vaccines cause autism': ('FALSE', 0.99, 'Extensively debunked by global medical research (CDC, WHO).'),
            'smoking causes cancer': ('TRUE', 0.99, 'Established medical consensus over decades of research.'),
            'climate change is real': ('TRUE', 0.98, 'Scientific consensus from IPCC and major scientific academies.'),
            'water is h2o': ('TRUE', 1.0, 'Fundamental chemical composition of water.'),
            'moon landing was faked': ('FALSE', 1.0, 'Extensively documented historical fact with physical evidence.'),
            'sun revolves around earth': ('FALSE', 1.0, 'Heliocentric model is a fundamental fact of astronomy.')
        }

        # Check hardcoded first
        for keyword, (verdict, conf, reasoning) in SETTLED_TRUTHS.items():
            if keyword in claim_lower:
                state['verdict'] = verdict
                state['confidence'] = conf
                state['moderator_reasoning'] = f"Settled Science: {reasoning}"
                logger.info(f"✅ Hardcoded consensus: {verdict}")
                
                # Still populate metrics for consistency
                if state['metrics'] is None: state['metrics'] = {}
                state['metrics']["consensus"] = {
                    "verdict": verdict,
                    "reasoning": reasoning,
                    "score": conf
                }
                # Populate synthetic entries so the Moderator has context
                # and the UI debate tab is not blank
                if not state['pro_arguments']:
                    state['pro_arguments'] = [f"[Settled science] {reasoning}"]
                if not state['con_arguments']:
                    state['con_arguments'] = [
                        f"[Consensus verdict: {verdict} with {conf:.0%} confidence — no debate required]"
                    ]
                if not state['pro_sources']:
                    state['pro_sources'] = [[]]
                if not state['con_sources']:
                    state['con_sources'] = [[]]
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
            # Use Gemini for cheap, fast consensus check
            # Use Gemini for cheap, fast consensus check
            response = self.client.call_structured(
                prompt=prompt,
                output_schema=ConsensusResponse,
                temperature=0.1,
                preferred_provider="gemini"
            )
            
            # response is now a ConsensusResponse object
            if response.verdict != "DEBATE" and response.confidence > 0.9:
                state['verdict'] = response.verdict
                state['confidence'] = response.confidence
                state['moderator_reasoning'] = f"Consensus Pre-Check: {response.reasoning}"
                logger.info(f"Consensus found: {state['verdict']}")
                
                # POPULATE SYNTHETIC ARGUMENTS HERE (NODE PERSISTS STATE)
                if not state['pro_arguments']:
                    state['pro_arguments'] = [f"[Consensus found] {response.reasoning}"]
                if not state['con_arguments']:
                    state['con_arguments'] = [f"[Consensus skip: {response.verdict}]"]
                if not state['pro_sources']:
                    state['pro_sources'] = [[]]
                if not state['con_sources']:
                    state['con_sources'] = [[]]
            
            # Save raw consensus data for Moderator's composite score
            if state['metrics'] is None: state['metrics'] = {}
            state['metrics']["consensus"] = {
                "verdict": response.verdict,
                "reasoning": response.reasoning,
                "score": response.confidence
            }
            
        except Exception as e:
            logger.warning(f"Consensus check failed: {e}")
            
        return state

    def _should_debate(self, state: DebateState) -> Literal["skip", "debate"]:
        # Logic: If consensus was already reached and confidence is high, skip the debate round.
        if state['verdict'] in ("TRUE", "FALSE", "NEUTRAL") and state['confidence'] > 0.9:
            return "skip"
        return "debate"

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
        stage = getattr(Stage, f"ROUND_{state['round']}_PRO", Stage.ROUND_1_PRO)
        self.tracker.update(stage, f"ProAgent arguing — Round {state['round']}")
        logger.info(f"ProAgent turn - Round {state['round']}")
        _olog("INFO", f"💬 ProAgent arguing — Round {state['round']}")
        response = self.pro_agent.generate(state)   # No try/except needed anymore
        state['pro_arguments'].append(response.argument)
        state['pro_sources'].append(response.sources)
        _olog("DEBUG", f"ProAgent response received", round=state['round'],
              sources=len(response.sources or []))
        return state

    def _con_agent_node(self, state: DebateState) -> DebateState:
        stage = getattr(Stage, f"ROUND_{state['round']}_CON", Stage.ROUND_1_CON)
        self.tracker.update(stage, f"ConAgent rebutting — Round {state['round']}")
        logger.info(f"ConAgent turn - Round {state['round']}")
        _olog("INFO", f"🔴 ConAgent rebutting — Round {state['round']}")
        response = self.con_agent.generate(state)
        state['con_arguments'].append(response.argument)
        state['con_sources'].append(response.sources)
        state['round'] += 1
        _olog("DEBUG", f"ConAgent response received", round=state['round'] - 1,
              sources=len(response.sources or []))
        return state
    
    def _should_continue(self, state: DebateState) -> Literal["continue", "end"]:
        # Logic: If round < num_rounds AND we don't have a high confidence verdict yet
        if state['round'] <= state['num_rounds']:
            return "continue"
        return "end"

    def _should_retry(self, state: DebateState) -> Literal["retry", "proceed"]:
        pro_rate = state['pro_verification_rate'] if state['pro_verification_rate'] is not None else 0.0
        con_rate = state['con_verification_rate'] if state['con_verification_rate'] is not None else 0.0
        if (pro_rate < 0.3 or con_rate < 0.3) and state['retry_count'] < 1:
            return "retry"
        return "proceed"

    def _retry_revision_node(self, state: DebateState) -> DebateState:
        logger.info("Revision loop triggered")
        state['retry_count'] += 1

        # Temporarily set round to the last real debate round so agents build
        # prompts for the correct context (not round 4 which does not exist).
        saved_round = state['round']
        state['round'] = state['num_rounds']  # = 3

        pro_resp = self.pro_agent.generate(state)
        if state['pro_arguments']:
            state['pro_arguments'][-1] = pro_resp.argument
        if state['pro_sources']:
            state['pro_sources'][-1] = pro_resp.sources

        con_resp = self.con_agent.generate(state)
        if state['con_arguments']:
            state['con_arguments'][-1] = con_resp.argument
        if state['con_sources']:
            state['con_sources'][-1] = con_resp.sources

        # Restore the post-increment round value so the rest of the graph
        # sees the correct state.
        state.round = saved_round
        return state
    
    def _fact_checker_node(self, state: DebateState) -> DebateState:
        self.tracker.update(Stage.FACT_CHECKING, "FactChecker verifying sources...")
        logger.info("FactChecker verifying sources...")
        _olog("INFO", "✅ FactChecker verifying sources...")
        try:
            state.pro_sources = URLNormalizer.sanitize_list(state.pro_sources)
            state.con_sources = URLNormalizer.sanitize_list(state.con_sources)

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
            logger.error(f"FactChecker failed: {e}", exc_info=True)
            # Ensure Moderator never receives None for these fields
            state.verification_results = state.verification_results or []
            state.pro_verification_rate = (
                state.pro_verification_rate if state.pro_verification_rate is not None else 0.0
            )
            state.con_verification_rate = (
                state.con_verification_rate if state.con_verification_rate is not None else 0.0
            )
            return state
    
    def _moderator_node(self, state: DebateState) -> DebateState:
        self.tracker.update(Stage.MODERATING, "Moderator synthesizing verdict...")
        _olog("INFO", "⚖️ Moderator synthesizing verdict...")
        try:
            response = self.moderator.generate(state)
            state['verdict'] = response.verdict
            state['confidence'] = response.confidence
            state['moderator_reasoning'] = response.reasoning
            state['metrics'] = response.metrics
            
            _olog("INFO", f"🏁 Debate Complete", verdict=state['verdict'])
            return state
        except RateLimitError as e:
            logger.warning(f"Moderator node: Rate limit hit: {e}")
            state['verdict'] = "RATE_LIMITED"
            state['confidence'] = 0.0
            if state['moderator_reasoning'] is None:
                retry_hint = f" Retry after ~{e.retry_after:.0f}s." if e.retry_after else ""
                state['moderator_reasoning'] = f"Rate limit exceeded.{retry_hint}"
            state['metrics'] = {}
            return state

    def _verdict_node(self, state: DebateState) -> DebateState:
        self.tracker.update(Stage.COMPLETE, f"Final Verdict: {state['verdict']}")
        logger.info(f"Final Verdict: {state['verdict']} (Confidence: {state['confidence']})")
        _olog("INFO", f"🎯 Verdict: {state['verdict']}",
              confidence=state['confidence'], verdict=state['verdict'])
        return state
    
    def run(self, claim: str, thread_id: str = "default") -> DebateState:
        logger.info(f"Running debate on: {claim}")
        _olog("INFO", f"🔍 Starting debate", claim=claim[:80])
        
        # Phase 4: Proactive Caching (Optimization 4-B)
        # Check unified semantic cache BEFORE decomposition to save API costs
        cache = get_cache()
        cached_result = cache.get_verdict(claim)
        if cached_result:
            state = DebateState.parse_obj(cached_result)
            state.is_cached = True
            return state

        # Phase 5: Claim Decomposition (#09)
        sub_claims = self.decomposer.decompose(claim)
        target_claim = sub_claims[0] 
        if len(sub_claims) > 1:
            logger.info(f"Multi-part claim detected. Processing primary part: '{target_claim}'")
        
        # Retrieve dual-sided evidence before debate for balanced analysis
        import concurrent.futures as _cf
        tavily = get_tavily_retriever()
        try:
            with _cf.ThreadPoolExecutor(max_workers=1) as _tex:
                _fut = _tex.submit(tavily.search_adversarial, claim, 5)
                adversarial_sources = _fut.result(timeout=12)  # 12 second max 
        except Exception:
            logger.warning("Tavily timed out or failed — proceeding without pre-fetched evidence")
            adversarial_sources = {"pro": [], "con": []}
        
        initial_state = DebateState(
            claim=claim, 
            pro_evidence=adversarial_sources["pro"],
            con_evidence=adversarial_sources["con"],
            evidence_sources=adversarial_sources["pro"] + adversarial_sources["con"] # RAAD: Root grounded context
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
                if final_state.verdict != "INSUFFICIENT EVIDENCE" or (final_state.confidence is not None and final_state.confidence > 0.1):
                    import json
                    state_json = json.loads(final_state.json())
                    set_cached_verdict(target_claim, state_json) # Cache target_claim
                else:
                    logger.warning("Skipping cache write for low-confidence Insufficient Evidence.")
            else:
                logger.warning(f"Skipping cache write due to invalid verdict: {final_state.verdict}")
            return final_state
        except Exception as e:
            logger.error(f"Debate failed: {e}")
            # Fix 4-A: More accurate error classification
            if "quota" in str(e).lower() or "limit" in str(e).lower() or "429" in str(e):
                initial_state.verdict = "RATE_LIMITED"
                initial_state.moderator_reasoning = "The debate was interrupted because API quotas were exhausted. Please try again in 1-2 minutes or use a different provider."
            else:
                initial_state.verdict = "SYSTEM_ERROR"
                initial_state.moderator_reasoning = f"Analysis failed due to a system error: {str(e)}"
            
            initial_state.confidence = 0.0
            initial_state.metrics = {}
            return initial_state

    def stream(self, claim: str, thread_id: str = "default"):
        """Stream debate progress for real-time UI updates."""
        logger.info(f"Steaming debate on: {claim}")
        
        # Phase 4: Proactive Caching (Optimization 4-B)
        cache = get_cache()
        cached_result = cache.get_verdict(claim)
        if cached_result:
            state = DebateState.parse_obj(cached_result)
            state.is_cached = True
            yield "cache_hit", state
            return

        # Phase 5: Claim Decomposition (#09)
        sub_claims = self.decomposer.decompose(claim)
        target_claim = sub_claims[0]
        if len(sub_claims) > 1:
            logger.info(f"Multi-part claim detected in stream. Processing primary part: '{target_claim}'")

        # Phase 3: RAAD - Retrieve First
        import concurrent.futures as _cf
        tavily = get_tavily_retriever()
        try:
            with _cf.ThreadPoolExecutor(max_workers=1) as _tex:
                _fut = _tex.submit(tavily.search_adversarial, target_claim, 5)
                adversarial_sources = _fut.result(timeout=12)
        except Exception:
            logger.warning("Tavily timed out or failed in stream — proceeding without pre-fetched evidence")
            adversarial_sources = {"pro": [], "con": []}
        
        initial_state = DebateState(
            claim=target_claim, 
            pro_evidence=adversarial_sources["pro"],
            con_evidence=adversarial_sources["con"],
            evidence_sources=adversarial_sources["pro"] + adversarial_sources["con"] # RAAD: Root grounded context
        )
        
        config = {"configurable": {"thread_id": thread_id}}
        
        # Stream from LangGraph
        last_state = initial_state
        try:
            for event in self.graph.stream(initial_state, config=config, stream_mode="values"):
                # LangGraph 'values' mode returns the state after each node
                if isinstance(event, dict):
                    last_state = DebateState.parse_obj(event)
                else:
                    last_state = event
                
                # Determine current active node if possible, or just yield state
                yield "progress", last_state
                
            # Final caching logic
            if last_state.verdict and last_state.verdict not in ("ERROR", "RATE_LIMITED", "SYSTEM_ERROR"):
                if last_state.verdict != "INSUFFICIENT EVIDENCE" or (last_state.confidence is not None and last_state.confidence > 0.1):
                    import json
                    state_json = json.loads(last_state.json())
                    set_cached_verdict(target_claim, state_json)
            
            yield "complete", last_state
            
        except Exception as e:
            logger.error(f"Stream failed: {e}")
            last_state.verdict = "INSUFFICIENT EVIDENCE"
            last_state.confidence = 0.0
            last_state.moderator_reasoning = f"System-level error during streaming: {str(e)}"
            yield "error", last_state


    def close(self):
        """No-op for backward compatibility with older tests."""
        pass

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    orchestrator = DebateOrchestrator()
    res = orchestrator.run("Does coffee cause cancer?")
    print(f"VERDICT: {res.verdict}")
