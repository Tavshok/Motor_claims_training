from datetime import datetime
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
