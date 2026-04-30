import streamlit as st
import sys
import json
from pathlib import Path
import tempfile
import pandas as pd
from io import BytesIO
from PIL import Image, ImageDraw
import os
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.processing.pdf_parser import extract_pdf_content
from src.processing.doc_parser import extract_docx_content
from src.processing.extractor import hybrid_extraction
from src.features.fraud_signals import calculate_fraud_risk
from src.damage.component_ontology import match_damage_description
from src.cost.cost_breakdown import (
    extract_vehicle_details,
    extract_all_quotations,
    flag_anomalies
)
from src.fusion.evidence_fusion import fuse_claim_data
from src.imaging.image_extractor import extract_images_from_pdf

# ----- Page config -----
st.set_page_config(page_title="Motor Claims Forensics", page_icon="📄", layout="wide")
st.title("🚗 KINGA Motor Claims Forensics – Batch & Review")
st.caption("Upload claim PDFs or Word documents in batches. Each batch is saved in memory for this session.")

# ----- Session state -----
if 'batches' not in st.session_state:
    st.session_state.batches = {}
if 'batch_counter' not in st.session_state:
    st.session_state.batch_counter = 0
if 'selected_batch_id' not in st.session_state:
    st.session_state.selected_batch_id = None

def save_batch(results):
    st.session_state.batch_counter += 1
    batch_id = f"Batch_{st.session_state.batch_counter}"
    st.session_state.batches[batch_id] = {
        "results": results,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "count": len([r for r in results if not r.get("error")])
    }
    st.session_state.selected_batch_id = batch_id

# ----- Sidebar -----
with st.sidebar:
    st.header("📚 Batch History")
    if st.session_state.batches:
        for bid, bdata in st.session_state.batches.items():
            btn_label = f"{bid} ({bdata['count']} claims) – {bdata['timestamp']}"
            if st.button(btn_label, key=f"btn_{bid}"):
                st.session_state.selected_batch_id = bid
        st.markdown("---")
        if st.button("🗑️ Clear all batches"):
            st.session_state.batches = {}
            st.session_state.batch_counter = 0
            st.session_state.selected_batch_id = None
            st.experimental_rerun()
    else:
        st.info("No batches processed yet.")

    st.markdown("---")
    st.header("⚙️ Settings")
    run_damage_detection = st.checkbox("Run damage detection (slow)", value=False)
    require_vehicle = st.checkbox("Exclude costs without vehicle info", value=True,
                                 help="Keep only cost rows where vehicle make & model are known")
    export_format = st.radio("Download format", ["Parquet", "JSONL", "JSON (single file)"])

# ----- Main uploader -----
uploaded_files = st.file_uploader(
    "Choose PDF or Word files",
    type=["pdf", "docx"],
    accept_multiple_files=True,
    help="Select one or more claim documents"
)

if uploaded_files:
    st.write(f"**{len(uploaded_files)} file(s) ready for processing**")
    if st.button("⚡ Process Batch", type="primary"):
        results = []
        progress_bar = st.progress(0, text="Starting...")
        status_text = st.empty()

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            for idx, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"Processing {idx+1}/{len(uploaded_files)}: {uploaded_file.name}")
                # Save file with original extension
                suffix = Path(uploaded_file.name).suffix
                pdf_path = tmp_path / uploaded_file.name
                with open(pdf_path, "wb") as f:
                    f.write(uploaded_file.read())
                uploaded_file.seek(0)

                try:
                    # ---- Extract text based on file type ----
                    if suffix.lower() == ".pdf":
                        text, raw_conf = extract_pdf_content(pdf_path)
                    elif suffix.lower() == ".docx":
                        text, raw_conf = extract_docx_content(pdf_path)
                    else:
                        st.warning(f"Unsupported file type: {suffix}")
                        continue

                    conf = raw_conf / 100.0 if raw_conf > 1 else raw_conf

                    extracted = hybrid_extraction(text)
                    vehicle = extract_vehicle_details(text)
                    components = match_damage_description(text)
                    cost_sections = extract_all_quotations(text)
                    fraud = calculate_fraud_risk(extracted, uploaded_file.name)

                    if not text.strip():
                        st.warning(f"⚠️ Very little text from {uploaded_file.name}")
                        enriched = fuse_claim_data(
                            file_name=uploaded_file.name, text=text,
                            extracted_fields=extracted, vehicle=vehicle,
                            components=components, cost_sections=cost_sections,
                            images=[], fraud=fraud
                        )
                        enriched["ocr_confidence"] = conf
                        enriched["error"] = "Very little text extracted"
                        enriched["full_text"] = text
                        results.append(enriched)
                    else:
                        # Images only for PDFs currently
                        if suffix.lower() == ".pdf":
                            images = extract_images_from_pdf(pdf_path, Path("./output"))
                        else:
                            images = []

                        if run_damage_detection and components and images:
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
                            components=components, cost_sections=cost_sections,
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

        save_batch(results)
        status_text.text("✅ Batch processing complete! Saved to history.")
        st.success("✅ Batch processing complete! Saved to history.")

