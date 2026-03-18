import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.orchestration.cache import get_cache


def generate_mock_verdict(claim: str, verdict: str, confidence: float, reasoning: str) -> dict:
    # pro_sources / con_sources must be List[List[str]] to match DebateState schema.
    # A single round with one URL each is enough for the seed.
    return {
        "verdict":            verdict,
        "confidence":         confidence,
        "pro_arguments":      [f"I argue in favor of the claim: {claim}."],
        "con_arguments":      [f"I argue against the claim: {claim}."],
        "pro_model_used":     "cache-seeder",
        "con_model_used":     "cache-seeder",
        "moderator_reasoning": reasoning,
        "pro_sources":        [["http://example.com/pro"]],   # List[List[str]] ✓
        "con_sources":        [["http://example.com/con"]],   # List[List[str]] ✓
        "evidence_sources":   [],
        "pro_verification_rate": 0.0,
        "con_verification_rate": 0.0,
        "verification_results":  [],
    }


SEEDS = [
    # Health & Science
    ("coffee prevents cancer",         "PARTIALLY TRUE", 0.65,
     "Some studies show correlation with reduced risk for certain cancers, but evidence is mixed."),
    ("vaccines cause autism",          "FALSE",          0.99,
     "Extensively debunked. No scientific evidence supports this claim."),
    ("earth is flat",                  "FALSE",          1.0,
     "The Earth is an oblate spheroid — proven by physics, satellite imagery, and centuries of observation."),
    ("exercise improves mental health","TRUE",           0.92,
     "Strong clinical evidence shows regular exercise reduces symptoms of depression and anxiety."),
    ("5g causes covid",                "FALSE",          1.0,
     "Baseless conspiracy theory with no scientific mechanism linking radio frequencies to a biological virus."),
    ("mobile phones cause cancer",     "FALSE",          0.85,
     "Large-scale epidemiological studies show no convincing evidence of increased cancer risk."),
    ("climate change is real",         "TRUE",           0.98,
     "Scientific consensus is overwhelming that the Earth's climate is warming, driven by human activity."),
    ("vitamin c cures colds",          "PARTIALLY TRUE", 0.45,
     "Vitamin C may slightly reduce cold duration if taken regularly, but does not cure or prevent them."),
    ("drinking water cures covid",     "FALSE",          1.0,
     "Complete misinformation. COVID-19 requires proper medical treatment."),
    ("ginger cures corona",            "FALSE",          0.99,
     "No clinical evidence that ginger cures or treats COVID-19."),

    # Technology & AI
    ("ai will replace all jobs by 2030","PARTIALLY TRUE",0.55,
     "AI will transform many industries, but complete job replacement by 2030 is unlikely."),
    ("windows is a linux distribution","FALSE",          1.0,
     "Windows uses the NT kernel, not the Linux kernel."),
    ("python is a compiled language",  "PARTIALLY TRUE", 0.60,
     "Python compiles to bytecode but is classified as an interpreted language."),

    # General Knowledge
    ("kohinoor belongs to india",      "PARTIALLY TRUE", 0.70,
     "Historically mined in India; current legal ownership is contested."),
    ("humans only use 10% of their brains","FALSE",      0.99,
     "Neuroimaging shows virtually all brain regions are active most of the time."),
    ("great wall of china is visible from space","PARTIALLY TRUE",0.50,
     "Visible from low Earth orbit with a camera under specific conditions; not with the naked eye."),

    # Sports & Entertainment
    ("rcb will win ipl 2026",          "INSUFFICIENT EVIDENCE", 0.10,
     "Future sporting events cannot be factually verified."),
    ("messi won the 2022 world cup",   "TRUE",           1.0,
     "Lionel Messi captained Argentina to victory in the 2022 FIFA World Cup."),

    # Science facts
    ("water boils at 100 degrees celsius","TRUE",        0.95,
     "At standard atmospheric pressure water boils at exactly 100 °C."),
    ("gold is heavier than lead",      "TRUE",           1.0,
     "Gold density 19.3 g/cm³ vs lead 11.3 g/cm³ — gold is denser."),
]


def main():
    print("=" * 60)
    print("InsightSwarm — Semantic Cache Seeder")
    print("=" * 60)

    try:
        cache = get_cache()
        if not cache.enabled:
            print("⚠️  Semantic cache disabled — skipping seeder.")
            return

        print(f"🔧  Seeding {len(SEEDS)} claims into {cache.db_path} ...")

        for i, (claim, verdict, conf, reason) in enumerate(SEEDS, 1):
            print(f"[{i:02d}/{len(SEEDS)}] {claim!r}")
            cache.set_verdict(claim, generate_mock_verdict(claim, verdict, conf, reason))

        print(f"\n✅  Seeded {len(SEEDS)} claims.  These will bypass the API entirely.")
        print("=" * 60)

    except Exception as e:
        print(f"❌  Seeder failed: {e}")


if __name__ == "__main__":
    main()
