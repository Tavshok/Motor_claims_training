import streamlit as st
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.processing.pdf_parser import extract_pdf_content
from src.processing.extractor import hybrid_extraction
from src.features.fraud_signals import calculate_fraud_risk
from src.dataset.schema import ClaimRecord, export_jsonl

st.set_page_config(page_title="Claims Review", layout="wide")
st.title("📄 Motor Claims Review")

uploaded = st.file_uploader("Upload a claim PDF", type="pdf")
if uploaded:
    temp = Path("temp.pdf")
    temp.write_bytes(uploaded.read())
    text, conf = extract_pdf_content(temp)
    extracted = hybrid_extraction(text)
    fraud = calculate_fraud_risk(extracted, uploaded.name)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Extracted")
        st.json(extracted)
        st.metric("OCR Confidence", f"{conf:.2f}")
    with col2:
        st.subheader("Fraud / Risk")
        st.metric("Risk Score", fraud["risk_score"])
        for f in fraud["flags"]:
            st.warning(f)
    with st.expander("Raw Text"):
        st.text(text)
    if st.button("Approve & Save"):
        record = ClaimRecord(
            file_name=uploaded.name, page_count=1, ocr_confidence=conf,
            claim_number=extracted.get("claim_number"),
            policy_number=extracted.get("policy_number"),
            vehicle_reg=extracted.get("vehicle_reg"),
            accident_date=extracted.get("accident_date"),
            claim_amount=extracted.get("claim_amount"),
            fraud_risk_score=fraud["risk_score"],
            fraud_flags=fraud["flags"],
        )
        out_dir = Path("./output")
        out_dir.mkdir(exist_ok=True)
        export_jsonl([record], out_dir / "reviewed_claims.jsonl")
        st.success("Saved!")
