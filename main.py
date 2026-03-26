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

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(
            "insightswarm.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger(__name__)

from src.orchestration.debate import DebateOrchestrator
# B3-P8 fix: use shared validation — remove duplicate local validate_claim()
from src.utils.validation import validate_claim


def print_header():
    print("\n" + "=" * 70)
    print(" " * 20 + "InsightSwarm")
    print(" " * 10 + "Multi-Agent AI Fact-Checking System")
    print("=" * 70)
    print("\nType \'quit\' or \'exit\' to stop.\n")
    print("=" * 70 + "\n")


def print_result(result) -> None:
    """B2-P9 fix: use .get() with empty-string defaults; never print None."""
    print("\n" + "=" * 70)
    print("DEBATE COMPLETE")
    print("=" * 70)

    verdict    = str(result.get("verdict", "UNKNOWN") or "UNKNOWN")
    confidence = float(result.get("confidence", 0.0) or 0.0)

    emoji_map = {
        "TRUE":                  "✅",
        "FALSE":                 "❌",
        "PARTIALLY TRUE":        "⚠️",
        "INSUFFICIENT EVIDENCE": "🔍",
        "UNVERIFIABLE":          "❓",
        "ERROR":                 "💥",
    }
    emoji = emoji_map.get(verdict, "⚖️")
    print(f"\n{emoji}  VERDICT:    {verdict}")
    print(f"📊 CONFIDENCE: {confidence:.1%}")

    print("\n" + "-" * 70)
    print("🎓 MODERATOR ANALYSIS:")
    print("-" * 70)
    reasoning = (result.get("reasoning") or result.get("moderator_reasoning")
                 or result.get("argument") or "")
    reasoning = "" if reasoning is None else str(reasoning)
    print(f"\n{reasoning}\n" if reasoning else "\n[No moderator analysis available]\n")

    pro_sources = result.get("pro_sources") or []
    con_sources = result.get("con_sources") or []
    total_pro   = sum(len(s) for s in pro_sources)
    total_con   = sum(len(s) for s in con_sources)
    pro_args    = list(result.get("pro_arguments") or [])
    con_args    = list(result.get("con_arguments") or [])
    print(f"📊 Rounds: {len(pro_args)}  PRO sources: {total_pro}  CON sources: {total_con}")

    for label, args, sources in [
        ("📘 PRO ARGUMENTS", pro_args, pro_sources),
        ("📕 CON ARGUMENTS", con_args, con_sources),
    ]:
        print("\n" + "-" * 70)
        print(f"{label}:")
        print("-" * 70)
        for i, (arg, src_list) in enumerate(zip(args, sources), 1):
            arg_str = str(arg) if arg is not None else ""
            print(f"\nRound {i}:\n{arg_str}")
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
            claim = input("Enter claim to verify (or \'quit\'): ").strip()
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
