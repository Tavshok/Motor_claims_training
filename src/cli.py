import argparse
import logging
import sys
from pathlib import Path
from tqdm import tqdm

from config.settings import OUTPUT_DIR, LOG_DIR, OCR_CONFIDENCE_THRESHOLD
from src.processing.pdf_parser import extract_pdf_content
from src.processing.doc_parser import extract_docx_content
from src.processing.extractor import hybrid_extraction
from src.features.fraud_signals import calculate_fraud_risk
from src.dataset.schema import ClaimRecord, export_parquet, export_jsonl
from src.damage.component_ontology import match_damage_description
from src.imaging.image_extractor import extract_images_from_pdf
from src.imaging.damage_detector import detect_damage_on_image, build_damage_prompts
from src.cost.cost_breakdown import (
    extract_vehicle_details,
    extract_cost_items,
    flag_anomalies
)
from src.fusion.evidence_fusion import fuse_claim_data
from src.graph.claim_graph import build_claim_graph, export_graph
from src.dataset.flat_dataset import generate_flat_dataset
import json

Path(LOG_DIR).mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(str(Path(LOG_DIR) / "pipeline.log")),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default=OUTPUT_DIR)
    parser.add_argument("--anonymise", action="store_true")
    parser.add_argument("--skip-detection", action="store_true",
                        help="Skip damage detection (save time)")
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "graphs").mkdir(parents=True, exist_ok=True)

    # Support both PDF and DOCX
    all_files = list(input_dir.glob("*.pdf")) + list(input_dir.glob("*.docx"))
    if not all_files:
        logger.error("No PDF or DOCX files found")
        return

    records = []
    all_claims_enriched = []

    for p in tqdm(all_files):
        try:
            # ---- TEXT EXTRACTION (based on file type) ----
            if p.suffix.lower() == ".pdf":
                text, raw_conf = extract_pdf_content(p)
            elif p.suffix.lower() == ".docx":
                text, raw_conf = extract_docx_content(p)
            else:
                continue

            conf = raw_conf / 100.0 if raw_conf > 1.0 else raw_conf
            if not text.strip():
                logger.warning(f"No text extracted from {p.name}, skipping")
                continue

            # ---- EXTRACTIONS ----
            extracted = hybrid_extraction(text)
            components = match_damage_description(text)
            logger.info(f"Components in {p.name}: {[c['canonical'] for c in components]}")

            # ---- VEHICLE DETAILS ----
            vehicle = extract_vehicle_details(text)
            logger.info(f"Vehicle in {p.name}: {vehicle}")

            # ---- COST BREAKDOWN ----
            cost_items = extract_cost_items(text, components)
            if cost_items:
                logger.info(f"Cost items found: {len(cost_items)}")
                cost_flags = flag_anomalies(cost_items, components)
                for flag in cost_flags:
                    logger.warning(f"Cost anomaly in {p.name}: {flag}")
            else:
                logger.info(f"No cost line items found in {p.name}")

            # ---- IMAGES (PDF only; DOCX images can be added later) ----
            if p.suffix.lower() == ".pdf":
                images = extract_images_from_pdf(p, output_dir)
            else:
                images = []   # no page images for Word docs for now

            # ---- DAMAGE DETECTION (only if images exist) ----
            if not args.skip_detection and components and images:
                prompts = build_damage_prompts(components)
                for img_meta in images:
                    img_path = Path(img_meta["image_path"])
                    if not img_path.is_absolute():
                        img_path = Path.cwd() / img_path
                    detections = detect_damage_on_image(img_path, prompts)
                    img_meta["detections"] = detections
                    if detections:
                        logger.info(f"  {img_meta['image_path']}: found {len(detections)} damages")
            else:
                for img_meta in images:
                    img_meta["detections"] = []

            # ---- FRAUD & RECORD ----
            fraud = calculate_fraud_risk(extracted, p.name)

            # ---- BUILD FUSION OBJECT ----
            enriched = fuse_claim_data(
                file_name=p.name,
                text=text,
                extracted_fields=extracted,
                vehicle=vehicle,
                components=components,
                cost_items=cost_items,
                images=images,
                fraud=fraud
            )
            enriched["ocr_confidence"] = conf
            all_claims_enriched.append(enriched)

            # ---- BUILD GRAPH ----
            claim_graph = build_claim_graph(enriched, p.stem)
            graph_path = output_dir / "graphs" / f"{p.stem}.graphml"
            export_graph(claim_graph, graph_path)
            logger.info(f"Graph exported to {graph_path}")

            # ---- SIMPLE RECORD ----
            record = ClaimRecord(
                file_name=p.name,
                page_count=1,
                ocr_confidence=conf,
                claim_number=extracted.get("claim_number"),
                policy_number=extracted.get("policy_number"),
                vehicle_reg=extracted.get("vehicle_reg"),
                accident_date=extracted.get("accident_date"),
                claim_amount=extracted.get("claim_amount"),
                fraud_risk_score=fraud["risk_score"],
                fraud_flags=fraud["flags"],
            )

            if args.anonymise:
                record.anonymise_pii()

            records.append(record)

        except Exception as e:
            logger.error(f"Failed to process {p.name}: {e}", exc_info=True)

    if records:
        export_parquet(records, output_dir / "claims_dataset.parquet")
        export_jsonl(records, output_dir / "claims_dataset.jsonl")
        logger.info(f"Done. {len(records)} simple records exported to {output_dir}")

        enriched_path = output_dir / "enriched_claims.json"
        with open(enriched_path, "w", encoding="utf-8") as f:
            json.dump(all_claims_enriched, f, indent=2, ensure_ascii=False)
        logger.info(f"Enriched claims (fusion) saved to {enriched_path}")

        # Flatten dataset
        flat_df = generate_flat_dataset(all_claims_enriched)
        flat_path = output_dir / "training_dataset.parquet"
        flat_df.to_parquet(flat_path, index=False)
        logger.info(f"Flat training dataset ({len(flat_df)} rows) saved to {flat_path}")
    else:
        logger.warning("No records created")

if __name__ == "__main__":
    main()