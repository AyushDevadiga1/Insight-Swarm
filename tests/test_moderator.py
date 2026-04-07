"""
Unit tests for Moderator Agent
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.moderator import Moderator
from src.core.models import DebateState, ModeratorVerdict
from src.llm.client import FreeLLMClient
from unittest.mock import MagicMock


def test_moderator_analysis():
    print("\n" + "=" * 70)
    print("Moderator Agent Test")
    print("=" * 70)

    # ── FIX: mock call_structured (not the old .call), return ModeratorVerdict ─
    client = MagicMock(spec=FreeLLMClient)
    client.call_structured.return_value = ModeratorVerdict(
        verdict="TRUE",
        confidence=0.85,
        reasoning="The evidence for coffee's health benefits is well-supported.",
        metrics={"credibility": 0.9, "balance": 0.5, "argument_quality": 0.8},
    )
    moderator = Moderator(client)

    # ── FIX: DebateState fields 'verdict', 'confidence', 'moderator_reasoning'
    # are non-Optional str/float — passing None raises Pydantic ValidationError.
    # Use the field defaults instead ("UNKNOWN", 0.0, "").
    test_state = DebateState(
        claim="Coffee prevents cancer",
        round=4,
        pro_arguments=[
            "Studies show coffee contains antioxidants that may reduce cancer risk by 15%.",
            "Multiple meta-analyses confirm the protective effect.",
            "The evidence is clear from large-scale studies.",
        ],
        con_arguments=[
            "Correlation does not imply causation — coffee drinkers may be healthier overall.",
            "WHO was cautious about coffee until 2016.",
            "Some studies show no effect or even increased risk for certain cancers.",
        ],
        pro_sources=[
            ["https://www.cancer.gov/", "https://pubmed.ncbi.nlm.nih.gov/12345"],
            ["https://www.hsph.harvard.edu/"],
            [],
        ],
        con_sources=[
            ["https://www.who.int/", "https://www.mayoclinic.org/"],
            ["https://www.cancer.org/"],
            [],
        ],
        pro_verification_rate=0.85,
        con_verification_rate=0.75,
        verification_results=[],
        # verdict / confidence / moderator_reasoning intentionally use defaults
        # ("UNKNOWN", 0.0, "") — do NOT pass None for non-Optional fields.
    )

    print("\n1. Testing Moderator analysis...")
    print(f"   Claim: {test_state['claim']}")
    print(f"   Pro verification: {test_state['pro_verification_rate']:.1%}")
    print(f"   Con verification: {test_state['con_verification_rate']:.1%}")

    result = moderator.generate(test_state)

    print("\n2. Moderator Verdict:")
    print(f"\n   Agent:      {result['agent']}")
    print(f"   Confidence: {result['confidence']:.1%}")
    print(f"\n   Reasoning:")
    for line in result["argument"].split("\n"):
        print(f"   {line}")

    # Basic sanity assertions
    assert result.agent    == "MODERATOR"
    assert result.verdict  == "TRUE"
    assert 0.0 <= result.confidence <= 1.0

    print("\n" + "=" * 70)
    print("✅ Moderator test complete!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    test_moderator_analysis()
