"""
ConAgent - Argues that the claim is FALSE using structured outputs.
"""
from typing import List, Dict, Any, Optional
from src.agents.base import BaseAgent, AgentResponse, DebateState
from src.llm.client import FreeLLMClient
from src.utils.url_helper import URLNormalizer
import logging

logger = logging.getLogger(__name__)

class ConAgent(BaseAgent):
    """
    Agent that argues the claim is FALSE.
    Takes the opposite position from ProAgent and challenges their evidence.
    """
    
    def __init__(self, llm_client: FreeLLMClient, preferred_provider: Optional[str] = None):
        super().__init__(llm_client)
        self.role = "CON"
        self.preferred_provider = preferred_provider or "openrouter"  # ConAgent prefers OpenRouter (Llama 3.1 70B)
    
    def _format_evidence(self, evidence_bundle):
        if not evidence_bundle:
            return "No specific evidence provided yet."
        return "\n".join([
            f"- {item.get('title', 'Source')} ({item.get('url', 'URL')}): {item.get('content', '')[:200]}..."
            for item in evidence_bundle
        ])

    def generate(self, state: DebateState) -> AgentResponse:
        """Generate argument AGAINST the claim using structured JSON output."""
        logger.info(f"ConAgent generating argument for Round {state.round}")
        
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
            response.agent = "CON"
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
        evidence_bundle = state.evidence_sources or state.con_evidence or []
        formatted_evidence = self._format_evidence(evidence_bundle)
        
        # ConAgent always challenges the latest ProAgent argument
        pro_argument = state.pro_arguments[-1] if state.pro_arguments else "No Pro argument yet"
        
        if round_num == 1:
            return f"""You are ConAgent. Argue that the claim is FALSE.
CLAIM: {state.claim}
PRO SAID: {pro_argument}
EVIDENCE: {formatted_evidence}

TASK: Rebut the Pro argument using these sources. Cite URLs. Identify flaws. Be concise."""
        else:
            latest_pro = state.pro_arguments[-1] if state.pro_arguments else ""
            feedback = f"\n\nFEEDBACK: {state.verification_feedback}\n" if state.verification_feedback else ""
                
            return f"""You are ConAgent. CLAIM: {state.claim} is FALSE.
PRO LATEST: {latest_pro}{feedback}
OUR PREVIOUS: {state.con_arguments[-1] if state.con_arguments else ""}

TASK: Debunk the Pro rebuttal and reinforce your case using: {formatted_evidence}. Be brief."""
