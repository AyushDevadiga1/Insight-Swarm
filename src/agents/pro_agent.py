"""
ProAgent - Argues that the claim is TRUE using structured outputs.
"""
<<<<<<< HEAD
from datetime import datetime
=======
from typing import List, Dict, Any, Optional
>>>>>>> origin/main
from src.agents.base import BaseAgent, AgentResponse, DebateState
from src.llm.client import FreeLLMClient
import logging

logger = logging.getLogger(__name__)


class ProAgent(BaseAgent):
<<<<<<< HEAD
    """Argues the claim is TRUE using adversarial prompting and structured output."""

    def __init__(self, llm_client: FreeLLMClient):
        super().__init__(llm_client)
        self.role               = "PRO"
        self.preferred_provider = "groq"   # ProAgent uses Groq (Llama)

=======
    """
    Agent that argues the claim is TRUE.
    Uses adversarial prompting and Pydantic structured output.
    """
    
    def __init__(self, llm_client: FreeLLMClient, preferred_provider: Optional[str] = None):
        super().__init__(llm_client)
        self.role = "PRO"
        self.preferred_provider = preferred_provider or "cerebras"  # ProAgent prefers Cerebras (Llama 3.1 8b)
    
>>>>>>> origin/main
    def _format_evidence(self, evidence_bundle):
        if not evidence_bundle:
            return "No specific evidence provided yet."
        return "\n".join(
            f"- {item.get('title', 'Source')} ({item.get('url', 'URL')}): "
            f"{item.get('content', '')[:200]}..."
            for item in evidence_bundle
        )

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
            self.call_count += 1
            return response

        except Exception as e:
            logger.error(f"ProAgent failed: {e}")
            error_msg = str(e)
            if "QUOTA_EXHAUSTED" in error_msg:
                argument   = "[API_FAILURE] Quota exhausted — update API keys or wait for reset."
                confidence = 0.0
            else:
                argument   = (f"I maintain that the claim '{state.claim}' is supported. "
                              f"(LLM error: technical issue)")
                confidence = 0.5
            return AgentResponse(
                agent="PRO", round=state.round,
                argument=argument, sources=[], confidence=confidence,
                timestamp=datetime.now().strftime("%H:%M:%S"),
            )

    def _build_prompt(self, state: DebateState, round_num: int) -> str:
        evidence_bundle   = state.evidence_sources or state.pro_evidence or []
        formatted_evidence = self._format_evidence(evidence_bundle)

        if round_num == 1:
            return f"""You are ProAgent in a formal debate. Your role is to argue that the claim is TRUE.
CLAIM: {state.claim}

EVIDENCE TO CITE:
{formatted_evidence}

YOUR TASK:
Build the strongest possible case FOR this claim using ONLY the provided evidence.
You MUST cite the source URLs. Be persuasive but factual."""
        else:
            con_argument = state.con_arguments[-1] if state.con_arguments else "No counter-argument yet."
            feedback_section = (
                f"\n\n{state.verification_feedback}\n" if state.verification_feedback else ""
            )
            return f"""You are ProAgent. Maintain that the following claim is TRUE: {state.claim}

The opposing agent argued:
{con_argument}{feedback_section}

YOUR TASK:
Address their rebuttal and strengthen your case.
Use supporting evidence from your research:
{formatted_evidence}"""
