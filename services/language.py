HINDI_WORDS = {
    "mera", "meri", "mere", "bacha", "baccha", "hai", "hain", "kya", "doodh",
    "dudh", "bukhar", "rota", "roti", "neend", "nahi", "nhi", "ho", "kar",
    "se", "ko", "ki", "ka", "aur", "bhi", "ab", "iska", "uska", "mujhe",
    "hum", "tum", "woh", "ye", "yeh", "din", "raat", "subah", "mahina",
    "mahine", "ghante", "thoda", "bohot", "bahut", "lagta", "lagti", "dena",
    "lena", "pilana", "khilana", "horha", "hora", "khansi", "zuqam", "zukam",
    "peeth", "pet", "sar", "dard", "zyada", "thodi", "abhi", "sirf", "lekin",
    "kyun", "kaise", "kitna", "he", "hai", "hein", "hoon", "baat", "theek",
    "accha", "acha", "batao", "bataiye", "karo", "karein", "dijiye", "please",
    "boliye", "suniye", "samjho"
}

# Explicit language switch requests
HINDI_REQUEST = ["speak in hindi", "hindi mein bolo", "hindi mein batao", "hindi bolein", "hindi me bolo"]
ENGLISH_REQUEST = ["speak in english", "english mein bolo", "english me bolo"]


def detect_language(text: str) -> str:
    t = text.lower().strip()

    # Explicit language requests
    if any(r in t for r in HINDI_REQUEST):
        return "hinglish"
    if any(r in t for r in ENGLISH_REQUEST):
        return "english"

    words = t.split()
    if not words:
        return "english"

    hindi_count = sum(1 for w in words if w in HINDI_WORDS)
    ratio = hindi_count / len(words)

    return "hinglish" if ratio >= 0.3 else "english"


def get_lang_instruction(text: str) -> str:
    lang = detect_language(text)
    if lang == "hinglish":
        return "IMPORTANT: User is writing in Hinglish/Hindi. Reply in Hinglish (mix of Hindi and English). Do NOT reply in English only."
    return "IMPORTANT: User is writing in English. Reply in English only."