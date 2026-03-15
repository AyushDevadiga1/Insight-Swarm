"""
Moderator - Analyzes debate quality and produces reasoned verdicts using structured outputs.
"""
from src.agents.base import BaseAgent, AgentResponse, DebateState
from src.core.models import ModeratorVerdict
from src.llm.client import FreeLLMClient, RateLimitError
import logging
import re

logger = logging.getLogger(__name__)

class Moderator(BaseAgent):
    """
    Agent that analyzes the debate and produces a verdict.
    Uses analytical prompting and Pydantic structured output.
    """
    
    def __init__(self, llm_client: FreeLLMClient):
        super().__init__(llm_client)
        self.role = "MODERATOR"
        self.preferred_provider = "groq"

    def generate(self, state: DebateState) -> AgentResponse:
        """Analyze complete debate and produce reasoned verdict."""
        logger.info("Moderator analyzing complete debate quality...")
        
        prompt = self._build_prompt(state, state.round)
        
        try:
            # Use call_structured with the ModeratorVerdict schema
            result = self.client.call_structured(
                prompt=prompt,
                output_schema=ModeratorVerdict,
                temperature=0.2  # Very low temperature for analytical consistency
            )
            
            self.call_count += 1
            
            # Convert ModeratorVerdict to AgentResponse for state compatibility
            return AgentResponse(
                agent="MODERATOR",
                round=state.round,
                argument=result.reasoning[:500] + "..." if len(result.reasoning) > 500 else result.reasoning,
                sources=[],
                confidence=result.confidence,
                verdict=result.verdict,
                reasoning=result.reasoning,
                metrics=result.metrics
            )
            
        except Exception as e:
            logger.error(f"Moderator failed: {e}")
            state.moderator_reasoning = str(e)  # <-- ADD THIS LINE so fallback sees it
            return self._fallback_verdict(state)
            
    def _fallback_verdict(self, state: DebateState) -> AgentResponse:
        """Graceful fallback with clear quota message."""
        logger.warning("Moderator fallback triggered")
        
        # Check if the error came from quota (passed via state or last exception)
        reason = state.moderator_reasoning or "Unknown error"
        if "QUOTA_EXHAUSTED" in reason.upper() or "429" in reason or "rate limit" in reason.lower():
            verdict = "RATE_LIMITED"
            argument = "Critical service outage: All available LLM quotas are exhausted. Verification cannot proceed."
            confidence = 0.0
        else:
            verdict = "SYSTEM_ERROR"
            argument = "A technical interruption occurred within the moderation protocol."
            confidence = 0.0
        
        return AgentResponse(
            agent="MODERATOR",
            round=state.round,
            argument=argument,
            sources=[],
            confidence=confidence,
            verdict=verdict,
            reasoning=f"System fallback triggered: {reason}",
            metrics={"credibility": 0.5, "balance": 0.5}
        )

    def _build_prompt(self, state: DebateState, round_num: int) -> str:
        pro_args = "\n\n".join([f"Round {i+1}: {arg}" for i, arg in enumerate(state.pro_arguments)])
        con_args = "\n\n".join([f"Round {i+1}: {arg}" for i, arg in enumerate(state.con_arguments)])
        
        verification_summary = ""
        if state.pro_verification_rate is not None:
            pro_rate = state.pro_verification_rate
            con_rate = (state.con_verification_rate or 0.0) if state.con_verification_rate is not None else 0.0
            verification_summary = f"""
SOURCE VERIFICATION SUMMARY:
- ProAgent Verification Rate: {pro_rate:.1%}
- ConAgent Verification Rate: {con_rate:.1%}
"""

        return f"""You are the impartial Moderator in a formal fact-checking debate.
CLAIM: {state.claim}

PRO ARGUMENTS (Supporting Claim):
{pro_args}

CON ARGUMENTS (Opposing Claim):
{con_args}

{verification_summary}

YOUR TASK:
Analyze the debate quality, assess source credibility, identify logical fallacies, and determine a final verdict.
Be rigorous, objective, and neutral. 

GUIDELINES FOR VERDICT:
- Prefer 'TRUE' or 'FALSE' if a clear preponderance of verifiable evidence exists.
- Use 'PARTIALLY TRUE' for multi-faceted claims with mixed evidence.
- ONLY use 'INSUFFICIENT EVIDENCE' if NO verifiable sources are found or the providers totally failed.
- Avoid 'wait-and-see' hesitation; make a definitive call based on the available data.
"""

