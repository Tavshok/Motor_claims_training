from pydantic import BaseModel, Field
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
            f.write(r.model_dump_json() + "\n")
