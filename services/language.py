HINDI_WORDS = {
    "mera", "meri", "mere", "bacha", "baccha", "hai", "hain", "kya", "doodh",
    "dudh", "bukhar", "rota", "roti", "neend", "nahi", "nhi", "ho", "kar",
    "se", "ko", "ki", "ka", "aur", "bhi", "ab", "iska", "uska", "mujhe",
    "hum", "tum", "woh", "ye", "yeh", "din", "raat", "subah", "mahina",
    "mahine", "ghante", "thoda", "bohot", "bahut", "lagta", "lagti", "dena",
    "lena", "pilana", "khilana", "horha", "hora", "khansi", "zuqam", "zukam",
    "peeth", "pet", "sar", "dard", "zyada", "thodi", "abhi", "sirf", "lekin",
    "kyun", "kaise", "kitna"
}


def detect_language(text: str) -> str:
    words = set(text.lower().split())
    return "hinglish" if len(words & HINDI_WORDS) >= 2 else "english"


def get_lang_instruction(text: str) -> str:
    lang = detect_language(text)
    if lang == "hinglish":
        return "IMPORTANT: The user wrote in Hinglish. You MUST reply in Hinglish (Hindi+English mix)."
    return "IMPORTANT: The user wrote in English. You MUST reply in English only. Do NOT use any Hindi or Urdu words."
