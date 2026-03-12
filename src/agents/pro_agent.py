"""
ProAgent - Argues that the claim is TRUE

This agent is given an adversarial prompt that FORCES it to find
evidence supporting the claim, regardless of the claim's actual truth.
"""

from typing import List
from src.agents.base import BaseAgent, AgentResponse, DebateState


class ProAgent(BaseAgent):
    """
    Agent that argues the claim is TRUE.
    
    Uses adversarial prompting to force the LLM to take a position
    in favor of the claim, even if the claim is questionable.
    """
    
    def __init__(self, llm_client):
        """
        Initialize ProAgent
        
        Args:
            llm_client: FreeLLMClient instance
        """
        super().__init__(llm_client)
        self.role = "PRO"
    
    def generate(self, state: DebateState) -> AgentResponse:
        """
        Generate argument FOR the claim.
        
        Process:
        1. Build adversarial prompt based on round
        2. Call LLM via FreeLLMClient (with error handling)
        3. Validate response before parsing
        4. Parse response to extract argument and sources
        5. Return structured response
        
        Args:
            state: Current debate state
            
        Returns:
            AgentResponse with PRO argument and sources
            
        Raises:
            ValueError: If response validation fails
            RuntimeError: If LLM call fails after retries
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Build prompt based on current round
        prompt = self._build_prompt(state, state['round'])
        
        # Call LLM with error handling
        response_text = None
        try:
            response_text = self.client.call(
                prompt,
                temperature=0.7,  # Some creativity for diverse arguments
                max_tokens=800,   # Enough for 150-200 word argument + sources
                timeout=30
            )
        except (ValueError, RuntimeError) as e:
            # Client validation or provider errors
            logger.error(f"❌ LLM call failed: {type(e).__name__} - ProAgent round {state['round']}")
            raise RuntimeError(f"Failed to generate PRO argument: {str(e)}")
        except Exception as e:
            # Unexpected errors (connection, timeout, etc.)
            logger.error(f"❌ Unexpected error during LLM call: {type(e).__name__}")
            logger.debug(f"   Error details: {str(e)[:200]}")
            raise RuntimeError(f"Unexpected error generating PRO argument: LLM provider error")
        
        # Validate response before parsing
        if response_text is None:
            logger.error("❌ LLM returned None response")
            raise ValueError("LLM returned None response for PRO argument")
        
        if not isinstance(response_text, str):
            logger.error(f"❌ LLM returned invalid type: {type(response_text).__name__}")
            raise ValueError(f"LLM response must be string, got {type(response_text).__name__}")
        
        if not response_text.strip():
            logger.error("❌ LLM returned empty response")
            raise ValueError("LLM returned empty response for PRO argument")
        
        # Parse response
        try:
            argument, sources = self._parse_response(response_text)
        except ValueError as e:
            logger.error(f"❌ Failed to parse LLM response: {e}")
            raise ValueError(f"Failed to parse PRO response: {str(e)}")
        
        # Track call
        self.call_count += 1
        
        # Return structured response
        return AgentResponse(
            agent="PRO",
            round=state['round'],
            argument=argument,
            sources=sources,
            confidence=0.75  # Placeholder - could be calculated from response
        )
    
    def _build_prompt(self, state: DebateState, round_num: int) -> str:
        """
        Build adversarial prompt that forces arguing FOR the claim.
        
        Round 1: Initial argument with sources
        Round 2+: Rebuttal to ConAgent's challenges
        
        Args:
            state: Current debate state
            round_num: Current round number
            
        Returns:
            Formatted prompt string
        """
        import html
        # Sanitize claim input to prevent prompt injection
        claim = html.escape(state['claim'])[:500]
        
        if round_num == 1:
            # Round 1: Initial argument
            return f"""You are ProAgent in a formal academic debate. Your role is to argue that the following claim is TRUE, regardless of your personal beliefs about its accuracy.

You MUST present the strongest possible case FOR this claim, using credible sources and sound reasoning.

CLAIM: {claim}

YOUR TASK:
1. Find 2-3 credible sources that support this claim (academic papers, reputable news, government health sites, etc.)
2. Present the strongest arguments in favor of the claim
3. Acknowledge potential weaknesses but explain why they don't invalidate the claim
4. Cite specific evidence: studies, statistics, expert quotes, research findings
5. Be persuasive but academically rigorous

FORMAT YOUR RESPONSE EXACTLY AS:

ARGUMENT:
[Your argument here: 150-200 words. Be specific, cite studies, use evidence.]

SOURCES:
- [Full URL or citation 1]
- [Full URL or citation 2]
- [Full URL or citation 3]

IMPORTANT:
- You are REQUIRED to argue FOR this claim
- Present the best possible case even if the claim seems unlikely
- Use only credible, verifiable sources
- Be specific with evidence (numbers, study names, dates)"""

        else:
            # Round 2+: Rebuttal
            con_argument = state['con_arguments'][-1] if state['con_arguments'] else "No counter-argument yet"
            con_sources = state['con_sources'][-1] if state['con_sources'] else []
            
            return f"""You previously argued that this claim is TRUE: {claim}

The opposing agent (ConAgent) has challenged your position with:

THEIR ARGUMENT:
{con_argument}

THEIR SOURCES:
{chr(10).join(f'- {s}' for s in con_sources) if con_sources else '- None cited'}

YOUR TASK:
1. Directly address their strongest points
2. Point out flaws, biases, or missing context in their argument
3. Strengthen your original position with NEW evidence if possible
4. Maintain that the claim is TRUE despite their challenges

FORMAT:

REBUTTAL:
[Your rebuttal: 100-150 words. Address their points directly.]

SOURCES:
- [Additional sources if you found new evidence]

Remember: You must maintain your position that the claim is TRUE."""


# ============================================
# TESTING CODE
# ============================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("ProAgent Test")
    print("="*60)
    
    from src.llm.client import FreeLLMClient
    
    # Initialize
    client = FreeLLMClient()
    pro_agent = ProAgent(client)
    
    # Test state
    test_state = DebateState(
        claim="Coffee prevents cancer",
        round=1,
        pro_arguments=[],
        con_arguments=[],
        pro_sources=[],
        con_sources=[],
        verdict=None,
        confidence=None
    )
    
    # Generate argument
    print("\n1. Generating ProAgent argument...")
    response = pro_agent.generate(test_state)
    
    # Display results
    print("\n2. ProAgent Response:")
    print(f"\n   Agent: {response['agent']}")
    print(f"   Round: {response['round']}")
    print(f"   Confidence: {response['confidence']}")
    
    print(f"\n   Argument ({len(response['argument'])} chars):")
    print(f"   {response['argument'][:300]}...")
    
    print(f"\n   Sources ({len(response['sources'])} found):")
    for i, source in enumerate(response['sources'], 1):
        print(f"   {i}. {source}")
    
    print("\n" + "="*60)
    print("✅ ProAgent test complete")
    print("="*60 + "\n")