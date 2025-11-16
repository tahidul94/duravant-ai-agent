# app.py

import os
import io
import streamlit as st
import pandas as pd

from openai import OpenAI

# Optional: for PDFs
try:
    import pypdf
except ImportError:
    pypdf = None


# ---------- OpenAI client ----------
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL_SUMMARY = "gpt-4.1-mini"
MODEL_CHAT = "gpt-4.1-mini"


# ---------- UI helpers ----------
def show_header():
    # If you have a logo.png in the same folder, it will show here
    try:
        st.image("logo.png", width=200)
    except Exception:
        pass

    st.title("Duravant Digital Assistant")
    st.caption(
        "Duravant assistant for SAP & Dynamics 365 reports, "
        "incident logs, quality records, and maintenance documents."
    )
    st.markdown("---")


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
    # Read all sheets and join them
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
    elif name.endswith(".xlsx") or name.endswith(".xls"):
        return extract_text_from_excel(buffer)
    elif name.endswith(".txt"):
        return file_bytes.decode(errors="ignore")
    else:
        # Fallback: try decode as text
        try:
            return file_bytes.decode(errors="ignore")
        except Exception:
            return "Unsupported file type. Please upload PDF, CSV, XLSX, or TXT."


# ---------- LLM calls ----------
def generate_summary(report_text: str) -> str:
    """
    Generate a structured summary of the uploaded report.
    """
    # Truncate very long inputs for safety
    trimmed = report_text[:15000]

    system_prompt = (
        "You are the Duravant Digital Assistant. You analyze manufacturing and ERP-related "
        "documents such as downtime reports, production summaries, quality logs, change requests, "
        "and service reports.\n\n"
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
    """
    Answer questions using the report text + summary + chat history.
    """
    # Truncate context to keep tokens reasonable
    report_snippet = report_text[:15000]
    summary_snippet = summary[:6000]

    system_prompt = (
        "You are the Duravant Digital Assistant, a ChatGPT-style assistant that answers questions "
        "about manufacturing and ERP-related documents.\n\n"
        "You MUST base your answers only on:\n"
        "1) The original report text\n"
        "2) The generated summary\n"
        "3) The prior conversation history\n\n"
        "If the user asks for information that is not present in the report, clearly say:\n"
        "'The report does not contain that information.'\n\n"
        "Be clear, concise, and use professional manufacturing/operations language."
    )

    messages = [{"role": "system", "content": system_prompt}]

    # Inject context as an assistant message up front
    context_block = (
        "Here is the current report context.\n\n"
        "=== SUMMARY ===\n"
        f"{summary_snippet}\n\n"
        "=== ORIGINAL REPORT TEXT (SNIPPET) ===\n"
        f"{report_snippet}\n"
    )
    messages.append({"role": "assistant", "content": context_block})

    # Add prior chat history (user/assistant turns)
    for turn in chat_history:
        messages.append(turn)

    # Add current user question
    messages.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
        model=MODEL_CHAT,
        messages=messages,
        temperature=0.2,
    )

    return response.choices[0].message.content.strip()


# ---------- Session state helpers ----------
def init_session_state():
    if "report_text" not in st.session_state:
        st.session_state.report_text = ""
    if "summary" not in st.session_state:
        st.session_state.summary = ""
    if "chat_history" not in st.session_state:
        # list of {"role": "user"/"assistant", "content": "..."}
        st.session_state.chat_history = []


def reset_conversation():
    st.session_state.chat_history = []


# ---------- Main app ----------
def main():
    st.set_page_config(
        page_title="Duravant Digital Assistant",
        page_icon="🤖",
        layout="wide",
    )

    init_session_state()
    show_header()

    # Sidebar: file upload & controls
    with st.sidebar:
        st.subheader("1. Upload a report")
        uploaded_file = st.file_uploader(
            "Upload SAP/D365 reports, incident logs, quality or service reports",
            type=["pdf", "csv", "xlsx", "xls", "txt"],
        )

        if st.button("Reset conversation"):
            reset_conversation()
            st.success("Conversation reset. You can start fresh questions.")

        st.markdown("---")
        st.caption(
            "Tip: Good examples include downtime reports, production summaries, "
            "quality logs, change requests, or service reports."
        )

    # If user uploaded a file and no report loaded yet OR filename changed
    if uploaded_file is not None:
        if "last_filename" not in st.session_state or st.session_state.last_filename != uploaded_file.name:
            # New file uploaded -> parse again and reset conversation
            with st.spinner("Reading and analyzing the report..."):
                report_text = load_report_text(uploaded_file)
                st.session_state.report_text = report_text
                st.session_state.summary = generate_summary(report_text)
                st.session_state.last_filename = uploaded_file.name
                reset_conversation()
            st.success("Report processed and summary generated.")

    # Layout: two columns (summary + chat)
    col_summary, col_chat = st.columns([1, 2])

    with col_summary:
        st.subheader("Report Summary")
        if st.session_state.summary:
            st.markdown(st.session_state.summary)
        else:
            st.info("Upload a report on the left sidebar to generate a summary.")

    with col_chat:
        st.subheader("Chat with the report")

        if not st.session_state.report_text:
            st.info("Upload a report first, then you can ask questions here.")
        else:
            # Display existing chat history
            for turn in st.session_state.chat_history:
                with st.chat_message(turn["role"]):
                    st.markdown(turn["content"])

            # Chat input
            user_input = st.chat_input("Ask a question about this report...")
            if user_input:
                # Show user message
                st.session_state.chat_history.append(
                    {"role": "user", "content": user_input}
                )
                with st.chat_message("user"):
                    st.markdown(user_input)

                # Get assistant reply
                with st.chat_message("assistant"):
                    with st.spinner("Thinking..."):
                        reply = chat_with_report(
                            user_message=user_input,
                            report_text=st.session_state.report_text,
                            summary=st.session_state.summary,
                            chat_history=st.session_state.chat_history,
                        )
                        st.markdown(reply)

                # Store assistant reply
                st.session_state.chat_history.append(
                    {"role": "assistant", "content": reply}
                )


if __name__ == "__main__":
    main()
