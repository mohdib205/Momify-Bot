"""
services/chatbot.py

Key change from original:
- get_response() now accepts baby_context parameter
- Baby context is injected into the system prompt so LLM
  knows baby details without asking the parent
"""

import re
import time
from groq import Groq

from core.config import GROQ_API_KEY, MODEL, HIGH_CONFIDENCE, LOW_CONFIDENCE
from core.prompts import STRICT_PROMPT, KNOWLEDGE_PROMPT
from core.logger import app_logger, log_chat
from services.retriever import retrieve, build_context
from services.safety import safety_check

client = Groq(api_key=GROQ_API_KEY)


# ── Prescription filter ───────────────────────────────────────────────────────

# Patterns that indicate a prescription-level medicine dose slipped through
_PRESCRIPTION_PATTERNS = [
    r'\b\d+(\.\d+)?\s*(ml|mg|mcg|cc)\b',
    r'\bevery\s+\d+\s+hours?\b',
    r'\b(once|twice|three\s+times)\s+(a\s+)?(day|daily)\b',
    r'\bfor\s+\d+\s+(days?|weeks?)\b',
    r'\b\d+\s+times?\s+(a\s+)?(day|daily)\b',
    r'\bdin\s+mein\s+\d+\s+baar\b',
    r'\b\d+\s+baar\s+(roz|daily|din)\b',
]

# Patterns that indicate supplement/vitamin context — these should NOT trigger the filter
# IU amounts (e.g. 400 IU, 600 IU) are standard supplement guidance, not prescriptions
_SUPPLEMENT_WHITELIST_PATTERNS = [
    r'\b\d+\s*IU\b',                          # 400 IU, 600 IU
    r'\bvit(amin)?\s*[dD]\b',                 # Vitamin D, Vit D
    r'\bvit(amin)?\s*[bB]\b',                 # Vitamin B
    r'\biron\s+drops?\b',                     # iron drops
    r'\bzinc\b',                              # zinc supplements
    r'\bcalcium\b',                           # calcium
    r'\bdepura\b',                            # Depura (Vit D brand)
    r'\braricap\b',                           # Raricap (iron brand)
    r'\bzincovit\b',                          # Zincovit
    r'\bsporolac\b',                          # Sporolac (probiotic)
    r'\bors\b',                               # ORS
]


def _is_supplement_context(text: str) -> bool:
    """Returns True if the text is talking about supplements/vitamins, not medicines."""
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in _SUPPLEMENT_WHITELIST_PATTERNS)

_DOCTOR_REDIRECT_EN = (
    "For the exact dose, frequency, and duration of any medicine, "
    "call your pediatrician directly. "
    "Every baby's weight and condition is different."
)

_DOCTOR_REDIRECT_HI = (
    "Exact dose, frequency aur duration ke liye apne doctor ko call karein. "
    "Har baby ka weight aur condition alag hoti hai."
)


def _contains_prescription_detail(text: str) -> bool:
    for pattern in _PRESCRIPTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def _is_hinglish(text: str) -> bool:
    hinglish_markers = ["hai", "karo", "aur", "nahi", "baby", "mama", "beti", "beta",
                        "karein", "dein", "rakho", "pilao", "kya", "mein"]
    words = text.lower().split()
    return sum(1 for w in words if w in hinglish_markers) >= 2


def _filter_prescription_response(response: str, query: str = "") -> str:
    if not _contains_prescription_detail(response):
        return response

    # If query OR response is supplement/vitamin context, skip filter entirely
    if _is_supplement_context(response) or _is_supplement_context(query):
        return response

    sentences      = re.split(r'(?<=[.!?।])\s+', response)
    safe_sentences = []
    prescription_found = False

    for sentence in sentences:
        if _contains_prescription_detail(sentence) and not _is_supplement_context(sentence):
            prescription_found = True
        else:
            safe_sentences.append(sentence)

    clean_response = " ".join(safe_sentences).strip()

    if prescription_found:
        redirect   = _DOCTOR_REDIRECT_HI if _is_hinglish(response) else _DOCTOR_REDIRECT_EN
        separator  = "\n\n" if clean_response else ""
        clean_response = f"{clean_response}{separator}⚠️ {redirect}"

    return clean_response


