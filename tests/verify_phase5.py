import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.trust_scorer import TrustScorer
from src.utils.claim_decomposer import ClaimDecomposer
from src.utils.summarizer import Summarizer
from src.llm.client import FreeLLMClient
from src.core.models import DebateState

def test_trust_scorer():
    print("\n--- Testing TrustScorer ---")
    urls = [
        "https://www.who.int/news/item",
        "https://www.nytimes.com/latest",
        "https://www.dailymail.co.uk/news",
        "https://myblog.com/post",
        "https://twitter.com/user/123"
    ]
    for url in urls:
        score = TrustScorer.get_score(url)
        label = TrustScorer.get_tier_label(score)
        print(f"URL: {url} -> Score: {score}, Tier: {label}")

def test_claim_decomposer():
    print("\n--- Testing ClaimDecomposer ---")
    client = FreeLLMClient()
    decomposer = ClaimDecomposer(client)
    complex_claim = "Climate change is real and it is caused by human activity, although some natural factors play a minor role."
    parts = decomposer.decompose(complex_claim)
    print(f"Original: {complex_claim}")
    print(f"Decomposed: {parts}")

def test_summarizer():
    print("\n--- Testing Summarizer ---")
    client = FreeLLMClient()
    summarizer = Summarizer(client)
    state = DebateState(
        claim="Is AI a threat?",
        round=3,
        pro_arguments=["AI can automate jobs leading to economic collapse.", "Autonomous weapons could start wars."],
        con_arguments=["AI can solve complex problems like climate change.", "AI will create new types of jobs and boost productivity."]
    )
    summary = summarizer.summarize_history(state)
    print(f"Summary: {summary}")

if __name__ == "__main__":
    test_trust_scorer()
    # Skip LLM calls in CI-like test if no keys, but here we can try
    try:
        test_claim_decomposer()
        test_summarizer()
    except Exception as e:
        print(f"LLM Tests skipped or failed: {e}")
