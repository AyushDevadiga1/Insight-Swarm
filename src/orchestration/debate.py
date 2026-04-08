"""
src/orchestration/debate.py — All batches applied. Final production version.
Single definition of every method. No duplicates.
Novelty modules (ArgumentationAnalyzer + AdaptiveConfidenceCalibrator) wired into pipeline.
ClaimComplexityEstimator + ExplainabilityEngine also wired.
BUG FIXES (D23): added close(), fixed contradiction detection, fixed None-guard in novelty.
"""
import sys, logging, json, re
from pathlib import Path
from typing import Optional, Literal, Any

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.models import DebateState, AgentResponse, ConsensusResponse
from src.llm.client import RateLimitError
from src.agents.pro_agent import ProAgent
from src.agents.con_agent import ConAgent
from src.agents.fact_checker import FactChecker
from src.agents.moderator import Moderator
from src.orchestration.cache import get_cached_verdict, set_cached_verdict, get_cache
from src.utils.tavily_retriever import get_tavily_retriever
from src.utils.claim_decomposer import ClaimDecomposer
from src.utils.summarizer import Summarizer
from src.llm.client import FreeLLMClient, RateLimitError
from src.novelty import get_complexity_estimator, get_explainability_engine
from src.utils.url_helper import URLNormalizer

logger = logging.getLogger(__name__)

