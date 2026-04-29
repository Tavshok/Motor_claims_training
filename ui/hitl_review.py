import streamlit as st
import sys
import json
from pathlib import Path
import tempfile

# Add project root to path so we can import our modules
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

st.set_page_config(page_title="Motor Claims Intelligence", page_icon="📄", layout="wide")

# ---- Custom styles ----
st.markdown("""
    <style>
    .reportview-container .main .block-container { max-width: 1400px; }
    .stMetric { text-align: center; }
    .stWarning { font-size: 0.95rem; }
    </style>
""", unsafe_allow_html=True)

st.title("🚗 KINGA Motor Claims Forensics")
st.caption("Drop a claim PDF to see structured data, component damage, cost breakdown, and fraud signals.")

uploaded_file = st.file_uploader("Upload a claim PDF", type=["pdf"])

if uploaded_file is not None:
    # Save uploaded file to a temporary location
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.read())
        pdf_path = Path(tmp.name)

    try:
        with st.spinner("🔍 Extracting text and running forensics..."):
            # ---- Text & OCR ----
            text, raw_conf = extract_pdf_content(pdf_path)
            conf = raw_conf / 100.0 if raw_conf > 1 else raw_conf

            if not text.strip():
                st.error("No text could be extracted from this PDF. It may be a scanned image without OCR support, or completely empty.")
                st.stop()

            # ---- Core extractions ----
            extracted = hybrid_extraction(text)
            vehicle = extract_vehicle_details(text)
            components = match_damage_description(text)
            cost_items = extract_cost_items(text, components)
            fraud = calculate_fraud_risk(extracted, uploaded_file.name)

            # Build enriched claim object (without images, since this is a quick UI)
            enriched = fuse_claim_data(
                file_name=uploaded_file.name,
                text=text,
                extracted_fields=extracted,
                vehicle=vehicle,
                components=components,
                cost_items=cost_items,
                images=[],   # no images in this lightweight UI
                fraud=fraud
            )
            enriched["ocr_confidence"] = round(conf, 3)

            # ---- Display results ----
            st.success(f"✅ Processed successfully (OCR confidence: {conf:.0%})")

            tab1, tab2, tab3, tab4 = st.tabs([
                "📋 Summary", "🔧 Components", "💰 Cost Breakdown", "🕵️ Fraud Signals"
            ])

            with tab1:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Claim Number", enriched.get("claim_number") or "N/A")
                with col2:
                    st.metric("Policy Number", enriched.get("policy_number") or "N/A")
                with col3:
                    st.metric("Accident Date", enriched.get("accident_date") or "N/A")

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Vehicle Make", enriched["vehicle"].get("make") or "N/A")
                with col2:
                    st.metric("Vehicle Model", enriched["vehicle"].get("model") or "N/A")
                with col3:
                    st.metric("Year", enriched["vehicle"].get("year") or "N/A")

                st.metric("Registration", enriched["vehicle"].get("registration") or "N/A")

            with tab2:
                if enriched["damage_components"]:
                    st.write(f"**{len(enriched['damage_components'])} component(s) found**")
                    comp_df = []
                    for c in enriched["damage_components"]:
                        comp_df.append({
                            "Component": c["canonical_name"],
                            "Category": c["category"],
                            "Confidence (text)": f"{c['text_confidence']:.0%}",
                            "Repair Estimate (ZAR)": (
                                f"Replace: R{c['repair_estimates'].get('replace', (0,0))[0]} – R{c['repair_estimates'].get('replace', (0,0))[1]}"
                                if c.get("repair_estimates") else "N/A"
                            )
                        })
                    st.dataframe(comp_df, use_container_width=True)
                else:
                    st.info("No vehicle components detected in the text.")

            with tab3:
                if enriched["cost_breakdown"]:
                    cost_df = []
                    for item in enriched["cost_breakdown"]:
                        cost_df.append({
                            "Description": item["description"],
                            "Original Amount": f"{item['original_amount']} {item['original_currency']}",
                            "Amount (USD)": f"${item['amount_usd']:,.2f}",
                            "Component": item["component_name"] or "Unmapped",
                            "Confidence": f"{item['match_confidence']:.0%}"
                        })
                    st.dataframe(cost_df, use_container_width=True)

                    # Show anomalies
                    anomalies = flag_anomalies(cost_items, components)
                    if anomalies:
                        st.subheader("⚠️ Cost Anomalies")
                        for a in anomalies:
                            st.warning(a)
                else:
                    st.info("No cost line items could be parsed from the text.")

            with tab4:
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Fraud Risk Score", f"{enriched['fraud']['risk_score']}/100")
                with col2:
                    if enriched['fraud']['flags']:
                        st.error("🚩 Fraud Flags Detected:")
                        for flag in enriched['fraud']['flags']:
                            st.write(f"- {flag}")
                    else:
                        st.success("No fraud flags raised.")

            # ---- Raw text expander ----
            with st.expander("📝 View extracted raw text (first 2000 chars)"):
                st.text(text[:2000])

            # ---- Download button ----
            st.download_button(
                label="💾 Download enriched claim (JSON)",
                data=json.dumps(enriched, indent=2, ensure_ascii=False),
                file_name=f"{uploaded_file.name}_enriched.json",
                mime="application/json"
            )

    except Exception as e:
        st.error(f"❌ Processing failed: {str(e)}")
        st.exception(e)
    finally:
        # Clean up temporary file
        try:
            pdf_path.unlink()
        except:
            pass