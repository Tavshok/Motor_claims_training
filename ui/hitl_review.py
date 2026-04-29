import streamlit as st
import sys
import json
from pathlib import Path
import tempfile
import pandas as pd
from io import BytesIO

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.processing.pdf_parser import extract_pdf_content
from src.processing.extractor import hybrid_extraction
from src.features.fraud_signals import calculate_fraud_risk
from src.damage.component_ontology import match_damage_description
from src.cost.cost_breakdown import (
    extract_vehicle_details,
    extract_cost_items,
    flag_anomalies
)
from src.fusion.evidence_fusion import fuse_claim_data

# ----- Page config -----
st.set_page_config(page_title="Motor Claims Intelligence", page_icon="📄", layout="wide")
st.title("🚗 KINGA Motor Claims Forensics – Batch Processing")
st.caption("Upload multiple PDF claim documents to process them in one go.")

with st.sidebar:
    st.header("📦 Output Options")
    export_format = st.radio("Download format", ["Parquet", "JSONL", "JSON (single file)"])
    st.markdown("---")
    st.info("All costs are normalised to USD. Currencies handled: ZAR, USD, BWP, EUR, GBP, ZIG, etc.")

uploaded_files = st.file_uploader(
    "Choose PDF files",
    type=["pdf"],
    accept_multiple_files=True,
    help="Select one or more claim PDFs"
)

