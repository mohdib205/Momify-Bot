"""
WhatsApp Dataset Cleaner v2
-----------------------------
Removes bad Q&A pairs from ALLQA_cleaned.json:
  1. Platform artifacts (@MoMify, image omitted etc.)
  2. Useless answers (phone numbers, redirects, "no specific answer")
  3. Vague context-only questions
  4. Dangerous wrong answers
  5. Answers that are questions back (doctor asking for more info)
  6. Answers referencing media not present (video, photo, image)

Usage:
    python data_pipeline/clean_whatsapp.py

Input:  data/ALLQA_cleaned.json
Output: data/ALLQA_cleaned_v2.json
        data/whatsapp_cleaning_report.txt
"""

import json
import re
import os

INPUT_FILE  = os.path.join("data", "ALLQA_cleaned.json")
OUTPUT_FILE = os.path.join("data", "ALLQA_cleaned_v2.json")
REPORT_FILE = os.path.join("data", "whatsapp_cleaning_report.txt")


# ══════════════════════════════════════════════════════
# Rule 1 — Platform artifacts
# ══════════════════════════════════════════════════════
PLATFORM_ARTIFACTS = [
    "momify:", "mf plus", "mf basic", "mf pluss",
    "image omitted", "video omitted", "document omitted",
    "pdf omitted", "‎image", "‎video",
    "@⁨momify⁩", "@momify",
]


def has_platform_artifacts(q: str, a: str) -> bool:
    combined = (q + " " + a).lower()
    return any(art in combined for art in PLATFORM_ARTIFACTS)


# ══════════════════════════════════════════════════════
# Rule 2 — Useless answers
# ══════════════════════════════════════════════════════
USELESS_ANSWER_PATTERNS = [
    "check the plus group please",
    "please ask on paed group",
    "please tell such queries on other baby care group",
    "search for it on insta or youtube",
    "ill try to make one today",
    "ill share a detailed pdf",
    "will do a session on the topic soon",
    "were working on e books and website",
    "sure call at",
    "no specific answer found",
    "kids diet chart",
    "6-12 months .pdf",
    "document omitted",
    "image omitted",
    "video omitted",
]


def is_useless_answer(answer: str) -> bool:
    a = answer.lower().strip()
    if any(p in a for p in USELESS_ANSWER_PATTERNS):
        return True
    if re.search(r"\b\d{10}\b", answer):   # phone number
        return True
    if len(answer.strip()) < 8:
        return True
    return False


# ══════════════════════════════════════════════════════
# Rule 3 — Answers that are questions back (no info value)
# ══════════════════════════════════════════════════════
ANSWER_IS_QUESTION_PAIRS = [
    # (question_substring, answer_substring)
    ("meri baby bahut dubali hai",         "birth weight and weight now"),
    ("hi dr.. meri baby 20 days",          "peeing normal? any cranky behaviour"),
    ("6.5 month old has not done potty",   "how many times does the baby have solids"),
    ("i'm a bit worried about my daughter. for the past few days she is barely eating",
                                           "can u send photos of the conjunctiva"),
    ("baby ko teething n fever hai",       "check fever and update"),
    ("i don't know i am also confused",    "get a stool rm done"),
]


def is_answer_a_question(q: str, a: str) -> bool:
    q_l = q.lower()
    a_l = a.lower()
    for qp, ap in ANSWER_IS_QUESTION_PAIRS:
        if qp in q_l and ap in a_l:
            return True
    return False


# ══════════════════════════════════════════════════════
# Rule 4 — Answers referencing absent media
# ══════════════════════════════════════════════════════
MEDIA_REFERENCE_PATTERNS = [
    "in this video",
    "as seen in the video",
    "from the image",
    "in the picture",
    "send a video",
    "send photos",
    "no sound of breathing only external noise",
]


def references_absent_media(answer: str) -> bool:
    a = answer.lower()
    return any(p in a for p in MEDIA_REFERENCE_PATTERNS)


