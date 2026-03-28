"""
src/orchestration/debate.py — All batches applied. Final production version.
Single definition of every method. No duplicates.
"""
import sys, logging, json, re
from pathlib import Path
from typing import Optional, Literal, Any

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver


sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.models import DebateState, AgentResponse, ConsensusResponse
from src.agents.pro_agent import ProAgent
from src.agents.con_agent import ConAgent
from src.agents.fact_checker import FactChecker
from src.agents.moderator import Moderator
from src.orchestration.cache import get_cached_verdict, set_cached_verdict, get_cache
from src.utils.tavily_retriever import get_tavily_retriever
from src.utils.claim_decomposer import ClaimDecomposer
from src.utils.summarizer import Summarizer
from src.llm.client import FreeLLMClient, RateLimitError
from src.utils.url_helper import URLNormalizer

logger = logging.getLogger(__name__)

SETTLED_TRUTHS = {
    r"earth is flat":             ("FALSE", 1.0,  "Earth is an oblate spheroid."),
    r"earth is round":            ("TRUE",  1.0,  "Earth is an oblate spheroid."),
    r"vaccines cause autism":     ("FALSE", 0.99, "Debunked by global medical research."),
    r"\bsmoking causes cancer\b":     ("TRUE",  0.99, "Established medical consensus."),
    r"\bclimate change is real\b":    ("TRUE",  0.98, "IPCC scientific consensus."),
    r"\bwater is h2o\b":              ("TRUE",  1.0,  "Fundamental chemistry."),
    r"\bmoon landing was faked\b":    ("FALSE", 1.0,  "Documented historical fact."),
    r"\bsun revolves around earth\b": ("FALSE", 1.0,  "Heliocentric model."),
}


