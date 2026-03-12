"""
DebateOrchestrator - Coordinates multi-round debate using LangGraph

Manages 3-round debate between ProAgent and ConAgent:
- Round 1: Both agents make initial arguments
- Round 2: Both agents rebut each other
- Round 3: Final synthesis
- Verdict: Calculate based on all arguments
"""

import sys
import logging
from pathlib import Path
from typing import Literal, Dict, Any
from langgraph.graph import StateGraph, END

# Add parent directories to path for imports when running directly
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.base import DebateState
from src.agents.pro_agent import ProAgent
from src.agents.con_agent import ConAgent
from src.agents.fact_checker import FactChecker
from src.llm.client import FreeLLMClient

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DebateOrchestrator:
    """
    Orchestrates multi-round debate between ProAgent and ConAgent.
    
    Uses LangGraph state machine to coordinate agent turns and
    manage debate flow.
    """
    
    def __init__(self):
        """Initialize orchestrator with agents and workflow"""
        
        # Initialize LLM client (shared by all agents)
        self.client = FreeLLMClient()
        
        # Initialize agents
        self.pro_agent = ProAgent(self.client)
        self.con_agent = ConAgent(self.client)
        self.fact_checker = FactChecker(self.client)
        
        # Build workflow
        self.workflow = self._build_workflow()
        
        logger.info("DebateOrchestrator initialized with ProAgent, ConAgent, and FactChecker")
    
    def _build_workflow(self) -> StateGraph:
        """
        Build LangGraph state machine for debate flow.
        
        Flow:
        START → ProAgent → ConAgent → (check rounds) → 
                ↑__________________|
                                   ↓
                          FactChecker → Verdict → END
        
        Returns:
            Compiled LangGraph workflow
        """
        
        # Create state graph
        workflow = StateGraph(DebateState)
        
        # Add nodes (each is a function that processes state)
        workflow.add_node("pro_agent", self._pro_agent_node)
        workflow.add_node("con_agent", self._con_agent_node)
        workflow.add_node("fact_checker", self._fact_checker_node)
        workflow.add_node("verdict", self._verdict_node)
        
        # Set entry point
        workflow.set_entry_point("pro_agent")
        
        # Pro → Con (always)
        workflow.add_edge("pro_agent", "con_agent")
        
        # Con → Check if should continue or end
        workflow.add_conditional_edges(
            "con_agent",
            self._should_continue,
            {
                "continue": "pro_agent",  # Loop back for another round
                "end": "fact_checker"      # Go to fact checker after debate ends
            }
        )
        
        # FactChecker → Verdict
        workflow.add_edge("fact_checker", "verdict")
        
        # Verdict → END
        workflow.add_edge("verdict", END)
        
        return workflow.compile()
    
    def _pro_agent_node(self, state: DebateState) -> DebateState:
        """
        Execute ProAgent turn.
        
        Args:
            state: Current debate state
            
        Returns:
            Updated state with ProAgent's response added
        """
        logger.info(f"ProAgent turn - Round {state['round']}")
        
        try:
            # Generate response
            response = self.pro_agent.generate(state)
            
            # Update state
            state['pro_arguments'].append(response['argument'])
            state['pro_sources'].append(response['sources'])
            
            logger.info(f"ProAgent completed - {len(response['argument'])} chars, {len(response['sources'])} sources")
            
        except Exception as e:
            logger.error(f"❌ ProAgent failed: {type(e).__name__}: {str(e)[:100]}")
            # Raise to let orchestrator handle recovery instead of polluting state
            raise RuntimeError(f"ProAgent generation failed") from e
        
        return state
    
    def _con_agent_node(self, state: DebateState) -> DebateState:
        """
        Execute ConAgent turn.
        
        Args:
            state: Current debate state
            
        Returns:
            Updated state with ConAgent's response added
        """
        logger.info(f"ConAgent turn - Round {state['round']}")
        
        try:
            # Generate response
            response = self.con_agent.generate(state)
            
            # Update state
            state['con_arguments'].append(response['argument'])
            state['con_sources'].append(response['sources'])
            
            # Increment round counter (after both agents have gone)
            state['round'] += 1
            
            logger.info(f"ConAgent completed - {len(response['argument'])} chars, {len(response['sources'])} sources")
            
        except Exception as e:
            logger.error(f"❌ ConAgent failed: {type(e).__name__}: {str(e)[:100]}")
            # Raise to let orchestrator handle recovery instead of polluting state
            state['round'] += 1
            raise RuntimeError(f"ConAgent generation failed") from e
        
        return state
    
    def _should_continue(self, state: DebateState) -> Literal["continue", "end"]:
        """
        Decide whether to continue debate or move to verdict.
        
        Args:
            state: Current debate state
            
        Returns:
            "continue" if more rounds needed, "end" if ready for verdict
        """
        if state['round'] > 3:  # After round 3, stop
            logger.info("Debate complete - moving to verdict")
            return "end"
        else:
            logger.info(f"Continuing to round {state['round']}")
            return "continue"
    
    def _fact_checker_node(self, state: DebateState) -> DebateState:
        """
        Execute FactChecker to verify all sources cited during debate.
        
        Args:
            state: Current debate state with all arguments and sources
            
        Returns:
            Updated state with verification results
        """
        logger.info("FactChecker: Starting source verification")
        
        try:
            # Generate verification response
            response = self.fact_checker.generate(state)
            
            # Store verification results in state
            state['verification_results'] = response['verification_results']
            
            # Calculate verification rates by agent
            pro_sources = []
            con_sources = []
            
            for result in response['verification_results']:
                if result['agent_source'] == 'PRO':
                    pro_sources.append(result)
                else:
                    con_sources.append(result)
            
            # Calculate individual verification rates
            if pro_sources:
                pro_verified = sum(1 for r in pro_sources if r['status'] == 'VERIFIED')
                state['pro_verification_rate'] = pro_verified / len(pro_sources)
            else:
                state['pro_verification_rate'] = 1.0  # No sources = perfect
            
            if con_sources:
                con_verified = sum(1 for r in con_sources if r['status'] == 'VERIFIED')
                state['con_verification_rate'] = con_verified / len(con_sources)
            else:
                state['con_verification_rate'] = 1.0  # No sources = perfect
            
            logger.info(f"Source verification complete")
            logger.info(f"  PRO verification rate: {state['pro_verification_rate']:.0%}")
            logger.info(f"  CON verification rate: {state['con_verification_rate']:.0%}")
            
        except Exception as e:
            logger.error(f"FactChecker failed: {e}")
            # Set default values if verification fails
            state['verification_results'] = []
            state['pro_verification_rate'] = 0.5
            state['con_verification_rate'] = 0.5
        
        return state
    
    def _verdict_node(self, state: DebateState) -> DebateState:
        """
        Calculate final verdict based on all arguments with weighted consensus.
        
        Algorithm:
        - Count words in PRO vs CON arguments
        - Weight by source verification rate (FactChecker)
        - FactChecker gets additional 2x weight (objective fact verification)
        - Calculate confidence based on weighted ratio
        
        Weighted score formula:
        pro_score = pro_words * pro_verification_rate
        con_score = con_words * con_verification_rate
        fact_score = (pro_verification_rate + con_verification_rate) / 2 * 2  (2x weight)
        
        final_score = (pro_score + con_score + fact_score) / (total + fact_weight)
        
        Args:
            state: Current debate state with verification data
            
        Returns:
            State with verdict and confidence set
        """
        logger.info("Calculating weighted verdict with source verification...")
        
        # Count words in arguments
        pro_words = sum(len(arg.split()) for arg in state['pro_arguments'])
        con_words = sum(len(arg.split()) for arg in state['con_arguments'])
        
        total_words = pro_words + con_words
        
        if total_words == 0:
            # Edge case: no arguments
            state['verdict'] = "UNVERIFIABLE"
            state['confidence'] = 0.0
            logger.warning("No arguments generated - verdict UNVERIFIABLE")
            return state
        
        # Get verification rates (default to 0.5 if not available)
        pro_verification_rate = state.get('pro_verification_rate', 0.5) or 0.5
        con_verification_rate = state.get('con_verification_rate', 0.5) or 0.5
        
        # Calculate weighted scores
        pro_score = pro_words * pro_verification_rate
        con_score = con_words * con_verification_rate
        
        # FactChecker gets 2x weight (objective verification is crucial)
        fact_score = ((pro_verification_rate + con_verification_rate) / 2.0) * 2.0
        
        # Calculate final weighted ratio
        total_weighted_words = pro_score + con_score
        
        if total_weighted_words == 0:
            # Both sides have 0 verified sources
            pro_ratio = 0.5
        else:
            pro_ratio = pro_score / total_weighted_words
        
        # Adjust by fact score (2x weight)
        # Fact score shifts the balance: if sources are mostly verified, maintain position
        # If sources are mostly hallucinated, move toward middle (PARTIALLY TRUE)
        if fact_score >= 1.5:
            # Most sources verified, trust the argument balance
            final_ratio = pro_ratio
        elif fact_score <= 0.5:
            # Most sources hallucinated, reduce confidence toward middle
            final_ratio = 0.5 + (pro_ratio - 0.5) * 0.3  # Only 30% trust
        else:
            # Mixed verification, proportional trust
            final_ratio = pro_ratio
        
        # Determine verdict based on final ratio
        if final_ratio > 0.65:
            state['verdict'] = "TRUE"
            state['confidence'] = final_ratio
        elif final_ratio < 0.35:
            state['verdict'] = "FALSE"
            state['confidence'] = 1.0 - final_ratio
        else:
            state['verdict'] = "PARTIALLY TRUE"
            state['confidence'] = 2.0 * abs(0.5 - final_ratio)  # Range 0-1
        
        # Log detailed verdict calculation
        logger.info(f"\n📊 VERDICT CALCULATION DETAILS:")
        logger.info(f"  Arguments:")
        logger.info(f"    PRO: {pro_words} words × {pro_verification_rate:.0%} verification = {pro_score:.0f}")
        logger.info(f"    CON: {con_words} words × {con_verification_rate:.0%} verification = {con_score:.0f}")
        logger.info(f"  FactChecker (2x weight):")
        logger.info(f"    Avg verification: {(pro_verification_rate + con_verification_rate) / 2.0:.0%} → score: {fact_score:.1f}")
        logger.info(f"  Final weighted ratio: {final_ratio:.1%}")
        logger.info(f"\n⚖️  VERDICT: {state['verdict']}")
        logger.info(f"📊 CONFIDENCE: {state['confidence']:.1%}")
        logger.info(f"  PRO: {pro_words} words ({pro_verification_rate:.0%} sources verified)")
        logger.info(f"  CON: {con_words} words ({con_verification_rate:.0%} sources verified)")
        
        return state
    
    def run(self, claim: str) -> DebateState:
        """
        Run complete debate on a claim.
        
        Args:
            claim: The claim to fact-check
            
        Returns:
            Final debate state with verdict and full history
        """
        logger.info(f"Starting debate on claim: {claim}")
        
        # Initialize state
        initial_state = DebateState(
            claim=claim,
            round=1,
            pro_arguments=[],
            con_arguments=[],
            pro_sources=[],
            con_sources=[],
            verification_results=None,
            pro_verification_rate=None,
            con_verification_rate=None,
            verdict=None,
            confidence=None
        )
        
        # Run workflow
        try:
            final_state = self.workflow.invoke(initial_state)
            logger.info("Debate completed successfully")
            return final_state
            
        except Exception as e:
            logger.error(f"Debate failed: {e}")
            # Return state with error
            initial_state['verdict'] = "ERROR"
            initial_state['confidence'] = 0.0
            return initial_state


