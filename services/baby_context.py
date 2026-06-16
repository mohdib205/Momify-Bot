"""
services/baby_context.py

Changes:
- fetch_baby_details() now accepts optional baby_id
- If baby_id given → fetch that specific baby
- If baby_id not given → return all babies (for selector)
- get_baby_context_from_token() accepts optional baby_id
- fetch_all_babies() now has TTL cache (5 min) — fixes 43s latency
"""

import os
import time
import requests
import jwt
from core.logger import app_logger

BABY_API_URL = os.environ.get("BABY_API_URL", "https://api.himomify.com")
JWT_SECRET   = os.environ.get("JWT_SECRET", "")

# ── TTL Cache ─────────────────────────────────────────────────────────────────
_baby_cache: dict = {}
_CACHE_TTL = 300  # 5 minutes — baby profile rarely changes


def extract_user_id(token: str) -> str | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_id = (
            payload.get("sub") or
            payload.get("user_id") or
            payload.get("userId") or
            payload.get("id")
        )
        if not user_id:
            app_logger.warning("JWT decoded but no user_id found in payload")
            return None
        return str(user_id)
    except jwt.ExpiredSignatureError:
        app_logger.warning("JWT token expired")
        return None
    except jwt.InvalidTokenError as e:
        app_logger.warning(f"Invalid JWT token: {e}")
        return None


def fetch_all_babies(token: str) -> list:
    """
    Returns list of all babies for this parent.
    Caches result for 5 minutes — avoids hitting baby API on every request.
    """
    cache_key = token[-20:]
    now = time.time()

    # Cache hit
    if cache_key in _baby_cache:
        data, ts = _baby_cache[cache_key]
        if now - ts < _CACHE_TTL:
            app_logger.debug("Baby context: cache hit")
            return data

    # Cache miss — call the API
    app_logger.debug("Baby context: cache miss, calling API")
    try:
        response = requests.get(
            f"{BABY_API_URL}/babies/user",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=3
        )
        if response.status_code == 200:
            data = response.json()
            babies = data if isinstance(data, list) else [data]
            _baby_cache[cache_key] = (babies, now)
            return babies
        app_logger.warning(f"Baby API returned {response.status_code}")
        return []
    except requests.exceptions.Timeout:
        app_logger.warning("Baby API timed out")
        return []
    except Exception as e:
        app_logger.error(f"Baby API error: {e}")
        return []


def fetch_baby_by_id(token: str, baby_id: int) -> dict | None:
    """
    Fetches a specific baby by ID from the babies list.
    """
    babies = fetch_all_babies(token)
    for baby in babies:
        if baby.get("id") == baby_id:
            return baby
    app_logger.warning(f"Baby ID {baby_id} not found in parent's babies list")
    return None


def build_baby_context(baby: dict) -> str:
    name         = baby.get("name", "the baby")
    gender       = baby.get("gender", "").upper()
    age          = baby.get("age", "unknown age")
    birth_weight = baby.get("birthWeight")
    dob          = baby.get("dateOfBirth", "")

    gender_str = "boy" if gender == "MALE" else "girl" if gender == "FEMALE" else "baby"
    pronoun    = "he/his" if gender == "MALE" else "she/her" if gender == "FEMALE" else "they/their"
    bw_str     = f"{birth_weight} kg" if birth_weight else "unknown"

    context = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BABY PROFILE — do not ask for these details, you already have them
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Name          : {name}
Age           : {age}
Gender        : {gender_str} (pronoun: {pronoun})
Date of Birth : {dob}
Birth Weight  : {bw_str}

Use this information naturally in your responses.
Address the baby by name when appropriate.
NEVER ask the parent for age, weight, or gender — you already know.
"""
    return context.strip()


def get_baby_context_from_token(token: str, baby_id: int | None = None) -> tuple[str, str | None, str | None]:
    """
    Main entry point — called from main.py.

    Returns tuple: (baby_context, parent_id, baby_id_str)
    - baby_context: string to inject into system prompt
    - parent_id: extracted from JWT
    - baby_id_str: the baby's ID as string (for logging)

    If baby_id is provided → fetch that specific baby
    If baby_id is None → fetch all babies:
        - 1 baby → auto-select
        - multiple → return empty context (parent app should have shown selector)
    """
    parent_id = extract_user_id(token)
    if not parent_id:
        return "", None, None

    babies = fetch_all_babies(token)
    if not babies:
        return "", parent_id, None

    # Select the right baby
    if baby_id is not None:
        baby = next((b for b in babies if b.get("id") == baby_id), None)
        if not baby:
            app_logger.warning(f"Baby ID {baby_id} not found for parent {parent_id}")
            return "", parent_id, None
    elif len(babies) == 1:
        # Only one baby — auto-select
        baby = babies[0]
    else:
        # Multiple babies, no baby_id provided — parent app should send baby_id
        app_logger.warning(f"Parent {parent_id} has {len(babies)} babies but no baby_id sent")
        return "", parent_id, None

    context     = build_baby_context(baby)
    baby_id_str = str(baby.get("id", ""))

    app_logger.info(
        f"Baby context loaded — parent={parent_id}, baby={baby.get('name')}, "
        f"id={baby_id_str}, age={baby.get('age')}"
    )
    return context, parent_id, baby_id_str