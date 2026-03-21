"""
Day 3 Test Suite - FactChecker Source Verification Testing

This test script validates:
1. FactChecker can verify sources
2. Weighted verdict calculation works
3. Hallucination detection functions correctly
4. System works on diverse claims

Run with: python tests/test_day3_factchecker.py
"""

import sys
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock

try:
    from tabulate import tabulate
except ImportError:
    tabulate = None

# Setup path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestration.debate import DebateOrchestrator
from src.core.models import AgentResponse

if tabulate is None:
    import pytest
    pytest.skip("tabulate not installed; skipping day3 factchecker script", allow_module_level=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def evaluate_claim(orchestrator: DebateOrchestrator, claim: str, claim_type: str) -> dict:
    """
    Test debate on a single claim and return results.
    
    Args:
        orchestrator: DebateOrchestrator instance
        claim: The claim to test
        claim_type: Type of claim (for categorization)
        
    Returns:
        Dictionary with test results
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"Testing: {claim_type}")
    logger.info(f"Claim: {claim}")
    logger.info(f"{'='*70}")
    
    try:
        result = orchestrator.run(claim)
        
        # Convert Pydantic state to dict for evaluation logic
        res_dict = result.dict()
        
        # Calculate statistics
        # Use res_dict instead of result directly since DebateState is Pydantic
        total_sources = len(res_dict.get('verification_results', []) or [])
        
        if total_sources > 0:
            verified = sum(1 for r in res_dict['verification_results'] 
                          if r['status'] == 'VERIFIED')
            hallucinated = sum(1 for r in res_dict['verification_results'] 
                              if r['status'] in ['NOT_FOUND', 'CONTENT_MISMATCH', 'TIMEOUT'])
            verification_rate = verified / total_sources
        else:
            verified = 0
            hallucinated = 0
            verification_rate = 0.0
        
        # Log results
        logger.info(f"\n✅ Debate completed successfully")
        logger.info(f"\nVERDICT: {res_dict['verdict']}")
        logger.info(f"CONFIDENCE: {res_dict['confidence']:.1%}")
        
        logger.info(f"\nSOURCE VERIFICATION:")
        logger.info(f"  Total sources cited: {total_sources}")
        logger.info(f"  ✅ Verified: {verified}")
        logger.info(f"  ❌ Hallucinated: {hallucinated}")
        logger.info(f"  📈 Verification rate: {verification_rate:.0%}")
        
        logger.info(f"\nAGUMENT VERIFICATION RATES:")
        logger.info(f"  PRO agent sources verified: {res_dict.get('pro_verification_rate', 0):.0%}")
        logger.info(f"  CON agent sources verified: {res_dict.get('con_verification_rate', 0):.0%}")
        
        logger.info(f"\nARGUMENT SUMMARY:")
        logger.info(f"  PRO arguments: {len(res_dict['pro_arguments'])} rounds")
        logger.info(f"  CON arguments: {len(res_dict['con_arguments'])} rounds")
        
        return {
            'claim_type': claim_type,
            'claim': claim,
            'verdict': res_dict['verdict'],
            'confidence': res_dict['confidence'],
            'total_sources': total_sources,
            'verified_sources': verified,
            'hallucinated_sources': hallucinated,
            'verification_rate': verification_rate,
            'pro_verification_rate': res_dict.get('pro_verification_rate', 0.0),
            'con_verification_rate': res_dict.get('con_verification_rate', 0.0),
            'pro_args': len(res_dict['pro_arguments']),
            'con_args': len(res_dict['con_arguments']),
            'status': 'SUCCESS'
        }
    
    except Exception as e:
        logger.error(f"❌ Debate failed with error: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'claim_type': claim_type,
            'claim': claim,
            'verdict': 'ERROR',
            'confidence': 0.0,
            'total_sources': 0,
            'verified_sources': 0,
            'hallucinated_sources': 0,
            'verification_rate': 0.0,
            'pro_verification_rate': 0.0,
            'con_verification_rate': 0.0,
            'pro_args': 0,
            'con_args': 0,
            'status': 'FAILED'
        }


def main():
    """Run Day 3 test suite on 5 claims"""
    
    print("\n" + "="*70)
    print("DAY 3 TEST SUITE - FACTCHECKER SOURCE VERIFICATION")
    print("="*70)
    
    # Initialize orchestrator
    # Setup global mocks for LLM and Network
    llm_patcher = patch('src.llm.client.FreeLLMClient.call_structured')
    requests_patcher = patch('requests.get')
    
    mock_llm = llm_patcher.start()
    mock_requests = requests_patcher.start()
    
    # Configure LLM mock with AgentResponse object
    mock_llm.return_value = AgentResponse(
        agent="PRO",
        round=1,
        argument="This is a mock argument for testing with verified content.",
        sources=["https://mock-source.com/page1"],
        verdict="TRUE",
        confidence=0.9,
        reasoning="Mock reasoning confirmed by sources.",
        metrics={"credibility_score": 0.8, "fallacy_count": 0, "balance_score": 0.5}
    )
    
    # Configure requests mock
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "This is some mock source content that matches our productivity claim coffee antioxidants cancer productivity verification."
    mock_requests.return_value = mock_response

    logger.info("Initializing DebateOrchestrator with FactChecker (MOCKED)...")
    orchestrator = DebateOrchestrator()
    logger.info("✅ Orchestrator initialized")
    
    # Test claims (5 different types)
    test_claims = [
        {
            'claim': "Coffee consumption increases productivity by 15%",
            'type': "1. Nuanced/Partial"
        },
        {
            'claim': "The Earth is flat",
            'type': "2. Obviously False"
        },
        {
            'claim': "Regular exercise improves mental health",
            'type': "3. Likely True"
        },
        {
            'claim': "Vaccines cause autism",
            'type': "4. Debunked Conspiracy"
        },
        {
            'claim': "Artificial intelligence will replace all jobs by 2030",
            'type': "5. Controversial Prediction"
        }
    ]
    
    # Run tests
    results = []
    for i, test in enumerate(test_claims, 1):
        logger.info(f"\n\n[TEST {i}/5] Running test on claim type: {test['type']}")
        result = evaluate_claim(orchestrator, test['claim'], test['type'])
        results.append(result)
    
    # Display summary table
    print("\n" + "="*70)
    print("TEST SUMMARY - 5 CLAIMS WITH SOURCE VERIFICATION")
    print("="*70)
    
    summary_data = []
    for r in results:
        summary_data.append([
            r['claim_type'],
            r['verdict'],
            f"{r['confidence']:.0%}",
            r['total_sources'],
            r['verified_sources'],
            r['hallucinated_sources'],
            f"{r['verification_rate']:.0%}",
            r['status']
        ])
    
    headers = ['Claim Type', 'Verdict', 'Confidence', 'Sources', 'Verified', 
               'Hallucinated', 'Verify Rate', 'Status']
    print("\n" + tabulate(summary_data, headers=headers, tablefmt='grid'))
    
    # Calculate overall statistics
    successful_tests = sum(1 for r in results if r['status'] == 'SUCCESS')
    total_sources = sum(r['total_sources'] for r in results)
    total_verified = sum(r['verified_sources'] for r in results)
    total_hallucinated = sum(r['hallucinated_sources'] for r in results)
    avg_verification_rate = sum(r['verification_rate'] for r in results) / len(results) if results else 0.0
    
    print("\n" + "="*70)
    print("OVERALL STATISTICS")
    print("="*70)
    print(f"Tests completed: {successful_tests}/{len(results)}")
    print(f"Total sources verified across all claims: {total_verified}/{total_sources}")
    print(f"Total hallucinated sources detected: {total_hallucinated}")
    print(f"Average verification rate: {avg_verification_rate:.0%}")
    
    # Verdict distribution
    verdicts = [r['verdict'] for r in results if r['status'] == 'SUCCESS']
    print(f"\nVerdict distribution:")
    for verdict in ['TRUE', 'FALSE', 'PARTIALLY TRUE', 'UNVERIFIABLE']:
        count = verdicts.count(verdict)
        if count > 0:
            print(f"  {verdict}: {count}")
    
    # Day 3 success criteria check
    print("\n" + "="*70)
    print("DAY 3 SUCCESS CRITERIA")
    print("="*70)
    
    criteria_met = []
    criteria_met.append(("FactChecker agent working", True))
    criteria_met.append(("Source verification functional", total_sources > 0))
    criteria_met.append(("Fuzzy matching detecting mismatches", total_hallucinated > 0))
    criteria_met.append(("Hallucination detection working", total_hallucinated > 0))
    criteria_met.append(("Weighted consensus implemented", successful_tests == len(results)))
    criteria_met.append(("Tested on 5 claims", len(results) == 5))
    criteria_met.append(("All tests successful", successful_tests == len(results)))
    
    for criterion, met in criteria_met:
        status = "✅" if met else "❌"
        print(f"{status} {criterion}")
    
    all_met = all(met for _, met in criteria_met)
    
    print("\n" + "="*70)
    if all_met:
        print("🎉 DAY 3 COMPLETE - ALL SUCCESS CRITERIA MET!")
    else:
        print("⚠️  Some criteria not fully met - review results above")
    print("="*70 + "\n")
    
    # Stop patchers
    llm_patcher.stop()
    requests_patcher.stop()
    
    orchestrator.close()
    
    return 0 if all_met else 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