if uploaded_files:
    st.write(f"**{len(uploaded_files)} file(s) selected**")

    if st.button("⚡ Process Batch", type="primary"):
        results = []
        progress_bar = st.progress(0, text="Starting...")
        status_text = st.empty()

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            for idx, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"Processing {idx+1}/{len(uploaded_files)}: {uploaded_file.name}")

                pdf_path = tmp_path / uploaded_file.name
                with open(pdf_path, "wb") as f:
                    f.write(uploaded_file.read())
                uploaded_file.seek(0)

                try:
                    text, raw_conf = extract_pdf_content(pdf_path)
                    conf = raw_conf / 100.0 if raw_conf > 1 else raw_conf

                    # Show debug info even if text is short
                    if not text.strip():
                        snippet = text[:200] if text else "(empty)"
                        st.warning(f"⚠️ Very little text from {uploaded_file.name} (OCR conf: {conf:.1%})")
                        st.caption(f"Raw snippet: {snippet}")
                        # Still try to extract what we can
                        extracted = hybrid_extraction(text)
                        vehicle = extract_vehicle_details(text)
                        components = match_damage_description(text)
                        cost_items = extract_cost_items(text, components)
                        fraud = calculate_fraud_risk(extracted, uploaded_file.name)
                        enriched = fuse_claim_data(
                            file_name=uploaded_file.name,
                            text=text,
                            extracted_fields=extracted,
                            vehicle=vehicle,
                            components=components,
                            cost_items=cost_items,
                            images=[],
                            fraud=fraud
                        )
                        enriched["ocr_confidence"] = conf
                        enriched["error"] = "Very little text extracted"
                        results.append(enriched)
                    else:
                        extracted = hybrid_extraction(text)
                        vehicle = extract_vehicle_details(text)
                        components = match_damage_description(text)
                        cost_items = extract_cost_items(text, components)
                        fraud = calculate_fraud_risk(extracted, uploaded_file.name)
                        enriched = fuse_claim_data(
                            file_name=uploaded_file.name,
                            text=text,
                            extracted_fields=extracted,
                            vehicle=vehicle,
                            components=components,
                            cost_items=cost_items,
                            images=[],
                            fraud=fraud
                        )
                        enriched["ocr_confidence"] = conf
                        enriched["error"] = None
                        results.append(enriched)

                except Exception as e:
                    st.error(f"❌ Failed on {uploaded_file.name}: {e}")
                    results.append({
                        "file_name": uploaded_file.name,
                        "ocr_confidence": 0.0,
                        "error": str(e)
                    })

                progress_bar.progress((idx + 1) / len(uploaded_files),
                                     text=f"Completed {idx+1}/{len(uploaded_files)}")

        status_text.text("✅ Batch processing complete!")

        if results:
            # Summary table
            summary_rows = []
            for r in results:
                if r.get("error"):
                    summary_rows.append({
                        "File": r["file_name"],
                        "Claim #": "N/A",
                        "Vehicle": "N/A",
                        "Components": "N/A",
                        "Cost Items": "N/A",
                        "Fraud Score": "N/A",
                        "OCR Conf.": f"{r.get('ocr_confidence', 0):.0%}",
                        "Error": r["error"]
                    })
                else:
                    summary_rows.append({
                        "File": r["file_name"],
                        "Claim #": r.get("claim_number", "N/A"),
                        "Vehicle": f"{r['vehicle'].get('make','')} {r['vehicle'].get('model','')} ({r['vehicle'].get('year','')})".strip(),
                        "Components": len(r["damage_components"]),
                        "Cost Items": len(r["cost_breakdown"]),
                        "Fraud Score": r["fraud"]["risk_score"],
                        "OCR Conf.": f"{r['ocr_confidence']:.0%}",
                        "Error": ""
                    })
            df_summary = pd.DataFrame(summary_rows)
            st.subheader("📊 Batch Results Overview")
            st.dataframe(df_summary, use_container_width=True)

            # Individual claim details
            st.subheader("🔍 Inspect Individual Claims")
            for i, r in enumerate(results):
                if r.get("error"):
                    st.warning(f"**{r['file_name']}** – Error: {r['error']}")
                    continue
                with st.expander(f"{r['file_name']}  (Fraud risk: {r['fraud']['risk_score']}/100)"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Claim #", r.get("claim_number", "N/A"))
                    with col2:
                        st.metric("Policy #", r.get("policy_number", "N/A"))
                    with col3:
                        st.metric("Accident Date", r.get("accident_date", "N/A"))
                    st.write("**Vehicle**")
                    st.json(r["vehicle"])
                    st.write(f"**Components ({len(r['damage_components'])})**")
                    if r["damage_components"]:
                        comp_df = pd.DataFrame([{
                            "Component": c["canonical_name"],
                            "Category": c["category"],
                            "Confidence": f"{c['text_confidence']:.0%}"
                        } for c in r["damage_components"]])
                        st.dataframe(comp_df, use_container_width=True)
                    else:
                        st.caption("No components detected.")
                    st.write(f"**Cost Breakdown ({len(r['cost_breakdown'])})**")
                    if r["cost_breakdown"]:
                        cost_df = pd.DataFrame([{
                            "Description": c["description"],
                            "Original": f"{c['original_amount']} {c['original_currency']}",
                            "USD": f"${c['amount_usd']:,.2f}",
                            "Component": c["component_name"] or "Unmapped",
                            "Confidence": f"{c['match_confidence']:.0%}"
                        } for c in r["cost_breakdown"]])
                        st.dataframe(cost_df, use_container_width=True)
                    else:
                        st.caption("No cost line items found.")
                    st.write("**Fraud Flags**")
                    if r["fraud"]["flags"]:
                        for flag in r["fraud"]["flags"]:
                            st.warning(flag)
                    else:
                        st.success("No flags raised.")
                    # Show raw text snippet for inspection
                    st.caption("Raw text (first 500 chars)")
                    st.code(r.get("extracted_text_summary", ""))

            # Download section
            st.subheader("💾 Download Processed Data")
            all_data = [r for r in results if not r.get("error")]
            if all_data:
                if export_format == "Parquet":
                    flat_rows = []
                    for claim in all_data:
                        base = {
                            "file_name": claim["file_name"],
                            "claim_number": claim.get("claim_number"),
                            "policy_number": claim.get("policy_number"),
                            "accident_date": claim.get("accident_date"),
                            "vehicle_make": claim["vehicle"].get("make"),
                            "vehicle_model": claim["vehicle"].get("model"),
                            "vehicle_year": claim["vehicle"].get("year"),
                            "vehicle_registration": claim["vehicle"].get("registration"),
                            "fraud_risk_score": claim["fraud"]["risk_score"],
                            "fraud_flags": ",".join(claim["fraud"]["flags"]),
                            "ocr_confidence": claim["ocr_confidence"],
                            "num_components": len(claim["damage_components"]),
                            "num_cost_items": len(claim["cost_breakdown"]),
                            "components_list": json.dumps([c["canonical_name"] for c in claim["damage_components"]]),
                            "cost_total_usd": sum(c["amount_usd"] for c in claim["cost_breakdown"]),
                        }
                        flat_rows.append(base)
                    df_export = pd.DataFrame(flat_rows)
                    buffer = BytesIO()
                    df_export.to_parquet(buffer, index=False)
                    buffer.seek(0)
                    st.download_button("📥 Download Parquet", buffer, file_name="batch_claims.parquet", mime="application/octet-stream")
                elif export_format == "JSONL":
                    jsonl = "\n".join([json.dumps(r, ensure_ascii=False) for r in all_data])
                    st.download_button("📥 Download JSONL", jsonl, file_name="batch_claims.jsonl", mime="application/jsonl")
                else:
                    st.download_button("📥 Download JSON", json.dumps(all_data, indent=2, ensure_ascii=False), file_name="batch_claims.json", mime="application/json")