import streamlit as st
import requests
import psycopg2
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# API_URL = "http://72.61.173.6:8010"
# API_URL = "https://bot.himomify.com"
API_URL = "http://127.0.0.1:8000/"
# API_URL = "http://187.127.146.155:8010/"



st.set_page_config(
    page_title="Momify",
    page_icon="🌸",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&display=swap');

/* ── CSS variables — light mode ── */
:root {
    --brand:        #8b4a7a;
    --brand-light:  #c47aaa;
    --bg:           #fdf6f9;
    --bg-sidebar:   #fff8fb;
    --bg-card:      #ffffff;
    --bg-user:      #f3e6ef;
    --border:       #f0dde8;
    --border-input: #e8c8dc;
    --text:         #2d1f2e;
    --text-muted:   #a07090;
    --text-sub:     #5a3a5a;
}

/* ── Dark mode overrides ── */
@media (prefers-color-scheme: dark) {
    :root {
        --brand:        #d4a0c4;
        --brand-light:  #e8c8dc;
        --bg:           #1a0f1a;
        --bg-sidebar:   #200f20;
        --bg-card:      #2a1a2a;
        --bg-user:      #3a1f3a;
        --border:       #4a2a4a;
        --border-input: #5a3a5a;
        --text:         #f0e8f0;
        --text-muted:   #c4a0c4;
        --text-sub:     #d4b0d4;
    }
}

*, *::before, *::after { box-sizing: border-box; }

html, body, .stApp {
    background: var(--bg) !important;
    font-family: 'DM Sans', sans-serif;
    color: var(--text) !important;
}

/* FIXED SIDEBAR ISSUE */
#MainMenu, footer {
    visibility: hidden;
}

/* KEEP HEADER + TOOLBAR VISIBLE */
header {
    visibility: visible !important;
}

.stDeployButton { display: none; }

.block-container {
    max-width: 720px !important;
    padding: 0 1.5rem 6rem !important;
}

/* ── Header ── */
.momify-header {
    text-align: center;
    padding: 2rem 0 1.2rem;
    border-bottom: 1px solid var(--border);
    margin-bottom: 1.5rem;
}
.momify-logo {
    font-family: 'DM Serif Display', serif;
    font-size: 2.2rem;
    color: var(--brand);
    letter-spacing: -0.5px;
    line-height: 1;
}
.momify-logo span { color: var(--brand-light); font-style: italic; }
.momify-tagline {
    font-size: 0.78rem;
    color: var(--text-muted);
    letter-spacing: 0.09em;
    text-transform: uppercase;
    margin-top: 0.35rem;
    font-weight: 500;
}

/* ── Chat messages ── */
div[data-testid="stChatMessage"] {
    background: transparent !important;
    border: none !important;
    padding: 0.2rem 0 !important;
}

/* ── Mode badge ── */
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

