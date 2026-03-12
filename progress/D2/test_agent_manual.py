"""
Manual testing of agents on different claim types

SECURITY FEATURES:
- Input validation before processing
- Error handling with safe error messages
- Timeout protection for LLM calls
- Comprehensive logging
"""

import sys
from pathlib import Path

# Add parent directory to path for imports when running directly
sys.path.insert(0, str(Path(__file__).parent))

from src.agents.pro_agent import ProAgent
from src.agents.con_agent import ConAgent
from src.agents.base import DebateState
from src.llm.client import FreeLLMClient
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def validate_claim(claim: str) -> None:
    """
    Validate claim before processing
    
    Args:
        claim: Claim text to validate
        
    Raises:
        ValueError: If claim is invalid
    """
    if not claim or not isinstance(claim, str):
        raise ValueError("Claim must be a non-empty string")
    
    if len(claim.strip()) == 0:
        raise ValueError("Claim cannot be empty or whitespace-only")
    
    if len(claim) > 1000:
        raise ValueError("Claim exceeds maximum length of 1000 characters")


def run_claim(claim: str) -> None:
    """
    Test both agents on a specific claim
    
    Args:
        claim: The claim to test
        
    Raises:
        ValueError: If claim is invalid
        RuntimeError: If LLM providers are unavailable
    """
    
    # Validate input
    validate_claim(claim)
    
    print(f"\n{'='*70}")
    print(f"CLAIM: {claim}")
    print('='*70)
    
    try:
        # Setup
        client = FreeLLMClient()
        pro_agent = ProAgent(client)
        con_agent = ConAgent(client)
        
        state = DebateState(
            claim=claim,
            round=1,
            pro_arguments=[],
            con_arguments=[],
            pro_sources=[],
            con_sources=[],
            verdict=None,
            confidence=None
        )
        
        # ProAgent argues FOR
        print("\n📘 PRO AGENT (Arguing FOR):")
        try:
            pro_response = pro_agent.generate(state)
            print(f"\n{pro_response['argument']}")
            print(f"\nSources cited: {len(pro_response['sources'])}")
            for i, source in enumerate(pro_response['sources'], 1):
                print(f"  {i}. {source}")
            
            # Update state
            state['pro_arguments'].append(pro_response['argument'])
            state['pro_sources'].append(pro_response['sources'])
        
        except Exception as e:
            logger.error(f"❌ ProAgent failed: {type(e).__name__}")
            print(f"   Error: {str(e)[:100]}")
            return
        
        # ConAgent argues AGAINST
        print("\n📕 CON AGENT (Arguing AGAINST):")
        try:
            con_response = con_agent.generate(state)
            print(f"\n{con_response['argument']}")
            print(f"\nSources cited: {len(con_response['sources'])}")
            for i, source in enumerate(con_response['sources'], 1):
                print(f"  {i}. {source}")
        
        except Exception as e:
            logger.error(f"❌ ConAgent failed: {type(e).__name__}")
            print(f"   Error: {str(e)[:100]}")
            raise
        
        print("\n" + "="*70 + "\n")
    
    except RuntimeError as e:
        logger.error(f"❌ LLM initialization failed: {e}")
        print(f"   Error: LLM providers unavailable")


if __name__ == "__main__":
    print("\n🧪 TESTING AGENTS ON 3 DIFFERENT CLAIMS")
    print("="*70)
    
    claims = [
        "Coffee prevents cancer",           # Nuanced (partial truth)
        "The Earth is flat",                 # Obviously false
        "Exercise improves mental health"    # Clearly true
    ]
    
    for claim in claims:
        try:
            run_claim(claim)
        except ValueError as e:
            logger.error(f"❌ Claim validation failed: {e}")
        except Exception as e:
            logger.error(f"❌ Unexpected error: {type(e).__name__}: {e}")
    
    print("✅ Manual testing complete!")