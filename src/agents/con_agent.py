"""
ConAgent - Argues that the claim is FALSE using structured outputs.
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


class ConAgent(BaseAgent):
<<<<<<< HEAD
    """Argues the claim is FALSE using adversarial prompting and structured output."""

    def __init__(self, llm_client: FreeLLMClient):
        super().__init__(llm_client)
        self.role               = "CON"
        self.preferred_provider = "gemini"   # ConAgent uses Gemini (different training data)

=======
    """
    Agent that argues the claim is FALSE.
    Takes the opposite position from ProAgent and challenges their evidence.
    """
    
    def __init__(self, llm_client: FreeLLMClient, preferred_provider: Optional[str] = None):
        super().__init__(llm_client)
        self.role = "CON"
        self.preferred_provider = preferred_provider or "openrouter"  # ConAgent prefers OpenRouter (Llama 3.1 70B)
    
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
            self.call_count += 1
            return response

        except Exception as e:
            logger.error(f"ConAgent failed: {e}")
            error_msg = str(e)
            if "QUOTA_EXHAUSTED" in error_msg:
                argument   = "[API_FAILURE] Quota exhausted — update API keys or wait for reset."
                confidence = 0.0
            else:
                argument   = (f"I maintain that the claim '{state.claim}' is unsupported. "
                              f"(LLM error: technical issue)")
                confidence = 0.5
            return AgentResponse(
                agent="CON", round=state.round,
                argument=argument, sources=[], confidence=confidence,
                timestamp=datetime.now().strftime("%H:%M:%S"),
            )

    def _build_prompt(self, state: DebateState, round_num: int) -> str:
        evidence_bundle    = state.evidence_sources or state.con_evidence or []
        formatted_evidence = self._format_evidence(evidence_bundle)
        pro_argument       = state.pro_arguments[-1] if state.pro_arguments else "No Pro argument yet."

        if round_num == 1:
            return f"""You are ConAgent in a formal debate. Your role is to argue that the claim is FALSE.
CLAIM: {state.claim}

PRO ARGUMENT TO CHALLENGE:
{pro_argument}

EVIDENCE TO CITE:
{formatted_evidence}

YOUR TASK:
Build the strongest possible case AGAINST this claim using the provided evidence.
You MUST cite source URLs. Identify flaws in the Pro argument and present counter-evidence."""
        else:
            feedback_section = (
                f"\n\nVERIFICATION FEEDBACK:\n{state.verification_feedback}\n"
                if state.verification_feedback else ""
            )
            return f"""You are ConAgent. Maintain that the following claim is FALSE: {state.claim}

YOUR PREVIOUS ARGUMENT:
{state.con_arguments[-1] if state.con_arguments else "Establishing initial case."}

LATEST PRO REBUTTAL:
{pro_argument}{feedback_section}

YOUR TASK:
Address their latest points while reinforcing your own case.
Use counter-evidence from these sources:
{formatted_evidence}"""
