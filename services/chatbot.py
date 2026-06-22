"""
services/chatbot.py

Key change from original:
- get_response() now accepts baby_context parameter
- Baby context is injected into the system prompt so LLM
  knows baby details without asking the parent
- RateLimitError handling, split into two cases:
    TPM (tokens/requests per MINUTE) -> transient, self-heals in ~60s,
        just show a "busy, try again" message, no key rotation
    TPD/RPD (tokens/requests per DAY) -> real outage risk, switch to the
        secondary Groq key. If BOTH keys are exhausted, return a distinct
        "keys_exhausted" mode + SERVICE_UNAVAILABLE code and alert the admin
        by email.
"""

import re
import time
from groq import Groq, RateLimitError

from core.config import GROQ_API_KEY_PRIMARY, MODEL, HIGH_CONFIDENCE, LOW_CONFIDENCE
from core.prompts import STRICT_PROMPT, KNOWLEDGE_PROMPT
from core.logger import app_logger, log_chat
from core.scheduler import send_admin_alert_email
from services.retriever import retrieve, build_context
from services.safety import safety_check
from services.token_tracker import log_token_usage
from services.key_manager import (
    get_active_key,
    get_active_key_name,
    mark_primary_dead,
    mark_secondary_dead,
    both_dead,
)

client = Groq(api_key=GROQ_API_KEY_PRIMARY)


# ── Prescription filter ───────────────────────────────────────────────────────

_PRESCRIPTION_PATTERNS = [
    r'\b\d+(\.\d+)?\s*(ml|mg|mcg|cc)\b',
    r'\bevery\s+\d+\s+hours?\b',
    r'\b(once|twice|three\s+times)\s+(a\s+)?(day|daily)\b',
    r'\bfor\s+\d+\s+(days?|weeks?)\b',
    r'\b\d+\s+times?\s+(a\s+)?(day|daily)\b',
    r'\bdin\s+mein\s+\d+\s+baar\b',
    r'\b\d+\s+baar\s+(roz|daily|din)\b',
]

_SUPPLEMENT_WHITELIST_PATTERNS = [
    r'\b\d+\s*IU\b',
    r'\bvit(amin)?\s*[dD]\b',
    r'\bvit(amin)?\s*[bB]\b',
    r'\biron\s+drops?\b',
    r'\bzinc\b',
    r'\bcalcium\b',
    r'\bdepura\b',
    r'\braricap\b',
    r'\bzincovit\b',
    r'\bsporolac\b',
    r'\bors\b',
]


def _is_supplement_context(text: str) -> bool:
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in _SUPPLEMENT_WHITELIST_PATTERNS)

_DOCTOR_REDIRECT_EN = (
    "For personalised guidance, you can speak to our available pediatricians here: "
    "https://www.google.com/"
)

