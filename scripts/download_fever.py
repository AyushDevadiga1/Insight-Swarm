"""
scripts/download_fever.py
=========================
Downloads a balanced 200-claim sample from the FEVER dataset via HuggingFace
datasets and saves it as data/fever_sample.json.

Usage:
    python scripts/download_fever.py
    python scripts/download_fever.py --n 100 --output data/fever_small.json

Requires:
    pip install datasets  (already in requirements.txt after this update)

FEVER label map:
    SUPPORTS  → claim is TRUE according to Wikipedia
    REFUTES   → claim is FALSE
    NOT ENOUGH INFO → claim cannot be verified from Wikipedia alone

We sample equal portions of SUPPORTS and REFUTES for a balanced binary
classification problem. NOT ENOUGH INFO claims are included only when
--include_nei flag is passed (useful for ablation).
"""

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

def download_fever(n: int = 200, output: Path = None, include_nei: bool = False, seed: int = 42):
    try:
        from datasets import load_dataset
    except ImportError:
        print("ERROR: 'datasets' package not installed.")
        print("Run: pip install datasets")
        sys.exit(1)

    print(f"Downloading FEVER dataset from HuggingFace...")
    try:
        ds = load_dataset("fever", "v1.0", split="paper_dev", trust_remote_code=True)
    except Exception:
        # Fallback: try the simpler split name
        try:
            ds = load_dataset("fever", "v1.0", split="validation", trust_remote_code=True)
        except Exception as e:
            print(f"ERROR: Could not load FEVER dataset: {e}")
            print("Trying alternative: nyu-mll/fever ...")
            try:
                ds = load_dataset("nyu-mll/fever", split="validation", trust_remote_code=True)
            except Exception as e2:
                print(f"ERROR: All FEVER sources failed: {e2}")
                _create_curated_fallback(output or ROOT / "data" / "fever_sample.json", n)
                return

    random.seed(seed)

    # Filter by label
    supports = [r for r in ds if r.get("label") == "SUPPORTS"]
    refutes  = [r for r in ds if r.get("label") == "REFUTES"]
    nei      = [r for r in ds if r.get("label") == "NOT ENOUGH INFO"]

    print(f"Raw: SUPPORTS={len(supports)}, REFUTES={len(refutes)}, NEI={len(nei)}")

    half = n // 2
    sample_supports = random.sample(supports, min(half, len(supports)))
    sample_refutes  = random.sample(refutes,  min(half, len(refutes)))
    sample = sample_supports + sample_refutes

    if include_nei:
        nei_n = n // 5  # 20% NEI
        sample += random.sample(nei, min(nei_n, len(nei)))

    random.shuffle(sample)

    # Normalise into clean dict
    clean = []
    for row in sample:
        claim = row.get("claim") or row.get("input") or ""
        label = row.get("label") or ""
        clean.append({
            "claim":       claim,
            "fever_label": label,
            # Map to InsightSwarm verdict space
            "expected_verdict": "TRUE"  if label == "SUPPORTS"
                          else "FALSE" if label == "REFUTES"
                          else "INSUFFICIENT EVIDENCE",
            "evidence": row.get("evidence_sentences", []),
        })

    out_path = output or ROOT / "data" / "fever_sample.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(clean)} claims → {out_path}")
    label_counts = {}
    for item in clean:
        label_counts[item["fever_label"]] = label_counts.get(item["fever_label"], 0) + 1
    for label, count in label_counts.items():
        print(f"  {label}: {count}")


