import os
from dotenv import load_dotenv
load_dotenv()

DATA_DIR = os.getenv("DATA_DIR", "./data")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./output")
LOG_DIR = os.getenv("LOG_DIR", "./logs")

OCR_LANG = "eng"
OCR_PSM = 3
OCR_CONFIDENCE_THRESHOLD = 60

PATTERNS = {
    "claim_number": r"(?:CLAIM\s*NO|Claim\s*(?:No|Number|#))\s*[:\-]?\s*([A-Z0-9\-/]+)",
    "policy_number": r"Policy\s*(?:No|Number|#)[:\s]*([A-Z0-9\-]+)",
    "vehicle_reg": r"(?:Reg|Registration|Plate)\s*(?:No|Number|#)?[:\s]*([A-Z]{2}\s?\d{2,3}\s?[A-Z]{1,2})",
    "accident_date": r"(?:Accident|Date of loss)[:\s]*(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})",
    "claim_amount": r"(?:Amount|Claim\s*amount|Total)[:\s]*([0-9]+[,\d]*\.\d{2})",
}

FRAUD_THRESHOLDS = {
    "high_amount_zarr": 150000,
    "late_report_days": 30,
    "duplicate_claim_window_days": 90,
}

PII_SALT = "change-me-in-production"
