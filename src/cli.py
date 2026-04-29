import argparse
import logging
import sys
from pathlib import Path
from tqdm import tqdm

from config.settings import OUTPUT_DIR, LOG_DIR, OCR_CONFIDENCE_THRESHOLD
from src.processing.pdf_parser import extract_pdf_content
from src.processing.extractor import hybrid_extraction
from src.features.fraud_signals import calculate_fraud_risk
from src.dataset.schema import ClaimRecord, export_parquet, export_jsonl

# Ensure the log directory exists BEFORE setting up the file handler
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
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = list(input_dir.glob("*.pdf"))
    if not pdf_files:
        logger.error("No PDFs found")
        return

    records = []
    for p in tqdm(pdf_files):
        try:
            # Extract raw OCR confidence (may be percentage 0-100)
            text, raw_conf = extract_pdf_content(p)
            # Normalize confidence to a 0-1 range for Pydantic validation
            conf = raw_conf / 100.0 if raw_conf > 1.0 else raw_conf

            if not text.strip():
                logger.warning(f"No text extracted from {p.name}, skipping")
                continue

            extracted = hybrid_extraction(text)
            fraud = calculate_fraud_risk(extracted, p.name)

            record = ClaimRecord(
                file_name=p.name,
                page_count=1,
                ocr_confidence=conf,          # now always between 0 and 1
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
        logger.info(f"Done. {len(records)} records exported to {output_dir}")
    else:
        logger.warning("No records created")

if __name__ == "__main__":
    main()