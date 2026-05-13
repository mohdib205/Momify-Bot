import streamlit as st
import requests
import psycopg2
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

API_URL = "http://localhost:8000"

st.set_page_config(page_title="Momify", page_icon="👶", layout="centered")
st.title("Momify")
st.caption("Baby health assistant · English & Hinglish")
st.divider()


# ════════════════════════════════════════
# DB — save feedback
# ════════════════════════════════════════

def save_feedback(query, bot_response, mode, score, verdict, failure_reason, doctor_notes, reviewed_by):
    db_url = os.environ.get("DB_URL", "")
    if not db_url:
        try:
            db_url = st.secrets.get("DB_URL", "")
        except Exception:
            db_url = ""
    if not db_url:
        st.error("DB_URL not set. Feedback cannot be saved.")
        return False
    try:
        conn = psycopg2.connect(db_url)
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO doctor_feedback
                (query, bot_response, mode, score, verdict, failure_reason, doctor_notes, reviewed_by, reviewed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (query, bot_response, mode, score, verdict, failure_reason, doctor_notes, reviewed_by, datetime.now()))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Failed to save feedback: {e}")
        return False


# ════════════════════════════════════════
# Session state init
# ════════════════════════════════════════

if "messages"            not in st.session_state: st.session_state.messages           = []
if "history"             not in st.session_state: st.session_state.history            = []
if "feedback_submitted"  not in st.session_state: st.session_state.feedback_submitted = {}


# ════════════════════════════════════════
# Sidebar — doctor mode
# ════════════════════════════════════════

with st.sidebar:
    st.header("👨‍⚕️ Doctor Review Mode")
    doctor_mode = st.toggle("Enable feedback panel", value=False)

    if doctor_mode:
        doctor_name = st.text_input(
            "Your name / ID",
            placeholder="Dr. Sharma",
            value=st.session_state.get("doctor_name", "")
        )
        st.session_state.doctor_name = doctor_name
        if not doctor_name.strip():
            st.warning("Enter your name to submit feedback.")
        else:
            st.success(f"Reviewing as: {doctor_name}")

    st.divider()
    if st.button("🗑️ Clear chat"):
        st.session_state.messages           = []
        st.session_state.history            = []
        st.session_state.feedback_submitted = {}
        st.rerun()


# ════════════════════════════════════════
# Render chat history
# ════════════════════════════════════════

for idx, msg in enumerate(st.session_state.messages):

    # User bubble
    if msg["role"] == "user":
        with st.chat_message("user", avatar="👩"):
            st.markdown(msg["content"])

    # Bot bubble
    else:
        with st.chat_message("assistant", avatar="👶"):
            st.markdown(msg["content"])

            # mode / score badge
            if "meta" in msg:
                mode  = msg["meta"].get("mode", "")
                score = msg["meta"].get("score", 0.0)
                color = {"data": "green", "weak": "orange", "fallback": "red"}.get(mode, "gray")
                st.caption(f":{color}[mode: {mode} | score: {score:.3f}]")

            # Feedback panel — doctor mode only
            if doctor_mode and "meta" in msg:
                feedback_key      = f"feedback_{idx}"
                already_submitted = st.session_state.feedback_submitted.get(feedback_key, False)

                if already_submitted:
                    st.success("✅ Feedback submitted")
                else:
                    with st.expander("📋 Leave feedback", expanded=False):

                        # Show parent's query for context
                        user_query = ""
                        if idx > 0 and st.session_state.messages[idx - 1]["role"] == "user":
                            user_query = st.session_state.messages[idx - 1]["content"]
                        if user_query:
                            st.markdown(f"**Parent asked:** _{user_query}_")
                            st.divider()

                        verdict = st.radio(
                            "Response verdict",
                            ["✅ Correct", "⚠️ Partially correct", "❌ Incorrect"],
                            horizontal=True,
                            key=f"verdict_{idx}"
                        )

                        failure_reason = ""
                        if verdict != "✅ Correct":
                            failure_reason = st.selectbox(
                                "What was wrong?",
                                [
                                    "— select —",
                                    "Should have given home remedy first",
                                    "Should NOT have mentioned medicine",
                                    "Wrong medicine category named",
                                    "Missing important advice",
                                    "Language / tone issue",
                                    "Gave dose / frequency / duration",
                                    "Said 'consult doctor' incorrectly",
                                    "Other"
                                ],
                                key=f"reason_{idx}"
                            )

                        doctor_notes = st.text_area(
                            "Notes — what should the correct response have been?",
                            placeholder="e.g. Should have suggested saline drops first.",
                            height=80,
                            key=f"notes_{idx}"
                        )

                        doctor_name    = st.session_state.get("doctor_name", "").strip()
                        submit_disabled = not doctor_name

                        if st.button("Submit feedback", key=f"submit_{idx}", disabled=submit_disabled):
                            if verdict != "✅ Correct" and failure_reason == "— select —":
                                st.error("Please select what was wrong before submitting.")
                            else:
                                success = save_feedback(
                                    query          = user_query,
                                    bot_response   = msg["content"],
                                    mode           = msg["meta"].get("mode", ""),
                                    score          = msg["meta"].get("score", 0.0),
                                    verdict        = verdict.split(" ", 1)[1].strip(),
                                    failure_reason = failure_reason if failure_reason != "— select —" else "",
                                    doctor_notes   = doctor_notes,
                                    reviewed_by    = doctor_name
                                )
                                if success:
                                    st.session_state.feedback_submitted[feedback_key] = True
                                    st.rerun()


# ════════════════════════════════════════
# Chat input
# ════════════════════════════════════════

user_input = st.chat_input("Ask about your baby...")

if user_input:

    with st.chat_message("user", avatar="👩"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    with st.chat_message("assistant", avatar="👶"):
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
                reply = "❌ Cannot connect to API. Make sure main.py is running on port 8000."
                mode  = "error"
                score = 0.0

        st.markdown(reply)

        if mode != "error":
            color = {"data": "green", "weak": "orange", "fallback": "red"}.get(mode, "gray")
            st.caption(f":{color}[mode: {mode} | score: {score:.3f}]")

    st.session_state.messages.append({
        "role":    "assistant",
        "content": reply,
        "meta":    {"mode": mode, "score": score}
    })
    st.session_state.history.append({"role": "user",      "content": user_input})
    st.session_state.history.append({"role": "assistant", "content": reply})
    st.rerun()