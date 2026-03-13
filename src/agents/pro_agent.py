"""
ProAgent - Argues that the claim is TRUE using structured outputs.
"""
from src.agents.base import BaseAgent, AgentResponse, DebateState
from src.llm.client import FreeLLMClient
import logging

logger = logging.getLogger(__name__)

class ProAgent(BaseAgent):
    """
    Agent that argues the claim is TRUE.
    Uses adversarial prompting and Pydantic structured output.
    """
    
    def __init__(self, llm_client: FreeLLMClient):
        super().__init__(llm_client)
        self.role = "PRO"
    
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
            response = self.client.call_structured(
                prompt=prompt,
                output_schema=AgentResponse,
                temperature=0.7
            )
            
            # Ensure the agent field is correct
            response.agent = "PRO"
            response.round = state.round
            
            self.call_count += 1
            return response
            
        except Exception as e:
            logger.error(f"ProAgent failed to generate structured response: {e}")
            # Fallback for critical failure
            return AgentResponse(
                agent="PRO",
                round=state.round,
                argument=f"I maintain my position that the claim '{state.claim}' is true, based on previous evidence.",
                sources=[],
                confidence=0.5
            )
    
    def _build_prompt(self, state: DebateState, round_num: int) -> str:
        evidence_bundle = state.get('pro_evidence', [])
        formatted_evidence = self._format_evidence(evidence_bundle)
        
        if round_num == 1:
            return f"""You are ProAgent in a formal debate. Your role is to argue that the claim is TRUE.
CLAIM: {state.claim}

EVIDENCE TO CITE:
{formatted_evidence}

YOUR TASK:
Build the strongest possible case FOR this claim. 
You MUST cite the source URLs provided in the evidence section.
Focus on being persuasive but factual."""
        else:
            con_argument = state.con_arguments[-1] if state.con_arguments else "No counter-argument yet"
            return f"""You are ProAgent. You must maintain that the following claim is TRUE: {state.claim}

The opposing agent argued:
{con_argument}

YOUR TASK:
Directly address their rebuttal and strengthen your original case. 
Use NEW evidence if available in your previous research:
{formatted_evidence}"""