# ══════════════════════════════════════════════════════
# Rule 5 — Vague follow-up questions with no standalone context
# ══════════════════════════════════════════════════════
VAGUE_QUESTION_PATTERNS = [
    "check the plus group",
    "please ask on paed group",
    "i used it not working",
    "powdee with milk? or water",
    "tablets come in 1000mg is that okay",
    "please suggest any brand or capsule names",
    "ok which company is best",
    "illness in the sense",
    "without fever or symptom can viral still be there",
    "for how long this behaviour persists",
    "how much peanut butter to give",
    "age and diet ?",
    "fibre me kya khilau",
    "what needs to be applied on it",
    "from what age should we give this",
    "ok and what else i can give to baby like in food",
    "since how many days the baby is having this",
    "age and weight and any fever",
    "hows the heat and humidity",
    "could it be due to hot water bath",
    "how many days ?",
    "like without putting the ear over the tummy",
    "when she poops is that hard or normal without any distress",
    "are you giving fibre and enough water to the baby with solifs",
    "ok cauliflower cabbage are gaseous i believe",
    "do we have any chart or pattern of food we should give",
    "like in food or meds ??",
    "is this normal? medications incase if this recurring",
    "for how many days should i give these medicines",
    "any tym urine sample can be given",
    "is there any other test also we should get done",
    "normally means the frequency of peeing",
    "whats the weight of the baby",
    "can u plz give me some examples",
    "what was the bw of the baby",
    "are u nebulising the kid ? once or twice",
    "baby active or lethargic",
    "anybody else has this in house",
    "check and tell if reappeared",
    "cough with mucous ? and also are you giving nasal saline",
    "ok should i use it or not",
    "is there another option besides lemon",
    "could this be reduced due to sweating",
    "since 7 am there is no pee",
    "peeing normal ? age rn and food",
    "any symptoms you are seeing",
    "making sound while putting pressure",
    "sikayi and burp not helping , still colic",
    "doing it so far not helping",
    "only during night does he vomit ? or during day too",
    "it is of green color and liquid , pls tell is this normal",
    "white part look slightly red",
    "is this something to be concerned about",
    "is this an emergency to visit? should i go today",
    "what could be the cause for this",
    "none of these are useful??",
    "since how many days the baby didnt poop",
    "when are you planning to do the same",
    "i don't know i am also confused",
    "after that stool were normal",
    "twice a day or once?",
    "one more thing i have taken citrazine tablet",
    "ok any other home available item i can use",
    "2500 kg hui thi abhi 2800 hui hai",
    "minor pain is there",
    "shall i overnight soak it",
    "ok, but 24 hr ma maybe formula feed",
    "ok but he is she is not eating while we forced to eat",
    "esa kyun ho rah hai dr",
    "please share guidance around weaning",
    "hi, which baby milk formula is best for newborns",
    "what can i offer",
    "can i give this to my 2.5 yr old as she is eating walls and mud",
    "please suggest what to give in diet also",
    "that time it reduced but now again the temperature is 99.9",
    "this appeared on his skin..suddenly",
    "but i am seeing around 9 since one month",
    "but before feed or after..",
    "2 times a day?",
    "also can you tell what spices can i introduce him now",
    "also, can i now introduce pancake/chilla to him",
    "what could be the possible reason doc , so that i can be careful",
    "hi the doc is on leave today, clinic is closed",
    "and what to apply on this?",
    "and what to do for runny nose?",
    "is this normal breathing? please tell",
    "what's that can you elaborate. is this concerning",
    "okay and is it normal if baby is peeing 2-3 times a day",
    "what symptoms needs to be observed",
    "she rejects water hardly takes 50-60 ml",
    "she is crying and refusing food not interested in eating",
    "after how much time after i can feed her",
    "could you please suggest any best brands",
    "after medication the hives faded but since evening",
    "these marks suddenly appeared on face of baby",
    "these still keep appearing but now they just appear",
    "how about when adding the powder to gravies",
    "i heard that hing weakens the bones",
    "what can be done to stop the reaction",
    "is it mosquito bite?",
    "baby ko ratme kela khilane se cough hota hai",
    "anyone else have this in house??",
    "hi , how long do i continue vitamin d",
    "i rubbed ice and wiped with water",
    "kya usko hum pila sakte hain",
    "should i give colicaid as well",
    "dr. which one should i use ?",
    "can we give kishmish to 6 months old if constipated",
    "can i give dates milk in cold n cough to baby",
    "sir/mam, will this bump subside on its own",
    "n in semi solids what should i give",
    "and what to apply on this",
    "which one i should prefer",
    "pee count is normal, also is sporolac for baby different",
    "he also has runny nose any medicine for that",
    "doc my baby is 8 mn 4 days",           # incomplete question
    "my baby is 9.5 months old.",            # incomplete question
    "my lo is 9 mn 26 days",                 # incomplete
    "ok should i use it or not",
    "is there any other test also",
    "now he did little bit black colour so is it normal",
    "fever is not down. when can i repeat the dose",
    "anything which i can give to her ,food",
    "i want to avoid milk anything apart from milk",
    "can this be due to viral cough too",
    "possible reason of vomit?",
    "he also eats his hands alot , while doing that today",
    "2 m baby chest feels congested, is taking less feeds",
    "but when i push his stomach it seems like he is having stomach pain",  # no context
    "hi dr meri baby ko constipation se stool me blood arha hai",  # keep - has answer
]