class DebateOrchestrator:
    def __init__(self, llm_client=None, pro_agent=None, con_agent=None,
                 fact_checker=None, moderator=None, tracker=None):
        self.client  = llm_client or FreeLLMClient()
        self.tracker = tracker

        self.pro_agent    = pro_agent    or ProAgent(self.client,    preferred_provider="groq")
        self.con_agent    = con_agent    or ConAgent(self.client,    preferred_provider="gemini")
        self.fact_checker = fact_checker or FactChecker(self.client, preferred_provider="groq")
        self.moderator    = moderator    or Moderator(self.client)
        self.summarizer       = Summarizer(self.client)
        self.claim_decomposer = ClaimDecomposer(self.client)
        self.checkpointer = SqliteSaver.from_conn_string("insightswarm_graph.db")
        self.graph        = self._build_graph()

    def set_tracker(self, tracker) -> None:
        """Inject tracker without rebuilding graph."""
        self.tracker = tracker

    def _set_stage(self, stage_name: str, message: str = "") -> None:
        if self.tracker is None: return
        try:
            from src.ui.progress_tracker import Stage
            self.tracker.set_stage(Stage(stage_name), message)
        except Exception:
            pass

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
                                       {"skip":"moderator","debate":"summarizer"})
        workflow.add_edge("summarizer", "pro_agent")
        workflow.add_edge("pro_agent",  "con_agent")
        workflow.add_conditional_edges("con_agent", self._should_continue,
                                       {"continue":"summarizer","end":"fact_checker"})
        workflow.add_conditional_edges("fact_checker", self._should_retry,
                                       {"retry":"revision","proceed":"moderator"})
        workflow.add_edge("revision", "fact_checker")
        workflow.add_edge("moderator", "verdict")
        workflow.add_edge("verdict",   END)
        return workflow.compile(checkpointer=self.checkpointer)

    # ── Nodes — each defined EXACTLY ONCE ────────────────────────────────────

    def _summarize_node(self, state: DebateState) -> DebateState:
        if state.round > 2:
            logger.info("Round > 2 — generating debate summary.")
            state.summary = self.summarizer.summarize_history(state)
        if len(state.pro_arguments) > 5:
            state.pro_arguments = state.pro_arguments[-5:]
            state.con_arguments = state.con_arguments[-5:]
        return state

    def _consensus_check_node(self, state: DebateState) -> DebateState:
        self._set_stage("CONSENSUS", "Running consensus pre-check...")
        logger.info("Consensus pre-check for: %s", state.claim)
        claim_lower = state.claim.lower()

        for pattern, (verdict, conf, reasoning) in SETTLED_TRUTHS.items():
            if re.search(pattern, claim_lower):
                state.verdict    = verdict
                state.confidence = conf
                state.moderator_reasoning = f"Settled Science: {reasoning}"
                if state.metrics is None: state.metrics = {}
                state.metrics["consensus"] = {"verdict":verdict,"reasoning":reasoning,"score":conf}
                logger.info("Hardcoded consensus: %s", verdict)
                return state

        prompt = (
            f"You are a Consensus Checker. Determine if there is a massive scientific consensus.\n"
            f"CLAIM: {state.claim}\n"
            f'Respond ONLY in JSON: {{"verdict":"TRUE"|"FALSE"|"NEUTRAL"|"DEBATE","reasoning":"...","confidence":0.0-1.0}}\n'
            f"If settled fact return TRUE/FALSE. If controversial return DEBATE."
        )
        try:
            import concurrent.futures as _cf
            with _cf.ThreadPoolExecutor(max_workers=1) as tex:
                fut      = tex.submit(self.client.call_structured, prompt, ConsensusResponse, 0.1, 500, 1, "gemini")
                response = fut.result(timeout=15)
            if response.verdict != "DEBATE" and response.confidence > 0.9:
                state.verdict    = response.verdict
                state.confidence = response.confidence
                state.moderator_reasoning = f"Consensus Pre-Check: {response.reasoning}"
                logger.info("Consensus found: %s", state.verdict)
            if state.metrics is None: state.metrics = {}
            state.metrics["consensus"] = {"verdict":response.verdict,"reasoning":response.reasoning,"score":response.confidence}
        except Exception as e:
            logger.warning("Consensus check failed (non-fatal): %s", e)
        return state

    def _should_debate(self, state: DebateState) -> Literal["skip","debate"]:
        if state.verdict in ("TRUE","FALSE","NEUTRAL") and (state.confidence or 0) > 0.9:
            return "skip"
        return "debate"

    def _pro_agent_node(self, state: DebateState) -> DebateState:
        self._set_stage("PRO", f"Round {state.round}")
        logger.info("ProAgent — Round %d", state.round)
        response = self.pro_agent.generate(state)
        state.pro_arguments = state.pro_arguments + [response.argument]
        state.pro_sources   = state.pro_sources   + [response.sources]
        return state

    def _con_agent_node(self, state: DebateState) -> DebateState:
        self._set_stage("CON", f"Round {state.round}")
        logger.info("ConAgent — Round %d", state.round)
        response = self.con_agent.generate(state)
        state.con_arguments = state.con_arguments + [response.argument]
        state.con_sources   = state.con_sources   + [response.sources]
        state.round += 1
        return state

    def _should_continue(self, state: DebateState) -> Literal["continue","end"]:
        if isinstance(state, dict):
            return "end" if state.get("round",1) > state.get("num_rounds",3) else "continue"
        return "end" if state.round > state.num_rounds else "continue"

    def _should_retry(self, state: DebateState) -> Literal["retry","proceed"]:
        last_pro = state.pro_arguments[-1] if state.pro_arguments else ""
        last_con = state.con_arguments[-1] if state.con_arguments else ""
        if "[API_FAILURE]" in last_pro or "[API_FAILURE]" in last_con:
            return "proceed"
        if (state.pro_verification_rate or 0) < 0.3 or (state.con_verification_rate or 0) < 0.3:
            if state.retry_count < 1:
                return "retry"
        return "proceed"

    def _retry_revision_node(self, state: DebateState) -> DebateState:
        logger.info("Revision loop triggered.")
        state.retry_count += 1
        saved_round = state.round
        state.round = state.num_rounds

        pro_resp = self.pro_agent.generate(state)
        if state.pro_arguments:
            state.pro_arguments = state.pro_arguments[:-1] + [pro_resp.argument]
        if state.pro_sources:
            state.pro_sources = state.pro_sources[:-1] + [pro_resp.sources]

        con_resp = self.con_agent.generate(state)
        if state.con_arguments:
            state.con_arguments = state.con_arguments[:-1] + [con_resp.argument]
        if state.con_sources:
            state.con_sources = state.con_sources[:-1] + [con_resp.sources]

        state.round = saved_round
        return state

    def _fact_checker_node(self, state: DebateState) -> DebateState:
        self._set_stage("FACT_CHECK", "Verifying sources...")
        logger.info("FactChecker verifying sources...")
        try:
            state.pro_sources = URLNormalizer.sanitize_list(state.pro_sources)
            state.con_sources = URLNormalizer.sanitize_list(state.con_sources)
            response = self.fact_checker.generate(state)
            metrics  = response.metrics or {}
            state.verification_results  = metrics.get("verification_results", [])
            state.pro_verification_rate = metrics.get("pro_rate", 0.0)
            state.con_verification_rate = metrics.get("con_rate", 0.0)
        except Exception as e:
            logger.error("FactChecker failed: %s", e)
        return state

    def _moderator_node(self, state: DebateState) -> DebateState:
        self._set_stage("MODERATOR", "Analysing debate quality...")
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
        self._set_stage("COMPLETE", f"Verdict: {state.verdict}")
        logger.info("Final verdict: %s (confidence: %s)", state.verdict, state.confidence)
        return state

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self, claim: str, thread_id: str = "default") -> DebateState:
        logger.info("Running debate on: %s", claim)

        cache  = get_cache()
        cached = cache.get_verdict(claim)
        if cached:
            state           = DebateState.model_validate(cached)
            state.is_cached = True
            self._set_stage("COMPLETE", "Loaded from cache")
            return state

        sub_claims   = self.claim_decomposer.decompose(claim)
        if len(sub_claims) > 1:
            target_claim = f"Complex User Claim:\n" + "\n".join(f"- {sc}" for sc in sub_claims)
        else:
            target_claim = claim
        if len(sub_claims) > 1:
            logger.info("Multi-part claim — primary: %r", target_claim)

        import concurrent.futures as _cf
        tavily = get_tavily_retriever()
        try:
            with _cf.ThreadPoolExecutor(max_workers=1) as tex:
                adversarial = tex.submit(tavily.search_adversarial, target_claim, 5).result(timeout=12)
        except Exception:
            logger.warning("Tavily timed out or failed — proceeding without evidence")
            adversarial = {"pro":[],"con":[]}

        initial_state = DebateState(
            claim=target_claim,
            pro_evidence=adversarial["pro"],
            con_evidence=adversarial["con"],
            evidence_sources=adversarial["pro"] + adversarial["con"],
        )
        final_state = initial_state

        try:
            raw_result = self.graph.invoke(initial_state, config={"configurable":{"thread_id":thread_id}})
            if isinstance(raw_result, dict):
                final_state = DebateState.model_validate(raw_result)
            elif hasattr(raw_result, "model_dump"):
                final_state = raw_result
            else:
                final_state = DebateState.model_validate(dict(raw_result))

            if not final_state.verdict:
                final_state.verdict    = "ERROR"
                final_state.confidence = final_state.confidence or 0.0
                final_state.moderator_reasoning = final_state.moderator_reasoning or "No verdict produced."

            if final_state.verdict not in ("ERROR","RATE_LIMITED","SYSTEM_ERROR",None):
                if final_state.verdict != "INSUFFICIENT EVIDENCE" or \
                        (final_state.confidence is not None and final_state.confidence > 0.1):
                    try:
                        set_cached_verdict(target_claim, json.loads(final_state.model_dump_json()))
                    except Exception as ce:
                        logger.warning("Cache write failed: %s", ce)
            return final_state

        except (ValueError, TypeError, AttributeError) as e:
            logger.error("Programming error in debate graph: %s", e)
            raise
        except Exception as e:
            logger.error("Debate failed (runtime): %s", e)
            self._set_stage("ERROR", str(e))
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
            state           = DebateState.model_validate(cached)
            state.is_cached = True
            self._set_stage("COMPLETE", "Loaded from cache")
            yield "cache_hit", state
            return

        sub_claims   = self.claim_decomposer.decompose(claim)
        if len(sub_claims) > 1:
            target_claim = f"Complex User Claim:\n" + "\n".join(f"- {sc}" for sc in sub_claims)
        else:
            target_claim = claim

        import concurrent.futures as _cf
        tavily = get_tavily_retriever()
        try:
            with _cf.ThreadPoolExecutor(max_workers=1) as tex:
                adversarial = tex.submit(tavily.search_adversarial, target_claim, 5).result(timeout=12)
        except Exception:
            logger.warning("Tavily timed out — proceeding without evidence")
            adversarial = {"pro":[],"con":[]}

        initial_state = DebateState(
            claim=target_claim,
            pro_evidence=adversarial["pro"],
            con_evidence=adversarial["con"],
            evidence_sources=adversarial["pro"] + adversarial["con"],
        )
        last_state = initial_state

        try:
            for event in self.graph.stream(initial_state, config={"configurable":{"thread_id":thread_id}}, stream_mode="values"):
                last_state = DebateState.model_validate(event) if isinstance(event, dict) else event
                yield "progress", last_state

            if last_state.verdict not in ("ERROR","RATE_LIMITED","SYSTEM_ERROR",None):
                if last_state.verdict != "INSUFFICIENT EVIDENCE" or \
                        (last_state.confidence is not None and last_state.confidence > 0.1):
                    try:
                        set_cached_verdict(target_claim, json.loads(last_state.model_dump_json()))
                    except Exception as ce:
                        logger.warning("Stream cache write failed: %s", ce)
            yield "complete", last_state

        except (ValueError, TypeError, AttributeError) as e:
            logger.error("Programming error during stream: %s", e)
            raise
        except Exception as e:
            logger.error("Stream failed (runtime): %s", e)
            self._set_stage("ERROR", str(e))
            last_state.verdict    = "INSUFFICIENT EVIDENCE"
            last_state.confidence = 0.0
            last_state.moderator_reasoning = f"Runtime error: {str(e)}"
            yield "error", last_state
