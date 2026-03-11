#!/usr/bin/env python3
"""
InsightSwarm CLI - Interactive Multi-Agent Fact Checker

Usage:
    python main.py

Then enter claims interactively to get verdicts.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports when running directly
sys.path.insert(0, str(Path(__file__).parent))

from src.orchestration.debate import DebateOrchestrator


def print_header():
    """Print application header"""
    print("\n" + "="*70)
    print(" " * 20 + "InsightSwarm")
    print(" " * 10 + "Multi-Agent AI Fact-Checking System")
    print("="*70)
    print("\nHow it works:")
    print("  1. Enter a claim to fact-check")
    print("  2. ProAgent argues the claim is TRUE")
    print("  3. ConAgent argues the claim is FALSE")
    print("  4. They debate for 3 rounds")
    print("  5. System calculates verdict based on arguments")
    print("\nType 'quit' or 'exit' to stop.\n")
    print("="*70 + "\n")


def print_result(result):
    """
    Print debate results in formatted way
    
    Args:
        result: DebateState with verdict and arguments
    """
    print("\n" + "="*70)
    print("DEBATE COMPLETE")
    print("="*70)
    
    # Verdict
    verdict_emoji = {
        "TRUE": "✅",
        "FALSE": "❌",
        "PARTIALLY TRUE": "⚠️",
        "UNVERIFIABLE": "❓",
        "ERROR": "💥"
    }
    
    emoji = verdict_emoji.get(result['verdict'], "⚖️")
    print(f"\n{emoji}  VERDICT: {result['verdict']}")
    print(f"📊 CONFIDENCE: {result['confidence']:.1%}")
    
    # Summary stats
    total_pro_sources = sum(len(sources) for sources in result['pro_sources'])
    total_con_sources = sum(len(sources) for sources in result['con_sources'])
    
    print(f"\n📊 DEBATE STATISTICS:")
    print(f"  • Total rounds: {len(result['pro_arguments'])}")
    print(f"  • PRO sources cited: {total_pro_sources}")
    print(f"  • CON sources cited: {total_con_sources}")
    
    # Arguments
    print("\n" + "-"*70)
    print("📘 PRO ARGUMENTS (arguing claim is TRUE):")
    print("-"*70)
    
    for i, arg in enumerate(result['pro_arguments'], 1):
        print(f"\nRound {i}:")
        print(f"{arg}")
        if result['pro_sources'][i-1]:
            print(f"\nSources:")
            for j, source in enumerate(result['pro_sources'][i-1], 1):
                print(f"  {j}. {source}")
    
    print("\n" + "-"*70)
    print("📕 CON ARGUMENTS (arguing claim is FALSE):")
    print("-"*70)
    
    for i, arg in enumerate(result['con_arguments'], 1):
        print(f"\nRound {i}:")
        print(f"{arg}")
        if result['con_sources'][i-1]:
            print(f"\nSources:")
            for j, source in enumerate(result['con_sources'][i-1], 1):
                print(f"  {j}. {source}")
    
    print("\n" + "="*70 + "\n")


def main():
    """Main CLI loop"""
    
    # Print header
    print_header()
    
    # Initialize orchestrator
    print("🔧 Initializing debate system...")
    try:
        orchestrator = DebateOrchestrator()
        print("✅ System ready!\n")
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        print("\nPlease check:")
        print("  1. .env file exists with API keys")
        print("  2. All dependencies installed (pip install -r requirements.txt)")
        print("  3. Virtual environment activated")
        sys.exit(1)
    
    # Main loop
    while True:
        # Get claim from user
        try:
            claim = input("Enter claim to verify (or 'quit'): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n👋 Goodbye!")
            break
        
        # Check for exit
        if claim.lower() in ['quit', 'exit', 'q']:
            print("\n👋 Goodbye!")
            break
        
        # Validate input
        if not claim:
            print("⚠️  Please enter a claim.\n")
            continue
        
        if len(claim) < 10:
            print("⚠️  Claim too short. Please enter at least 10 characters.\n")
            continue
        
        # Run debate
        print(f"\n🔍 Analyzing: \"{claim}\"")
        print("⏳ Running 3-round debate (this takes 30-90 seconds)...")
        print("   • ProAgent arguing FOR the claim")
        print("   • ConAgent arguing AGAINST the claim")
        print("   • Computing verdict...\n")
        
        try:
            result = orchestrator.run(claim)
            print_result(result)
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Debate interrupted. Starting over...\n")
            continue
            
        except Exception as e:
            print(f"\n❌ Error during debate: {e}")
            print("Please try again or check logs.\n")
            continue


if __name__ == "__main__":
    main()