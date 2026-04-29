import re

EMERGENCY_KEYWORDS = [
    "not breathing", "stopped breathing", "can't breathe", "cannot breathe",
    "blue lips", "lips are blue", "turning blue",
    "unconscious", "unresponsive", "not waking up", "won't wake up",
    "seizure", "convulsion", "fitting", "shaking uncontrollably",
    "saans nahi", "saans band", "saans ruk", "saans nhi",
    "neela ho", "neele ho", "lips neele", "honth neele",
    "behosh", "hosh nahi", "uth nahi raha", "uth nhi raha",
    "mirgi", "jhatke", "fits aa",
]

NEWBORN_AGE_KW = [
    "newborn", "new born",
    "1 day", "2 day", "3 day", "4 day", "5 day", "6 day", "7 day",
    "8 day", "9 day", "10 day", "11 day", "12 day", "13 day", "14 day",
    "15 day", "16 day", "17 day", "18 day", "19 day", "20 day",
    "21 day", "22 day", "23 day", "24 day", "25 day", "26 day", "27 day", "28 day",
    "1 month old", "2 month old", "one month", "two month",
    "6 week", "7 week", "8 week", "9 week", "10 week", "11 week", "12 week",
    "naya janam", "naye janam", "nayi janam",
    "abhi paida", "abhi hua", "abhi hui",
    "1 mahine", "2 mahine", "ek mahine", "do mahine",
    "1 hafte", "2 hafte", "3 hafte", "4 hafte",
    "kuch din ka", "kuch din ki",
]

NEWBORN_FEVER_KW = [
    "fever", "temperature", "temp is", "temp high", "body hot", "feeling hot",
    "bukhar", "bukhaar", "tapman", "garam", "taap",
    "100", "101", "102", "103", "104",
]

BLOOD_STOOL_KW = [
    "blood in stool", "blood in poop", "bloody stool", "bloody poop",
    "stool mein blood", "stool me blood", "stool mai blood",
    "potty mein blood", "potty me blood", "potty mai blood",
    "potty mein khoon", "potty me khoon", "potty mai khoon",
    "laal potty", "khoon aa raha", "mal mein khoon",
]

HIGH_FEVER_KW = ["102", "103", "104", "105", "tez bukhar", "bahut tez bukhar", "very high fever", "high fever"]
BABY_KW = ["baby", "bacha", "baccha", "infant", "child", "bachche"]

CHILD_AGE_PATTERN = re.compile(r"\b(\d+(?:\.\d+)?)\s*year[s]?\s*(old)?\b", re.IGNORECASE)


def safety_check(query: str) -> str | None:
    q = query.lower()

    for kw in EMERGENCY_KEYWORDS:
        if kw in q:
            return "EMERGENCY: Please go to the hospital immediately. / Yeh emergency hai — abhi hospital jaiye."

    is_newborn = any(kw in q for kw in NEWBORN_AGE_KW)
    has_fever  = any(kw in q for kw in NEWBORN_FEVER_KW)
    if is_newborn and has_fever:
        return "3 mahine se chote baby ko fever hai — TURANT doctor ke paas jaiye. / Baby under 3 months with fever must see a doctor immediately. Do NOT wait."

    for kw in BLOOD_STOOL_KW:
        if kw in q:
            return "Blood in stool is serious. Please see a pediatrician TODAY. / Potty mein blood serious hai — aaj hi doctor se milein."

    if any(kw in q for kw in HIGH_FEVER_KW) and any(kw in q for kw in BABY_KW):
        return "Very high fever in a baby — please see a doctor today. / Itna tez bukhar — aaj doctor ko zaroor dikhayein."

    return None