#!/usr/bin/env python3
"""
main.py — All batches applied. Final production version.
"""
import sys, logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler("insightswarm.log", maxBytes=5*1024*1024, backupCount=3, encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

from src.orchestration.debate import DebateOrchestrator
from src.utils.validation import validate_claim


def print_header():
    print("\n" + "="*70)
    print(" "*20 + "InsightSwarm")
    print(" "*10 + "Multi-Agent AI Fact-Checking System")
    print("="*70)
    print("\nType 'quit' or 'exit' to stop.\n" + "="*70 + "\n")


def print_result(result) -> None:
    print("\n" + "="*70 + "\nDEBATE COMPLETE\n" + "="*70)
    verdict    = str(result.get("verdict","UNKNOWN") or "UNKNOWN")
    confidence = float(result.get("confidence", 0.0) or 0.0)
    emoji = {"TRUE":"✅","FALSE":"❌","PARTIALLY TRUE":"⚠️","INSUFFICIENT EVIDENCE":"🔍","ERROR":"💥"}.get(verdict,"⚖️")
    print(f"\n{emoji}  VERDICT:    {verdict}")
    print(f"📊 CONFIDENCE: {confidence:.1%}")
    print("\n" + "-"*70 + "\n🎓 MODERATOR ANALYSIS:\n" + "-"*70)
    reasoning = (result.get("reasoning") or result.get("moderator_reasoning") or result.get("argument") or "")
    reasoning = "" if reasoning is None else str(reasoning)
    print(f"\n{reasoning}\n" if reasoning else "\n[No moderator analysis available]\n")
    pro_sources = result.get("pro_sources") or []
    con_sources = result.get("con_sources") or []
    pro_args    = list(result.get("pro_arguments") or [])
    con_args    = list(result.get("con_arguments") or [])
    print(f"📊 Rounds: {len(pro_args)}  PRO sources: {sum(len(s) for s in pro_sources)}  CON sources: {sum(len(s) for s in con_sources)}")
    for label, args, sources in [("📘 PRO ARGUMENTS", pro_args, pro_sources),
                                   ("📕 CON ARGUMENTS", con_args, con_sources)]:
        print("\n" + "-"*70 + f"\n{label}:\n" + "-"*70)
        for i, (arg, src_list) in enumerate(zip(args, sources), 1):
            print(f"\nRound {i}:\n{str(arg) if arg is not None else ''}")
            for j, src in enumerate(src_list, 1):
                print(f"  {j}. {src}")
    print("\n" + "="*70 + "\n")


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
            print("\n\n👋 Goodbye!"); break
        if claim.lower() in ("quit","exit","q"):
            print("\n👋 Goodbye!"); break
        valid, msg = validate_claim(claim)
        if not valid:
            print(f"⚠️  {msg}\n"); continue
        print(f"\n🔍 Analysing: \"{claim}\"")
        print("⏳ Running 3-round debate (30-90 seconds)...\n")
        try:
            result = orchestrator.run(claim, num_rounds=3)
            result_dict = result.model_dump() if hasattr(result, "model_dump") else dict(result)
            print_result(result_dict)
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted.\n")
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


if __name__ == "__main__":
    main()
