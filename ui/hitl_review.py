import streamlit as st
import sys
import json
from pathlib import Path
import tempfile
import pandas as pd
from io import BytesIO
from PIL import Image, ImageDraw
import os

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
from src.imaging.image_extractor import extract_images_from_pdf

# ----- Page config -----
st.set_page_config(page_title="Motor Claims Forensics", page_icon="📄", layout="wide")
st.title("🚗 KINGA Motor Claims Forensics – Batch & Review")
st.caption("Upload claim PDFs. Results are kept until you clear them.")

# ----- Session state -----
if 'results' not in st.session_state:
    st.session_state.results = None

# ----- Sidebar -----
with st.sidebar:
    st.header("⚙️ Settings")
    run_damage_detection = st.checkbox("Run damage detection (slow)", value=False)
    export_format = st.radio("Download format", ["Parquet", "JSONL", "JSON (single file)"])
    if st.session_state.results is not None:
        st.success(f"{len([r for r in st.session_state.results if not r.get('error')])} claims processed")
        if st.button("🗑️ Clear stored results"):
            st.session_state.results = None
            st.experimental_rerun()
    st.info("All costs normalised to USD.")

# ----- Main uploader -----
uploaded_files = st.file_uploader(
    "Choose PDF files",
    type=["pdf"],
    accept_multiple_files=True,
    help="Select one or more claim PDFs"
)

if uploaded_files:
    st.write(f"**{len(uploaded_files)} file(s) ready**")
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

                    if not text.strip():
                        snippet = text[:200] if text else "(empty)"
                        st.warning(f"⚠️ Very little text from {uploaded_file.name}")
                        extracted = hybrid_extraction(text)
                        vehicle = extract_vehicle_details(text)
                        components = match_damage_description(text)
                        cost_items = extract_cost_items(text, components)
                        fraud = calculate_fraud_risk(extracted, uploaded_file.name)
                        enriched = fuse_claim_data(
                            file_name=uploaded_file.name, text=text,
                            extracted_fields=extracted, vehicle=vehicle,
                            components=components, cost_items=cost_items,
                            images=[], fraud=fraud
                        )
                        enriched["ocr_confidence"] = conf
                        enriched["error"] = "Very little text extracted"
                        enriched["full_text"] = text
                        results.append(enriched)
                    else:
                        extracted = hybrid_extraction(text)
                        vehicle = extract_vehicle_details(text)
                        components = match_damage_description(text)
                        cost_items = extract_cost_items(text, components)
                        fraud = calculate_fraud_risk(extracted, uploaded_file.name)

                        # ---- Extract images ----
                        images = extract_images_from_pdf(pdf_path, Path("./output"))
                        # Run damage detection if enabled
                        if run_damage_detection and components:
                            from src.imaging.damage_detector import detect_damage_on_image, build_damage_prompts
                            prompts = build_damage_prompts(components)
                            for img_meta in images:
                                try:
                                    detections = detect_damage_on_image(Path(img_meta["image_path"]), prompts)
                                    img_meta["detections"] = detections
                                except:
                                    img_meta["detections"] = []
                        else:
                            for img_meta in images:
                                img_meta["detections"] = []

                        enriched = fuse_claim_data(
                            file_name=uploaded_file.name, text=text,
                            extracted_fields=extracted, vehicle=vehicle,
                            components=components, cost_items=cost_items,
                            images=images, fraud=fraud
                        )
                        enriched["ocr_confidence"] = conf
                        enriched["error"] = None
                        enriched["full_text"] = text
                        results.append(enriched)

                except Exception as e:
                    st.error(f"❌ Failed on {uploaded_file.name}: {e}")
                    results.append({
                        "file_name": uploaded_file.name,
                        "ocr_confidence": 0.0,
                        "error": str(e),
                        "full_text": ""
                    })

                progress_bar.progress((idx+1)/len(uploaded_files), text=f"Done {idx+1}/{len(uploaded_files)}")

        st.session_state.results = results
        status_text.text("✅ Batch processing complete!")

# ----- Display stored results -----
if st.session_state.results:
    results = st.session_state.results
    st.subheader("📊 Batch Results Overview")
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
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True)

    # Individual claims
    st.subheader("🔍 Inspect Claims")
    for i, r in enumerate(results):
        if r.get("error"):
            st.warning(f"**{r['file_name']}** – Error: {r['error']}")
            continue
        with st.expander(f"{r['file_name']}  (Fraud risk: {r['fraud']['risk_score']}/100)"):
            col1, col2, col3 = st.columns(3)
            with col1: st.metric("Claim #", r.get("claim_number", "N/A"))
            with col2: st.metric("Policy #", r.get("policy_number", "N/A"))
            with col3: st.metric("Accident Date", r.get("accident_date", "N/A"))
            st.write("**Vehicle**")
            st.json(r["vehicle"])

            # Components
            st.write(f"**Components ({len(r['damage_components'])})**")
            if r["damage_components"]:
                comp_df = pd.DataFrame([{
                    "Component": c["canonical_name"],
                    "Category": c["category"],
                    "Confidence": f"{c['text_confidence']:.0%}"
                } for c in r["damage_components"]])
                st.dataframe(comp_df, use_container_width=True)

            # Cost breakdown
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

            # Fraud flags
            st.write("**Fraud Flags**")
            if r["fraud"]["flags"]:
                for flag in r["fraud"]["flags"]:
                    st.warning(flag)
            else:
                st.success("No flags.")

            # Images
            imgs = r.get("images", [])
            if imgs:
                st.write(f"**Page Images ({len(imgs)})**")
                cols = st.columns(min(len(imgs), 3))
                for idx_img, img_meta in enumerate(imgs):
                    img_path = img_meta["image_path"]
                    if os.path.exists(img_path):
                        pil_img = Image.open(img_path)
                        # Draw bounding boxes if detections exist
                        for det in img_meta.get("detections", []):
                            draw = ImageDraw.Draw(pil_img)
                            b = det["bbox"]
                            w, h = pil_img.size
                            rect = [b["x"]*w, b["y"]*h, (b["x"]+b["w"])*w, (b["y"]+b["h"])*h]
                            draw.rectangle(rect, outline="red", width=3)
                            draw.text((rect[0], rect[1]-10), f"{det['label']} ({det['confidence']:.2f})", fill="red")
                        cols[idx_img % 3].image(pil_img, caption=f"Page {img_meta['page_number']}", use_container_width=True)

            # Full raw text
            with st.expander("📄 Full extracted text"):
                st.text(r.get("full_text", ""))

    # ---- Permanent download buttons ----
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
                    "full_text": claim.get("full_text", "")
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