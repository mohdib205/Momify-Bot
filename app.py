import streamlit as st
import requests
import psycopg2
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

API_URL = "http://72.61.173.6:8010"

st.set_page_config(
    page_title="Momify",
    page_icon="🌸",
    layout="centered",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&display=swap');

*, *::before, *::after { box-sizing: border-box; }

html, body, .stApp {
    background: #fdf6f9;
    font-family: 'DM Sans', sans-serif;
    color: #2d1f2e;
}

#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }
div[data-testid="stToolbar"] { display: none; }

.block-container {
    max-width: 720px !important;
    padding: 0 1.5rem 6rem !important;
}

/* Header */
.momify-header {
    text-align: center;
    padding: 2rem 0 1.2rem;
    border-bottom: 1px solid #f0dde8;
    margin-bottom: 1.5rem;
}
.momify-logo {
    font-family: 'DM Serif Display', serif;
    font-size: 2.2rem;
    color: #8b4a7a;
    letter-spacing: -0.5px;
    line-height: 1;
}
.momify-logo span { color: #c47aaa; font-style: italic; }
.momify-tagline {
    font-size: 0.78rem;
    color: #a07090;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    margin-top: 0.35rem;
    font-weight: 500;
}

/* Chat bubbles */
div[data-testid="stChatMessage"] {
    background: transparent !important;
    border: none !important;
    padding: 0.2rem 0 !important;
}

/* Mode badge */
.mode-badge {
    display: inline-block;
    font-size: 0.67rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    padding: 0.12rem 0.5rem;
    border-radius: 20px;
    margin-top: 0.25rem;
    text-transform: uppercase;
}
.badge-data     { background: #e8f5e9; color: #2e7d32; }
.badge-weak     { background: #fff3e0; color: #e65100; }
.badge-fallback { background: #fce4ec; color: #c62828; }
.badge-error    { background: #f5f5f5; color: #757575; }

/* Feedback card */
.feedback-card {
    background: #ffffff;
    border: 1px solid #f0dde8;
    border-radius: 14px;
    padding: 1rem 1.2rem;
    margin-top: 0.6rem;
    box-shadow: 0 1px 6px rgba(139,74,122,0.05);
}
.feedback-label {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #a07090;
    margin-bottom: 0.6rem;
}
.feedback-submitted {
    font-size: 0.82rem;
    color: #2e7d32;
    font-weight: 500;
    padding: 0.4rem 0;
}

/* Chat input */
div[data-testid="stChatInput"] {
    border-top: 1px solid #f0dde8 !important;
    background: #fdf6f9 !important;
    padding: 0.75rem 0 !important;
}
div[data-testid="stChatInput"] textarea {
    border-radius: 24px !important;
    border: 1.5px solid #e8c8dc !important;
    background: #ffffff !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.9rem !important;
    color: #2d1f2e !important;
    box-shadow: 0 2px 8px rgba(139,74,122,0.07) !important;
}
div[data-testid="stChatInput"] textarea:focus {
    border-color: #c47aaa !important;
    box-shadow: 0 2px 12px rgba(139,74,122,0.14) !important;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #fff8fb !important;
    border-right: 1px solid #f0dde8 !important;
}
section[data-testid="stSidebar"] * {
    font-family: 'DM Sans', sans-serif !important;
}

/* Buttons */
.stButton > button {
    background: #8b4a7a !important;
    color: white !important;
    border: none !important;
    border-radius: 20px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.83rem !important;
    padding: 0.35rem 1.1rem !important;
    transition: background 0.2s !important;
}
.stButton > button:hover { background: #7a3d6a !important; }

.ghost-btn > button {
    background: transparent !important;
    color: #a07090 !important;
    border: 1px solid #e8c8dc !important;
}
.ghost-btn > button:hover {
    background: #f3e6ef !important;
    color: #8b4a7a !important;
}

/* Radio */
.stRadio > div { gap: 0.5rem !important; }
.stRadio label { font-size: 0.83rem !important; }

/* Selectbox */
.stSelectbox label { font-size: 0.83rem !important; }

/* Text input */
.stTextInput input {
    border-radius: 10px !important;
    border: 1px solid #e8c8dc !important;
    font-size: 0.88rem !important;
}
.stTextInput input:focus { border-color: #c47aaa !important; }

/* Text area */
.stTextArea textarea {
    border-radius: 10px !important;
    border: 1px solid #e8c8dc !important;
    font-size: 0.85rem !important;
}

/* Divider */
hr { border: none; border-top: 1px solid #f0dde8; }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════
# DB
# ════════════════════════════════════════

def save_feedback(query, bot_response, mode, score, verdict, failure_reason, doctor_notes, reviewed_by):
    db_url = os.environ.get("DB_URL", "")
    if not db_url:
        try:
            db_url = st.secrets.get("DB_URL", "")
        except Exception:
            db_url = ""
    if not db_url:
        st.error("DB_URL not set.")
        return False
    try:
        conn = psycopg2.connect(db_url)
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO doctor_feedback
                (query, bot_response, mode, score, verdict, failure_reason, doctor_notes, reviewed_by, reviewed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (query, bot_response, mode, score, verdict, failure_reason,
              doctor_notes, reviewed_by, datetime.now()))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Could not save feedback: {e}")
        return False


# ════════════════════════════════════════
# Session state
# ════════════════════════════════════════

if "messages"           not in st.session_state: st.session_state.messages           = []
if "history"            not in st.session_state: st.session_state.history            = []
if "feedback_submitted" not in st.session_state: st.session_state.feedback_submitted = {}


# ════════════════════════════════════════
# Sidebar
# ════════════════════════════════════════

with st.sidebar:
    st.markdown("""
        <div style='font-family:"DM Serif Display",serif;font-size:1.3rem;color:#8b4a7a;padding:0.5rem 0 1rem'>
            Momify
        </div>
    """, unsafe_allow_html=True)

    st.markdown("**Your name**")
    doctor_name = st.text_input(
        "",
        placeholder="Dr. Sharma",
        value=st.session_state.get("doctor_name", ""),
        label_visibility="collapsed"
    )
    st.session_state.doctor_name = doctor_name

    if doctor_name.strip():
        st.markdown(f"""
            <div style='font-size:0.8rem;color:#2e7d32;margin-top:-0.3rem;margin-bottom:0.8rem'>
                Reviewing as {doctor_name}
            </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
            <div style='font-size:0.78rem;color:#e65100;margin-top:-0.3rem;margin-bottom:0.8rem'>
                Enter your name to submit feedback
            </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("""
        <div style='font-size:0.78rem;color:#a07090;font-weight:600;
                    letter-spacing:0.07em;text-transform:uppercase;margin-bottom:0.5rem'>
            Response modes
        </div>
        <div style='font-size:0.8rem;color:#5a3a5a;line-height:2.2'>
            <span style='background:#e8f5e9;color:#2e7d32;padding:2px 9px;
                         border-radius:10px;font-weight:600;font-size:0.7rem'>DATA</span>
            &nbsp;Strong dataset match<br>
            <span style='background:#fff3e0;color:#e65100;padding:2px 9px;
                         border-radius:10px;font-weight:600;font-size:0.7rem'>WEAK</span>
            &nbsp;Partial match<br>
            <span style='background:#fce4ec;color:#c62828;padding:2px 9px;
                         border-radius:10px;font-weight:600;font-size:0.7rem'>FALLBACK</span>
            &nbsp;Knowledge base used
        </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<div class="ghost-btn">', unsafe_allow_html=True)
    if st.button("Clear conversation"):
        st.session_state.messages           = []
        st.session_state.history            = []
        st.session_state.feedback_submitted = {}
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


# ════════════════════════════════════════
# Header
# ════════════════════════════════════════

st.markdown("""
<div class="momify-header">
    <div class="momify-logo">Mom<span>ify</span></div>
    <div class="momify-tagline">Baby health assistant &nbsp;·&nbsp; English & Hinglish</div>
</div>
""", unsafe_allow_html=True)


# ════════════════════════════════════════
# Chat history
# ════════════════════════════════════════

for idx, msg in enumerate(st.session_state.messages):

    if msg["role"] == "user":
        with st.chat_message("user", avatar="👤"):
            st.markdown(msg["content"])

    else:
        with st.chat_message("assistant", avatar="🌸"):
            st.markdown(msg["content"])

            # Mode badge
            if "meta" in msg:
                mode  = msg["meta"].get("mode", "")
                score = msg["meta"].get("score", 0.0)
                badge = {"data":"badge-data","weak":"badge-weak",
                         "fallback":"badge-fallback"}.get(mode, "badge-error")
                st.markdown(
                    f'<span class="mode-badge {badge}">{mode} {score:.2f}</span>',
                    unsafe_allow_html=True
                )

            # Feedback panel — always visible
            if "meta" in msg:
                feedback_key      = f"feedback_{idx}"
                already_submitted = st.session_state.feedback_submitted.get(feedback_key, False)

                st.markdown('<div class="feedback-card">', unsafe_allow_html=True)
                st.markdown('<div class="feedback-label">Doctor Feedback</div>', unsafe_allow_html=True)

                if already_submitted:
                    st.markdown('<div class="feedback-submitted">Feedback recorded — thank you.</div>',
                                unsafe_allow_html=True)
                else:
                    # Parent query for context
                    user_query = ""
                    if idx > 0 and st.session_state.messages[idx - 1]["role"] == "user":
                        user_query = st.session_state.messages[idx - 1]["content"]
                    if user_query:
                        st.markdown(
                            f'<div style="font-size:0.8rem;color:#a07090;margin-bottom:0.5rem">'
                            f'Parent asked: <em>{user_query}</em></div>',
                            unsafe_allow_html=True
                        )

                    verdict = st.radio(
                        "Verdict",
                        ["Correct", "Partially correct", "Incorrect"],
                        horizontal=True,
                        key=f"verdict_{idx}",
                        label_visibility="collapsed"
                    )

                    failure_reason = ""
                    if verdict != "Correct":
                        failure_reason = st.selectbox(
                            "What was wrong?",
                            ["— select —",
                             "Should have given home remedy first",
                             "Should NOT have mentioned medicine",
                             "Wrong medicine category named",
                             "Missing important advice",
                             "Language / tone issue",
                             "Gave dose / frequency / duration",
                             "Said 'consult doctor' incorrectly",
                             "Other"],
                            key=f"reason_{idx}",
                            label_visibility="collapsed"
                        )

                    doctor_notes = st.text_area(
                        "Notes",
                        placeholder="What should the correct response have been? (optional)",
                        height=70,
                        key=f"notes_{idx}",
                        label_visibility="collapsed"
                    )

                    doctor_name_val = st.session_state.get("doctor_name", "").strip()
                    if st.button("Submit feedback", key=f"submit_{idx}",
                                 disabled=not doctor_name_val):
                        if verdict != "Correct" and failure_reason == "— select —":
                            st.error("Please select what was wrong.")
                        else:
                            ok = save_feedback(
                                query          = user_query,
                                bot_response   = msg["content"],
                                mode           = msg["meta"].get("mode", ""),
                                score          = msg["meta"].get("score", 0.0),
                                verdict        = verdict,
                                failure_reason = failure_reason if failure_reason != "— select —" else "",
                                doctor_notes   = doctor_notes,
                                reviewed_by    = doctor_name_val
                            )
                            if ok:
                                st.session_state.feedback_submitted[feedback_key] = True
                                st.rerun()

                st.markdown('</div>', unsafe_allow_html=True)


# ════════════════════════════════════════
# Chat input
# ════════════════════════════════════════

user_input = st.chat_input("Ask about your baby's health...")

if user_input:
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    with st.chat_message("assistant", avatar="🌸"):
        with st.spinner(""):
            try:
                response = requests.post(
                    f"{API_URL}/chat",
                    json={"message": user_input, "history": st.session_state.history},
                    timeout=30
                )
                data  = response.json()
                reply = data.get("reply", "Something went wrong.")
                mode  = data.get("mode",  "fallback")
                score = data.get("score", 0.0)
            except requests.exceptions.ConnectionError:
                reply = "Unable to reach the server. Please try again in a moment."
                mode  = "error"
                score = 0.0

        st.markdown(reply)

        if mode != "error":
            badge = {"data":"badge-data","weak":"badge-weak",
                     "fallback":"badge-fallback"}.get(mode, "badge-error")
            st.markdown(
                f'<span class="mode-badge {badge}">{mode} {score:.2f}</span>',
                unsafe_allow_html=True
            )

    st.session_state.messages.append({
        "role":    "assistant",
        "content": reply,
        "meta":    {"mode": mode, "score": score}
    })
    st.session_state.history.append({"role": "user",      "content": user_input})
    st.session_state.history.append({"role": "assistant", "content": reply})
    st.rerun()