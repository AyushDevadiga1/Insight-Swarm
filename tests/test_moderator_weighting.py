import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.moderator import Moderator
from src.core.models import SourceVerification
from unittest.mock import MagicMock

def test_weighting():
    mock_client = MagicMock()
    mod = Moderator(llm_client=mock_client)
    
    # Case 1: High trust, high confidence vs Low trust, low confidence
    results = [
        {
            "url": "high-trust.com", 
            "status": "VERIFIED", 
            "confidence": 0.9, 
            "trust_score": 0.95,
            "agent_source": "PRO"
        },
        {
            "url": "low-trust.com", 
            "status": "ERROR", 
            "confidence": 0.4, 
            "trust_score": 0.2,
            "agent_source": "PRO"
        }
    ]
    
    score = mod._calculate_weighted_score(results, "PRO")
    print(f"Weighted Score (Case 1): {score:.4f}")
    assert score > 0.8, f"Score {score} should be close to 0.9 due to high trust weighting"

    # Case 2: Even split but higher trust for FALSE (represented by agent CON)
    results = [
        {"url": "a.com", "status": "VERIFIED", "confidence": 0.8, "trust_score": 0.4, "agent_source": "PRO"},
        {"url": "b.com", "status": "VERIFIED", "confidence": 0.8, "trust_score": 0.9, "agent_source": "PRO"},
        {"url": "c.com", "status": "ERROR", "confidence": 0.8, "trust_score": 0.9, "agent_source": "PRO"}
    ]
    score = mod._calculate_weighted_score(results, "PRO")
    print(f"Weighted Score (Case 2 - Mixed): {score:.4f}")
    # (0.4*0.8 + 0.9*0.8) / (0.4*0.8 + 0.9*0.8 + 0.9*0.8) = 1.04 / 1.76 = 0.59
    assert score < 0.7, "Score should be downgraded by failures"

if __name__ == "__main__":
    try:
        test_weighting()
        print("✅ Trust-Weighted Verification Tests Passed!")
    except Exception as e:
        print(f"❌ Test Failed: {e}")
        sys.exit(1)