def _create_curated_fallback(output: Path, n: int):
    """
    If HuggingFace is unreachable, create a hand-curated 50-claim sample
    with known ground-truth labels for offline testing.
    """
    print("\nCreating curated fallback dataset (50 claims, known labels)...")

    CURATED = [
        # SUPPORTS (TRUE)
        {"claim": "The Eiffel Tower is located in Paris.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE"},
        {"claim": "Albert Einstein was born in Germany.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE"},
        {"claim": "The Great Wall of China was built over many centuries.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE"},
        {"claim": "William Shakespeare wrote Hamlet.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE"},
        {"claim": "The human body has 206 bones in adults.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE"},
        {"claim": "The Amazon River is the largest river by discharge volume.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE"},
        {"claim": "Neil Armstrong was the first human to walk on the Moon.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE"},
        {"claim": "DNA carries genetic information in living organisms.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE"},
        {"claim": "The speed of light in a vacuum is approximately 299,792 km/s.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE"},
        {"claim": "Mount Everest is the highest mountain above sea level.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE"},
        {"claim": "Photosynthesis is the process by which plants make food from sunlight.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE"},
        {"claim": "The Cold War ended in 1991.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE"},
        {"claim": "Leonardo da Vinci painted the Mona Lisa.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE"},
        {"claim": "The periodic table was developed by Dmitri Mendeleev.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE"},
        {"claim": "Penicillin was discovered by Alexander Fleming.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE"},
        {"claim": "The human heart has four chambers.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE"},
        {"claim": "The Pacific Ocean is the largest ocean on Earth.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE"},
        {"claim": "Charles Darwin proposed the theory of evolution by natural selection.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE"},
        {"claim": "The Berlin Wall fell in 1989.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE"},
        {"claim": "Oxygen makes up approximately 21% of Earth's atmosphere.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE"},
        {"claim": "J.K. Rowling is the author of the Harry Potter series.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE"},
        {"claim": "The Olympic Games originated in ancient Greece.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE"},
        {"claim": "Water boils at 100 degrees Celsius at sea level.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE"},
        {"claim": "Abraham Lincoln was the 16th President of the United States.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE"},
        {"claim": "The human brain contains approximately 86 billion neurons.", "fever_label": "SUPPORTS", "expected_verdict": "TRUE"},
        # REFUTES (FALSE)
        {"claim": "The Eiffel Tower is located in London.", "fever_label": "REFUTES", "expected_verdict": "FALSE"},
        {"claim": "Albert Einstein was born in France.", "fever_label": "REFUTES", "expected_verdict": "FALSE"},
        {"claim": "The Great Wall of China was built in a single dynasty.", "fever_label": "REFUTES", "expected_verdict": "FALSE"},
        {"claim": "Isaac Newton wrote Hamlet.", "fever_label": "REFUTES", "expected_verdict": "FALSE"},
        {"claim": "The human body has 100 bones in adults.", "fever_label": "REFUTES", "expected_verdict": "FALSE"},
        {"claim": "The Nile River is the largest river by discharge volume.", "fever_label": "REFUTES", "expected_verdict": "FALSE"},
        {"claim": "Buzz Aldrin was the first human to walk on the Moon.", "fever_label": "REFUTES", "expected_verdict": "FALSE"},
        {"claim": "RNA is the primary carrier of genetic information in all organisms.", "fever_label": "REFUTES", "expected_verdict": "FALSE"},
        {"claim": "The speed of light is approximately 100,000 km/s.", "fever_label": "REFUTES", "expected_verdict": "FALSE"},
        {"claim": "K2 is the highest mountain above sea level.", "fever_label": "REFUTES", "expected_verdict": "FALSE"},
        {"claim": "Photosynthesis is the process by which animals digest food.", "fever_label": "REFUTES", "expected_verdict": "FALSE"},
        {"claim": "The Cold War ended in 1945.", "fever_label": "REFUTES", "expected_verdict": "FALSE"},
        {"claim": "Michelangelo painted the Mona Lisa.", "fever_label": "REFUTES", "expected_verdict": "FALSE"},
        {"claim": "The periodic table was developed by Marie Curie.", "fever_label": "REFUTES", "expected_verdict": "FALSE"},
        {"claim": "Penicillin was discovered by Louis Pasteur.", "fever_label": "REFUTES", "expected_verdict": "FALSE"},
        {"claim": "The human heart has two chambers.", "fever_label": "REFUTES", "expected_verdict": "FALSE"},
        {"claim": "The Atlantic Ocean is the largest ocean on Earth.", "fever_label": "REFUTES", "expected_verdict": "FALSE"},
        {"claim": "Gregor Mendel proposed the theory of evolution by natural selection.", "fever_label": "REFUTES", "expected_verdict": "FALSE"},
        {"claim": "The Berlin Wall fell in 1979.", "fever_label": "REFUTES", "expected_verdict": "FALSE"},
        {"claim": "Nitrogen makes up approximately 21% of Earth's atmosphere.", "fever_label": "REFUTES", "expected_verdict": "FALSE"},
        {"claim": "Stephen King is the author of the Harry Potter series.", "fever_label": "REFUTES", "expected_verdict": "FALSE"},
        {"claim": "The Olympic Games originated in ancient Rome.", "fever_label": "REFUTES", "expected_verdict": "FALSE"},
        {"claim": "Water boils at 50 degrees Celsius at sea level.", "fever_label": "REFUTES", "expected_verdict": "FALSE"},
        {"claim": "Abraham Lincoln was the 10th President of the United States.", "fever_label": "REFUTES", "expected_verdict": "FALSE"},
        {"claim": "The human brain contains approximately 10 billion neurons.", "fever_label": "REFUTES", "expected_verdict": "FALSE"},
    ]

    import random
    random.shuffle(CURATED)
    sample = CURATED[:min(n, len(CURATED))]
    for item in sample:
        item["evidence"] = []

    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(sample, f, indent=2)

    print(f"Curated fallback saved: {len(sample)} claims → {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download FEVER benchmark sample")
    parser.add_argument("--n", type=int, default=200, help="Total claims to sample (default: 200)")
    parser.add_argument("--output", type=str, default=None, help="Output JSON path")
    parser.add_argument("--include_nei", action="store_true", help="Include NOT ENOUGH INFO claims")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    out = Path(args.output) if args.output else None
    download_fever(n=args.n, output=out, include_nei=args.include_nei, seed=args.seed)
