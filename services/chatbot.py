import time
from groq import Groq

from core.config import GROQ_API_KEY, MODEL, HIGH_CONFIDENCE, LOW_CONFIDENCE
from core.prompts import STRICT_PROMPT, KNOWLEDGE_PROMPT
from core.logger import app_logger, log_chat
from services.retriever import retrieve, build_context
from services.safety import safety_check
from services.language import get_lang_instruction

client = Groq(api_key=GROQ_API_KEY)


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
        user_msg = f"{lang_instruction}\n\nPartially relevant Q&A pairs:\n{context}\nParent's question: {message}\nIf the above pairs are not sufficient, use your knowledge to answer."
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
        reply = response.choices[0].message.content
    except Exception as e:
        app_logger.error(f"Groq API error: {e}")
        raise

    response_time_ms = (time.time() - start_time) * 1000
    app_logger.info(f"Response time: {response_time_ms:.0f}ms")

    # 7. Log chat record
    log_chat(
        query=message,
        reply=reply,
        mode=mode,
        score=round(best_score, 3),
        response_time_ms=response_time_ms
    )

    return reply, mode, round(best_score, 3)
