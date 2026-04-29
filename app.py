import streamlit as st
import requests

API_URL = "http://localhost:8000"

st.set_page_config(page_title="Momify", page_icon="👶", layout="centered")
st.title(" Momify")
st.caption("Baby health assistant · English & Hinglish")
st.divider()

if "messages" not in st.session_state:
    st.session_state.messages = []
if "history" not in st.session_state:
    st.session_state.history = []

if st.button("🗑️ Clear chat"):
    st.session_state.messages = []
    st.session_state.history = []
    st.rerun()

for msg in st.session_state.messages:
    avatar = "👩" if msg["role"] == "user" else "👶"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

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
                print(data)
                reply = data["reply"]
            except requests.exceptions.ConnectionError:
                reply = "❌ Cannot connect to API. Make sure main.py is running on port 8000."

        st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.session_state.history.append({"role": "user",      "content": user_input})
    st.session_state.history.append({"role": "assistant", "content": reply})
