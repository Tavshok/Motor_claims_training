# src/cost/cost_breakdown.py
"""
Extract vehicle details and repair cost line items from claim text.
Maps items to components using the ontology, flags anomalies.
"""

import re
from typing import List, Dict, Any, Optional
from src.damage.component_ontology import COMPONENT_ONTOLOGY

# ── Vehicle extraction (new, precise patterns only) ──

def extract_vehicle_details(text: str) -> Dict[str, Optional[str]]:
    """
    Extract vehicle make, model, year from text.
    Returns dict with keys 'make', 'model', 'year' (or None).
    Uses patterns found in your actual documents: Make : Jeep, Model : Cherokee, Year : 2015
    """
    # Non‑greedy match, stop at newline, comma, or end of line
    m_make = re.search(r'Make\s*:\s*(.*?)(?:[\n\r.,]|$)', text, re.IGNORECASE)
    m_model = re.search(r'Model\s*:\s*(.*?)(?:[\n\r.,]|$)', text, re.IGNORECASE)
    m_year = re.search(r'Year\s*:\s*(\d{4})', text, re.IGNORECASE)

    make = m_make.group(1).strip().title() if m_make else None
    model = m_model.group(1).strip().upper() if m_model else None
    year = m_year.group(1) if m_year else None

    # If we got at least make and model, it's a valid extraction
    if make and model:
        return {"make": make, "model": model, "year": year}
    # Otherwise return whatever we found (may be partial or None)
    return {"make": make, "model": model, "year": year}


# ── Cost line item patterns (unchanged) ──
COST_LINE_PATTERNS = [
    # "Front bumper – R1 200" or "Front bumper R1 200"
    r'(?P<desc>[A-Za-z\s/&-]+?)\s*[-–:]\s*(?P<currency>[Rr$ZzAaUuSsDd]+)\s*(?P<amount>[\d\s,]+\.?\d{0,2})',
    # "Replace left headlight: $350"
    r'(?P<desc>[A-Za-z\s/&-]+?)\s*[:]\s*(?P<currency>[Rr$ZzAaUuSsDd]+)\s*(?P<amount>[\d\s,]+\.?\d{0,2})',
    # "R1 200 for front bumper"
    r'(?P<currency>[Rr$ZzAaUuSsDd]+)\s*(?P<amount>[\d\s,]+\.?\d{0,2})\s*(?:for|of)\s+(?P<desc>[A-Za-z\s/&-]+)',
    # "Amount: R1200.00 (Front bumper)"
    r'Amount\s*[:\-]?\s*(?P<currency>[Rr$ZzAaUuSsDd]+)\s*(?P<amount>[\d\s,]+\.?\d{0,2})\s*\((?P<desc>[^)]+)\)',
]


def _clean_amount(amount_str: str) -> float:
    """Remove spaces and commas, parse to float."""
    clean = amount_str.replace(" ", "").replace(",", "")
    try:
        return float(clean)
    except:
        return 0.0


def extract_cost_items(text: str, components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Find all cost line items and map them to the nearest component.
    Returns list of dicts:
        - description: raw text description
        - amount: float
        - currency: original currency symbol
        - component_id: mapped component (or None)
        - component_name: canonical name (or None)
        - match_confidence: 0-1
    """
    items = []
    for pattern in COST_LINE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            desc = match.group("desc").strip().lower()
            currency = match.group("currency").upper()
            amount = _clean_amount(match.group("amount"))
            if amount <= 0:
                continue

            # Try to map description to a component ontology entry
            best_comp = None
            best_confidence = 0.0
            desc_lower = desc.lower()
            for comp in COMPONENT_ONTOLOGY:
                for alias in comp["aliases"]:
                    if alias in desc_lower:
                        # Simple confidence based on how exactly the alias appears
                        conf = 0.9 if alias == desc_lower else 0.7
                        if conf > best_confidence:
                            best_confidence = conf
                            best_comp = comp
                        break   # one alias match per component is enough

            items.append({
                "description": desc,
                "amount": amount,
                "currency": currency,
                "component_id": best_comp["component_id"] if best_comp else None,
                "component_name": best_comp["canonical"] if best_comp else None,
                "match_confidence": best_confidence,
            })
    return items


def flag_anomalies(cost_items: List[Dict[str, Any]], components: List[Dict[str, Any]]) -> List[str]:
    """
    Compare extracted costs to expected ranges from the ontology.
    Returns a list of anomaly descriptions.
    """
    flags = []
    for item in cost_items:
        if not item["component_id"]:
            continue
        # Find the component in the ontology
        comp = next((c for c in COMPONENT_ONTOLOGY if c["component_id"] == item["component_id"]), None)
        if not comp or "repair_cost_estimates" not in comp:
            continue
        ranges = comp["repair_cost_estimates"]
        amount = item["amount"]
        anomaly = None
        if "replace" in ranges:
            lo, hi = ranges["replace"]
            if amount < lo * 0.5:
                anomaly = f"Replace cost {amount} is unusually low for {comp['canonical']} (typical {lo}-{hi})"
            elif amount > hi * 2:
                anomaly = f"Replace cost {amount} is unusually high for {comp['canonical']} (typical {lo}-{hi})"
        if not anomaly and "repair" in ranges:
            lo, hi = ranges["repair"]
            if amount < lo * 0.5:
                anomaly = f"Repair cost {amount} is unusually low for {comp['canonical']} (typical {lo}-{hi})"
            elif amount > hi * 2:
                anomaly = f"Repair cost {amount} is unusually high for {comp['canonical']} (typical {lo}-{hi})"
        if anomaly:
            flags.append(anomaly)
    return flags