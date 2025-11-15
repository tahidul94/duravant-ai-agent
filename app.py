import os

from dotenv import load_dotenv
from openai import OpenAI
import streamlit as st
import pdfplumber
import docx
from PIL import Image

# ---------------------- Config & Client ----------------------

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    st.error(
        "OPENAI_API_KEY is not set. "
        "Please configure it in Streamlit secrets or your .env file."
    )
    st.stop()

client = OpenAI(api_key=api_key)

# Limit to keep very large reports under control
MAX_CHARS = 16000


# ---------------------- Helpers ----------------------


def extract_text_from_pdf(uploaded_pdf) -> str:
    """Extract text from a PDF file."""
    text = ""
    with pdfplumber.open(uploaded_pdf) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text


def extract_text_from_docx(uploaded_docx) -> str:
    """Extract text from a DOCX file."""
    document = docx.Document(uploaded_docx)
    paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def summarize_report(report_text: str) -> str:
    """Call OpenAI to summarize the report in a structured, business-friendly way."""

    trimmed_text = report_text[:MAX_CHARS]

    prompt = f"""
You are the **Duravant Digital Assistant**, supporting IT, SAP, and operations teams.

You receive reports exported from systems like SAP, Dynamics 365, or plant-floor tools.
Your job is to turn them into a concise, executive-ready summary that busy managers
and analysts can act on quickly.

Using the report below, produce three sections using clear markdown headings:

## Executive Summary
8–10 sentences explaining the situation in plain business language. Mention process,
systems, plants, or customers if relevant.

## Key Points
5–8 bullet points capturing the most important facts, metrics, risks, and decisions.

## Recommended Actions
3–6 specific, action-oriented bullet points. Focus on what operations, IT/SAP, or
management should do next.

Report:
\"\"\"{trimmed_text}\"\"\"
"""

    response = client.responses.create(
        model="gpt-4o-mini",
        input=prompt,
    )

    return response.output[0].content[0].text


def show_header():
    # If you named the file differently, change "logo.png" below
    try:
        logo = Image.open("logo.png")
        st.image(logo, width=200)
    except Exception:
        # If logo not found, just show the title
        pass

    st.title("Duravant Digital Assistant")
    st.caption(
        "Smart summaries for SAP & Dynamics 365 reports — built to cut reading time "
        "and reduce confusion across operations and IT."
    )
    st.markdown("---")


# ---------------------- UI ----------------------


def main():
    show_header()

    st.markdown(
        "Upload a report exported from **SAP**, **Dynamics 365**, or another system, "
        "or simply paste the contents below. The assistant will generate an "
        "executive-ready summary, key points, and recommended actions."
    )

    tab_file, tab_text = st.tabs(
        ["📄 Upload report (PDF / DOCX)", "✏️ Paste report text"]
    )

    # ---------- Tab A: File Upload ----------
    with tab_file:
        st.subheader("Upload a report file")

        uploaded_file = st.file_uploader(
            "Choose a PDF or Word (DOCX) report",
            type=["pdf", "docx"],
            help="For example: downtime reports, production summaries, quality logs, "
                 "change requests, or service reports.",
        )

        if uploaded_file is not None:
            if uploaded_file.type == "application/pdf":
                raw_text = extract_text_from_pdf(uploaded_file)
            elif (
                uploaded_file.type
                == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ):
                raw_text = extract_text_from_docx(uploaded_file)
            else:
                st.error("Unsupported file type.")
                raw_text = ""

            if raw_text.strip():
                st.success("Report loaded successfully. Ready to summarize.")
                with st.expander("Preview extracted text (optional)"):
                    st.write(raw_text[:1500] + ("...\n\n[truncated]" if len(raw_text) > 1500 else ""))

                if st.button("Summarize uploaded report", key="summarize_file"):
                    with st.spinner("Generating summary…"):
                        summary = summarize_report(raw_text)
                    st.subheader("AI Summary")
                    st.markdown(summary)
            else:
                st.warning(
                    "No readable text was found in this file. "
                    "Please check the document or try another file."
                )

    # ---------- Tab B: Text Input ----------
    with tab_text:
        st.subheader("Paste report text")

        example_hint = (
            "Paste here the body of a downtime report, SAP change request, "
            "Dynamics 365 export, or any long operational/IT document."
        )
        manual_text = st.text_area(
            "Report text",
            height=260,
            placeholder=example_hint,
        )

        if st.button("Summarize pasted text", key="summarize_text"):
            if not manual_text.strip():
                st.warning("Please paste a report before summarizing.")
            else:
                with st.spinner("Generating summary…"):
                    summary = summarize_report(manual_text)
                st.subheader("AI Summary")
                st.markdown(summary)


if __name__ == "__main__":
    main()
