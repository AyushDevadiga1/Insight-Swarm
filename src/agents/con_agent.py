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
            return f"""You are ConAgent in a formal debate. Your role is to argue that the claim is FALSE.
CLAIM: {state.claim}

PRO ARGUMENT TO CHALLENGE:
{pro_argument}

EVIDENCE TO CITE:
{formatted_evidence}

YOUR TASK:
Build the strongest possible case AGAINST this claim using the PROVIDED REBUTTAL EVIDENCE. 
You MUST cite the source URLs. Focus on identifying flaws in the Pro argument and presenting counter-evidence from these specific sources."""
        else:
            # Identify the new rebuttal to challenge
            latest_pro = state.pro_arguments[-1] if state.pro_arguments else "No Pro argument yet"
            
            feedback_section = ""
            if state.verification_feedback:
                feedback_section = f"\n\nVERIFICATION FEEDBACK:\n{state.verification_feedback}\n"
                
            return f"""You are ConAgent. You must maintain that the following claim is FALSE: {state.claim}

YOUR PREVIOUS ARGUMENT:
{state.con_arguments[-1] if state.con_arguments else "Establishing initial case."}

THE OPPOSING AGENT'S LATEST REBUTTAL:
{latest_pro}{feedback_section}

YOUR TASK:
Directly address their latest points while reinforcing your own previous case. 
Use NEW evidence if available or cite existing sources to debunk their claims:
{formatted_evidence}"""
