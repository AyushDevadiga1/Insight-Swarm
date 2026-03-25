"""
ConAgent - Argues that the claim is FALSE using structured outputs.
Merge conflicts resolved: HEAD version kept, preferred_provider param added,
datetime import preserved, _sanitize_sources() inherited from BaseAgent.
"""
from datetime import datetime
from typing import Optional
from src.agents.base import BaseAgent, AgentResponse, DebateState
from src.llm.client import FreeLLMClient
import logging

logger = logging.getLogger(__name__)


class ConAgent(BaseAgent):
    """Argues the claim is FALSE using adversarial prompting and structured output."""

    def __init__(self, llm_client: FreeLLMClient, preferred_provider: Optional[str] = None):
        super().__init__(llm_client)
        self.role               = "CON"
        # Default to gemini — uses different training data from groq/llama,
        # giving genuinely different perspectives for the opposing argument
        self.preferred_provider = preferred_provider or "gemini"

    def _format_evidence(self, evidence_bundle) -> str:
        if not evidence_bundle:
            return (
                "No pre-fetched evidence available. "
                "Use your training knowledge and clearly label each claim as "
                "'[General Knowledge]' since no URLs were retrieved."
            )
        lines = []
        for item in evidence_bundle:
            title   = item.get("title", "Source")
            url     = item.get("url", "")
            content = item.get("content", "")[:300]
            lines.append(f"- {title} ({url}): {content}...")
        return "\n".join(lines)

    def generate(self, state: DebateState) -> AgentResponse:
        """Generate argument AGAINST the claim."""
        logger.info(f"ConAgent generating — Round {state.round}")

        prompt = self._build_prompt(state, state.round)

        try:
            response = self.client.call_structured(
                prompt=prompt,
                output_schema=AgentResponse,
                temperature=0.7,
                preferred_provider=self.preferred_provider,
            )
            response.agent     = "CON"
            response.round     = state.round
            response.sources   = self._sanitize_sources(response.sources)
            response.timestamp = datetime.now().strftime("%H:%M:%S")
            self.call_count   += 1
            return response

        except Exception as e:
            logger.error(f"ConAgent failed: {e}")
            error_msg = str(e)
            if "QUOTA_EXHAUSTED" in error_msg or "429" in error_msg.lower():
                argument   = "[API_FAILURE] Quota exhausted — update API keys or wait for reset."
                confidence = 0.0
            else:
                argument = (
                    f"The claim '{state.claim}' is not fully supported by the available evidence. "
                    f"[Note: Full argument generation encountered a technical issue; "
                    f"this is a minimal fallback response.]"
                )
                confidence = 0.3

            return AgentResponse(
                agent="CON",
                round=state.round,
                argument=argument,
                sources=[],
                confidence=confidence,
                timestamp=datetime.now().strftime("%H:%M:%S"),
            )

    def _build_prompt(self, state: DebateState, round_num: int) -> str:
        # Use global evidence_sources (Tavily dual-sided), fall back to con_evidence
        evidence_bundle    = state.evidence_sources or state.con_evidence or []
        formatted_evidence = self._format_evidence(evidence_bundle)
        pro_argument       = state.pro_arguments[-1] if state.pro_arguments else "No Pro argument yet."

        if round_num == 1:
            return f"""You are ConAgent in a formal fact-checking debate. Your role is to argue that the following claim is FALSE or overstated.

CLAIM: {state.claim}

THE PRO AGENT ARGUED:
{pro_argument}

COUNTER-EVIDENCE TO USE:
{formatted_evidence}

YOUR TASK:
1. Build the strongest possible case AGAINST this claim.
2. Directly challenge the Pro argument — identify flaws, missing context, or cherry-picked data.
3. If pre-fetched URLs are available above, cite them. If not, use your training knowledge labeled as [General Knowledge].
4. Be specific and cite real counter-examples in 3-5 sentences.
5. List any source URLs you cite in the 'sources' field.

Keep your argument factual and direct. Do NOT start with "I" or "As an AI"."""

        else:
            latest_pro       = state.pro_arguments[-1] if state.pro_arguments else "No new Pro argument."
            feedback_section = (
                f"\n\nVERIFICATION FEEDBACK (improve your source citations):\n"
                f"{state.verification_feedback}\n"
            ) if state.verification_feedback else ""

            return f"""You are ConAgent. Continue arguing that the following claim is FALSE: {state.claim}

YOUR PREVIOUS ARGUMENT:
{state.con_arguments[-1] if len(state.con_arguments) > 1 else "Establishing initial case."}

LATEST PRO REBUTTAL:
{latest_pro}{feedback_section}

COUNTER-EVIDENCE:
{formatted_evidence}

YOUR TASK:
1. Rebut the Pro's latest argument specifically — don't repeat yourself.
2. Identify new flaws, missing context, or contradictory evidence.
3. If your previous sources failed verification, cite stronger alternatives.
4. Keep your response to 3-5 focused sentences."""