SETTLED_TRUTHS = {
    r"earth is flat":              ("FALSE", 1.0,  "Earth is an oblate spheroid."),
    r"earth is round":             ("TRUE",  1.0,  "Earth is an oblate spheroid."),
    r"vaccines cause autism":      ("FALSE", 0.99, "Debunked by global medical research."),
    r"\bsmoking causes cancer\b":  ("TRUE",  0.99, "Established medical consensus."),
    r"\bclimate change is real\b": ("TRUE",  0.98, "IPCC scientific consensus."),
    r"\bwater is h2o\b":           ("TRUE",  1.0,  "Fundamental chemistry."),
    r"\bmoon landing was faked\b": ("FALSE", 1.0,  "Documented historical fact."),
    r"\bsun revolves around earth\b": ("FALSE", 1.0, "Heliocentric model."),
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
        self.checkpointer = MemorySaver()
        self.graph        = self._build_graph()
        self._closed      = False

    def set_tracker(self, tracker) -> None:
        """Inject tracker without rebuilding graph."""
        self.tracker = tracker

    def close(self) -> None:
        """
        Release resources held by this orchestrator instance.
        Safe to call multiple times. Used by tests and CLI tools to
        prevent dangling threads after a run.
        """
        if self._closed:
            return
        self._closed = True
        # The module-level _VERIFY_POOL in fact_checker.py is registered
        # with atexit; nothing extra needed here. Just mark closed.
        logger.debug("DebateOrchestrator.close() called — resources released.")

    def _set_stage(self, stage_name: str, message: str = "") -> None:
        if self.tracker is None: return
        try:
            from src.ui.progress_tracker import Stage
            self.tracker.set_stage(Stage(stage_name), message)
        except Exception as _e:
            # ISSUE-010 FIX: log instead of silently swallowing — tracker errors must not mask audit trails
            logger.debug("Progress tracker update failed (non-fatal): %s", _e)

    def _build_graph(self) -> Any:
        workflow = StateGraph(DebateState)
        workflow.add_node("consensus_check", self._consensus_check_node)
        workflow.add_node("summarizer",      self._summarize_node)
        workflow.add_node("pro_agent",       self._pro_agent_node)
        workflow.add_node("con_agent",       self._con_agent_node)
        workflow.add_node("fact_checker",    self._fact_checker_node)
        workflow.add_node("human_review",    self._human_review_node)
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
                                       {"retry":"revision","proceed":"human_review"})
        workflow.add_edge("revision", "fact_checker")
        workflow.add_edge("human_review", "moderator")
        workflow.add_edge("moderator", "verdict")
        workflow.add_edge("verdict",   END)
        return workflow.compile(
            checkpointer=self.checkpointer,
            interrupt_before=["human_review"]
        )

    # ── Nodes ────────────────────────────────────────────────────────────────

    def _summarize_node(self, state: DebateState) -> DebateState:
        if state.round > 2:
            logger.info("Round > 2 — generating debate summary.")
            state.summary = self.summarizer.summarize_history(state)
        if len(state.pro_arguments) > 5:
            state.pro_arguments = state.pro_arguments[-5:]
            state.con_arguments = state.con_arguments[-5:]
            state.pro_sources   = state.pro_sources[-5:]
            state.con_sources   = state.con_sources[-5:]
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
                state.metrics["consensus"] = {"verdict": verdict, "reasoning": reasoning, "score": conf}
                logger.info("Hardcoded consensus: %s", verdict)
                if not state.pro_arguments:
                    state.pro_arguments = [f"[Settled science — debate skipped] {reasoning}"]
                if not state.con_arguments:
                    state.con_arguments = [f"[Consensus verdict: {verdict} ({conf:.0%} confidence) — no debate required]"]
                if not state.pro_sources: state.pro_sources = [[]]
                if not state.con_sources: state.con_sources = [[]]
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
                if not state.pro_arguments:
                    state.pro_arguments = [f"[Consensus settled — debate skipped] {response.reasoning}"]
                if not state.con_arguments:
                    state.con_arguments = [f"[Consensus verdict: {response.verdict} ({response.confidence:.0%} confidence)]"]
                if not state.pro_sources: state.pro_sources = [[]]
                if not state.con_sources: state.con_sources = [[]]
            if state.metrics is None: state.metrics = {}
            state.metrics["consensus"] = {
                "verdict": response.verdict, "reasoning": response.reasoning, "score": response.confidence
            }
        except Exception as e:
            logger.warning("Consensus check failed (non-fatal): %s", e)
        return state

    def _should_debate(self, state: DebateState) -> Literal["skip", "debate"]:
        if state.verdict in ("TRUE", "FALSE", "NEUTRAL") and (state.confidence or 0) > 0.9:
            return "skip"
        return "debate"

    def _pro_agent_node(self, state: DebateState) -> DebateState:
        self._set_stage("PRO", f"Round {state.round}")
        logger.info("ProAgent — Round %d", state.round)
        try:
            response = self.pro_agent.generate(state)
            state.pro_arguments = state.pro_arguments + [response.argument]
            state.pro_sources   = state.pro_sources   + [response.sources]
        except RateLimitError:
            logger.error("ProAgent rate limited")
            state.pro_arguments = state.pro_arguments + ["[API_FAILURE] ProAgent: Rate Limit Exceeded"]
            state.pro_sources   = state.pro_sources   + [[]]
        except Exception as e:
            logger.error("ProAgent failed: %s", e)
            state.pro_arguments = state.pro_arguments + [f"[API_FAILURE] ProAgent Error: {e}"]
            state.pro_sources   = state.pro_sources   + [[]]
        return state

    def _con_agent_node(self, state: DebateState) -> DebateState:
        self._set_stage("CON", f"Round {state.round}")
        logger.info("ConAgent — Round %d", state.round)
        try:
            response = self.con_agent.generate(state)
            state.con_arguments = state.con_arguments + [response.argument]
            state.con_sources   = state.con_sources   + [response.sources]
        except RateLimitError:
            logger.error("ConAgent rate limited")
            state.con_arguments = state.con_arguments + ["[API_FAILURE] ConAgent: Rate Limit Exceeded"]
            state.con_sources   = state.con_sources   + [[]]
        except Exception as e:
            logger.error("ConAgent failed: %s", e)
            state.con_arguments = state.con_arguments + [f"[API_FAILURE] ConAgent Error: {e}"]
            state.con_sources   = state.con_sources   + [[]]
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
            return "proceed"
        if (state.pro_verification_rate or 0) < 0.3 or (state.con_verification_rate or 0) < 0.3:
            if state.retry_count < 1:
                return "retry"
        return "proceed"

    def _retry_revision_node(self, state: DebateState) -> DebateState:
        logger.info("Revision loop triggered.")
        state.retry_count += 1
        # BUG FIX #5: Save/restore round so agents build prompts for the correct
        # context (num_rounds = last real debate round, not post-increment 4).
        saved_round = state.round
        state.round = state.num_rounds

        pro_resp = self.pro_agent.generate(state)
        if state.pro_arguments:
            state.pro_arguments = state.pro_arguments[:-1] + [pro_resp.argument]
        if state.pro_sources:
            state.pro_sources   = state.pro_sources[:-1]   + [pro_resp.sources]

        con_resp = self.con_agent.generate(state)
        if state.con_arguments:
            state.con_arguments = state.con_arguments[:-1] + [con_resp.argument]
        if state.con_sources:
            state.con_sources   = state.con_sources[:-1]   + [con_resp.sources]

        state.round = saved_round
        return state

    def _fact_checker_node(self, state: DebateState) -> DebateState:
        self._set_stage("FACT_CHECK", "Verifying sources...")
        logger.info("FactChecker verifying sources...")

        allowed_urls = set()
        for pool in [state.evidence_sources, state.pro_evidence, state.con_evidence]:
            if pool:
                for item in pool:
                    if item.get("url"):
                        allowed_urls.add(item["url"])

        def strip_hallucinations(source_lists):
            cleaned = []
            for slist in source_lists:
                valid = []
                for url in slist:
                    if url in allowed_urls:
                        valid.append(url)
                    else:
                        logger.warning("Stripped hallucinated URL: %s", url)
                cleaned.append(valid)
            return cleaned

        if allowed_urls:
            state.pro_sources = strip_hallucinations(state.pro_sources)
            state.con_sources = strip_hallucinations(state.con_sources)

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

    def _human_review_node(self, state: DebateState) -> DebateState:
        self._set_stage("HUMAN_REVIEW", "Awaiting human review override (if any)")
        logger.info("Interrupt hit: awaiting human review...")
        return state

    def _moderator_node(self, state: DebateState) -> DebateState:
        self._set_stage("MODERATOR", "Analysing debate quality...")
        try:
            response                  = self.moderator.generate(state)
            state.verdict             = response.verdict
            state.confidence          = response.confidence
            state.moderator_reasoning = response.reasoning
            # BUG FIX: merge instead of replace so 'consensus' key is not lost
            if state.metrics is None:
                state.metrics = {}
            state.metrics.update(response.metrics or {})

            # ── NOVELTY 1: ArgumentationAnalyzer ─────────────────────────────
            try:
                from src.novelty.argumentation_analysis import get_argumentation_analyzer
                analyzer     = get_argumentation_analyzer()
                pro_analyses = []
                for i, arg in enumerate(state.pro_arguments):
                    srcs = state.pro_sources[i] if i < len(state.pro_sources) else []
                    if "[API_FAILURE]" not in arg:
                        pro_analyses.append(analyzer.analyze_argument(arg, srcs, "PRO"))
                con_analyses = []
                for i, arg in enumerate(state.con_arguments):
                    srcs = state.con_sources[i] if i < len(state.con_sources) else []
                    if "[API_FAILURE]" not in arg:
                        con_analyses.append(analyzer.analyze_argument(arg, srcs, "CON"))
                if pro_analyses and con_analyses:
                    debate_quality = analyzer.compare_debate_quality(pro_analyses, con_analyses)
                    state.metrics["argumentation_analysis"] = {
                        "pro_avg_quality":     debate_quality.get("pro_average_quality", 0.0),
                        "con_avg_quality":     debate_quality.get("con_average_quality", 0.0),
                        "quality_gap":         debate_quality.get("quality_gap", 0.0),
                        "pro_fallacy_count":   debate_quality.get("pro_total_fallacies", 0),
                        "con_fallacy_count":   debate_quality.get("con_total_fallacies", 0),
                        "debate_quality":      debate_quality.get("debate_quality", "low"),
                        "higher_quality_side": debate_quality.get("higher_quality_side", "PRO"),
                    }
                    logger.info("ArgumentationAnalyzer complete: pro=%.2f con=%.2f",
                                debate_quality.get("pro_average_quality", 0),
                                debate_quality.get("con_average_quality", 0))
            except Exception as _e:
                logger.warning("ArgumentationAnalyzer failed (non-fatal): %s", _e)

            # ── NOVELTY 2: AdaptiveConfidenceCalibrator ───────────────────────
            raw_confidence = state.confidence
            try:
                from src.novelty.confidence_calibration import get_calibrator
                calibrator = get_calibrator()
                calibrated_conf, calibration_meta = calibrator.calibrate(
                    raw_confidence       = raw_confidence,
                    verdict              = state.verdict,
                    claim                = state.claim,
                    verification_results = state.verification_results or [],
                    pro_args             = state.pro_arguments,
                    con_args             = state.con_arguments,
                    pro_sources          = state.pro_sources,
                    con_sources          = state.con_sources,
                )
                state.confidence        = calibrated_conf
                state.metrics["calibration"] = calibration_meta
                logger.info("ConfidenceCalibrator: %.3f → %.3f (%s)",
                            raw_confidence, calibrated_conf,
                            calibration_meta.get("adjustment_type", "none"))
            except Exception as _e:
                logger.warning("ConfidenceCalibrator failed (non-fatal): %s", _e)

        except RateLimitError as e:
            logger.error("Moderator rate limited.")
            state.verdict    = "RATE_LIMITED"
            state.confidence = 0.0
            hint = f" Retry after ~{e.retry_after:.0f}s." if e.retry_after else ""
            state.moderator_reasoning = state.moderator_reasoning or f"Rate limit exceeded.{hint}"
            state.metrics = {}
        return state

    def _verdict_node(self, state: DebateState) -> DebateState:
        # NOVELTY 3: ExplainabilityEngine — generate XAI explanation
        try:
            explainer   = get_explainability_engine()
            explanation = explainer.generate_explanation(state.to_dict(), level="standard")
            if state.metrics is None:
                state.metrics = {}
            state.metrics["explanation"] = explanation
        except Exception as _xe:
            logger.warning("ExplainabilityEngine failed (non-fatal): %s", _xe)

        self._set_stage("COMPLETE", f"Verdict: {state.verdict}")
        logger.info("Final verdict: %s (confidence: %s)", state.verdict, state.confidence)
        return state

    # ── Public API ────────────────────────────────────────────────────────────

    def _debate_parallel_claims(self, claims: list[str], base_thread_id: str) -> list[DebateState]:
        import concurrent.futures
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self._run_single_claim, claim, [], f"{base_thread_id}-subclaim-{i}"): claim
                for i, claim in enumerate(claims)
            }
            for future in concurrent.futures.as_completed(futures):
                try:
                    results.append(future.result(timeout=180))
                except Exception as e:
                    logger.error("Sub-claim debate failed: %s", e)
                    results.append(DebateState(
                        claim=futures[future], verdict="ERROR", confidence=0.0,
                        moderator_reasoning=f"Sub-claim debate failed: {e}",
                        metrics={}, pro_evidence=[], con_evidence=[], evidence_sources=[],
                        pro_arguments=[], con_arguments=[], pro_sources=[], con_sources=[]
                    ))
        return results

    def _aggregate_sub_claim_verdicts(self, results: list[DebateState]) -> DebateState:
        weighted_votes = {"TRUE": 0.0, "FALSE": 0.0, "PARTIALLY TRUE": 0.0, "INSUFFICIENT EVIDENCE": 0.0}
        for result in results:
            if result.verdict in weighted_votes:
                weighted_votes[result.verdict] += result.confidence
        final_verdict = (
            max(weighted_votes, key=weighted_votes.get)
            if any(weighted_votes.values()) else "INSUFFICIENT EVIDENCE"
        )
        total_weight     = sum(weighted_votes.values())
        final_confidence = weighted_votes[final_verdict] / total_weight if total_weight > 0 else 0.0
        parts = [
            f"Sub-claim {i}: \"{r.claim}\" → {r.verdict} ({r.confidence:.0%} confidence)"
            for i, r in enumerate(results, 1)
        ]
        return DebateState(
            claim=" AND ".join(r.claim for r in results),
            sub_claims=[r.claim for r in results],
            verdict=final_verdict,
            confidence=final_confidence,
            moderator_reasoning="Multi-claim analysis:\n" + "\n".join(parts),
            pro_arguments=[arg for r in results for arg in r.pro_arguments],
            con_arguments=[arg for r in results for arg in r.con_arguments],
            pro_sources=[src for r in results for src in r.pro_sources],
            con_sources=[src for r in results for src in r.con_sources],
            pro_evidence=[], con_evidence=[], evidence_sources=[],
            metrics={
                "sub_claim_results": [r.model_dump() for r in results],
                "aggregation_method": "confidence_weighted_voting",
            }
        )

    def _run_single_claim(self, target_claim: str, sub_claims: list[str],
                          thread_id: str, num_rounds: int = 3) -> DebateState:
        import concurrent.futures
        tavily = get_tavily_retriever()
        self._set_stage("SEARCHING", "Retrieving web evidence...")
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as tex:
                adversarial = tex.submit(tavily.search_adversarial, target_claim, 5).result(timeout=12)
        except Exception:
            logger.warning("Tavily timed out or failed — proceeding without evidence")
            adversarial = {"pro": [], "con": []}

        initial_state = DebateState(
            claim=target_claim, sub_claims=sub_claims, num_rounds=num_rounds,
            pro_evidence=adversarial["pro"], con_evidence=adversarial["con"],
            evidence_sources=adversarial["pro"] + adversarial["con"],
        )
        final_state = initial_state
        from src.resilience.fallback_handler import FallbackHandler

        def _execute_graph():
            cfg = {"configurable": {"thread_id": thread_id}}
            result = self.graph.invoke(initial_state, config=cfg)
            # BUG FIX: graph is compiled with interrupt_before=["human_review"].
            # In benchmark / headless mode there is no human override, so auto-
            # resume past the interrupt so the moderator + verdict nodes run.
            _r = DebateState.model_validate(result) if isinstance(result, dict) else result
            if (
                (getattr(_r, "verdict", "UNKNOWN") or "UNKNOWN") == "UNKNOWN"
                and getattr(_r, "pro_arguments", [])
                and not getattr(_r, "human_verdict_override", None)
            ):
                logger.info("Auto-resuming graph past human_review interrupt (no override set)")
                result = self.graph.invoke(None, config=cfg)
            return result

        def _fallback_state():
            f = initial_state.model_copy(deep=True)
            f.verdict    = "INSUFFICIENT EVIDENCE"
            f.confidence = 0.0
            f.moderator_reasoning = "System error prevented complete analysis."
            return f

        try:
            raw = FallbackHandler.execute(operations=[_execute_graph], graceful_fallback=_fallback_state)
            if isinstance(raw, dict):
                final_state = DebateState.model_validate(raw)
            elif hasattr(raw, "model_dump"):
                final_state = raw
            else:
                final_state = DebateState.model_validate(dict(raw))

            if not final_state.verdict:
                final_state.verdict           = "ERROR"
                final_state.confidence        = final_state.confidence or 0.0
                final_state.moderator_reasoning = final_state.moderator_reasoning or "No verdict produced."

            if final_state.verdict not in ("ERROR", "RATE_LIMITED", "SYSTEM_ERROR", None):
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
            final_state.verdict           = "INSUFFICIENT EVIDENCE"
            final_state.confidence        = 0.0
            final_state.moderator_reasoning = f"Runtime error: {e}"
            final_state.metrics           = {}
            return final_state

    def run(self, claim: str, thread_id: str = "default", num_rounds: int = 3) -> DebateState:
        logger.info("Running debate on: %s", claim)

        cache  = get_cache()
        cached = cache.get_verdict(claim)
        if cached:
            state           = DebateState.model_validate(cached)
            state.is_cached = True
            self._set_stage("COMPLETE", "Loaded from cache")
            return state

        # NOVELTY: Claim Complexity Estimation — adjusts debate depth automatically
        try:
            estimator          = get_complexity_estimator()
            complexity_profile = estimator.estimate_complexity(claim)
            tier               = complexity_profile.get("complexity_tier", "medium")
            logger.info("Claim complexity: %s", tier)
            adjusted_params    = estimator.adjust_debate_parameters(num_rounds, 5, complexity_profile)
            num_rounds_to_use  = adjusted_params["adjusted_rounds"]
            if num_rounds_to_use > num_rounds and tier in ("high", "very_high"):
                try:
                    if sys.stdin.isatty():
                        print(f"\n⚠️  High-complexity claim (tier: {tier}).")
                        ans = input(f"   Use {num_rounds_to_use} rounds? [y/N]: ").strip().lower()
                        if ans == "y":
                            num_rounds = num_rounds_to_use
                    else:
                        num_rounds = num_rounds_to_use
                except Exception as _tty_e:
                    # ISSUE-010 FIX: stdin.isatty() can fail in some environments; log and continue
                    logger.debug("TTY stdin check failed (non-fatal): %s", _tty_e)
        except Exception as _ce:
            logger.warning("ClaimComplexityEstimator failed (non-fatal): %s", _ce)

        self._set_stage("DECOMPOSING", "Analyzing claim structure...")
        sub_claims = self.claim_decomposer.decompose(claim)
        if len(sub_claims) > 1:
            logger.info("Multi-claim detected: %d sub-claims", len(sub_claims))
            sub_results = self._debate_parallel_claims(sub_claims, thread_id)
            aggregated  = self._aggregate_sub_claim_verdicts(sub_results)
            aggregated.is_cached = False
            return aggregated

        return self._run_single_claim(claim, [], thread_id, num_rounds=num_rounds)

    def stream(self, claim: str, thread_id: str = "default", num_rounds: int = 3):
        logger.info("Streaming debate on: %s", claim)
        cache  = get_cache()
        cached = cache.get_verdict(claim)
        if cached:
            state           = DebateState.model_validate(cached)
            state.is_cached = True
            self._set_stage("COMPLETE", "Loaded from cache")
            yield "cache_hit", state
            return

        # NOVELTY: Claim Complexity Estimation — auto-apply in stream mode
        try:
            estimator       = get_complexity_estimator()
            cp              = estimator.estimate_complexity(claim)
            adjusted        = estimator.adjust_debate_parameters(num_rounds, 5, cp)
            num_rounds      = adjusted["adjusted_rounds"]
        except Exception as _ce:
            logger.warning("ClaimComplexityEstimator failed (non-fatal): %s", _ce)

        self._set_stage("DECOMPOSING", "Analyzing claim structure...")
        sub_claims = self.claim_decomposer.decompose(claim)
        target_claim = (
            "Complex User Claim:\n" + "\n".join(f"- {sc}" for sc in sub_claims)
            if len(sub_claims) > 1 else claim
        )

        import concurrent.futures as _cf
        tavily = get_tavily_retriever()
        self._set_stage("SEARCHING", "Retrieving web evidence...")
        try:
            with _cf.ThreadPoolExecutor(max_workers=1) as tex:
                adversarial = tex.submit(tavily.search_adversarial, target_claim, 5).result(timeout=12)
        except Exception:
            logger.warning("Tavily timed out — proceeding without evidence")
            adversarial = {"pro": [], "con": []}

        initial_state = DebateState(
            claim=target_claim,
            sub_claims=sub_claims if len(sub_claims) > 1 else [],
            num_rounds=num_rounds,
            pro_evidence=adversarial["pro"],
            con_evidence=adversarial["con"],
            evidence_sources=adversarial["pro"] + adversarial["con"],
        )
        last_state = initial_state

        try:
            for event in self.graph.stream(
                initial_state,
                config={"configurable": {"thread_id": thread_id}},
                stream_mode="values",
            ):
                last_state = DebateState.model_validate(event) if isinstance(event, dict) else event
                yield "progress", last_state

            if last_state.verdict not in ("ERROR", "RATE_LIMITED", "SYSTEM_ERROR", None):
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
            last_state.verdict            = "INSUFFICIENT EVIDENCE"
            last_state.confidence         = 0.0
            last_state.moderator_reasoning = f"Runtime error: {e}"
            yield "error", last_state
