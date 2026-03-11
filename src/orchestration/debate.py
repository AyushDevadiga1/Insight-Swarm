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
        
        # Build workflow
        self.workflow = self._build_workflow()
        
        logger.info("DebateOrchestrator initialized with ProAgent and ConAgent")
    
    def _build_workflow(self) -> StateGraph:
        """
        Build LangGraph state machine for debate flow.
        
        Flow:
        START → ProAgent → ConAgent → (check rounds) → 
                ↑__________________|
                                   ↓
                              Verdict → END
        
        Returns:
            Compiled LangGraph workflow
        """
        
        # Create state graph
        workflow = StateGraph(DebateState)
        
        # Add nodes (each is a function that processes state)
        workflow.add_node("pro_agent", self._pro_agent_node)
        workflow.add_node("con_agent", self._con_agent_node)
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
                "end": "verdict"           # Go to verdict calculation
            }
        )
        
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
            logger.error(f"ProAgent failed: {e}")
            # Add error placeholder
            state['pro_arguments'].append(f"[Error: {str(e)}]")
            state['pro_sources'].append([])
        
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
            logger.error(f"ConAgent failed: {e}")
            state['con_arguments'].append(f"[Error: {str(e)}]")
            state['con_sources'].append([])
            state['round'] += 1
        
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
    
    def _verdict_node(self, state: DebateState) -> DebateState:
        """
        Calculate final verdict based on all arguments.
        
        Simple algorithm for MVP:
        - Count total words in PRO vs CON arguments
        - More words = stronger position (proxy for evidence)
        - Calculate confidence based on ratio
        
        Args:
            state: Current debate state
            
        Returns:
            State with verdict and confidence set
        """
        logger.info("Calculating verdict...")
        
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
        
        # Calculate ratio
        pro_ratio = pro_words / total_words
        
        # Determine verdict
        if pro_ratio > 0.60:
            state['verdict'] = "TRUE"
            state['confidence'] = pro_ratio
        elif pro_ratio < 0.40:
            state['verdict'] = "FALSE"
            state['confidence'] = 1 - pro_ratio
        else:
            state['verdict'] = "PARTIALLY TRUE"
            state['confidence'] = 2.0 * abs(0.5 - pro_ratio)  # Range 0-1: low at 0.5 (tied), high at extremes
        
        logger.info(f"Verdict: {state['verdict']} ({state['confidence']:.2%} confidence)")
        logger.info(f"  PRO: {pro_words} words across {len(state['pro_arguments'])} arguments")
        logger.info(f"  CON: {con_words} words across {len(state['con_arguments'])} arguments")
        
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