# ── Main response function ────────────────────────────────────────────────────

def get_response(
    message:      str,
    qa_data:      list,
    history:      list,
    baby_context: str = ""
) -> tuple[str, str, float]:

    start_time = time.time()
    app_logger.info(f"Incoming query: {message!r}")

    # 1. Safety check
    safety_msg = safety_check(message)
    if safety_msg:
        app_logger.warning(f"Safety triggered for query: {message!r}")
        log_chat(
            query=message,
            reply=safety_msg,
            mode="emergency",
            score=0.0,
            response_time_ms=(time.time() - start_time) * 1000
        )
        return safety_msg, "emergency", 0.0

    # 2. Detect language — hard instruction injected into every user message
    hinglish_markers = [
        "mere", "mera", "meri", "hai", "hain", "kya", "karo", "karein",
        "aur", "nahi", "nhi", "baby ko", "batao", "btao", "he", "ho",
        "doodh", "bukhar", "sardi", "thoda", "zyada", "din", "raat",
        "abhi", "pehle", "baad", "kyun", "kaise", "kab", "kuch", "bhi",
        "uske", "uski", "uska", "woh", "hum", "tum", "app", "please bataiye",
        "kindly btaye", "plz", "hy doctor", "hlo"
    ]
    msg_lower = message.lower()
    is_hinglish = sum(1 for w in hinglish_markers if w in msg_lower) >= 1
    lang_instruction = (
        "IMPORTANT: Reply in Hinglish (Hindi + English mix). The parent wrote in Hinglish."
        if is_hinglish else
        "IMPORTANT: Reply in English only. The parent wrote in English. Do NOT use Hindi or Hinglish."
    )

    # 3. Retrieve from dataset
    best_score, retrieved = retrieve(message, qa_data)
    app_logger.debug(f"Retrieval score: {best_score:.3f} | top results: {len(retrieved)}")

    # 4. Decide mode and build user message
    if best_score >= HIGH_CONFIDENCE:
        context  = build_context(retrieved)
        system   = STRICT_PROMPT
        user_msg = f"{lang_instruction}\n\nRetrieved Q&A pairs:\n{context}\nParent's question: {message}"
        mode     = "data"

    elif best_score >= LOW_CONFIDENCE:
        context  = build_context(retrieved)
        system   = STRICT_PROMPT
        user_msg = (
            f"{lang_instruction}\n\n"
            f"Partially relevant Q&A pairs:\n{context}\n"
            f"Parent's question: {message}\n"
            f"If the above pairs are not relevant, use your own knowledge."
        )
        mode     = "weak"

    else:
        system   = KNOWLEDGE_PROMPT
        user_msg = f"{lang_instruction}\n\nParent's question: {message}"
        mode     = "fallback"

    # 4. Inject baby context into system prompt if available
    if baby_context:
        system = system + f"\n\n{baby_context}"

    app_logger.info(f"Mode: {mode} | Score: {best_score:.3f} | Baby context: {'yes' if baby_context else 'no'}")

    # 5. Build messages with history
    messages = [{"role": "system", "content": system}]
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_msg})

    # 6. Call Groq
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=1024,
            temperature=0.3
        )
        raw_reply = response.choices[0].message.content
    except Exception as e:
        app_logger.error(f"Groq API error: {e}")
        raise

    # 7. Prescription filter
    # Pass both query and reply — if query is supplement context, don't filter
    reply = _filter_prescription_response(raw_reply, message)
    if reply != raw_reply:
        app_logger.warning("Prescription filter triggered.")

    response_time_ms = (time.time() - start_time) * 1000
    app_logger.info(f"Response time: {response_time_ms:.0f}ms")

    # 8. Log
    log_chat(
        query=message,
        reply=reply,
        mode=mode,
        score=round(best_score, 3),
        response_time_ms=response_time_ms
    )

    return reply, mode, round(best_score, 3)