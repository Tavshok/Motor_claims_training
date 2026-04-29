# setup_project.py – Creates the full project structure
import os

BASE_DIR = "."

files = {
    ".gitignore": "__pycache__/\n*.pyc\n.env\n.vscode/\noutput/\ndata/\nvenv/\n",
    "config/settings.py": '''import os
from dotenv import load_dotenv
load_dotenv()

DATA_DIR = os.getenv("DATA_DIR", "./data")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./output")
LOG_DIR = os.getenv("LOG_DIR", "./logs")

OCR_LANG = "eng"
OCR_PSM = 3
OCR_CONFIDENCE_THRESHOLD = 60

PATTERNS = {
    "claim_number": r"Claim\\s*(?:No|Number|#)[:\\s]*([A-Z0-9]+)",
    "policy_number": r"Policy\\s*(?:No|Number|#)[:\\s]*([A-Z0-9\\-]+)",
    "vehicle_reg": r"(?:Reg|Registration|Plate)\\s*(?:No|Number|#)?[:\\s]*([A-Z]{2}\\s?\\d{2,3}\\s?[A-Z]{1,2})",
    "accident_date": r"(?:Accident|Date of loss)[:\\s]*(\\d{1,2}[/\\-.]\\d{1,2}[/\\-.]\\d{2,4})",
    "claim_amount": r"(?:Amount|Claim\\s*amount|Total)[:\\s]*([0-9]+[,\\d]*\\.\\d{2})",
}

FRAUD_THRESHOLDS = {
    "high_amount_zarr": 150000,
    "late_report_days": 30,
    "duplicate_claim_window_days": 90,
}

PII_SALT = "change-me-in-production"
''',
    "src/processing/pdf_parser.py": '''import logging
from pathlib import Path
import PyPDF2
from pdf2image import convert_from_path
import pytesseract
import cv2
import numpy as np

logger = logging.getLogger(__name__)

def preprocess_image(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return cv2.fastNlMeansDenoising(thresh, h=30)

def extract_pdf_content(pdf_path):
    text = ""
    confidences = []
    try:
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\\n"
    except Exception as e:
        logger.warning(f"PyPDF2 error: {e}")

    if len(text.split()) > 50:
        return text, 1.0

    logger.info(f"OCR fallback for {pdf_path}")
    try:
        images = convert_from_path(pdf_path, dpi=300)
    except Exception as e:
        logger.error(f"PDF convert error: {e}")
        return text, 0.0

    for img in images:
        preprocessed = preprocess_image(np.array(img))
        data = pytesseract.image_to_data(preprocessed, output_type=pytesseract.Output.DICT)
        words = []
        for i, w in enumerate(data["text"]):
            conf = int(data["conf"][i])
            if w.strip() and conf > 0:
                words.append(w)
                confidences.append(conf)
        text += " ".join(words) + "\\n"

    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    return text, avg_conf
''',
    "src/processing/extractor.py": '''import re
import logging
import spacy
from config.settings import PATTERNS

logger = logging.getLogger(__name__)
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    logger.error("spaCy model missing. Run: python -m spacy download en_core_web_sm")
    nlp = None

def extract_with_regex(text):
    fields = {}
    for name, pattern in PATTERNS.items():
        match = re.search(pattern, text, re.IGNORECASE)
        fields[name] = match.group(1).strip() if match else None
    return fields

def extract_with_spacy(text):
    if nlp is None:
        return {}
    doc = nlp(text[:100000])
    entities = {}
    for ent in doc.ents:
        if ent.label_ == "DATE" and "accident_date" not in entities:
            entities["accident_date"] = ent.text
        elif ent.label_ == "MONEY" and "claim_amount" not in entities:
            entities["claim_amount"] = ent.text
    return entities

def hybrid_extraction(text):
    regex_fields = extract_with_regex(text)
    if nlp:
        spacy_fields = extract_with_spacy(text)
        merged = {**spacy_fields, **regex_fields}
    else:
        merged = regex_fields
    return merged
''',
    "src/features/fraud_signals.py": '''from datetime import datetime
from config.settings import FRAUD_THRESHOLDS

def calculate_fraud_risk(extracted, pdf_name=""):
    signals = {"high_amount": False, "late_report": False, "potential_duplicate": False,
               "risk_score": 0, "flags": []}

    try:
        amt = extracted.get("claim_amount")
        if amt:
            amt = float(amt.replace(",", ""))
            if amt > FRAUD_THRESHOLDS["high_amount_zarr"]:
                signals["high_amount"] = True
                signals["risk_score"] += 30
                signals["flags"].append("HIGH_AMOUNT")
    except:
        pass

    try:
        date_str = extracted.get("accident_date")
        if date_str:
            for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y"):
                try:
                    accident_date = datetime.strptime(date_str, fmt)
                    if (datetime.now() - accident_date).days > FRAUD_THRESHOLDS["late_report_days"]:
                        signals["late_report"] = True
                        signals["risk_score"] += 20
                        signals["flags"].append("LATE_REPORT")
                    break
                except:
                    pass
    except:
        pass

    claim_no = extracted.get("claim_number")
    if claim_no and len(claim_no) < 5:
        signals["potential_duplicate"] = True
        signals["risk_score"] += 10
        signals["flags"].append("SHORT_CLAIM_NO")

    signals["risk_score"] = min(signals["risk_score"], 100)
    return signals
''',
    "src/dataset/schema.py": '''from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
import json
import hashlib
from config.settings import PII_SALT

class ClaimRecord(BaseModel):
    file_name: str
    page_count: int
    ocr_confidence: float = Field(ge=0.0, le=1.0)
    claim_number: Optional[str] = None
    policy_number: Optional[str] = None
    vehicle_reg: Optional[str] = None
    accident_date: Optional[str] = None
    claim_amount: Optional[str] = None
    fraud_risk_score: int = 0
    fraud_flags: list[str] = []
    processed_timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    def anonymise_pii(self):
        for field in ["claim_number", "policy_number", "vehicle_reg"]:
            val = getattr(self, field)
            if val:
                salted = (val + PII_SALT).encode()
                setattr(self, field, hashlib.sha256(salted).hexdigest()[:16])

def records_to_dataframe(records):
    return pd.DataFrame([r.model_dump() for r in records])

def export_parquet(records, output_path):
    df = records_to_dataframe(records)
    pq.write_table(pa.Table.from_pandas(df), output_path)

def export_jsonl(records, output_path):
    with open(output_path, "w") as f:
        for r in records:
            f.write(r.model_dump_json() + "\\n")
''',
    "src/cli.py": '''import argparse, logging, sys
from pathlib import Path
from tqdm import tqdm
from config.settings import OUTPUT_DIR, LOG_DIR, OCR_CONFIDENCE_THRESHOLD
from src.processing.pdf_parser import extract_pdf_content
from src.processing.extractor import hybrid_extraction
from src.features.fraud_signals import calculate_fraud_risk
from src.dataset.schema import ClaimRecord, export_parquet, export_jsonl

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                    handlers=[logging.FileHandler(LOG_DIR / "pipeline.log"), logging.StreamHandler(sys.stdout)])
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
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    pdf_files = list(input_dir.glob("*.pdf"))
    if not pdf_files:
        logger.error("No PDFs found")
        return

    records = []
    for p in tqdm(pdf_files):
        text, conf = extract_pdf_content(p)
        extracted = hybrid_extraction(text)
        fraud = calculate_fraud_risk(extracted, p.name)
        record = ClaimRecord(
            file_name=p.name, page_count=1, ocr_confidence=conf,
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

    if records:
        export_parquet(records, output_dir / "claims_dataset.parquet")
        export_jsonl(records, output_dir / "claims_dataset.jsonl")
        logger.info(f"Done. {len(records)} records exported to {output_dir}")
    else:
        logger.warning("No records created")

if __name__ == "__main__":
    main()
''',
    "ui/hitl_review.py": '''import streamlit as st
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
''',
    "scripts/setup_tesseract.sh": "#!/bin/bash\nsudo apt update && sudo apt install -y tesseract-ocr\n",
    "config/__init__.py": "",
    "src/__init__.py": "",
    "src/processing/__init__.py": "",
    "src/features/__init__.py": "",
    "src/dataset/__init__.py": "",
    "ui/__init__.py": "",
}

for path, content in files.items():
    full = os.path.join(BASE_DIR, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)

print("✅ Project files created successfully! You can now open Jupyter Lab.")