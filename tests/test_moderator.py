"""
Unit tests for Moderator Agent
"""

import sys
import logging
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.moderator import Moderator
from src.agents.base import DebateState
from src.llm.client import FreeLLMClient

def test_moderator_analysis():
    print("\n" + "="*70)
    print("Moderator Agent Test")
    print("="*70)
    
    # Initialize
    client = FreeLLMClient()
    moderator = Moderator(client)
    
    # Mock debate state
    test_state = DebateState(
        claim="Coffee prevents cancer",
        round=4,
        pro_arguments=[
            "Studies show coffee contains antioxidants that may reduce cancer risk by 15%.",
            "Multiple meta-analyses confirm the protective effect.",
            "The evidence is clear from large-scale studies."
        ],
        con_arguments=[
            "Correlation does not imply causation - coffee drinkers may be healthier overall.",
            "WHO was cautious about coffee until 2016.",
            "Some studies show no effect or even increased risk for certain cancers."
        ],
        pro_sources=[
            ["https://www.cancer.gov/", "https://pubmed.ncbi.nlm.nih.gov/12345"],
            ["https://www.hsph.harvard.edu/"],
            []
        ],
        con_sources=[
            ["https://www.who.int/", "https://www.mayoclinic.org/"],
            ["https://www.cancer.org/"],
            []
        ],
        verdict=None,
        confidence=None,
        pro_verification_rate=0.85,
        con_verification_rate=0.75,
        verification_results=[],
        fact_check_result="5 out of 6 sources verified",
        moderator_reasoning=None,
    )
    
    print("\n1. Testing Moderator analysis...")
    print(f"   Claim: {test_state['claim']}")
    print(f"   Pro verification: {test_state['pro_verification_rate']:.1%}")
    print(f"   Con verification: {test_state['con_verification_rate']:.1%}")
    
    # Generate verdict
    result = moderator.generate(test_state)
    
    # Display results
    print("\n2. Moderator Verdict:")
    print(f"\n   Agent: {result['agent']}")
    print(f"   Confidence: {result['confidence']:.1%}")
    
    print(f"\n   Reasoning:")
    reasoning_lines = result['argument'].split('\n')
    for line in reasoning_lines:
        print(f"   {line}")
    
    print("\n" + "="*70)
    print("✅ Moderator test complete!")
    print("="*70 + "\n")

if __name__ == "__main__":
    test_moderator_analysis()
