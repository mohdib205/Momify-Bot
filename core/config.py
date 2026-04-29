import os
from dotenv import load_dotenv

load_dotenv()

# GROQ_API_KEY    = "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"
# QA_FILE         = os.getenv("QA_FILE", r"data\ALLQA_cleaned.json")
# MODEL           = "llama-3.3-70b-versatile"
# TOP_K           = 5
# DB_URL          = os.getenv("DB_URL")

# # ── Cosine similarity thresholds (0.0 to 1.0) ──
# # Jaccard was 0.15 / 0.05 — cosine scores are much higher
# # 0.6+ = strong semantic match → answer strictly from data
# # 0.4+ = moderate match       → use data but allow supplement
# # <0.4 = weak/no match        → fall back to knowledge prompt
# HIGH_CONFIDENCE = 0.60
# LOW_CONFIDENCE  = 0.40

import os
from dotenv import load_dotenv
 
load_dotenv()
 
GROQ_API_KEY    = "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"
QA_FILE         = os.getenv("QA_FILE", r"data\babydoc_merged.json")
MODEL           = "llama-3.3-70b-versatile"
# Judge_MODEL           = "llama-3.1-8b-instant"
TOP_K           = 5
HIGH_CONFIDENCE = 0.60
LOW_CONFIDENCE  = 0.40
DB_URL          = os.getenv("DB_URL")