"""
Moderator - Analyzes debate quality and produces reasoned verdicts using structured outputs.
"""
from src.agents.base import BaseAgent, AgentResponse, DebateState
from src.core.models import ModeratorVerdict
from src.llm.client import FreeLLMClient, RateLimitError
import logging

logger = logging.getLogger(__name__)

# Maximum characters per argument block when the full transcript is used.
# When a debate summary is available the Moderator only sees the final round
# verbatim so this cap mainly protects the no-summary path.
_MAX_ARG_CHARS = 600


class Moderator(BaseAgent):
    """
    Agent that analyses the debate and produces a verdict.
    Uses analytical prompting and Pydantic structured output.
    """

    def __init__(self, llm_client: FreeLLMClient):
        super().__init__(llm_client)
        self.role = "MODERATOR"
        self.preferred_provider = "groq"

    def generate(self, state: DebateState) -> AgentResponse:
        """Analyse complete debate and produce reasoned verdict."""
        logger.info("Moderator analysing debate quality...")

        prompt = self._build_prompt(state, state.round)

        try:
            result = self.client.call_structured(
                prompt=prompt,
                output_schema=ModeratorVerdict,
                temperature=0.2,
            )
            self.call_count += 1

            # ── Composite confidence formula ───────────────────────────────
            # (arg_quality * 0.3) + (avg_ver_rate * 0.3) + (avg_trust * 0.2) + (consensus * 0.2)

            arg_quality = 0.5
            if result.metrics and "argument_quality" in result.metrics:
                raw = result.metrics["argument_quality"]
                arg_quality = raw / 100.0 if raw > 1 else raw

            pro_rate     = state.pro_verification_rate or 0.0
            con_rate     = state.con_verification_rate or 0.0
            avg_ver_rate = (pro_rate + con_rate) / 2

            # Trust scores surfaced by FactChecker
            trust_scores = []
            if state.metrics and "verification_results" in state.metrics:
                for r in state.metrics["verification_results"]:
                    if r.get("status") == "VERIFIED":
                        trust_scores.append(r.get("trust_score", 0.5))
            avg_trust = sum(trust_scores) / len(trust_scores) if trust_scores else 0.5

            consensus_score = 0.5
            if state.metrics and "consensus" in state.metrics:
                cd = state.metrics["consensus"]
                if cd.get("verdict") == result.verdict:
                    consensus_score = cd.get("score", 0.8)
                elif cd.get("verdict") == "DEBATE":
                    consensus_score = 0.5
                else:
                    consensus_score = 0.2

            composite = (
                arg_quality      * 0.3 +
                avg_ver_rate     * 0.3 +
                avg_trust        * 0.2 +
                consensus_score  * 0.2
            )

            final_metrics = result.metrics or {}
            final_metrics["confidence_breakdown"] = {
                "argument_quality_weight": 0.3, "argument_quality_score": arg_quality,
                "verification_weight": 0.3,     "verification_score": avg_ver_rate,
                "trust_weight": 0.2,            "trust_score": avg_trust,
                "consensus_weight": 0.2,        "consensus_score": consensus_score,
            }

            return AgentResponse(
                agent="MODERATOR",
                round=state.round,
                argument=result.reasoning[:500] + "..." if len(result.reasoning) > 500 else result.reasoning,
                sources=[],
                confidence=float(composite),
                verdict=result.verdict,
                reasoning=result.reasoning,
                metrics=final_metrics,
            )

        except Exception as e:
            logger.error(f"Moderator failed: {e}")
            state.moderator_reasoning = str(e)
            return self._fallback_verdict(state)

    def _fallback_verdict(self, state: DebateState) -> AgentResponse:
        logger.warning("Moderator fallback triggered.")
        reason = state.moderator_reasoning or "Unknown error"
        if any(kw in reason.upper() for kw in ("QUOTA_EXHAUSTED", "429", "RATE LIMIT")):
            verdict  = "RATE_LIMITED"
            argument = "All LLM quotas exhausted — verification cannot proceed."
            confidence = 0.0
        else:
            verdict  = "SYSTEM_ERROR"
            argument = "A technical interruption occurred in the moderation protocol."
            confidence = 0.0

        return AgentResponse(
            agent="MODERATOR", round=state.round,
            argument=argument, sources=[],
            confidence=confidence, verdict=verdict,
            reasoning=f"System fallback: {reason}",
            metrics={"credibility": 0.5, "balance": 0.5},
        )

    def _build_prompt(self, state: DebateState, round_num: int) -> str:
        # ── Context compression (fixes R-34 / NEW-04) ─────────────────────
        # When a summary is available (generated by the Summarizer node after
        # round 2), use it to represent earlier rounds and only show the final
        # round verbatim.  This prevents the Moderator prompt from exceeding
        # Groq's processing window on long debates.
        if state.summary:
            pro_final = state.pro_arguments[-1][:_MAX_ARG_CHARS] if state.pro_arguments else "No argument."
            con_final = state.con_arguments[-1][:_MAX_ARG_CHARS] if state.con_arguments else "No argument."
            pro_args = (
                f"[DEBATE SUMMARY — earlier rounds]\n{state.summary}\n\n"
                f"[FINAL PRO ARGUMENT — Round {len(state.pro_arguments)}]\n{pro_final}"
            )
            con_args = (
                f"[See summary above for earlier rounds]\n\n"
                f"[FINAL CON ARGUMENT — Round {len(state.con_arguments)}]\n{con_final}"
            )
        else:
            # Full transcript for short debates (rounds 1-2)
            pro_args = "\n\n".join(
                f"Round {i+1}: {arg[:_MAX_ARG_CHARS]}"
                for i, arg in enumerate(state.pro_arguments)
            )
            con_args = "\n\n".join(
                f"Round {i+1}: {arg[:_MAX_ARG_CHARS]}"
                for i, arg in enumerate(state.con_arguments)
            )

        verification_summary = ""
        if state.pro_verification_rate is not None:
            pro_rate = state.pro_verification_rate
            con_rate = state.con_verification_rate or 0.0
            verification_summary = (
                f"\nSOURCE VERIFICATION SUMMARY:\n"
                f"- ProAgent verification rate: {pro_rate:.1%}\n"
                f"- ConAgent verification rate: {con_rate:.1%}\n"
            )

        return f"""You are the impartial Moderator in a formal fact-checking debate.
CLAIM: {state.claim}

PRO ARGUMENTS (Supporting Claim):
{pro_args}

CON ARGUMENTS (Opposing Claim):
{con_args}
{verification_summary}
YOUR TASK:
Analyse debate quality, assess source credibility, identify logical fallacies, and determine a final verdict.
Be rigorous, objective, and neutral.

GUIDELINES FOR VERDICT:
- Prefer 'TRUE' or 'FALSE' if a clear preponderance of verifiable evidence exists.
- Use 'PARTIALLY TRUE' for multi-faceted claims with mixed evidence.
- ONLY use 'INSUFFICIENT EVIDENCE' if NO verifiable sources are found or providers totally failed.
- Avoid wait-and-see hesitation; make a definitive call based on available data.

HEALTH & SAFETY: If the claim involves medical treatments, cures, or health practices that could
cause harm if followed, prefix your reasoning with exactly:
"SAFETY NOTE: Consult a medical professional before acting on health-related claims."

STRUCTURED OUTPUT REQUIREMENTS:
Include in your metrics dictionary:
- "argument_quality": float 0.0-1.0 — logical strength of arguments
- "logical_fallacies": list of any fallacies detected
- "credibility_score": float 0.0-1.0 — overall evidence credibility
"""
