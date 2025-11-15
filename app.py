import os
from dotenv import load_dotenv
from openai import OpenAI
import streamlit as st
import pdfplumber
import docx

# Load API Key
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# -------- PDF Extraction --------
def extract_text_from_pdf(uploaded_pdf):
    text = ""
    with pdfplumber.open(uploaded_pdf) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

# -------- DOCX Extraction --------
def extract_text_from_docx(uploaded_docx):
    doc = docx.Document(uploaded_docx)
    full_text = []
    for paragraph in doc.paragraphs:
        full_text.append(paragraph.text)
    return "\n".join(full_text)

# -------- Summarizer --------
def summarize_report(report_text: str) -> str:
    prompt = f"""
You summarize IT and business reports for stakeholders
in manufacturing and ERP environments.

Provide 3 sections:

## Executive Summary
8–10 sentences.

## Key Points
5–8 bullet points.

## Recommended Actions
3–5 action items.

Make it concise and business-friendly.

Report:
\"\"\"{report_text}\"\"\"
"""

    response = client.responses.create(
        model="gpt-4o-mini",
        input=prompt
    )

    return response.output[0].content[0].text


# ---------------------- UI -----------------------

st.title("AI Report Summarizer")

st.write("Upload a PDF/DOCX or paste text to get an executive summary.")

# ---------------------- File Upload Section -----------------------
st.subheader("Option A: Upload a File (PDF or DOCX)")

uploaded_file = st.file_uploader("Upload your report", type=["pdf", "docx"])

file_text = ""

if uploaded_file:
    if uploaded_file.type == "application/pdf":
        file_text = extract_text_from_pdf(uploaded_file)

    elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        file_text = extract_text_from_docx(uploaded_file)

    st.success("File uploaded and text extracted!")

# ---------------------- Text Input Section -----------------------
st.subheader("Option B: Paste Text")

manual_text = st.text_area("Paste your report text here", height=250)

# ---------------------- Summarize -----------------------
if st.button("Summarize"):

    if uploaded_file and file_text.strip():
        # If file uploaded
        with st.spinner("Summarizing file..."):
            summary = summarize_report(file_text)
        st.markdown(summary)

    elif manual_text.strip():
        # If text pasted
        with st.spinner("Summarizing text..."):
            summary = summarize_report(manual_text)
        st.markdown(summary)

    else:
        st.warning("Please upload a file OR paste text before summarizing.")
