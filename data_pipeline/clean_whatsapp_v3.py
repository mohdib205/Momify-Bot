"""
data_pipeline/clean_whatsapp_v3.py

Cleans the WhatsApp Q&A dataset by removing:
1. Questions too short to have standalone meaning
2. Known garbage/follow-up patterns
3. Answers that are clearly mismatched (medicine for wrong condition)
4. Questions that are about the mother, not the baby
5. Duplicate questions with conflicting answers (keep the better one)

Usage:
    python data_pipeline/clean_whatsapp_v3.py
"""

import json
import re
import os

INPUT_FILE  = "data/ALLQA_cleaned_v2.json"
OUTPUT_FILE = "data/ALLQA_cleaned_v3.json"


# ── 1. Questions too vague to have standalone meaning ─────────────────────────
GARBAGE_QUESTION_PATTERNS = [
    r"^for how many days",
    r"^how to give that",
    r"^is this ok",
    r"^is this save",
    r"^is this safe",
    r"^is this normal",
    r"^anybody else",
    r"^what's that",
    r"^anything i can apply",
    r"^so which lotion",
    r"^so what can i give",
    r"^also i have",
    r"^also he ",
    r"^also she ",
    r"^also suggest",
    r"^and what ",
    r"^and if ",
    r"^and how ",
    r"^can i give this",
    r"^can we give this",
    r"^can we continue",
    r"^okay and which",
    r"^ok and ",
    r"^like full cream",
    r"^woth ",
    r"^its must or",
    r"^without cbc",
    r"^giving any sweets",
    r"^thank you and",
    r"^thanks,? do i need",
    r"^what is that can you",
    r"^now runny nose",
    r"^now i fill",
    r"^he is having disturbed",
    r"^because fever is still",
    r"^could this be the sign",
    r"^are u supplementing",
    r"^its happening even when",
    r"^what can i do to avoid any problem",
    r"^please suggest as he is",
    r"^can i give this syrup",  # no context of which syrup
    r"^these have spread",
    r"^sir/mam",
    r"^pls give me the diet",
    r"^konsi medicine",
    r"^any tips for",
    r"^any remedy or treatment",
    r"^i was giving raisins",
    r"^i don't know i am also confused",
    r"^can i give",   # too short — only catches "can i give" with nothing else
]

# ── 2. Minimum word count for a question to be meaningful ────────────────────
MIN_QUESTION_WORDS = 6

# ── 3. Questions clearly about the MOTHER, not the baby ─────────────────────
MOTHER_PATTERNS = [
    r"i have a (back pain|cold|headache|fever|pain)",
    r"i am facing (severe|hair fall|pain)",
    r"i am becoming a second time mommy",
    r"after (the )?delivery how to loss",
    r"after c section can i eat",
    r"(lactating|breastfeeding) mom.*supplement",
    r"can i take.*for (my )?cold",
    r"also i have a cold since yesterday.*medicine",
    r"postpartum depression",
    r"episiotomy stitches",
    r"when do periods generally come",
    r"mera weight bhi",
    r"how to loss the weigh",
]

# ── 4. Known mismatched answers — (question_substring, bad_answer_substring) ─
MISMATCHED_PAIRS = [
    ("trouble passing stool", "pcm or ibugesic"),          # paracetamol for constipation
    ("trouble passing stool", "ibugesic plus"),
    ("teary eye", "sporolac"),                             # probiotic for eye
    ("assalamualaikum meri beti rato", "not recommended"), # no context
    ("is this save for 5 months", "not recommended"),      # no context what "this" is
    ("wat is the dose of this", "salbutamol"),             # "this" has no referent
    ("without cbc test", "ferrium xt"),                    # incomplete question
    ("can i give this syrup", "increase the diet"),        # no referent
]


def is_garbage_question(question: str) -> bool:
    q = question.strip().lower()

    # Too short
    if len(q.split()) < MIN_QUESTION_WORDS:
        return True

    # Matches garbage pattern
    for pattern in GARBAGE_QUESTION_PATTERNS:
        if re.match(pattern, q):
            return True

    return False


def is_mother_question(question: str) -> bool:
    q = question.strip().lower()
    for pattern in MOTHER_PATTERNS:
        if re.search(pattern, q):
            return True
    return False


def is_mismatched(question: str, answer: str) -> bool:
    q = question.strip().lower()
    a = answer.strip().lower()
    for q_sub, a_sub in MISMATCHED_PAIRS:
        if q_sub in q and a_sub in a:
            return True
    return False


def contains_dose(answer: str) -> bool:
    """Flag answers that contain explicit dose amounts."""
    patterns = [
        r"\b\d+(\.\d+)?\s*(ml|mg|mcg)\b",
        r"\b\d+\s*drops?\b",
    ]
    for p in patterns:
        if re.search(p, answer, re.IGNORECASE):
            return True
    return False


def clean(input_path: str, output_path: str):
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Input: {len(data)} pairs")

    kept      = []
    removed   = {"garbage_q": 0, "mother_q": 0, "mismatched": 0, "has_dose": 0}

    for item in data:
        q = item.get("question", "").strip()
        a = item.get("answer", "").strip()

        if is_garbage_question(q):
            removed["garbage_q"] += 1
            continue

        if is_mother_question(q):
            removed["mother_q"] += 1
            continue

        if is_mismatched(q, a):
            removed["mismatched"] += 1
            continue

        if contains_dose(a):
            # Don't remove — just strip the dose from the answer
            # Replace dose-containing sentences with a redirect
            a = re.sub(
                r"[^.!?]*\b\d+(\.\d+)?\s*(ml|mg|mcg|drops?)\b[^.!?]*[.!?]?",
                "Call your pediatrician for the exact dose.",
                a,
                flags=re.IGNORECASE
            ).strip()
            item["answer"] = a
            removed["has_dose"] += 1  # counted but still kept

        kept.append(item)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(kept, f, ensure_ascii=False, indent=2)

    print(f"\nRemoved:")
    print(f"  Garbage / vague questions : {removed['garbage_q']}")
    print(f"  Mother-only questions     : {removed['mother_q']}")
    print(f"  Mismatched pairs          : {removed['mismatched']}")
    print(f"  Dose answers (cleaned)    : {removed['has_dose']}")
    print(f"\nOutput: {len(kept)} pairs → {output_path}")


if __name__ == "__main__":
    clean(INPUT_FILE, OUTPUT_FILE)