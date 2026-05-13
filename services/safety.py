"""
services/safety.py

Minimal safety layer — only intercepts genuinely dangerous situations
that require immediate action regardless of context.

Removed by design:
- Emergency keyword checks (seizure, blue lips, etc.) — a parent with
  a critical emergency will not be using a chatbot
- Newborn fever checks — app is for 0-2 year olds, all babies included
- Language-specific keyword lists — LLM handles language natively now
"""

BLOOD_STOOL_KEYWORDS = [
    "blood in stool",
    "bloody stool",
    "stool me blood",
    "potty mein khoon",
    "potty me khoon",
    "latrine mein khoon",
]


def safety_check(query: str) -> str | None:
    """
    Returns a warning message string if a safety rule triggers,
    otherwise returns None and processing continues normally.
    """
    q = query.lower()

    for kw in BLOOD_STOOL_KEYWORDS:
        if kw in q:
            return (
                "Potty mein khoon dikhna concerning ho sakta hai. "
                "Aaj hi apne pediatrician ko call karein."
            )

    return None