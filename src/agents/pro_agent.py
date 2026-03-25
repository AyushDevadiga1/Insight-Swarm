"""
ProAgent - Argues that the claim is TRUE using structured outputs.
Merge conflicts resolved: HEAD version kept, preferred_provider param added,
datetime import preserved, _sanitize_sources() inherited from BaseAgent.
"""
from datetime import datetime
from typing import Optional
from src.agents.base import BaseAgent, AgentResponse, DebateState
from src.llm.client import FreeLLMClient
import logging

logger = logging.getLogger(__name__)


class ProAgent(BaseAgent):
    """Argues the claim is TRUE using adversarial prompting and structured output."""

    def __init__(self, llm_client: FreeLLMClient, preferred_provider: Optional[str] = None):
        super().__init__(llm_client)
        self.role               = "PRO"
        # Default to groq — reliable, fast, working per orchestrator comment
        self.preferred_provider = preferred_provider or "groq"

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
        """Generate argument FOR the claim."""
        logger.info(f"ProAgent generating — Round {state.round}")

        prompt = self._build_prompt(state, state.round)

        try:
            response = self.client.call_structured(
                prompt=prompt,
                output_schema=AgentResponse,
                temperature=0.7,
                preferred_provider=self.preferred_provider,
            )
            response.agent     = "PRO"
            response.round     = state.round
            response.sources   = self._sanitize_sources(response.sources)
            response.timestamp = datetime.now().strftime("%H:%M:%S")
            self.call_count   += 1
            return response

        except Exception as e:
            logger.error(f"ProAgent failed: {e}")
            error_msg = str(e)
            if "QUOTA_EXHAUSTED" in error_msg or "429" in error_msg.lower():
                argument   = "[API_FAILURE] Quota exhausted — update API keys or wait for reset."
                confidence = 0.0
            else:
                argument = (
                    f"Based on available evidence, the claim '{state.claim}' "
                    f"appears to be TRUE. [Note: Full argument generation encountered "
                    f"a technical issue; this is a minimal fallback response.]"
                )
                confidence = 0.3

            return AgentResponse(
                agent="PRO",
                round=state.round,
                argument=argument,
                sources=[],
                confidence=confidence,
                timestamp=datetime.now().strftime("%H:%M:%S"),
            )

    def _build_prompt(self, state: DebateState, round_num: int) -> str:
        # Prefer global evidence_sources (Tavily dual-sided), fall back to pro_evidence
        evidence_bundle    = state.evidence_sources or state.pro_evidence or []
        formatted_evidence = self._format_evidence(evidence_bundle)

        if round_num == 1:
            return f"""You are ProAgent in a formal fact-checking debate. Your role is to argue that the following claim is TRUE.

CLAIM: {state.claim}

EVIDENCE TO USE:
{formatted_evidence}

YOUR TASK:
1. Build the strongest possible case FOR this claim.
2. If pre-fetched URLs are available above, cite them directly. If not, use your training knowledge and label each assertion as [General Knowledge].
3. Be specific, cite real examples, and make a persuasive argument in 3-5 sentences.
4. List any source URLs you cite in the 'sources' field.

Keep your argument factual and direct. Do NOT start with "I" or "As an AI"."""

        else:
            con_argument     = state.con_arguments[-1] if state.con_arguments else "No counter-argument yet."
            feedback_section = (
                f"\n\nVERIFICATION FEEDBACK (use this to improve your sources):\n"
                f"{state.verification_feedback}\n"
            ) if state.verification_feedback else ""

            return f"""You are ProAgent. Continue arguing that the following claim is TRUE: {state.claim}

THE OPPOSING AGENT ARGUED:
{con_argument}{feedback_section}

SUPPORTING EVIDENCE:
{formatted_evidence}

YOUR TASK:
1. Directly rebut the Con argument — address their specific points.
2. Reinforce your case with additional evidence or stronger reasoning.
3. If your previous sources failed verification, cite different or better sources.
4. Keep your response to 3-5 focused sentences."""
