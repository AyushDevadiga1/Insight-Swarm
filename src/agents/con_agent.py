"""
ConAgent - Argues that the claim is FALSE

This agent challenges ProAgent's evidence and presents counter-arguments.
"""

from typing import List
from src.agents.base import BaseAgent, AgentResponse, DebateState


class ConAgent(BaseAgent):
    """
    Agent that argues the claim is FALSE.
    
    Takes the opposite position from ProAgent and challenges
    their evidence and reasoning.
    """
    
    def __init__(self, llm_client):
        """
        Initialize ConAgent
        
        Args:
            llm_client: FreeLLMClient instance
        """
        super().__init__(llm_client)
        self.role = "CON"
    
    def generate(self, state: DebateState) -> AgentResponse:
        """
        Generate argument AGAINST the claim.
        
        Process:
        1. Build adversarial prompt based on round
        2. Call LLM via FreeLLMClient (with error handling)
        3. Validate response before parsing
        4. Parse response to extract argument and sources
        5. Return structured response
        
        Args:
            state: Current debate state (includes ProAgent's arguments)
            
        Returns:
            AgentResponse with CON counter-argument and sources
            
        Raises:
            ValueError: If response validation fails
            RuntimeError: If LLM call fails
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Build prompt
        prompt = self._build_prompt(state, state['round'])
        
        # Call LLM with error handling
        response_text = None
        try:
            response_text = self.client.call(
                prompt,
                temperature=0.7,
                max_tokens=800,
                timeout=30
            )
        except (ValueError, RuntimeError) as e:
            # Client validation or provider errors
            logger.error(f"❌ LLM call failed: {type(e).__name__} - ConAgent round {state['round']}")
            raise RuntimeError(f"Failed to generate CON argument: {str(e)}")
        except Exception as e:
            # Unexpected errors (connection, timeout, etc.)
            logger.error(f"❌ Unexpected error during LLM call: {type(e).__name__}")
            logger.debug(f"   Error details: {str(e)[:200]}")
            raise RuntimeError(f"Unexpected error generating CON argument: LLM provider error")
        
        # Validate response before parsing
        if response_text is None:
            logger.error("❌ LLM returned None response")
            raise ValueError("LLM returned None response for CON argument")
        
        if not isinstance(response_text, str):
            logger.error(f"❌ LLM returned invalid type: {type(response_text).__name__}")
            raise ValueError(f"LLM response must be string, got {type(response_text).__name__}")
        
        if not response_text.strip():
            logger.error("❌ LLM returned empty response")
            raise ValueError("LLM returned empty response for CON argument")
        
        # Parse response
        try:
            argument, sources = self._parse_response(response_text)
        except ValueError as e:
            logger.error(f"❌ Failed to parse LLM response: {e}")
            raise ValueError(f"Failed to parse CON response: {str(e)}")
        
        # Track call
        self.call_count += 1
        
        return AgentResponse(
            agent="CON",
            round=state['round'],
            argument=argument,
            sources=sources,
            confidence=0.75
        )
    
    def _build_prompt(self, state: DebateState, round_num: int) -> str:
        """
        Build adversarial prompt that forces arguing AGAINST the claim.
        
        Args:
            state: Current debate state
            round_num: Current round number
            
        Returns:
            Formatted prompt string
        """
        claim = state['claim']
        
        if round_num == 1:
            # Get ProAgent's argument to challenge
            pro_argument = state['pro_arguments'][0] if state['pro_arguments'] else "No argument yet"
            pro_sources = state['pro_sources'][0] if state['pro_sources'] else []
            
            return f"""You are ConAgent in a formal academic debate. Your role is to argue that the following claim is FALSE, regardless of your personal beliefs.

You MUST present the strongest possible case AGAINST this claim.

CLAIM: {claim}

ProAgent has argued FOR this claim with:

THEIR ARGUMENT:
{pro_argument}

THEIR SOURCES:
{chr(10).join(f'- {s}' for s in pro_sources) if pro_sources else '- None cited'}

YOUR TASK:
1. Challenge the credibility, methodology, or relevance of ProAgent's sources
2. Find 2-3 credible sources that contradict or question the claim
3. Point out logical flaws, missing context, or overgeneralizations in their argument
4. Present the strongest evidence AGAINST the claim
5. Be rigorous and evidence-based

FORMAT YOUR RESPONSE EXACTLY AS:

ARGUMENT:
[Your counter-argument: 150-200 words. Challenge their evidence specifically.]

SOURCES:
- [Full URL or citation 1]
- [Full URL or citation 2]
- [Full URL or citation 3]

IMPORTANT:
- You are REQUIRED to argue AGAINST this claim
- Challenge ProAgent's evidence directly
- Use credible, verifiable sources
- Be specific (cite conflicting studies, point out flaws)"""

        else:
            # Round 2+: Counter-rebuttal
            pro_rebuttal = state['pro_arguments'][-1] if len(state['pro_arguments']) > 1 else "No rebuttal yet"
            
            return f"""ProAgent has responded to your challenge with:

THEIR REBUTTAL:
{pro_rebuttal}

YOUR TASK:
1. Counter their rebuttal points
2. Reinforce why the claim is FALSE
3. Provide additional evidence if available
4. Maintain your position

FORMAT:

REBUTTAL:
[Your counter-rebuttal: 100-150 words]

SOURCES:
- [Additional sources if needed]

Remember: You must maintain that the claim is FALSE."""


# ============================================
# TESTING CODE
# ============================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("ConAgent Test (requires ProAgent to run first)")
    print("="*60)
    
    from src.llm.client import FreeLLMClient
    from src.agents.pro_agent import ProAgent
    
    # Initialize
    client = FreeLLMClient()
    pro_agent = ProAgent(client)
    con_agent = ConAgent(client)
    
    # Test state
    state = DebateState(
        claim="Coffee prevents cancer",
        round=1,
        pro_arguments=[],
        con_arguments=[],
        pro_sources=[],
        con_sources=[],
        verdict=None,
        confidence=None
    )
    
    # Step 1: ProAgent argues FOR
    print("\n1. ProAgent arguing FOR the claim...")
    pro_response = pro_agent.generate(state)
    state['pro_arguments'].append(pro_response['argument'])
    state['pro_sources'].append(pro_response['sources'])
    
    print(f"   ✅ ProAgent: {pro_response['argument'][:100]}...")
    
    # Step 2: ConAgent argues AGAINST
    print("\n2. ConAgent arguing AGAINST the claim...")
    con_response = con_agent.generate(state)
    
    # Display results
    print("\n3. Debate Results:")
    print("\n   📘 PRO ARGUMENT:")
    print(f"   {pro_response['argument'][:200]}...")
    print(f"\n   PRO SOURCES: {len(pro_response['sources'])} cited")
    
    print("\n   📕 CON ARGUMENT:")
    print(f"   {con_response['argument'][:200]}...")
    print(f"\n   CON SOURCES: {len(con_response['sources'])} cited")
    
    print("\n" + "="*60)
    print("✅ Both agents debated successfully!")
    print("="*60 + "\n")