# app.py

import os
import io
import streamlit as st
import pandas as pd
from openai import OpenAI

# Optional: PDF parsing
try:
    import pypdf
except ImportError:
    pypdf = None


# ---------- OpenAI client ----------
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL_SUMMARY = "gpt-4.1-mini"
MODEL_CHAT = "gpt-4.1-mini"


# ---------- Minimal styling ----------
def inject_custom_css():
    st.markdown(
        """
        <style>
        .stApp {
            background-color: #f3f4f6;
        }
        html, body, [class^="css"] {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }

        .da-header {
            padding: 10px 4px 16px 4px;
            border-bottom: 1px solid #e5e7eb;
            margin-bottom: 10px;
        }
        .da-title {
            font-size: 28px;
            font-weight: 600;
            color: #111827;
            margin-bottom: 4px;
        }
        .da-subtitle {
            color: #6b7280;
            font-size: 14px;
        }

        .da-card {
            background-color: #ffffff;
            border-radius: 12px;
            padding: 18px 20px;
            border: 1px solid #e5e7eb;
            box-shadow: 0 1px 4px rgba(15, 23, 42, 0.04);
            margin-top: 12px;
        }
        .da-card-title {
            font-weight: 600;
            color: #111827;
            font-size: 14px;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }

        section[data-testid="stSidebar"] {
            background-color: #111827;
        }
        section[data-testid="stSidebar"] * {
            color: #e5e7eb !important;
        }
        section[data-testid="stSidebar"] .stButton>button {
            background-color: #f9fafb;
            color: #111827;
            border-radius: 999px;
            border: none;
            font-weight: 500;
        }

        [data-testid="stChatMessage"] {
            border-radius: 10px;
            padding: 10px 12px !important;
            margin-bottom: 6px;
        }

        .stChatInputContainer {
            border-radius: 999px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------- Header ----------
def show_header():
    st.markdown(
        """
        <div class="da-header">
            <div class="da-title">Duravant Digital Assistant</div>
            <div class="da-subtitle">
                Upload a report to get a structured summary, then ask follow-up questions in a chat-style interface.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------- File handling / text extraction ----------
def extract_text_from_pdf(file) -> str:
    if pypdf is None:
        return "PDF support not available. Install 'pypdf' to enable PDF parsing."

    reader = pypdf.PdfReader(file)
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n\n".join(pages)


def extract_text_from_csv(file) -> str:
    df = pd.read_csv(file)
    return df.to_string(index=False)


def extract_text_from_excel(file) -> str:
    xls = pd.ExcelFile(file)
    parts = []
    for sheet in xls.sheet_names:
        df = xls.parse(sheet)
        parts.append(f"=== Sheet: {sheet} ===\n{df.to_string(index=False)}")
    return "\n\n".join(parts)


def load_report_text(uploaded_file) -> str:
    if uploaded_file is None:
        return ""

    file_bytes = uploaded_file.read()
    buffer = io.BytesIO(file_bytes)
    name = uploaded_file.name.lower()

    if name.endswith(".pdf"):
        return extract_text_from_pdf(buffer)
    elif name.endswith(".csv"):
        return extract_text_from_csv(buffer)
    elif name.endswith((".xlsx", ".xls")):
        return extract_text_from_excel(buffer)
    elif name.endswith(".txt"):
        return file_bytes.decode(errors="ignore")
    else:
        try:
            return file_bytes.decode(errors="ignore")
        except Exception:
            return "Unsupported file type. Please upload PDF, CSV, XLSX, or TXT."


# ---------- LLM helpers ----------
def generate_summary(report_text: str) -> str:
    trimmed = report_text[:15000]

    system_prompt = (
        "You are the Duravant Digital Assistant. You analyze manufacturing and ERP-related "
        "documents such as downtime reports, production summaries, quality logs, change requests, "
        "service reports, and maintenance records.\n\n"
        "Summarize the content in the following structured format:\n"
        "1) Summary of Issue or Topic\n"
        "2) Technical Findings / Key Details\n"
        "3) Business Impact\n"
        "4) Immediate Corrective Actions (if applicable)\n"
        "5) Follow-up Recommendations\n\n"
        "Use concise bullet points. If a section is not relevant, write 'Not specified in the report.'"
    )

    response = client.chat.completions.create(
        model=MODEL_SUMMARY,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": trimmed},
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content.strip()


def chat_with_report(user_message: str, report_text: str, summary: str, chat_history: list) -> str:
    report_snippet = report_text[:15000]
    summary_snippet = summary[:6000]

    system_prompt = (
        "You are the Duravant Digital Assistant, a conversational assistant that answers questions "
        "about manufacturing and ERP-related documents.\n\n"
        "You MUST base your answers only on:\n"
        "1) The original report text\n"
        "2) The generated summary\n"
        "3) The prior conversation history\n\n"
        "If the user asks for information that is not present in the report, clearly say:\n"
        "'The report does not contain that information.'\n\n"
        "Be clear, concise, and use professional language."
    )

    messages = [{"role": "system", "content": system_prompt}]

    context_block = (
        "Here is the current report context.\n\n"
        "=== SUMMARY ===\n"
        f"{summary_snippet}\n\n"
        "=== ORIGINAL REPORT TEXT (SNIPPET) ===\n"
        f"{report_snippet}\n"
    )
    messages.append({"role": "assistant", "content": context_block})

    for turn in chat_history:
        messages.append(turn)

    messages.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
        model=MODEL_CHAT,
        messages=messages,
        temperature=0.2,
    )

    return response.choices[0].message.content.strip()


# ---------- Session state ----------
def init_session_state():
    if "report_text" not in st.session_state:
        st.session_state.report_text = ""
    if "summary" not in st.session_state:
        st.session_state.summary = ""
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "last_filename" not in st.session_state:
        st.session_state.last_filename = None


def reset_conversation():
    st.session_state.chat_history = []


# ---------- Main app ----------
def main():
    st.set_page_config(
        page_title="Duravant Digital Assistant",
        page_icon="🤖",
        layout="wide",
    )

    inject_custom_css()
    init_session_state()
    show_header()

    # Sidebar (simple)
    with st.sidebar:
        st.markdown("### Upload a report")
        uploaded_file = st.file_uploader(
            "PDF, CSV, Excel, or TXT",
            type=["pdf", "csv", "xlsx", "xls", "txt"],
        )

        if st.button("Reset conversation"):
            reset_conversation()
            st.success("Conversation reset.")

        st.markdown("---")
        st.caption(
            "Examples: downtime reports, production summaries, incident reports, "
            "quality logs, change requests, service and maintenance reports."
        )

    # Handle new upload -> summary first
    if uploaded_file is not None and st.session_state.last_filename != uploaded_file.name:
        with st.spinner("Reading and summarizing the report..."):
            report_text = load_report_text(uploaded_file)
            st.session_state.report_text = report_text
            st.session_state.summary = generate_summary(report_text)
            st.session_state.last_filename = uploaded_file.name
            reset_conversation()
        st.success("Summary generated. Review it below, then ask questions.")

    # SUMMARY CARD (always above chat)
    st.markdown(
        '<div class="da-card"><div class="da-card-title">Report Summary</div>',
        unsafe_allow_html=True,
    )

    if st.session_state.summary:
        st.markdown(st.session_state.summary)
    else:
        st.info("Upload a report in the sidebar to generate a summary.")

    st.markdown("</div>", unsafe_allow_html=True)

    # Only show chat section AFTER we have a summary
    if st.session_state.summary:
        st.markdown(
            '<div class="da-card"><div class="da-card-title">Chat with the report</div>',
            unsafe_allow_html=True,
        )

        if not st.session_state.report_text:
            st.info("Upload a report first.")
        else:
            # Existing history
            for turn in st.session_state.chat_history:
                with st.chat_message(turn["role"]):
                    st.markdown(turn["content"])

            # New question
            user_input = st.chat_input("Ask a question about this report...")
            if user_input:
                # Show user message
                with st.chat_message("user"):
                    st.markdown(user_input)

                # Get answer
                with st.chat_message("assistant"):
                    with st.spinner("Thinking..."):
                        reply = chat_with_report(
                            user_message=user_input,
                            report_text=st.session_state.report_text,
                            summary=st.session_state.summary,
                            chat_history=st.session_state.chat_history,
                        )
                        st.markdown(reply)

                # Save history
                st.session_state.chat_history.extend(
                    [
                        {"role": "user", "content": user_input},
                        {"role": "assistant", "content": reply},
                    ]
                )

        st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
