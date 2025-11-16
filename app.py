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


# ---------- Styling ----------
def inject_custom_css():
    st.markdown(
        """
        <style>
        /* Global layout / colors */
        .stApp {
            background-color: #f3f4f6;
        }
        html, body, [class^="css"] {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }

        /* Header */
        .da-header {
            padding: 10px 4px 24px 4px;
            border-bottom: 1px solid #e5e7eb;
            margin-bottom: 10px;
        }
        .da-title {
            font-size: 30px;
            font-weight: 600;
            color: #0f172a;
            margin-bottom: 4px;
        }
        .da-subtitle {
            color: #6b7280;
            font-size: 15px;
        }

        /* Hero metric cards */
        .da-metric-card {
            background-color: #ffffff;
            border-radius: 12px;
            padding: 12px 16px;
            border: 1px solid #e5e7eb;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
            font-size: 13px;
        }
        .da-metric-label {
            text-transform: uppercase;
            font-weight: 600;
            letter-spacing: 0.07em;
            font-size: 11px;
            color: #6b7280;
            margin-bottom: 2px;
        }

        /* Main content cards */
        .da-card {
            background-color: #ffffff;
            border-radius: 14px;
            padding: 18px 20px;
            border: 1px solid #e5e7eb;
            box-shadow: 0 2px 6px rgba(15, 23, 42, 0.04);
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

        /* Sidebar */
        section[data-testid="stSidebar"] {
            background-color: #111827;
            color: #e5e7eb;
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

        /* Chat bubbles (very light styling to keep it robust to changes) */
        [data-testid="stChatMessage"] {
            border-radius: 10px;
            padding: 12px 14px !important;
            margin-bottom: 6px;
        }

        /* Chat input */
        .stChatInputContainer {
            border-radius: 999px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------- Header ----------
def show_header():
    with st.container():
        col_logo, col_text = st.columns([1, 4])

        with col_logo:
            try:
                st.image("logo.png", use_column_width=True)
            except Exception:
                st.markdown("### 🤖")

        with col_text:
            st.markdown(
                """
                <div class="da-header">
                    <div class="da-title">Duravant Digital Assistant</div>
                    <div class="da-subtitle">
                        Modern AI copilot for SAP &amp; Dynamics 365 reports, incident logs, quality records, and maintenance documents.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Small metric cards under header
        m1, m2, m3 = st.columns(3)
        with m1:
            st.markdown(
                """
                <div class="da-metric-card">
                    <div class="da-metric-label">Report types</div>
                    Downtime • Quality • Service • Change Requests
                </div>
                """,
                unsafe_allow_html=True,
            )
        with m2:
            st.markdown(
                """
                <div class="da-metric-card">
                    <div class="da-metric-label">Outputs</div>
                    Structured summaries, root causes, business impact, actions
                </div>
                """,
                unsafe_allow_html=True,
            )
        with m3:
            st.markdown(
                """
                <div class="da-metric-card">
                    <div class="da-metric-label">Interaction</div>
                    Chat-style Q&amp;A grounded in uploaded reports
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
    """Generate a structured summary of the uploaded report."""
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
    """Answer questions using the report text + summary + chat history."""
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
        "Be clear, concise, and use professional language suitable for operations, maintenance, "
        "supply chain, and finance stakeholders."
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

    # Sidebar
    with st.sidebar:
        st.markdown("### 📂 Step 1: Upload a report")
        uploaded_file = st.file_uploader(
            "SAP/D365 exports, incident logs, quality or service reports",
            type=["pdf", "csv", "xlsx", "xls", "txt"],
        )

        st.markdown("### 💬 Step 2: Ask questions")
        st.caption(
            "Once the summary is generated, use the chat panel to explore causes, impacts, and actions."
        )

        if st.button("Reset conversation"):
            reset_conversation()
            st.success("Conversation reset.")

        st.markdown("---")
        st.caption(
            "Good candidates: downtime reports, production summaries, quality logs, "
            "change requests, service reports, maintenance records."
        )

    # Handle new upload
    if uploaded_file is not None:
        if st.session_state.last_filename != uploaded_file.name:
            with st.spinner("Reading and analyzing the report..."):
                report_text = load_report_text(uploaded_file)
                st.session_state.report_text = report_text
                st.session_state.summary = generate_summary(report_text)
                st.session_state.last_filename = uploaded_file.name
                reset_conversation()
            st.success("Report processed and summary generated.")

    # Main layout
    col_summary, col_chat = st.columns([1, 2])

    # Summary card
    with col_summary:
        st.markdown(
            '<div class="da-card"><div class="da-card-title">Report Summary</div>',
            unsafe_allow_html=True,
        )

        if st.session_state.summary:
            st.markdown(st.session_state.summary)
        else:
            st.info("Upload a report in the sidebar to generate a summary.")

        st.markdown("</div>", unsafe_allow_html=True)

    # Chat card
    with col_chat:
        st.markdown(
            '<div class="da-card"><div class="da-card-title">Chat with the report</div>',
            unsafe_allow_html=True,
        )

        if not st.session_state.report_text:
            st.info("Upload a report first, then you can ask questions here.")
        else:
            # Show history
            for turn in st.session_state.chat_history:
                with st.chat_message(turn["role"]):
                    st.markdown(turn["content"])

            # New input
            user_input = st.chat_input("Ask a question about this report...")
            if user_input:
                # Show user message immediately
                with st.chat_message("user"):
                    st.markdown(user_input)

                # Get assistant answer
                with st.chat_message("assistant"):
                    with st.spinner("Thinking..."):
                        reply = chat_with_report(
                            user_message=user_input,
                            report_text=st.session_state.report_text,
                            summary=st.session_state.summary,
                            chat_history=st.session_state.chat_history,
                        )
                        st.markdown(reply)

                # Update history
                st.session_state.chat_history.extend(
                    [
                        {"role": "user", "content": user_input},
                        {"role": "assistant", "content": reply},
                    ]
                )

        st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
