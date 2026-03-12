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
from src.agents.moderator import Moderator
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
        self.moderator = Moderator(self.client)  # NEW
        
        # Build workflow
        self.workflow = self._build_workflow()
        
        logger.info("DebateOrchestrator initialized with 4 agents")
    
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
        workflow.add_node("moderator", self._moderator_node)  # NEW
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
        
        # FactChecker → Moderator (NEW)
        workflow.add_edge("fact_checker", "moderator")
        
        # Moderator → Verdict (NEW)
        workflow.add_edge("moderator", "verdict")
        
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
            # FIX 5: Only increment on success
            state['round'] += 1
            
            logger.info(f"ConAgent completed - {len(response['argument'])} chars, {len(response['sources'])} sources")
            
        except Exception as e:
            logger.error(f"❌ ConAgent failed: {type(e).__name__}: {str(e)[:100]}")
            # FIX 5: Only increment round counter on successful agent completion
            # Before it was: state['round'] += 1 (WRONG)
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
        if state['round'] >= 3:  # After round 3, stop (FIX 1: >= 3 instead of > 3)
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
            
            # Calculate individual verification rates (FIX 2 & 12)
            if pro_sources:
                pro_verified = sum(1 for r in pro_sources if r['status'] == 'VERIFIED')
                pro_hallucinated = sum(1 for r in pro_sources if r['status'] in ['NOT_FOUND', 'CONTENT_MISMATCH'])
                pro_timeout = sum(1 for r in pro_sources if r['status'] == 'TIMEOUT')
                state['pro_verification_rate'] = pro_verified / len(pro_sources)
                logger.info(f"  PRO sources: {pro_verified} verified, {pro_hallucinated} hallucinated, {pro_timeout} timeout")
            else:
                state['pro_verification_rate'] = 0.0  # FIX 2: No sources = 0.0% verification
                logger.warning("ProAgent cited no sources - verification rate set to 0.0")
            
            if con_sources:
                con_verified = sum(1 for r in con_sources if r['status'] == 'VERIFIED')
                con_hallucinated = sum(1 for r in con_sources if r['status'] in ['NOT_FOUND', 'CONTENT_MISMATCH'])
                con_timeout = sum(1 for r in con_sources if r['status'] == 'TIMEOUT')
                state['con_verification_rate'] = con_verified / len(con_sources)
                logger.info(f"  CON sources: {con_verified} verified, {con_hallucinated} hallucinated, {con_timeout} timeout")
            else:
                state['con_verification_rate'] = 0.0  # FIX 2: No sources = 0.0% verification
                logger.warning("ConAgent cited no sources - verification rate set to 0.0")
            
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
    
    def _moderator_node(self, state: DebateState) -> DebateState:
        """
        Execute Moderator analysis.
        
        Moderator reviews all arguments and produces reasoned verdict.
        
        Args:
            state: Current debate state
            
        Returns:
            Updated state with Moderator's verdict
        """
        logger.info("Moderator analyzing debate quality...")
        
        try:
            response = self.moderator.generate(state)
            
            # FIX 3: Store Moderator's verdict and reasoning directly from structured response
            state['verdict'] = response.get('verdict', 'INSUFFICIENT EVIDENCE')
            state['confidence'] = response.get('confidence', 0.5)
            state['moderator_reasoning'] = response['argument']  # Already parsed reasoning
            
            logger.info(f"Moderator verdict: {state['verdict']} ({state['confidence']:.1%})")
            
        except Exception as e:
            logger.error(f"Moderator analysis failed: {e}")
            
            # Fallback
            state['verdict'] = "ERROR"
            state['confidence'] = 0.0
            state['moderator_reasoning'] = f"Moderator analysis failed: {str(e)}"
        
        return state


    def _verdict_node(self, state: DebateState) -> DebateState:
        """
        Final verdict node - already set by Moderator.
        
        This node logs the final verdict and a safe preview of reasoning.
        
        Args:
            state: Debate state with Moderator's verdict
            
        Returns:
            State (unchanged)
        """
        verdict = state.get('verdict', 'INSUFFICIENT EVIDENCE')
        confidence = state.get('confidence', 0.0)
        reasoning = state.get('moderator_reasoning', 'N/A')
        
        logger.info(f"Final verdict: {verdict} ({confidence:.1%} confidence)")
        
        # Safe logging of reasoning (truncate and strip to avoid log pollution)
        safe_reasoning = reasoning.replace('\n', ' ').strip()
        if len(safe_reasoning) > 150:
            safe_reasoning = safe_reasoning[:147] + "..."
            
        logger.info(f"Moderator reasoning preview: {safe_reasoning}")
        
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
        
        # Initialize state (FIX 10: Use None for optional fields)
        initial_state: DebateState = {
            "claim": claim,
            "round": 1,
            "pro_arguments": [],
            "con_arguments": [],
            "pro_sources": [],
            "con_sources": [],
            "verdict": None,
            "confidence": None,
            "verification_results": None,
            "pro_verification_rate": None,
            "con_verification_rate": None,
            "fact_check_result": None,
            "moderator_reasoning": None
        }
        
        # Run workflow
        try:
            final_state = self.workflow.invoke(initial_state)
            logger.info("Debate completed successfully")
            return final_state
            
        except Exception as e:
            logger.error(f"Debate failed: {e}")
            # Ensure all keys are present even on error
            initial_state['verdict'] = "ERROR"
            initial_state['confidence'] = 0.0
            initial_state['moderator_reasoning'] = f"Debate failed: {str(e)}"
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