# ============================================
# TESTING CODE
# ============================================

if __name__ == "__main__":
    # Fix for Windows console encoding
    import sys
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("\n" + "="*70)
    print("DebateOrchestrator Test")
    print("="*70)
    
    # Initialize
    orchestrator = DebateOrchestrator()
    
    # Test claim
    claim = "Coffee prevents cancer"
    
    print(f"\n🔍 Testing claim: {claim}")
    print("⏳ Running 3-round debate...\n")
    
    # Run debate
    result = orchestrator.run(claim)
    
    # Display results
    print("="*70)
    print("DEBATE RESULTS")
    print("="*70)
    
    print(f"\n⚖️  VERDICT: {result['verdict']}")
    print(f"📊 CONFIDENCE: {result['confidence']:.1%}")
    
    print("\n📘 PRO ARGUMENTS:")
    for i, arg in enumerate(result['pro_arguments'], 1):
        print(f"\n  Round {i}:")
        print(f"  {arg[:200]}...")
        print(f"  Sources: {len(result['pro_sources'][i-1])}")
    
    print("\n📕 CON ARGUMENTS:")
    for i, arg in enumerate(result['con_arguments'], 1):
        print(f"\n  Round {i}:")
        print(f"  {arg[:200]}...")
        print(f"  Sources: {len(result['con_sources'][i-1])}")
    
    print("\n" + "="*70)
    print("✅ Test complete!")
    print("="*70 + "\n")