/* ── Query subject badge ── */
.subject-badge {
    display: inline-block;
    font-size: 0.67rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    padding: 0.12rem 0.5rem;
    border-radius: 20px;
    margin-top: 0.25rem;
    margin-left: 0.4rem;
    text-transform: uppercase;
}
.badge-subject-baby   { background: #e3f2fd; color: #1565c0; }
.badge-subject-mother { background: #f3e5f5; color: #6a1b9a; }

/* ── Feedback card ── */
.feedback-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
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
    color: var(--text-muted);
    margin-bottom: 0.6rem;
}
.feedback-submitted {
    font-size: 0.82rem;
    color: #4caf50;
    font-weight: 500;
    padding: 0.4rem 0;
}
.feedback-parent-q {
    font-size: 0.8rem;
    color: var(--text-muted);
    margin-bottom: 0.5rem;
    font-style: italic;
}

/* ── Chat input ── */
div[data-testid="stChatInput"] {
    border-top: 1px solid var(--border) !important;
    background: var(--bg) !important;
    padding: 0.75rem 0 !important;
}
div[data-testid="stChatInput"] textarea {
    border-radius: 24px !important;
    border: 1.5px solid var(--border-input) !important;
    background: var(--bg-card) !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.9rem !important;
    color: var(--text) !important;
    box-shadow: 0 2px 8px rgba(139,74,122,0.07) !important;
}
div[data-testid="stChatInput"] textarea:focus {
    border-color: var(--brand) !important;
    box-shadow: 0 2px 12px rgba(139,74,122,0.14) !important;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: var(--bg-sidebar) !important;
    border-right: 1px solid var(--border) !important;
}
section[data-testid="stSidebar"] * {
    font-family: 'DM Sans', sans-serif !important;
    color: var(--text) !important;
}

/* ── Buttons ── */
.stButton > button {
    background: var(--brand) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 20px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.83rem !important;
    padding: 0.35rem 1.1rem !important;
    transition: opacity 0.2s !important;
}
.stButton > button:hover { opacity: 0.88 !important; }

.ghost-btn > button {
    background: transparent !important;
    color: var(--text-muted) !important;
    border: 1px solid var(--border-input) !important;
}
.ghost-btn > button:hover {
    background: var(--bg-user) !important;
    color: var(--brand) !important;
}

/* ── Form submit button ── */
div[data-testid="stFormSubmitButton"] > button {
    background: var(--brand) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 20px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.83rem !important;
}

/* ── Radio ── */
.stRadio > div { gap: 0.5rem !important; }
.stRadio label { font-size: 0.83rem !important; color: var(--text) !important; }

/* ── Selectbox ── */
.stSelectbox label { font-size: 0.83rem !important; color: var(--text) !important; }
.stSelectbox > div > div {
    background: var(--bg-card) !important;
    border-color: var(--border-input) !important;
    color: var(--text) !important;
}

/* ── Text input ── */
.stTextInput input {
    border-radius: 10px !important;
    border: 1px solid var(--border-input) !important;
    background: var(--bg-card) !important;
    color: var(--text) !important;
    font-size: 0.88rem !important;
}
.stTextInput input:focus { border-color: var(--brand) !important; }

/* ── Text area ── */
.stTextArea textarea {
    border-radius: 10px !important;
    border: 1px solid var(--border-input) !important;
    background: var(--bg-card) !important;
    color: var(--text) !important;
    font-size: 0.85rem !important;
}

/* ── Divider ── */
hr { border: none; border-top: 1px solid var(--border); }

/* ── Hide st.form box ── */
div[data-testid="stForm"] {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
    box-shadow: none !important;
}

/* ── Markdown text inside chat ── */
div[data-testid="stChatMessage"] p,
div[data-testid="stChatMessage"] li,
div[data-testid="stChatMessage"] span {
    color: var(--text) !important;
}
            
            /* ===== FIX SIDEBAR TOGGLE ICON ===== */

/* Keep toolbar visible */
[data-testid="stToolbar"] {
    display: flex !important;
}

/* Hide broken material icon text */
[data-testid="stBaseButton-headerNoPadding"] span {
    display: none !important;
}

/* Create custom hamburger icon */
[data-testid="stBaseButton-headerNoPadding"]::after {
    content: "☰";
    font-size: 22px;
    color: white;
    display: block;
    line-height: 1;
}

/* Clean button styling */
[data-testid="stBaseButton-headerNoPadding"] {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════
# DB
# ════════════════════════════════════════

def save_feedback(query, bot_response, mode, score,
                  verdict, failure_reason,
                  doctor_notes, reviewed_by):

    try:
        response = requests.post(
            f"{API_URL}/submit_feedback",
            json={
                "query": query,
                "bot_response": bot_response,
                "mode": mode,
                "score": score,
                "verdict": verdict,
                "failure_reason": failure_reason,
                "doctor_notes": doctor_notes,
                "reviewed_by": reviewed_by
            },
            timeout=15
        )

        if response.status_code == 200:
            return True

        st.error("Could not save feedback.")
        return False

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

# ════════════════════════════════════════
# Sidebar
# ════════════════════════════════════════

with st.sidebar:
    st.markdown('<div style="font-family:\'DM Serif Display\',serif;font-size:1.3rem;color:#8b4a7a;padding:0.5rem 0 1rem">Momify</div>', unsafe_allow_html=True)

    st.markdown("**Your name**")
    doctor_name = st.text_input(
        "",
        placeholder="Dr. Momify",
        value=st.session_state.get("doctor_name", ""),
        label_visibility="collapsed"
    )
    st.session_state.doctor_name = doctor_name

    if doctor_name.strip():
        st.markdown(f'<div style="font-size:0.8rem;color:#4caf50;margin-top:-0.3rem;margin-bottom:0.8rem">Reviewing as {doctor_name}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="font-size:0.78rem;color:#e65100;margin-top:-0.3rem;margin-bottom:0.8rem">Enter your name to submit feedback</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("""
        <div style='font-size:0.78rem;color:#a07090;font-weight:600;
                    letter-spacing:0.07em;text-transform:uppercase;margin-bottom:0.5rem'>
            Response modes
        </div>
        <div style='font-size:0.8rem;line-height:2.4'>
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

# Permanent sidebar toggle button fixed to top-left corner
# Keep native Streamlit sidebar toggle visible
st.markdown("""
<style>
button[kind="header"] {
    display: block !important;
}
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════
# Query subject toggle (Baby / Mother) — drives query_subject sent to /chat
# ════════════════════════════════════════

if "query_subject" not in st.session_state:
    st.session_state.query_subject = "baby"

st.markdown(
    '<div style="font-size:0.78rem;color:#a07090;font-weight:600;'
    'letter-spacing:0.07em;text-transform:uppercase;margin-bottom:0.4rem">'
    'This question is about</div>',
    unsafe_allow_html=True
)
subject_choice = st.radio(
    "",
    ["Baby", "Mother"],
    horizontal=True,
    label_visibility="collapsed",
    key="subject_toggle"
)
st.session_state.query_subject = subject_choice.lower()


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

            # Mode badge + query subject badge
            if "meta" in msg:
                mode  = msg["meta"].get("mode", "")
                score = msg["meta"].get("score", 0.0)
                badge = {"data":"badge-data","weak":"badge-weak",
                         "fallback":"badge-fallback"}.get(mode, "badge-error")

                subject = msg["meta"].get("query_subject", "baby")
                subject_badge_class = "badge-subject-mother" if subject == "mother" else "badge-subject-baby"

                st.markdown(
                    f'<span class="mode-badge {badge}">{mode} {score:.2f}</span>'
                    f'<span class="subject-badge {subject_badge_class}">{subject}</span>',
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

                    with st.form(key=f"form_{idx}", clear_on_submit=True):
                        verdict = st.radio(
                            "Verdict",
                            ["Correct", "Partially correct", "Incorrect"],
                            horizontal=True,
                            key=f"verdict_{idx}"
                        )

                        failure_reason = st.selectbox(
                            "What was wrong? (select if not Correct)",
                            ["— select —",
                             "Should have given home remedy first",
                             "Should NOT have mentioned medicine",
                             "Wrong medicine category named",
                             "Missing important advice",
                             "Language / tone issue",
                             "Gave dose / frequency / duration",
                             "Said 'consult doctor' incorrectly",
                             "Other"],
                            key=f"reason_{idx}"
                        )

                        doctor_notes = st.text_area(
                            "Notes (optional)",
                            placeholder="What should the correct response have been?",
                            height=70,
                            key=f"notes_{idx}"
                        )

                        submitted = st.form_submit_button("Submit feedback")

                    if submitted:
                        doctor_name_val = st.session_state.get("doctor_name", "").strip()
                        if not doctor_name_val:
                            st.error("Enter your name in the sidebar first.")
                        elif verdict != "Correct" and failure_reason == "— select —":
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

    current_subject = st.session_state.query_subject

    with st.chat_message("assistant", avatar="🌸"):
        with st.spinner(""):
            try:
                response = requests.post(
                    f"{API_URL}/chat",
                    json={
                        "message": user_input,
                        "history": st.session_state.history,
                        "query_subject": current_subject
                    },
                    timeout=30
                )
                data          = response.json()
                reply         = data.get("reply", "Something went wrong.")
                mode          = data.get("mode",  "fallback")
                score         = data.get("score", 0.0)
                query_subject = data.get("query_subject", current_subject)
            except requests.exceptions.ConnectionError:
                reply         = "Unable to reach the server. Please try again in a moment."
                mode          = "error"
                score         = 0.0
                query_subject = current_subject

        st.markdown(reply)

        if mode != "error":
            badge = {"data":"badge-data","weak":"badge-weak",
                     "fallback":"badge-fallback"}.get(mode, "badge-error")
            subject_badge_class = "badge-subject-mother" if query_subject == "mother" else "badge-subject-baby"
            st.markdown(
                f'<span class="mode-badge {badge}">{mode} {score:.2f}</span>'
                f'<span class="subject-badge {subject_badge_class}">{query_subject}</span>',
                unsafe_allow_html=True
            )

    st.session_state.messages.append({
        "role":    "assistant",
        "content": reply,
        "meta":    {"mode": mode, "score": score, "query_subject": query_subject}
    })
    st.session_state.history.append({"role": "user",      "content": user_input})
    st.session_state.history.append({"role": "assistant", "content": reply})
    st.rerun()