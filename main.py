#!/usr/bin/env python3
"""
InsightSwarm CLI — Interactive Multi-Agent Fact Checker

Usage:
    python main.py
"""

import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Tuple

sys.path.insert(0, str(Path(__file__).parent))

# Rotating log handler — prevents insightswarm.log growing unboundedly in production.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(
            "insightswarm.log",
            maxBytes=5 * 1024 * 1024,   # 5 MB per file
            backupCount=3,               # keep 3 rotated backups
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger(__name__)

from src.orchestration.debate import DebateOrchestrator


def validate_claim(claim: str) -> Tuple[bool, str]:
    """Validate a user-submitted claim for safety and quality."""
    if not claim or not claim.strip():
        return False, "Claim cannot be empty."

    if len(claim) > 500:
        return False, "Claim too long (max 500 characters)."

    if len(claim.split()) < 3:
        return False, "Claim too short (minimum 3 words)."

    import re
    injection_patterns = [
        r"ignore\s+previous\s+instructions",
        r"ignore\s+all\s+previous",
        r"disregard\s+all\s+previous",
        r"\bsystem\s*:\s*",
    ]
    for pattern in injection_patterns:
        if re.search(pattern, claim.lower()):
            return False, "Prompt injection detected."

    return True, ""


def print_header():
    print("\n" + "=" * 70)
    print(" " * 20 + "InsightSwarm")
    print(" " * 10 + "Multi-Agent AI Fact-Checking System")
    print("=" * 70)
    print("\nType 'quit' or 'exit' to stop.\n")
    print("=" * 70 + "\n")


def print_result(result):
    print("\n" + "=" * 70)
    print("DEBATE COMPLETE")
    print("=" * 70)

    emoji_map = {
        "TRUE": "✅", "FALSE": "❌",
        "PARTIALLY TRUE": "⚠️", "INSUFFICIENT EVIDENCE": "🔍",
        "UNVERIFIABLE": "❓", "ERROR": "💥",
    }
    emoji = emoji_map.get(result["verdict"], "⚖️")
    print(f"\n{emoji}  VERDICT:    {result['verdict']}")
    print(f"📊 CONFIDENCE: {result['confidence']:.1%}")

    print("\n" + "-" * 70)
    print("🎓 MODERATOR ANALYSIS:")
    print("-" * 70)
    print(f"\n{result.get('moderator_reasoning', '')}\n")

    total_pro = sum(len(s) for s in result["pro_sources"])
    total_con = sum(len(s) for s in result["con_sources"])
    print(f"📊 Rounds: {len(result['pro_arguments'])}  "
          f"PRO sources: {total_pro}  CON sources: {total_con}")

    for label, args, sources in [
        ("📘 PRO ARGUMENTS", result["pro_arguments"], result["pro_sources"]),
        ("📕 CON ARGUMENTS", result["con_arguments"], result["con_sources"]),
    ]:
        print("\n" + "-" * 70)
        print(f"{label}:")
        print("-" * 70)
        for i, (arg, src_list) in enumerate(zip(args, sources), 1):
            print(f"\nRound {i}:\n{arg}")
            for j, src in enumerate(src_list, 1):
                print(f"  {j}. {src}")

    print("\n" + "=" * 70 + "\n")


def main():
    print_header()
    print("🔧 Initialising debate system...")
    try:
        orchestrator = DebateOrchestrator()
        print("✅ System ready!\n")
    except Exception as e:
        print(f"❌ Failed to initialise: {e}")
        sys.exit(1)

    while True:
        try:
            claim = input("Enter claim to verify (or 'quit'): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n👋 Goodbye!")
            break

        if claim.lower() in ("quit", "exit", "q"):
            print("\n👋 Goodbye!")
            break

        valid, msg = validate_claim(claim)
        if not valid:
            print(f"⚠️  {msg}\n")
            continue

        print(f"\n🔍 Analysing: \"{claim}\"")
        print("⏳ Running 3-round debate (30-90 seconds)...\n")

        try:
            result = orchestrator.run(claim)
            print_result(result)
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted.\n")
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


if __name__ == "__main__":
    main()
