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
            verdict = "INSUFFICIENT EVIDENCE"
            argument = "API quota exhausted. Cannot complete fact-checking. Please add fresh Groq/Gemini keys in .env or wait."
            confidence = 0.0
        else:
            verdict = "INSUFFICIENT EVIDENCE"
            argument = "Technical error during moderation. Defaulting to insufficient evidence."
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
            verification_summary = f"""
SOURCE VERIFICATION SUMMARY:
- ProAgent Verification Rate: {state.pro_verification_rate:.1%}
- ConAgent Verification Rate: {state.con_verification_rate or 0.0:.1%}
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
Be rigorous, objective, and neutral."""

    def _parse_moderator_response(self, text: str):
        """Parse a freeform moderator response into structured fields."""
        verdict = "INSUFFICIENT EVIDENCE"
        confidence = 0.0
        reasoning = ""
        metrics = {}

        if not text:
            return verdict, confidence, reasoning, metrics

        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            # Normalize "VERDICT - TRUE" to "VERDICT: TRUE"
            if " - " in line and ":" not in line:
                line = line.replace(" - ", ":", 1)
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip().lower()
                value = value.strip()
                if key.startswith("verdict"):
                    v = value.lower()
                    if "partially" in v:
                        verdict = "PARTIALLY TRUE"
                    elif "insufficient" in v:
                        verdict = "INSUFFICIENT EVIDENCE"
                    elif "true" in v:
                        verdict = "TRUE"
                    elif "false" in v:
                        verdict = "FALSE"
                elif key.startswith("confidence"):
                    try:
                        confidence = float(value)
                    except ValueError:
                        pass
                elif key.startswith("reasoning"):
                    reasoning = value

        if not reasoning:
            reasoning = text.strip()

        return verdict, confidence, reasoning, metrics
