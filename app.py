import streamlit as st
import requests
import psycopg2
import os
import json
import base64
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# API_URL = "http://72.61.173.6:8010"
API_URL = "https://bot.himomify.com"
# API_URL = "http://127.0.0.1:8000/"
# API_URL = "http://187.127.146.155:8010/"


def extract_parent_id_from_token(token: str):
    """
    TEST-BRANCH ONLY — mirrors services/baby_context.py's extract_user_id()
    field-priority order (Phase 8 fix: userId checked before sub, since sub
    holds an email in this backend's JWTs, not a numeric id). This is a
    local, unverified decode purely so the test app can log/display the
    actual parent identity instead of the raw token string — it does NOT
    verify the signature, and must never be used for real auth decisions.
    """
    if not token:
        return None
    try:
        payload_segment = token.split(".")[1]
        padding = "=" * (-len(payload_segment) % 4)
        decoded = base64.urlsafe_b64decode(payload_segment + padding)
        claims = json.loads(decoded)
        return (
            claims.get("userId") or
            claims.get("user_id") or
            claims.get("id") or
            claims.get("sub")  # email — last resort only, same order as Phase 8's fix
        )
    except Exception:
        return None


# ════════════════════════════════════════════════════════════════
# TEST-BRANCH ONLY — reply-chain workflow simulation
# Mirrors the schemas sketched in Integration Guide (2) / Phase 12:
#   community_posts  -> stand-in for Java's MySQL reply-tree table
#   ml_chat_logs      -> stand-in for Java's Postgres ML-observability log,
#                        including the history_context addition
# Not part of the real production app. Safe to strip out entirely if this
# branch's code is ever merged back.
# ════════════════════════════════════════════════════════════════

DB_URL = os.environ.get("DB_URL", "")


def _get_conn():
    return psycopg2.connect(DB_URL)


