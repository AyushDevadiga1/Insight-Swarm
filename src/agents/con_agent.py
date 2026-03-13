"""
ConAgent - Argues that the claim is FALSE using structured outputs.
"""
from src.agents.base import BaseAgent, AgentResponse, DebateState
from src.llm.client import FreeLLMClient
import logging

logger = logging.getLogger(__name__)

class ConAgent(BaseAgent):
    """
    Agent that argues the claim is FALSE.
    Takes the opposite position from ProAgent and challenges their evidence.
    """
    
    def __init__(self, llm_client: FreeLLMClient):
        super().__init__(llm_client)
        self.role = "CON"
    
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
            response = self.client.call_structured(
                prompt=prompt,
                output_schema=AgentResponse,
                temperature=0.7
            )
            
            # Ensure the agent field is correct
            response.agent = "CON"
            response.round = state.round
            
            self.call_count += 1
            return response
            
        except Exception as e:
            logger.error(f"ConAgent failed to generate structured response: {e}")
            # Fallback for critical failure
            return AgentResponse(
                agent="CON",
                round=state.round,
                argument=f"I maintain my position that the claim '{state.claim}' is false, as the evidence provided by the ProAgent is insufficient or flawed.",
                sources=[],
                confidence=0.5
            )
    
    def _build_prompt(self, state: DebateState, round_num: int) -> str:
        evidence_bundle = state.get('con_evidence', [])
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
Build the strongest possible case AGAINST this claim. 
You MUST cite the source URLs provided in the evidence section.
Focus on identifying flaws in the Pro argument and presenting counter-evidence."""
        else:
            pro_rebuttal = state.pro_arguments[-1] if len(state.pro_arguments) > 1 else "No Pro rebuttal yet"
            return f"""You are ConAgent. You must maintain that the following claim is FALSE: {state.claim}

The opposing agent responded with:
{pro_rebuttal}

YOUR TASK:
Directly address their rebuttal and reinforce your original case. 
Use NEW evidence if available in your previous research:
{formatted_evidence}"""