def is_vague_question(question: str) -> bool:
    q = question.lower().strip()
    for pattern in VAGUE_QUESTION_PATTERNS:
        if pattern in q:
            return True
    if len(question.strip()) < 12:
        return True
    return False


# ══════════════════════════════════════════════════════
# Rule 6 — Dangerous wrong answers
# ══════════════════════════════════════════════════════
DANGEROUS_PAIRS = [
    # (question_contains, answer_contains, reason)
    ("breastfeed my baby immediately after bath",
     "drink plenty of water before feeding",
     "Answer is for milk supply, not for feeding after bath"),

    ("my 3 month daughter is having runny nose, watery eyes sometimes coughing",
     "start supplementing vit d 3 and iron",
     "Vit D/iron is wrong treatment for cold/runny nose"),

    ("my baby is 5 month and 20 days old i am the   breastfeeding mom but i can start the formula milk",
     "not normal drink plenty of water before feeding",
     "Answer starts with 'not normal' — mismatch from different thread"),

    ("muje constipation h me baby ko apna milk feed krwa skti hon",
     "latch properly try different positions slightly and check",
     "Mother has constipation, answer is about baby latching — wrong"),

    ("what should be done when new born 18 days old baby got fever",
     "yes that will do for now but keep trying to give water by straw",
     "DANGEROUS: Newborn fever must go to doctor immediately — this answer is from different thread"),

    ("my lo (5 months 8 days) got his reducing substance positive",
     "although not recommended unless utmost necessity",
     "Incomplete answer with no actionable advice"),

    ("my 8 months old daughter is passing little hard stools, she is finding difficult to pass it. i am giving her fiber , however she drinks very little water",
     "yes decrease water does this",
     "DANGEROUS: Decreasing water makes constipation worse, not better"),

    ("2 m baby chest feels congested, is taking less feeds and after feeds is removing sticky white fluid",
     "yes you can give",
     "No context — 'yes you can give' with no medicine mentioned"),

    ("sir my baby boy is 9 month old and somedays he is crying in sleeping time at night",
     "get a blood test",
     "Blood test not indicated for night crying — mismatch"),

    ("any solution for milk blebs on nipples? cream or any other?",
     "get a blood test",
     "Blood test not relevant for milk blebs — mismatch"),

    ("he also eats his hands alot , while doing that today he got hurt",
     "avoid both better to give fruits directly",
     "No context — 'avoid both' refers to something else"),

    ("can i give this syrup 1 yr old son  for cough nd cold nd eyes conjunctivitis also",
     "increase the diet and bf 3/4 times a day",
     "Answer about diet/bf is wrong for cough+conjunctivitis question"),

    ("my 9 month old baby suddenly had these red bumps on one hand. look like mosquito bites. what can i apply",
     "any food like beet root or dragon fruit",
     "Food suggestion for mosquito bites — completely wrong mismatch"),

    ("baby 2 yr + fever nahi hai but body garam hai",
     "yes you can but keep it supervised",
     "What is 'yes you can'? No context — mismatch"),

    ("if any special care is to be taken?",
     "just apply ice on affected area and give pcm as prescribed",
     "Vague follow-up with no standalone meaning"),

    ("what can be done while cluster feeding?",
     "drink a lot of water and take your supplements iron calcium and b complex daily",
     "Answer is for postpartum mother nutrition, not cluster feeding advice"),

    ("during pregnancy my thyroid level was 5.871",
     "share the reports please",
     "Not an answer — doctor asking for more info"),
]


