import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.orchestration.cache import get_cache

def generate_mock_verdict(claim: str, verdict: str, confidence: float, reasoning: str) -> dict:
    return {
        "verdict": verdict,
        "confidence": confidence,
        "pro_arguments": [f"I argue in favor of the claim: {claim}."],
        "con_arguments": [f"I argue against the claim: {claim}."],
        "pro_model_used": "cache-seeder",
        "con_model_used": "cache-seeder",
        "moderator_reasoning": reasoning,
        "pro_sources": [{"url": "http://example.com/pro", "content": "Supporting evidence."}],
        "con_sources": [{"url": "http://example.com/con", "content": "Opposing evidence."}],
        "evidence_sources": [],
        "model_stats": {"groq_calls": 0, "gemini_calls": 0, "total_calls": 0}
    }

SEEDS = [
    # Health & Science
    ("coffee prevents cancer", "PARTIALLY TRUE", 0.65, "Some studies show correlation with reduced risk for certain cancers, but evidence is mixed."),
    ("vaccines cause autism", "FALSE", 0.99, "Extensively debunked. No scientific evidence supports this claim. Originally based on a retracted fraudulent study."),
    ("earth is flat", "FALSE", 1.0, "The Earth is an oblate spheroid. This is proven by physics, satellite imagery, and centuries of observation."),
    ("exercise improves mental health", "TRUE", 0.92, "Strong clinical evidence shows regular exercise reduces symptoms of depression and anxiety."),
    ("5g causes covid", "FALSE", 1.0, "This is a baseless conspiracy theory with absolutely no scientific mechanism or evidence linking radio frequencies to a biological virus."),
    ("mobile phones cause cancer", "FALSE", 0.85, "Large-scale epidemiological studies show no convincing evidence of increased cancer risk from standard mobile phone use."),
    ("climate change is real", "TRUE", 0.98, "The scientific consensus is overwhelming that the Earth's climate is warming, primarily driven by human activities like greenhouse gas emissions."),
    ("vitamin c cures colds", "PARTIALLY TRUE", 0.45, "Vitamin C may slightly reduce the duration of a cold if taken regularly before onset, but it does not proactively cure or prevent them."),
    ("drinking water cures covid", "FALSE", 1.0, "Complete misinformation. COVID-19 requires proper medical treatment and cannot be cured by simply drinking water."),
    ("ginger cures corona", "FALSE", 0.99, "Although ginger has minor anti-inflammatory properties, there is zero clinical evidence that it cures or treats COVID-19."),
    
    # Technology & AI
    ("ai will replace all jobs by 2030", "PARTIALLY TRUE", 0.55, "While AI will profoundly transform many industries and automate certain tasks, complete job replacement by 2030 is highly unlikely based on current economic models."),
    ("windows is a linux distribution", "FALSE", 1.0, "Windows is a proprietary operating system developed by Microsoft, which uses the NT kernel, not the Linux kernel."),
    ("python is a compiled language", "PARTIALLY TRUE", 0.60, "Python code is compiled down to bytecode before execution, but it is primarily classified as an interpreted language rather than a traditionally compiled one like C or Go."),
    
    # General Knowledge & History
    ("kohinoor belongs to india", "PARTIALLY TRUE", 0.70, "The Koh-i-Noor diamond was historically mined in India and owned by various Indian dynasties. However, its current legal ownership is contested, as it was 'gifted' to the British Crown under highly coercive circumstances during the colonial era."),
    ("humans only use 10% of their brains", "FALSE", 0.99, "Neuroimaging shows that humans use virtually every part of the brain, and most parts are active almost all the time."),
    ("great wall of china is visible from space", "PARTIALLY TRUE", 0.50, "It can be seen from low Earth orbit under specific lighting conditions with a camera, but it is extremely difficult to see with the naked eye due to its narrow width and color blending with the surroundings."),
    
    # Sports & Entertainment
    ("rcb will win ipl 2026", "INSUFFICIENT EVIDENCE", 0.10, "Future sporting events cannot be factually verified. Any claim about a specific team winning a future tournament is purely speculative."),
    ("messi won the 2022 world cup", "TRUE", 1.0, "Lionel Messi captained the Argentina national football team to victory in the 2022 FIFA World Cup held in Qatar."),
    
    # Recent Events / Common Queries
    ("water boils at 100 degrees celsius", "TRUE", 0.95, "At standard atmospheric pressure at sea level, water boils at precisely 100 degrees Celsius."),
    ("gold is heavier than lead", "TRUE", 1.0, "Gold has a density of 19.3 g/cm³, whereas lead has a density of 11.3 g/cm³. Therefore, gold is much denser and heavier than lead for a given volume.")
]

def main():
    print("="*60)
    print("InsightSwarm - Semantic Cache Seeder")
    print("="*60)
    
    try:
        cache = get_cache()
        if not cache.enabled:
            print("⚠️ Semantic Cache is disabled. Skipping seeder.")
            return

        print(f"🔧 Seeding {len(SEEDS)} common claims into {cache.db_path}...")
        
        for i, (claim, verdict, conf, reason) in enumerate(SEEDS, 1):
            print(f"[{i}/{len(SEEDS)}] Encoding: '{claim}'...")
            verdict_data = generate_mock_verdict(claim, verdict, conf, reason)
            # set_verdict automatically encodes using SentenceTransformer
            cache.set_verdict(claim, verdict_data)
            
        print("\n✅ Seed complete! These queries will bypass the API entirely.")
        print("="*60)
        
    except Exception as e:
        print(f"❌ Failed to seed cache: {e}")

if __name__ == "__main__":
    main()
