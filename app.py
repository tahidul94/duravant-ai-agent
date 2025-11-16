# app.py

import os
import io
import streamlit as st
import pandas as pd
from openai import OpenAI

# Optional PDF support
try:
    import pypdf
except ImportError:
    pypdf = None


# ---------- OpenAI client ----------
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL_SUMMARY = "gpt-4.1-mini"
MODEL_CHAT = "gpt-4.1-mini"


# ---------- Header ----------
def show_header():
    # Show logo if present
    if os.path.exists("logo.png"):
        st.image("logo.png", width=180)
    st.title("Duravant Digital Assistant")
    st.caption(
        "Upload a report to generate a summary, then ask follow-up questions."
    )
    st.markdown("---")


# ---------- File parsing ----------
def extract_text_from_pdf(file) -> str:
    if pypdf is None:
        return "PDF support not available. Install pypdf."

    reader = pypdf.PdfReader(file)
    pages = []
    for p in reader.pages:
        try:
            pages.append(p.extract_text() or "")
        except:
            pages.append("")
    return "\n\n".join(pages)


def extract_text_from_csv(file) -> str:
    df = pd.read_csv(file)
    return df.to_string(index=False)


def extract_text_from_excel(file) -> str:
    xls = pd.ExcelFile(file)
    out = []
    for sheet in xls.sheet_names:
        df = xls.parse(sheet)
        out.append(f"== Sheet: {sheet} ==\n{df.to_string(index=False)}")
    return "\n\n".join(out)


def load_report_text(uploaded_file) -> str:
    if uploaded_file is None:
        return ""

    bytes_data = uploaded_file.read()
    buffer = io.BytesIO(bytes_data)
    name = uploaded_file.name.lower()

    if name.endswith(".pdf"):
        return extract_text_from_pdf(buffer)
    elif name.endswith(".csv"):
        return extract_text_from_csv(buffer)
    elif name.endswith((".xlsx", ".xls")):
        return extract_text_from_excel(buffer)
    elif name.endswith(".txt"):
        return bytes_data.decode(errors="ignore")
    else:
        try:
            return bytes_data.decode(errors="ignore")
        except:
            return "Unsupported file format."


# ---------- LLM handlers ----------
def generate_summary(report_text: str) -> str:
    prompt = (
        "You are the Duravant Digital Assistant. Summarize the following report using this structure:\n\n"
        "1. Summary of Issue or Topic\n"
        "2. Technical Findings / Key Details\n"
        "3. Business Impact\n"
        "4. Immediate Corrective Actions\n"
        "5. Follow-up Recommendations\n\n"
        "Keep it concise and only based on the content provided."
    )

    response = client.chat.completions.create(
        model=MODEL_SUMMARY,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": report_text[:15000]},
        ],
        temperature=0,
    )

    return response.choices[0].message.content.strip()


def chat_with_report(user_text: str, report_text: str, summary: str, history: list):
    system_prompt = (
        "You are the Duravant Digital Assistant. Answer questions ONLY using:\n"
        "- The uploaded report\n"
        "- The summary\n"
        "- The chat history\n\n"
        "If the user asks something not in the report, say: "
        "'The report does not contain that information.'"
    )

    messages = [{"role": "system", "content": system_prompt}]

    # Add context
    context = (
        "=== SUMMARY ===\n" + summary[:6000] +
        "\n\n=== REPORT CONTENT (trimmed) ===\n" + report_text[:15000]
    )
    messages.append({"role": "assistant", "content": context})

    # Add previous conversation
    for turn in history:
        messages.append(turn)

    # Add new question
    messages.append({"role": "user", "content": user_text})

    response = client.chat.completions.create(
        model=MODEL_CHAT,
        messages=messages,
        temperature=0,
    )

    return response.choices[0].message.content.strip()


# ---------- Session State ----------
def init_state():
    for key in ["report_text", "summary", "chat_history", "last_file"]:
        if key not in st.session_state:
            st.session_state[key] = None if key != "chat_history" else []


def reset_chat():
    st.session_state.chat_history = []


# ---------- MAIN ----------
def main():
    st.set_page_config(page_title="Duravant Digital Assistant", layout="wide")

    init_state()
    show_header()

    # Sidebar
    with st.sidebar:
        st.subheader("Upload a report")
        uploaded = st.file_uploader(
            "PDF, CSV, Excel or TXT",
            type=["pdf", "csv", "xlsx", "xls", "txt"]
        )

        if st.button("Reset conversation"):
            reset_chat()
            st.success("Conversation cleared.")

        st.markdown("---")
        st.caption("Examples: downtime reports, service reports, quality logs, maintenance logs, change requests.")

    # New file uploaded
    if uploaded and uploaded.name != st.session_state.last_file:
        with st.spinner("Reading and summarizing report..."):
            report_text = load_report_text(uploaded)
            st.session_state.report_text = report_text
            st.session_state.summary = generate_summary(report_text)
            st.session_state.last_file = uploaded.name
            reset_chat()
        st.success("Summary generated. Scroll down to review.")

    # Summary Section
    st.subheader("Report Summary")
    if st.session_state.summary:
        st.markdown(st.session_state.summary)
    else:
        st.info("Upload a report to generate a summary.")

    st.markdown("---")

    # Chat Section
    if st.session_state.summary:
        st.subheader("Chat with the report")

        # Show previous messages
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # Input
        user_input = st.chat_input("Ask a question...")
        if user_input:
            # Show user message
            st.chat_message("user").markdown(user_input)

            # Generate reply
            reply = chat_with_report(
                user_input,
                st.session_state.report_text,
                st.session_state.summary,
                st.session_state.chat_history,
            )

            st.chat_message("assistant").markdown(reply)

            # Store in history
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            st.session_state.chat_history.append({"role": "assistant", "content": reply})


if __name__ == "__main__":
    main()
