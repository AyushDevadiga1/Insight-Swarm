"""
ProAgent - Argues that the claim is TRUE using structured outputs.
"""
from typing import List, Dict, Any, Optional
from src.agents.base import BaseAgent, AgentResponse, DebateState
from src.llm.client import FreeLLMClient
from src.utils.url_helper import URLNormalizer
import logging

logger = logging.getLogger(__name__)

class ProAgent(BaseAgent):
    """
    Agent that argues the claim is TRUE.
    Uses adversarial prompting and Pydantic structured output.
    """
    
    def __init__(self, llm_client: FreeLLMClient, preferred_provider: Optional[str] = None):
        super().__init__(llm_client)
        self.role = "PRO"
        self.preferred_provider = preferred_provider or "cerebras"  # ProAgent prefers Cerebras (Llama 3.1 8b)
    
    def _format_evidence(self, evidence_bundle):
        if not evidence_bundle:
            return "No specific evidence provided yet."
        return "\n".join([
            f"- {item.get('title', 'Source')} ({item.get('url', 'URL')}): {item.get('content', '')[:200]}..."
            for item in evidence_bundle
        ])

    def generate(self, state: DebateState) -> AgentResponse:
        """Generate argument FOR the claim using structured JSON output."""
        logger.info(f"ProAgent generating argument for Round {state.round}")
        
        prompt = self._build_prompt(state, state.round)
        
        try:
            # Use the new call_structured method which returns an AgentResponse model
            from src.config import AgentConfig
            response = self.client.call_structured(
                prompt=prompt,
                output_schema=AgentResponse,
                temperature=AgentConfig.DEFAULT_TEMPERATURE,
                preferred_provider=self.preferred_provider
            )
            
            # Ensure the agent field is correct
            response.agent = "PRO"
            response.round = state.round
            
            sanitized = []
            if response.sources:
                for s in response.sources:
                    res = URLNormalizer.sanitize_url(s)
                    if res:
                        sanitized.append(res)
            response.sources = sanitized
            
            self.call_count += 1
            return response
            
        except Exception as e:
            logger.error(f"{self.role}Agent failed to generate structured response: {e}")
            error_msg = str(e)
            if "QUOTA_EXHAUSTED" in error_msg:
                argument = f"[API QUOTA EXHAUSTED] Cannot generate new argument. Please update your API keys in .env or wait for quota reset."
                confidence = 0.0
            else:
                argument = f"I maintain my position that the claim '{state.claim}' is {self.role.lower()}. (LLM call failed due to technical issue)"
                confidence = 0.5
            
            return AgentResponse(
                agent=self.role,
                round=state.round,
                argument=argument,
                sources=[],
                confidence=confidence
            )
    
    def _build_prompt(self, state: DebateState, round_num: int) -> str:
        # RAAD: Prioritize global evidence_sources for strict grounding
        evidence_bundle = state.evidence_sources or state.pro_evidence or []
        formatted_evidence = self._format_evidence(evidence_bundle)
        
        if round_num == 1:
            return f"""You are ProAgent. Argue that the claim is TRUE.
CLAIM: {state.claim}
EVIDENCE: {formatted_evidence}

TASK: Build a strong case using ONLY these sources. Cite URL accurately. Be concise and persuasive."""
        else:
            con_argument = state.con_arguments[-1] if state.con_arguments else ""
            feedback = f"\n\n{state.verification_feedback}" if state.verification_feedback else ""
                
            return f"""You are ProAgent. CLAIM: {state.claim} is TRUE.
OPPONENT SAID: {con_argument}{feedback}

TASK: Refute their points and strengthen your case using: {formatted_evidence}. Be brief."""