def is_dangerous(q: str, a: str) -> tuple:
    q_l = q.lower()
    a_l = a.lower()
    for q_pat, a_pat, reason in DANGEROUS_PAIRS:
        if q_pat in q_l and a_pat in a_l:
            return True, reason
    return False, ""


# ══════════════════════════════════════════════════════
# Clean text helper
# ══════════════════════════════════════════════════════
def clean_text(text: str) -> str:
    text = re.sub(r"@⁨[^⁩]+⁩", "", text)
    text = re.sub(r"@\w+", "", text)
    text = re.sub(r"^MoMify:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\w[\w\s]+:\s*", "", text)
    text = text.replace("‎", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ══════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════
def main():
    print(f"Loading {INPUT_FILE}...")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"Loaded {len(data)} records.")

    kept    = []
    removed = []
    stats   = {
        "total":             len(data),
        "platform_artifact": 0,
        "useless_answer":    0,
        "vague_question":    0,
        "answer_is_question":0,
        "media_reference":   0,
        "dangerous":         0,
        "kept":              0,
    }

    for r in data:
        q = clean_text(r.get("question", "").strip())
        a = clean_text(r.get("answer",   "").strip())
        reason = None
        detail = ""

        if has_platform_artifacts(q, a):
            reason = "platform_artifact"
            stats["platform_artifact"] += 1

        elif is_useless_answer(a):
            reason = "useless_answer"
            stats["useless_answer"] += 1

        elif is_vague_question(q):
            reason = "vague_question"
            stats["vague_question"] += 1

        elif is_answer_a_question(q, a):
            reason = "answer_is_question"
            stats["answer_is_question"] += 1

        elif references_absent_media(a):
            reason = "media_reference"
            stats["media_reference"] += 1

        else:
            dangerous, detail = is_dangerous(q, a)
            if dangerous:
                reason = "dangerous"
                stats["dangerous"] += 1

        if reason:
            removed.append({
                "reason":   reason,
                "detail":   detail,
                "question": q[:120],
                "answer":   a[:120],
            })
        else:
            kept.append({
                "question": q,
                "answer":   a,
                "source":   "whatsapp"
            })
            stats["kept"] += 1

    print(f"\nKept:    {stats['kept']}")
    print(f"Removed: {len(removed)}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(kept, f, ensure_ascii=False, indent=2)
    print(f"Saved → {OUTPUT_FILE}")

    report = f"""
WhatsApp Dataset Cleaning Report v2
=====================================
Total input              : {stats['total']}
Kept                     : {stats['kept']}
Removed                  : {len(removed)}

Removal reasons:
  Platform artifacts     : {stats['platform_artifact']}
  Useless answers        : {stats['useless_answer']}
  Vague questions        : {stats['vague_question']}
  Answer is a question   : {stats['answer_is_question']}
  References absent media: {stats['media_reference']}
  Dangerous/wrong        : {stats['dangerous']}

REMOVED RECORDS:
"""
    for r in removed:
        report += f"\n[{r['reason']}] {r['detail']}\n"
        report += f"  Q: {r['question']}\n"
        report += f"  A: {r['answer']}\n"

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report → {REPORT_FILE}")
    print(f"\nNext: run merge_datasets.py using ALLQA_cleaned_v2.json as ORIGINAL_FILE")


if __name__ == "__main__":
    main()