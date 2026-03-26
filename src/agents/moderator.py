"""
Moderator - Analyzes debate quality and produces reasoned verdicts using structured outputs.
Merge conflicts resolved: HEAD version kept. OpenRouter/Claude override removed.
Uses self.preferred_provider (default: gemini) — set by orchestrator.
"""
from typing import Optional
from src.agents.base import BaseAgent, AgentResponse, DebateState
from src.core.models import ModeratorVerdict
from src.llm.client import FreeLLMClient, RateLimitError
import logging

logger = logging.getLogger(__name__)

# Cap argument length in prompt to prevent context overflow
_MAX_ARG_CHARS = 800


class Moderator(BaseAgent):
    """
    Analyses the debate and produces a structured verdict.
    Uses low temperature (0.2) for analytical consistency.
    """

    def __init__(self, llm_client: FreeLLMClient, preferred_provider: Optional[str] = None):
        super().__init__(llm_client)
        self.role               = "MODERATOR"
        # Default to gemini for reasoning quality; orchestrator can override
        self.preferred_provider = preferred_provider or "gemini"

    def generate(self, state: DebateState) -> AgentResponse:
        """Analyse complete debate and produce reasoned verdict."""
        logger.info("Moderator analysing debate quality...")

        prompt = self._build_prompt(state, state.round)

        try:
            # Use the provider configured by the orchestrator — no hardcoded override
            result = self.client.call_structured(
                prompt=prompt,
                output_schema=ModeratorVerdict,
                temperature=0.2,
                preferred_provider=self.preferred_provider,
            )
            self.call_count += 1

            # ── Composite confidence formula ──────────────────────────────────
            # Weights: argument quality 30%, source verification 30%,
            #          source trust 20%, consensus pre-check 20%

            # B2-P8 fix: treat empty metrics dict same as None for argument_quality
            arg_quality = 0.5
            metrics_dict = result.metrics or {}
            raw_aq = metrics_dict.get("argument_quality")
            if raw_aq is not None:
                try:
                    raw_aq = float(raw_aq)
                    arg_quality = raw_aq / 100.0 if raw_aq > 1.0 else raw_aq
                except (TypeError, ValueError):
                    pass

            pro_rate     = state.pro_verification_rate or 0.0
            con_rate     = state.con_verification_rate or 0.0
            avg_ver_rate = (pro_rate + con_rate) / 2

            # Trust scores from FactChecker results
            trust_scores = []
            ver_results  = state.verification_results or []
            for r in ver_results:
                if isinstance(r, dict) and r.get("status") == "VERIFIED":
                    trust_scores.append(float(r.get("trust_score", 0.5)))
            avg_trust = sum(trust_scores) / len(trust_scores) if trust_scores else 0.5

            consensus_score = 0.5
            if state.metrics and "consensus" in state.metrics:
                cd = state.metrics["consensus"]
                if cd.get("verdict") == result.verdict:
                    consensus_score = float(cd.get("score", 0.8))
                elif cd.get("verdict") == "DEBATE":
                    consensus_score = 0.5
                else:
                    consensus_score = 0.2

            composite = (
                arg_quality     * 0.3 +
                avg_ver_rate    * 0.3 +
                avg_trust       * 0.2 +
                consensus_score * 0.2
            )
            # Clamp to [0, 1]
            composite = max(0.0, min(1.0, composite))

            final_metrics = result.metrics or {}
            final_metrics["confidence_breakdown"] = {
                "argument_quality_weight": 0.3,  "argument_quality_score": arg_quality,
                "verification_weight":     0.3,  "verification_score":     avg_ver_rate,
                "trust_weight":            0.2,  "trust_score":            avg_trust,
                "consensus_weight":        0.2,  "consensus_score":        consensus_score,
            }

            reasoning = result.reasoning or ""
            if len(reasoning) > 1500:
                reasoning = reasoning[:1497] + "..."

            return AgentResponse(
                agent="MODERATOR",
                round=state.round,
                argument=reasoning[:500] + "..." if len(reasoning) > 500 else reasoning,
                sources=[],
                confidence=float(composite),
                verdict=result.verdict,
                reasoning=reasoning,
                metrics=final_metrics,
            )

        except RateLimitError as e:
            logger.error(f"Moderator rate limited: {e}")
            state.moderator_reasoning = str(e)
            return self._fallback_verdict(state)
        except Exception as e:
            logger.error(f"Moderator failed: {e}")
            state.moderator_reasoning = str(e)
            return self._fallback_verdict(state)

    def _fallback_verdict(self, state: DebateState) -> AgentResponse:
        logger.warning("Moderator fallback triggered.")
        reason = state.moderator_reasoning or "Unknown error"
        if any(kw in reason.upper() for kw in ("QUOTA_EXHAUSTED", "429", "RATE LIMIT", "RATE_LIMIT")):
            verdict    = "RATE_LIMITED"
            argument   = "All LLM quotas exhausted — verification cannot proceed."
            confidence = 0.0
        else:
            verdict    = "SYSTEM_ERROR"
            argument   = "A technical interruption occurred in the moderation protocol."
            confidence = 0.0

        return AgentResponse(
            agent="MODERATOR",
            round=state.round,
            argument=argument,
            sources=[],
            confidence=confidence,
            verdict=verdict,
            reasoning=f"System fallback triggered: {reason}",
            metrics={"credibility": 0.5, "balance": 0.5},
        )

    def _build_prompt(self, state: DebateState, round_num: int) -> str:
        has_sources = bool(
            (state.pro_sources and any(s for s in state.pro_sources)) or
            (state.con_sources and any(s for s in state.con_sources))
        )
        pro_ver_rate = state.pro_verification_rate or 0.0
        con_ver_rate = state.con_verification_rate or 0.0
        no_sources   = not has_sources or (pro_ver_rate == 0.0 and con_ver_rate == 0.0)

        # Context compression: use summary for long debates, full transcript for short ones
        if state.summary:
            pro_final = (state.pro_arguments[-1] if state.pro_arguments else "No argument.")[:_MAX_ARG_CHARS]
            con_final = (state.con_arguments[-1] if state.con_arguments else "No argument.")[:_MAX_ARG_CHARS]
            pro_args  = (
                f"[EARLIER ROUNDS SUMMARY]\n{state.summary}\n\n"
                f"[FINAL PRO ARGUMENT — Round {len(state.pro_arguments)}]\n{pro_final}"
            )
            con_args  = (
                f"[See summary above for earlier rounds]\n\n"
                f"[FINAL CON ARGUMENT — Round {len(state.con_arguments)}]\n{con_final}"
            )
        else:
            pro_args = "\n\n".join(
                f"Round {i+1}: {arg[:_MAX_ARG_CHARS]}"
                for i, arg in enumerate(state.pro_arguments)
            ) or "No Pro arguments recorded."
            con_args = "\n\n".join(
                f"Round {i+1}: {arg[:_MAX_ARG_CHARS]}"
                for i, arg in enumerate(state.con_arguments)
            ) or "No Con arguments recorded."

        verification_section = ""
        if state.pro_verification_rate is not None:
            verification_section = (
                f"\nSOURCE VERIFICATION SUMMARY:\n"
                f"- ProAgent source verification rate: {pro_ver_rate:.1%}\n"
                f"- ConAgent source verification rate: {con_ver_rate:.1%}\n"
            )

        zero_source_guidance = ""
        if no_sources:
            zero_source_guidance = """
IMPORTANT — NO VERIFIED SOURCES:
Neither agent provided verifiable URLs, or all sources failed verification.
This may mean: (a) agents used general knowledge without citing URLs, 
(b) all cited URLs were hallucinated or inaccessible, or (c) a network issue occurred.
In this case:
- Do NOT automatically return INSUFFICIENT EVIDENCE.
- Evaluate the QUALITY of the arguments themselves.
- If the arguments are logically strong and consistent with well-known facts,
  return TRUE/FALSE/PARTIALLY TRUE with moderate confidence (0.3-0.6).
- Only return INSUFFICIENT EVIDENCE if the claim is genuinely ambiguous 
  AND the arguments provide no meaningful signal.
"""

        return f"""You are the impartial Moderator in a formal fact-checking debate.

CLAIM: {state.claim}

PRO ARGUMENTS (Arguing the claim is TRUE):
{pro_args}

CON ARGUMENTS (Arguing the claim is FALSE):
{con_args}
{verification_section}{zero_source_guidance}
YOUR TASK:
Analyse debate quality, assess argument strength, identify logical fallacies, and determine a final verdict.
Be rigorous, objective, and neutral. Make a DEFINITIVE call — avoid vague hedging.

VERDICT GUIDELINES:
- Use 'TRUE' or 'FALSE' if one side clearly has stronger, more credible arguments.
- Use 'PARTIALLY TRUE' for claims that are true in some contexts but false in others.
- Use 'INSUFFICIENT EVIDENCE' ONLY if both sides provide no meaningful signal whatsoever.
- NEVER use 'INSUFFICIENT EVIDENCE' just because no URLs were verified — evaluate argument quality.

SAFETY NOTE: If the claim involves medical treatments or health practices, prefix your 
reasoning with: "SAFETY NOTE: Consult a medical professional before acting on health-related claims."

STRUCTURED OUTPUT — include in your metrics dictionary:
- "argument_quality": float 0.0-1.0 (logical strength of arguments overall)
- "logical_fallacies": list of any fallacies detected (empty list if none)
- "credibility_score": float 0.0-1.0 (evidence credibility)
"""
