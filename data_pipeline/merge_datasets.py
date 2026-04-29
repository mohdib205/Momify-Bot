"""
BabyDoc Dataset Merge
----------------------
Merges two datasets:
  1. ALLQA_cleaned.json        — original WhatsApp Q&A (Indian, verified)
  2. babydoc_dataset_final.json — cleaned HealthCareMagic (doctor tone, English)

Strategy:
  - Original WhatsApp data kept as-is (already Indian, high quality)
  - HealthCareMagic data adds volume and doctor-like tone
  - Duplicates removed by semantic similarity on question text
  - Original data takes priority over HealthCareMagic on conflicts

Usage:
    python data_pipeline/merge_datasets.py

Output:
    data/babydoc_merged.json
    data/merge_report.txt
"""

import json
import os
import re
from tqdm import tqdm

ORIGINAL_FILE    = os.path.join("data", "ALLQA_cleaned.json")
HEALTHCARE_FILE  = os.path.join("data", "babydoc_dataset_final.json")
OUTPUT_FILE      = os.path.join("data", "babydoc_merged.json")
REPORT_FILE      = os.path.join("data", "merge_report.txt")
os.makedirs("data", exist_ok=True)


# ── Normalize question for dedup comparison ──
def normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)   # remove punctuation
    text = re.sub(r"\s+", " ", text)       # normalize spaces
    return text


# ── Tokenize for Jaccard similarity ──
def tokenize(text: str) -> set:
    return set(normalize(text).split())


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ── Check if a question is too similar to any existing question ──
def is_duplicate(question: str, existing_tokens: list[set], threshold: float = 0.75) -> bool:
    q_tokens = tokenize(question)
    for tokens in existing_tokens:
        if jaccard(q_tokens, tokens) >= threshold:
            return True
    return False


def main():
    # ── Load original WhatsApp data ──
    print(f"Loading original WhatsApp data from {ORIGINAL_FILE}...")
    with open(ORIGINAL_FILE, "r", encoding="utf-8") as f:
        original_data = json.load(f)
    print(f"Original records: {len(original_data)}")

    # ── Load HealthCareMagic data ──
    print(f"\nLoading HealthCareMagic data from {HEALTHCARE_FILE}...")
    with open(HEALTHCARE_FILE, "r", encoding="utf-8") as f:
        hcm_data = json.load(f)
    print(f"HealthCareMagic records: {len(hcm_data)}")

    # ── Normalize original data format ──
    # Original has: {"question": ..., "answer": ...}
    # HealthCareMagic has: {"question": ..., "answer": ...} (after cleaning)
    merged   = []
    seen_tokens = []

    # Step 1 — Add all original WhatsApp data first (priority)
    print("\nAdding original WhatsApp data (priority)...")
    skipped_original = 0
    for r in tqdm(original_data):
        q = r.get("question", "").strip()
        a = r.get("answer",   "").strip()

        if not q or not a:
            skipped_original += 1
            continue
        if a.lower() in ["no specific answer found", "no specific answer", ""]:
            skipped_original += 1
            continue

        merged.append({
            "question": q,
            "answer":   a,
            "source":   "whatsapp"
        })
        seen_tokens.append(tokenize(q))

    print(f"Added {len(merged)} original records (skipped {skipped_original} incomplete)")

    # Step 2 — Add HealthCareMagic data, skip duplicates
    print("\nAdding HealthCareMagic data (skipping duplicates)...")
    added_hcm   = 0
    skipped_dup = 0
    skipped_quality = 0

    for r in tqdm(hcm_data):
        q = r.get("question", "").strip()
        a = r.get("answer",   "").strip()

        if not q or not a:
            skipped_quality += 1
            continue

        # Skip if too similar to existing question
        if is_duplicate(q, seen_tokens, threshold=0.75):
            skipped_dup += 1
            continue

        merged.append({
            "question": q,
            "answer":   a,
            "source":   "healthcaremagic"
        })
        seen_tokens.append(tokenize(q))
        added_hcm += 1

    print(f"Added {added_hcm} HealthCareMagic records")
    print(f"Skipped {skipped_dup} duplicates")
    print(f"Skipped {skipped_quality} low quality")
    print(f"\nTotal merged records: {len(merged)}")

    # ── Save ──
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(f"Saved → {OUTPUT_FILE}")

    # ── Report ──
    whatsapp_count = sum(1 for r in merged if r["source"] == "whatsapp")
    hcm_count      = sum(1 for r in merged if r["source"] == "healthcaremagic")

    report = f"""
BabyDoc Dataset Merge Report
==============================
Original WhatsApp records   : {len(original_data)}
HealthCareMagic records     : {len(hcm_data)}

After merge:
  From WhatsApp             : {whatsapp_count}
  From HealthCareMagic      : {hcm_count}
  Total                     : {len(merged)}

Skipped:
  Incomplete original       : {skipped_original}
  Duplicates (HCM)          : {skipped_dup}
  Low quality (HCM)         : {skipped_quality}

Output: {OUTPUT_FILE}

Note:
  WhatsApp data = Indian medicines, Hinglish, verified by doctors
  HealthCareMagic = Doctor-like tone, detailed English answers
  Combined = best of both worlds
"""
    print(report)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report → {REPORT_FILE}")


if __name__ == "__main__":
    main()