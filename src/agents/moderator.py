"""
Moderator - Analyzes debate quality and produces reasoned verdicts using structured outputs.
"""
from typing import List, Dict, Any, Optional
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
    
    def __init__(self, llm_client: FreeLLMClient, preferred_provider: Optional[str] = None):
        super().__init__(llm_client)
        self.role = "MODERATOR"
        self.preferred_provider = preferred_provider or "openrouter"

    def generate(self, state: DebateState) -> AgentResponse:
        """Analyze complete debate and produce reasoned verdict."""
        logger.info("Moderator analyzing complete debate quality...")
        
        prompt = self._build_prompt(state, state.round)
        
        try:
            # Use the provider configured by the orchestrator (default: gemini)
            # Do not override with OpenRouter/Claude-3.5-Sonnet — that model costs money
            # and OpenRouter is currently non-functional for this project
            result = self.client.call_structured(
                prompt=prompt,
                output_schema=ModeratorVerdict,
                temperature=0.2,  # Very low temperature for analytical consistency
                preferred_provider=self.preferred_provider
            )
            
            self.call_count += 1
            
            # Math: (arg_quality * 0.3) + (avg_ver_rate * 0.3) + (avg_trust * 0.2) + (consensus * 0.2)
            
            arg_quality = 0.5
            if result.metrics and "argument_quality" in result.metrics:
                arg_quality = result.metrics["argument_quality"] / 100.0 if result.metrics["argument_quality"] > 1 else result.metrics["argument_quality"]
            
            pro_rate = state.pro_verification_rate or 0.0
            con_rate = state.con_verification_rate or 0.0
            avg_ver_rate = (pro_rate + con_rate) / 2

            # Calculate trust scores across all sources
            from src.utils.trust_scorer import TrustScorer
            
            pro_trust_scores = []
            con_trust_scores = []
            
            # Score Pro sources
            for round_sources in state.pro_sources:
                for url in round_sources:
                    score = TrustScorer.get_score(url)
                    pro_trust_scores.append(score)
            
            # Score Con sources
            for round_sources in state.con_sources:
                for url in round_sources:
                    score = TrustScorer.get_score(url)
                    con_trust_scores.append(score)
            
            pro_avg_trust = sum(pro_trust_scores) / len(pro_trust_scores) if pro_trust_scores else 0.5
            con_avg_trust = sum(con_trust_scores) / len(con_trust_scores) if con_trust_scores else 0.5
            avg_trust = (pro_avg_trust + con_avg_trust) / 2
            
            logger.info(f"Trust scores - Pro: {pro_avg_trust:.2f}, Con: {con_avg_trust:.2f}")
            
            consensus_score = 0.5
            if state.metrics and "consensus" in state.metrics:
                consensus_data = state.metrics["consensus"]
                if consensus_data.get("verdict") == result.verdict:
                    consensus_score = consensus_data.get("score", 0.8)
                elif consensus_data.get("verdict") == "DEBATE":
                    consensus_score = 0.5
                else:
                    consensus_score = 0.2
            
            composite_confidence = (arg_quality * 0.3) + (avg_ver_rate * 0.3) + (avg_trust * 0.2) + (consensus_score * 0.2)
            
            # Update metrics with breakdown
            final_metrics = result.metrics or {}
            final_metrics.update({
                "confidence_breakdown": {
                    "argument_quality_weight": 0.3,
                    "argument_quality_score": arg_quality,
                    "verification_weight": 0.3,
                    "verification_score": avg_ver_rate,
                    "trust_weight": 0.2,
                    "trust_score": avg_trust,
                    "consensus_weight": 0.2,
                    "consensus_score": consensus_score
                }
            })

            # Enforce reasoning length cap for token efficiency
            reasoning = result.reasoning
            if len(reasoning) > 1500:
                reasoning = reasoning[:1497] + "..."

            return AgentResponse(
                agent="MODERATOR",
                round=state.round,
                argument=result.reasoning[:500] + "..." if len(result.reasoning) > 500 else result.reasoning,
                sources=[],
                confidence=float(composite_confidence),
                verdict=result.verdict,
                reasoning=reasoning,
                metrics=final_metrics
            )
            
        except Exception as e:
            logger.exception(f"Moderator synthesis failed critically: {e}")
            state.moderator_reasoning = f"CritError: {type(e).__name__} - {str(e)}"
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
        
        # Calculate trust for display
        from src.utils.trust_scorer import TrustScorer
        pro_trust_scores = [TrustScorer.get_score(url) 
                            for sources in state.pro_sources 
                            for url in sources]
        con_trust_scores = [TrustScorer.get_score(url) 
                            for sources in state.con_sources 
                            for url in sources]
        
        pro_avg = sum(pro_trust_scores) / len(pro_trust_scores) if pro_trust_scores else 0.5
        con_avg = sum(con_trust_scores) / len(con_trust_scores) if con_trust_scores else 0.5
        
        trust_summary = f"""
SOURCE CREDIBILITY ANALYSIS:
- Pro sources average trust: {pro_avg:.2f}/1.0 (higher = more credible)
  • {len(pro_trust_scores)} sources cited
  • Trust tier breakdown: {len([s for s in pro_trust_scores if s >= 0.8])} high-trust, {len([s for s in pro_trust_scores if s < 0.5])} low-trust
- Con sources average trust: {con_avg:.2f}/1.0
  • {len(con_trust_scores)} sources cited
  • Trust tier breakdown: {len([s for s in con_trust_scores if s >= 0.8])} high-trust, {len([s for s in con_trust_scores if s < 0.5])} low-trust

IMPORTANT: Weight arguments by source credibility. Arguments backed by 
high-trust sources (.gov, .edu, peer-reviewed) should carry MORE weight
than those from low-trust sources (.xyz, blogs, unknown domains).
"""

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

{trust_summary}

{verification_summary}

YOUR TASK:
Analyze the debate quality, assess source credibility, identify logical fallacies, and determine a final verdict.
Be rigorous, objective, and neutral. 

GUIDELINES FOR VERDICT:
- Prefer 'TRUE' or 'FALSE' if a clear preponderance of verifiable evidence exists.
- Use 'PARTIALLY TRUE' for multi-faceted claims with mixed evidence.
- ONLY use 'INSUFFICIENT EVIDENCE' if NO verifiable sources are found or the providers totally failed.
- Avoid 'wait-and-see' hesitation; make a definitive call based on the available data.

STRUCTURED OUTPUT REQUIREMENTS:
In your metrics dictionary, include:
- "argument_quality": A score from 0.0 to 1.0 reflecting the logical strength of the arguments.
- "logical_fallacies": List of any fallacies detected.
- "credibility_score": A score from 0.0 to 1.0 for overall evidence credibility.
"""

