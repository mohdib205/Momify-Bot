"""
services/baby_context.py

Fetches baby details from:
GET https://api.himomify.com/babies/user
Authorization: Bearer <token>

Response is a list — we use the first baby.
User ID comes from JWT token, not the endpoint.

Example response:
[
  {
    "id": 7,
    "name": "Sher",
    "gender": "MALE",
    "dateOfBirth": "2025-05-08",
    "birthWeight": 15.0,
    "age": "1 years 0 months 14 days",
    "userId": 8
  }
]
"""

import os
import requests
import jwt
from core.logger import app_logger

BABY_API_URL = os.environ.get("BABY_API_URL", "https://api.himomify.com")
JWT_SECRET   = os.environ.get("JWT_SECRET", "")


def extract_user_id(token: str) -> str | None:
    """
    Decode JWT and extract user ID.
    Returns None if token is invalid or expired.
    """
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"]
        )
        # Adjust key name based on what your JWT payload uses
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


def fetch_baby_details(token: str) -> dict | None:
    """
    Hits GET /babies/user with the JWT token.
    Returns the first baby's details as a dict, or None if request fails.
    """
    try:
        response = requests.get(
            f"{BABY_API_URL}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()

            # Response is a list — use first baby
            if isinstance(data, list) and len(data) > 0:
                return data[0]
            elif isinstance(data, dict):
                return data
            else:
                app_logger.warning("Baby API returned empty list")
                return None

        else:
            app_logger.warning(f"Baby API returned {response.status_code}")
            return None

    except requests.exceptions.Timeout:
        app_logger.warning("Baby API timed out")
        return None
    except Exception as e:
        app_logger.error(f"Baby API error: {e}")
        return None


def build_baby_context(baby: dict) -> str:
    """
    Builds baby context string from API response fields.
    Uses the 'age' field directly since API already calculates it.
    """
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


def get_baby_context_from_token(token: str) -> str:
    """
    Main entry point — called from main.py.
    Returns baby context string ready to inject into system prompt.
    Returns empty string if anything fails — bot still works without it.
    """
    # Validate token first
    user_id = extract_user_id(token)
    if not user_id:
        return ""

    # Fetch baby details
    baby = fetch_baby_details(token)
    if not baby:
        return ""

    context = build_baby_context(baby)
    app_logger.info(
        f"Baby context loaded for user {user_id} — "
        f"name={baby.get('name')}, age={baby.get('age')}, gender={baby.get('gender')}"
    )
    return context