import re
import time
from groq import Groq

from core.config import GROQ_API_KEY, MODEL, HIGH_CONFIDENCE, LOW_CONFIDENCE
from core.prompts import STRICT_PROMPT, KNOWLEDGE_PROMPT
from core.logger import app_logger, log_chat
from services.retriever import retrieve, build_context
from services.safety import safety_check
from services.language import get_lang_instruction

client = Groq(api_key=GROQ_API_KEY)

# ─────────────────────────────────────────────
# PRESCRIPTION FILTER
# ─────────────────────────────────────────────

# Patterns that indicate a prescription-level response slipped through the LLM
_PRESCRIPTION_PATTERNS = [
    r'\b\d+(\.\d+)?\s*(ml|mg|mcg|cc)\b',               # 2.5ml, 10mg, 0.5cc
    r'\bevery\s+\d+\s+hours?\b',                          # every 6 hours
    r'\b(once|twice|three\s+times)\s+(a\s+)?(day|daily)\b',  # twice a day
    r'\bfor\s+\d+\s+(days?|weeks?)\b',                   # for 5 days
    r'\b\d+\s+times?\s+(a\s+)?(day|daily)\b',            # 3 times a day
    r'\bdin\s+mein\s+\d+\s+baar\b',                      # Hinglish: din mein 2 baar
    r'\b\d+\s+baar\s+(roz|daily|din)\b',                 # Hinglish: 2 baar roz
]

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
    """Simple heuristic — reuse the same logic as language.py."""
    hinglish_markers = ["hai", "karo", "aur", "nahi", "baby", "mama", "beti", "beta"]
    words = text.lower().split()
    return sum(1 for w in words if w in hinglish_markers) >= 2


def _filter_prescription_response(response: str) -> str:
    """
    If the LLM response contains dosage / frequency / duration details,
    strip those sentences and append the doctor-redirect message.
    Returns the cleaned response unchanged if no prescription detail found.
    """
    if not _contains_prescription_detail(response):
        return response  # Nothing to fix

    # Split into sentences, keep only non-prescription ones
    sentences = re.split(r'(?<=[.!?।])\s+', response)
    safe_sentences = []
    prescription_found = False

    for sentence in sentences:
        if _contains_prescription_detail(sentence):
            prescription_found = True
            # Drop this sentence — it contains a dose/frequency/duration
        else:
            safe_sentences.append(sentence)

    clean_response = " ".join(safe_sentences).strip()

    if prescription_found:
        redirect = (
            _DOCTOR_REDIRECT_HI
            if _is_hinglish(response)
            else _DOCTOR_REDIRECT_EN
        )
        separator = "\n\n" if clean_response else ""
        clean_response = f"{clean_response}{separator}⚠️ {redirect}"

    return clean_response


# ─────────────────────────────────────────────
# MAIN RESPONSE FUNCTION
# ─────────────────────────────────────────────

def get_response(message: str, qa_data: list, history: list) -> tuple[str, str, float]:
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

    # 2. Language instruction
    lang_instruction = get_lang_instruction(message)

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
            f"{lang_instruction}\n\nPartially relevant Q&A pairs:\n{context}\n"
            f"Parent's question: {message}\n"
            f"If the above pairs are not sufficient, use your knowledge to answer."
        )
        mode     = "weak"

    else:
        system   = KNOWLEDGE_PROMPT
        user_msg = f"{lang_instruction}\n\nParent's question: {message}"
        mode     = "fallback"

    app_logger.info(f"Mode: {mode} | Score: {best_score:.3f}")

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

    # 7. Post-generation prescription filter (catches any LLM slippage)
    reply = _filter_prescription_response(raw_reply)

    if reply != raw_reply:
        app_logger.warning("Prescription filter triggered — dose/frequency/duration stripped from response.")

    response_time_ms = (time.time() - start_time) * 1000
    app_logger.info(f"Response time: {response_time_ms:.0f}ms")

    # 8. Log chat record
    log_chat(
        query=message,
        reply=reply,
        mode=mode,
        score=round(best_score, 3),
        response_time_ms=response_time_ms
    )

    return reply, mode, round(best_score, 3)