# ----- Display selected batch -----
if st.session_state.selected_batch_id and st.session_state.batches:
    batch = st.session_state.batches[st.session_state.selected_batch_id]
    results = batch["results"]
    st.subheader(f"📊 {st.session_state.selected_batch_id} – {batch['count']} claims processed ({batch['timestamp']})")

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
                "Components": len(r.get("damage_components", [])),
                "Cost Items": sum(len(sec.get("items", [])) for sec in r.get("cost_breakdown_sections", [])),
                "Fraud Score": r["fraud"]["risk_score"],
                "OCR Conf.": f"{r['ocr_confidence']:.0%}",
                "Error": ""
            })
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True)

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

            st.write(f"**Components ({len(r.get('damage_components', []))}**")
            if r["damage_components"]:
                comp_df = pd.DataFrame([{
                    "Component": c["canonical_name"],
                    "Category": c["category"],
                    "Confidence": f"{c['text_confidence']:.0%}"
                } for c in r["damage_components"]])
                st.dataframe(comp_df, use_container_width=True)

            st.write("**Cost Breakdown**")
            sections = r.get("cost_breakdown_sections", [])
            if not sections:
                st.caption("No cost line items found.")
            else:
                for sec in sections:
                    st.markdown(f"##### {sec['section_title']}  ({sec.get('extraction_method', '')})")
                    if sec["items"]:
                        cost_df = pd.DataFrame([{
                            "Description": c["description"],
                            "Original": f"{c['original_amount']} {c['original_currency']}",
                            "USD": f"${c['amount_usd']:,.2f}",
                            "Component": c["component_name"] or "Unmapped",
                            "Confidence": f"{c['match_confidence']:.0%}",
                            "Quote #": c.get("quote_column", "")
                        } for c in sec["items"]])
                        st.dataframe(cost_df, use_container_width=True)
                    else:
                        st.caption("No items in this section.")

            st.write("**Fraud Flags**")
            if r["fraud"]["flags"]:
                for flag in r["fraud"]["flags"]:
                    st.warning(flag)
            else:
                st.success("No flags.")

            imgs = r.get("images", [])
            if imgs:
                st.write(f"**Page Images ({len(imgs)})**")
                cols = st.columns(min(len(imgs), 3))
                for idx_img, img_meta in enumerate(imgs):
                    img_path = img_meta["image_path"]
                    if os.path.exists(img_path):
                        pil_img = Image.open(img_path)
                        for det in img_meta.get("detections", []):
                            draw = ImageDraw.Draw(pil_img)
                            b = det["bbox"]
                            w, h = pil_img.size
                            rect = [b["x"]*w, b["y"]*h, (b["x"]+b["w"])*w, (b["y"]+b["h"])*h]
                            draw.rectangle(rect, outline="red", width=3)
                            draw.text((rect[0], rect[1]-10), f"{det['label']} ({det['confidence']:.2f})", fill="red")
                        cols[idx_img % 3].image(pil_img, caption=f"Page {img_meta['page_number']}", use_container_width=True)

            with st.expander("📄 Full extracted text"):
                st.text(r.get("full_text", ""))

    st.subheader("💾 Download Selected Batch")
    all_data = [r for r in results if not r.get("error")]
    if all_data:
        if export_format == "Parquet":
            flat_rows = []
            for claim in all_data:
                if require_vehicle:
                    make = claim["vehicle"].get("make")
                    model = claim["vehicle"].get("model")
                    if not make or not model:
                        continue
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
                    "num_cost_items": sum(len(sec["items"]) for sec in claim.get("cost_breakdown_sections", [])),
                    "components_list": json.dumps([c["canonical_name"] for c in claim["damage_components"]]),
                    "cost_total_usd": sum(c["amount_usd"] for sec in claim.get("cost_breakdown_sections", []) for c in sec["items"]),
                    "full_text": claim.get("full_text", "")
                }
                flat_rows.append(base)
            if flat_rows:
                df_export = pd.DataFrame(flat_rows)
                buffer = BytesIO()
                df_export.to_parquet(buffer, index=False)
                buffer.seek(0)
                st.download_button("📥 Download Parquet", buffer, file_name=f"{st.session_state.selected_batch_id}_claims.parquet", mime="application/octet-stream")
            else:
                st.warning("No rows after vehicle filter.")
        elif export_format == "JSONL":
            filtered = [r for r in all_data if not require_vehicle or (r["vehicle"].get("make") and r["vehicle"].get("model"))]
            if filtered:
                jsonl = "\n".join([json.dumps(r, ensure_ascii=False) for r in filtered])
                st.download_button("📥 Download JSONL", jsonl, file_name=f"{st.session_state.selected_batch_id}_claims.jsonl", mime="application/jsonl")
            else:
                st.warning("No data after vehicle filter.")
        else:
            filtered = [r for r in all_data if not require_vehicle or (r["vehicle"].get("make") and r["vehicle"].get("model"))]
            if filtered:
                st.download_button("📥 Download JSON", json.dumps(filtered, indent=2, ensure_ascii=False), file_name=f"{st.session_state.selected_batch_id}_claims.json", mime="application/json")
            else:
                st.warning("No data after vehicle filter.")