_DOCTOR_REDIRECT_HI = (
    "Personalised guidance ke liye, hamare available pediatricians se baat karein: "
    "https://www.google.com/"
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


# ── Language detection ────────────────────────────────────────────────────────

_HINGLISH_MARKERS = [
    "mere", "mera", "meri", "hai", "hain", "kya", "karo", "karein",
    "aur", "nahi", "nhi", "baby ko", "batao", "btao",
    "doodh", "bukhar", "sardi", "thoda", "zyada", "din", "raat",
    "abhi", "pehle", "baad", "kyun", "kaise", "kab", "kuch", "bhi",
    "uske", "uski", "uska", "woh", "hum", "tum",
    "please bataiye", "kindly btaye", "hy doctor",
    "bata", "dena", "lena", "karna", "hoga", "chahiye",
    "theek", "bilkul", "achha", "bahut", "bohot",
]

def _detect_hinglish(message: str) -> bool:
    msg_lower = message.lower()
    matches = sum(1 for marker in _HINGLISH_MARKERS if marker in msg_lower)
    return matches >= 2


# ── Rate-limit helpers ─────────────────────────────────────────────────────────

def _is_daily_limit_error(error_message: str) -> bool:
    """
    Distinguishes a DAILY limit hit (TPD/RPD) from a per-MINUTE hit (TPM/RPM).
    Groq's error body includes the literal phrase, e.g.:
      "...on tokens per day (TPD): Limit 100000, Used 99414..."
    vs
      "...on tokens per minute (TPM): Limit 12000, Used 11953..."
    """
    return bool(re.search(r"tokens per day|requests per day|\(TPD\)|\(RPD\)", error_message, re.IGNORECASE))


def _call_groq(messages: list):
    """Single place that actually calls Groq, using whichever key is currently active."""
    client.api_key = get_active_key()
    raw_response = client.chat.completions.with_raw_response.create(
        model=MODEL,
        messages=messages,
        max_tokens=1024,
        temperature=0.3
    )
    response  = raw_response.parse()
    raw_reply = response.choices[0].message.content
    return response, raw_reply


# ── Main response function ────────────────────────────────────────────────────

def get_response(
    message:       str,
    qa_data:       list,
    history:       list,
    baby_context:  str = "",
    parent_id:     str | None = None,
    baby_id:       str | None = None,
    query_subject: str = "baby"
) -> tuple[str, str, float, int]:

    start_time = time.time()
    app_logger.info(f"Incoming query: {message!r}")

    # 1. Safety check
    safety_msg = safety_check(message)
    if safety_msg:
        app_logger.warning(f"Safety triggered for query: {message!r}")
        response_time_ms = int((time.time() - start_time) * 1000)
        log_chat(
            query=message,
            reply=safety_msg,
            mode="emergency",
            score=0.0,
            response_time_ms=response_time_ms,
            query_subject=query_subject
        )
        return safety_msg, "emergency", 0.0, response_time_ms

    # 2. Detect language
    is_hinglish = _detect_hinglish(message)
    lang_instruction = (
        "LANGUAGE INSTRUCTION: The parent wrote in Hinglish. Reply in Hinglish only. Do NOT reply in English."
        if is_hinglish else
        "LANGUAGE INSTRUCTION: The parent wrote in English. Reply in English only. Do NOT use any Hindi or Hinglish words."
    )
    app_logger.debug(f"Language detected: {'Hinglish' if is_hinglish else 'English'}")

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

    # 5. Inject baby context into system prompt if available
    if baby_context:
        system = system + f"\n\n{baby_context}"

    # 5b. If this question is about the mother, not the baby, tell the model so —
    # otherwise it defaults to assuming every question is about the baby's health.
    if query_subject == "mother":
        system = system + (
            "\n\nIMPORTANT: This question is about the parent (mother), not the baby. "
            "Answer accordingly — do not assume the question is about the baby's health."
        )

    app_logger.info(f"Mode: {mode} | Score: {best_score:.3f} | Baby context: {'yes' if baby_context else 'no'} | Query subject: {query_subject}")

    # 6. Build messages with history
    messages = [{"role": "system", "content": system}]
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_msg})

    # 7. Call Groq — with two-key fallback on daily-limit errors
    try:
        response, raw_reply = _call_groq(messages)

    except RateLimitError as e:
        error_text = str(e)
        response_time_ms = int((time.time() - start_time) * 1000)

        # ── Case A: daily limit (TPD/RPD) — this is the real outage risk ──
        if _is_daily_limit_error(error_text):
            failed_key_name = get_active_key_name()
            if failed_key_name == "primary":
                mark_primary_dead()
            else:
                mark_secondary_dead()

            if both_dead():
                app_logger.critical(f"BOTH GROQ KEYS EXHAUSTED — manual intervention required: {e}")
                try:
                    send_admin_alert_email(
                        subject="🚨 Momify: Both Groq keys exhausted (daily limit)"
                    )
                except Exception as mail_err:
                    app_logger.error(f"Failed to send admin alert email: {mail_err}")

                log_chat(
                    query=message,
                    reply="SERVICE_UNAVAILABLE",
                    mode="keys_exhausted",
                    score=0.0,
                    response_time_ms=response_time_ms,
                    parent_id=parent_id,
                    baby_id=baby_id,
                    query_subject=query_subject
                )
                return "SERVICE_UNAVAILABLE", "keys_exhausted", 0.0, response_time_ms

            # One key just died, the other is still fresh — retry once
            try:
                response, raw_reply = _call_groq(messages)
            except RateLimitError as e2:
                # Secondary failed too, immediately — treat as both dead
                mark_secondary_dead()
                app_logger.critical(f"BOTH GROQ KEYS EXHAUSTED — manual intervention required: {e2}")
                try:
                    send_admin_alert_email(
                        subject="🚨 Momify: Both Groq keys exhausted (daily limit)"
                    )
                except Exception as mail_err:
                    app_logger.error(f"Failed to send admin alert email: {mail_err}")

                response_time_ms = int((time.time() - start_time) * 1000)
                log_chat(
                    query=message,
                    reply="SERVICE_UNAVAILABLE",
                    mode="keys_exhausted",
                    score=0.0,
                    response_time_ms=response_time_ms,
                    parent_id=parent_id,
                    baby_id=baby_id,
                    query_subject=query_subject
                )
                return "SERVICE_UNAVAILABLE", "keys_exhausted", 0.0, response_time_ms

        # ── Case B: per-minute limit (TPM/RPM) — transient, self-heals in ~60s ──
        else:
            app_logger.warning(f"Rate limit hit (TPM): {e}")
            fallback_reply = (
                "Hamara assistant abhi thoda busy hai. Kripya kuch second baad phir try karein 🙏"
                if is_hinglish else
                "Our assistant is a little busy right now. Please try again in a few seconds 🙏"
            )
            log_chat(
                query=message,
                reply=fallback_reply,
                mode="rate_limited",
                score=0.0,
                response_time_ms=response_time_ms,
                parent_id=parent_id,
                baby_id=baby_id,
                query_subject=query_subject
            )
            return fallback_reply, "rate_limited", 0.0, response_time_ms

    except Exception as e:
        app_logger.error(f"Groq API error: {e}")
        raise

    # 8. Log token usage
    usage = response.usage
    log_token_usage(
        model=MODEL,
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        mode=mode,
        parent_id=parent_id,
        baby_id=baby_id,
    )

    # 9. Prescription filter
    reply = _filter_prescription_response(raw_reply, message)
    if reply != raw_reply:
        app_logger.warning("Prescription filter triggered.")

    response_time_ms = int((time.time() - start_time) * 1000)
    app_logger.info(f"Response time: {response_time_ms}ms")

    # 10. Log chat
    log_chat(
        query=message,
        reply=reply,
        mode=mode,
        score=round(best_score, 3),
        response_time_ms=response_time_ms,
        parent_id=parent_id,
        baby_id=baby_id,
        query_subject=query_subject
    )

    return reply, mode, round(best_score, 3), response_time_ms