def init_test_tables():
    """Creates the two test tables if they don't exist. Safe to call every run."""
    if not DB_URL:
        return
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS community_posts (
                id              SERIAL PRIMARY KEY,
                parent_id       VARCHAR,
                baby_id         VARCHAR,
                query_subject   VARCHAR(10) DEFAULT 'baby',
                role            VARCHAR(20) NOT NULL,
                content         TEXT NOT NULL,
                reply_to_id     INTEGER REFERENCES community_posts(id),
                created_at      TIMESTAMP DEFAULT NOW()
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ml_chat_logs (
                id                 SERIAL PRIMARY KEY,
                parent_id          VARCHAR,
                baby_id            VARCHAR,
                query              TEXT,
                raw_bot_response   TEXT,
                mode               VARCHAR(20),
                score              FLOAT,
                response_time_ms   INT,
                query_subject      VARCHAR(10),
                history_context    JSONB,
                prompt_tokens      INT,
                completion_tokens  INT,
                total_tokens       INT,
                created_at         TIMESTAMP DEFAULT NOW()
            );
        """)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        st.sidebar.error(f"Test DB init failed: {e}")


def save_post(parent_id, baby_id, query_subject, role, content, reply_to_id=None):
    """Inserts one row into community_posts, returns its new id (or None on failure)."""
    if not DB_URL:
        return None
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO community_posts (parent_id, baby_id, query_subject, role, content, reply_to_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (parent_id, baby_id, query_subject, role, content, reply_to_id))
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return new_id
    except Exception as e:
        st.error(f"Failed to save post: {e}")
        return None


def resolve_chain(reply_to_id):
    """
    Walks reply_to_id backward from the given post, collecting the chain
    in chronological (oldest-first) order. Returns a list of {role, content}
    dicts ready to drop straight into the /chat `history` field.
    """
    if not DB_URL or reply_to_id is None:
        return []
    try:
        conn = _get_conn()
        cur = conn.cursor()
        chain = []
        current_id = reply_to_id
        while current_id is not None:
            cur.execute(
                "SELECT id, role, content, reply_to_id FROM community_posts WHERE id = %s",
                (current_id,)
            )
            row = cur.fetchone()
            if not row:
                break
            _, role, content, parent_reply_id = row
            chain.append({"role": role, "content": content})
            current_id = parent_reply_id
        cur.close()
        conn.close()
        chain.reverse()  # was newest-first from walking backward, flip to chronological
        return chain
    except Exception as e:
        st.error(f"Failed to resolve chain: {e}")
        return []


def log_ml_chat(parent_id, baby_id, query, raw_bot_response, mode, score,
                 response_time_ms, query_subject, history_context,
                 prompt_tokens=None, completion_tokens=None, total_tokens=None):
    """Mirrors the ml_chat_logs write Java would do, async, on its side."""
    if not DB_URL:
        return
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ml_chat_logs
            (parent_id, baby_id, query, raw_bot_response, mode, score,
             response_time_ms, query_subject, history_context,
             prompt_tokens, completion_tokens, total_tokens)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            parent_id, baby_id, query, raw_bot_response, mode, score,
            response_time_ms, query_subject, json.dumps(history_context),
            prompt_tokens, completion_tokens, total_tokens
        ))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        st.error(f"Failed to log ml_chat_logs row: {e}")


init_test_tables()



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


# ════════════════════════════════════════════════════════════════
# TEST-BRANCH ONLY — token / baby_id / reply-to inputs
# Lets the tester simulate the real auth + multi-baby + reply-chain
# scenario without needing a real parent app frontend.
# ════════════════════════════════════════════════════════════════

with st.expander("🧪 Test controls (token, baby_id, reply-to)", expanded=True):
    test_token = st.text_input(
        "Bearer token (optional)",
        value=st.session_state.get("test_token", ""),
        placeholder="paste JWT here, or leave blank to test with no auth"
    )
    st.session_state.test_token = test_token

    test_baby_id = st.text_input(
        "baby_id (only needed if parent has multiple babies)",
        value=st.session_state.get("test_baby_id", ""),
        placeholder="e.g. 7 — leave blank for single-baby auto-resolve"
    )
    st.session_state.test_baby_id = test_baby_id

    # Build the reply-to options from this session's posted messages.
    # Only assistant messages are valid reply targets — replying to a user's
    # own question isn't a real product scenario (per Integration Guide 2:
    # parents reply to answers, not to questions).
    if "post_ids" not in st.session_state:
        st.session_state.post_ids = []  # list of (post_id, role, short_label)

    reply_label_to_id = {
        f"#{pid} (bot): {label}": pid
        for pid, role, label in st.session_state.post_ids
        if role == "assistant"
    }
    fresh_option = "— none, this is a fresh question —"
    reply_options = [fresh_option] + list(reply_label_to_id.keys())
    reply_choice = st.selectbox(
        "Reply to a previous bot answer in this test session",
        reply_options,
        key="reply_to_selector"
    )

    st.session_state.reply_to_post_id = reply_label_to_id.get(reply_choice)  # None if fresh_option chosen


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
    reply_to_id      = st.session_state.get("reply_to_post_id")

    # ── TEST-BRANCH: resolve the reply chain from the DB instead of
    # using a flat running history — this is what Java would do by
    # walking reply_to_id backward, per Integration Guide (2).
    resolved_history = resolve_chain(reply_to_id) if reply_to_id else []

    token_input = st.session_state.get("test_token", "").strip()
    baby_id_input = st.session_state.get("test_baby_id", "").strip()

    headers = {}
    if token_input:
        headers["Authorization"] = f"Bearer {token_input}"

    payload = {
        "message": user_input,
        "history": resolved_history,
        "query_subject": current_subject
    }
    if baby_id_input:
        try:
            payload["baby_id"] = int(baby_id_input)
        except ValueError:
            st.warning("baby_id must be a number — ignoring it for this request.")

    with st.chat_message("assistant", avatar="🌸"):
        with st.spinner(""):
            try:
                response = requests.post(
                    f"{API_URL}/chat",
                    json=payload,
                    headers=headers,
                    timeout=30
                )
                data              = response.json()
                reply             = data.get("reply", "Something went wrong.")
                mode              = data.get("mode",  "fallback")
                score             = data.get("score", 0.0)
                response_time_ms  = data.get("response_time_ms", 0)
                query_subject     = data.get("query_subject", current_subject)
            except requests.exceptions.ConnectionError:
                reply             = "Unable to reach the server. Please try again in a moment."
                mode              = "error"
                score             = 0.0
                response_time_ms  = 0
                query_subject     = current_subject

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

            # ── TEST-BRANCH: show the exact chain length / approx size sent,
            # so you can watch cost grow as chains get deeper.
            chain_pairs = len(resolved_history) // 2
            approx_chars = sum(len(m["content"]) for m in resolved_history) + len(user_input)
            st.caption(f"🧪 chain depth: {chain_pairs} prior pair(s) · ~{approx_chars} chars sent this call")

    # ── TEST-BRANCH: persist this exchange as two posts (user + assistant)
    # in community_posts, and log the turn to ml_chat_logs, mirroring what
    # Java would do — lets you inspect both tables' real row shapes after.
    parent_id_for_log = extract_parent_id_from_token(token_input) if token_input else None
    baby_id_for_log    = baby_id_input if baby_id_input else None

    user_post_id = save_post(
        parent_id=parent_id_for_log,
        baby_id=baby_id_for_log,
        query_subject=current_subject,
        role="user",
        content=user_input,
        reply_to_id=reply_to_id
    )
    assistant_post_id = save_post(
        parent_id=parent_id_for_log,
        baby_id=baby_id_for_log,
        query_subject=current_subject,
        role="assistant",
        content=reply,
        reply_to_id=user_post_id
    )

    if user_post_id is not None:
        short_label = (user_input[:30] + "…") if len(user_input) > 30 else user_input
        st.session_state.post_ids.append((user_post_id, "user", short_label))
    if assistant_post_id is not None:
        short_label = (reply[:30] + "…") if len(reply) > 30 else reply
        st.session_state.post_ids.append((assistant_post_id, "assistant", short_label))

    log_ml_chat(
        parent_id=parent_id_for_log,
        baby_id=baby_id_for_log,
        query=user_input,
        raw_bot_response=reply,
        mode=mode,
        score=score,
        response_time_ms=response_time_ms,
        query_subject=query_subject,
        history_context=resolved_history
    )

    st.session_state.messages.append({
        "role":    "assistant",
        "content": reply,
        "meta":    {"mode": mode, "score": score, "query_subject": query_subject}
    })
    # Note: flat st.session_state.history is no longer used for the /chat call —
    # the chain sent as `history` is resolved fresh from community_posts based
    # on the "reply to" selection above. Reset the reply-to selector after send
    # so the next message defaults to "fresh question" unless explicitly chosen.
    st.session_state.reply_to_post_id = None
    st.rerun()