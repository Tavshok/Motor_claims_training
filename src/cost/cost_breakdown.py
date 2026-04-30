# src/cost/cost_breakdown.py
"""
Multi‑quotation, table‑aware cost extraction with abbreviation normalisation.
"""

import re
from typing import List, Dict, Any, Optional

# (Keep your component ontology import)
from src.damage.component_ontology import COMPONENT_ONTOLOGY

# ── Abbreviation normalisation ──
ABBREVIATIONS = {
    "l/fender": "left fender",
    "r/fender": "right fender",
    "l/headlight": "left headlight",
    "r/headlight": "right headlight",
    "l/taillight": "left tail light",
    "r/taillight": "right tail light",
    "l/mirror": "left side mirror",
    "r/mirror": "right side mirror",
    "lh": "left",
    "rh": "right",
    "fr": "front",
    "rr": "rear",
}

def normalise_abbreviations(text: str) -> str:
    """Expand common abbreviations to full component names."""
    for abbr, full in ABBREVIATIONS.items():
        text = re.sub(r'\b' + re.escape(abbr) + r'\b', full, text, flags=re.IGNORECASE)
    return text


# ── Vehicle extraction (unchanged from your latest fix) ──
def extract_vehicle_details(text: str) -> Dict[str, Optional[str]]:
    m_make = re.search(r'Make\s*:\s*(.*?)(?:[\n\r.,]|$)', text, re.IGNORECASE)
    m_model = re.search(r'Model\s*:\s*(.*?)(?:[\n\r.,]|$)', text, re.IGNORECASE)
    m_year = re.search(r'Year\s*:\s*(\d{4})', text, re.IGNORECASE)

    make = m_make.group(1).strip().title() if m_make else None
    model = m_model.group(1).strip().upper() if m_model else None
    year = m_year.group(1) if m_year else None
    if make and model:
        return {"make": make, "model": model, "year": year}
    return {"make": make, "model": model, "year": year}


# ── Free‑text cost patterns (unchanged) ──
COST_LINE_PATTERNS = [
    r'(?P<desc>[A-Za-z\s/&-]+?)\s*[-–:]\s*(?P<currency>[Rr$ZzAaUuSsDd]+)\s*(?P<amount>[\d\s,]+\.?\d{0,2})',
    r'(?P<desc>[A-Za-z\s/&-]+?)\s*[:]\s*(?P<currency>[Rr$ZzAaUuSsDd]+)\s*(?P<amount>[\d\s,]+\.?\d{0,2})',
    r'(?P<currency>[Rr$ZzAaUuSsDd]+)\s*(?P<amount>[\d\s,]+\.?\d{0,2})\s*(?:for|of)\s+(?P<desc>[A-Za-z\s/&-]+)',
    r'Amount\s*[:\-]?\s*(?P<currency>[Rr$ZzAaUuSsDd]+)\s*(?P<amount>[\d\s,]+\.?\d{0,2})\s*\((?P<desc>[^)]+)\)',
]

def _clean_amount(amount_str: str) -> float:
    clean = amount_str.replace(" ", "").replace(",", "")
    try:
        return float(clean)
    except:
        return 0.0


def _map_component(desc: str) -> Optional[Dict[str, Any]]:
    """Return best component ontology entry for a description."""
    best = None
    best_conf = 0.0
    desc_lower = desc.lower()
    for comp in COMPONENT_ONTOLOGY:
        for alias in comp["aliases"]:
            if alias in desc_lower:
                conf = 0.9 if alias == desc_lower else 0.7
                if conf > best_conf:
                    best_conf = conf
                    best = comp
                break
    if best:
        return {
            "component_id": best["component_id"],
            "component_name": best["canonical"],
            "match_confidence": best_conf
        }
    return None


def extract_cost_items_from_text(text: str) -> List[Dict[str, Any]]:
    """Standard regex‑based cost extraction from a text block."""
    items = []
    for pattern in COST_LINE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            desc = match.group("desc").strip().lower()
            currency = match.group("currency").upper()
            amount = _clean_amount(match.group("amount"))
            if amount <= 0:
                continue
            comp = _map_component(desc)
            item = {
                "description": desc,
                "amount": amount,
                "currency": currency,
                "component_id": comp["component_id"] if comp else None,
                "component_name": comp["component_name"] if comp else None,
                "match_confidence": comp["match_confidence"] if comp else 0.0
            }
            items.append(item)
    return items


def extract_table_cost_items(text: str) -> List[Dict[str, Any]]:
    """
    Fallback parser for lines that contain multiple numeric amounts.
    Assumes the first number is the amount (currency taken from context or default 'USD').
    The part description is the leading non‑numeric text.
    """
    items = []
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Split by whitespace, gather all numeric tokens
        tokens = line.split()
        nums = []
        for tok in tokens:
            # Remove commas, check if it's a float
            clean = tok.replace(",", "")
            try:
                val = float(clean)
                nums.append(val)
            except ValueError:
                pass
        if len(nums) >= 1:
            # The description is everything before the first numeric token
            first_num_idx = None
            for i, tok in enumerate(tokens):
                clean = tok.replace(",", "")
                try:
                    float(clean)
                    first_num_idx = i
                    break
                except ValueError:
                    continue
            desc_words = tokens[:first_num_idx] if first_num_idx is not None else tokens[:1]
            desc = " ".join(desc_words).strip().lower()
            if not desc:
                continue
            comp = _map_component(desc)
            # Create one cost item per numeric value (each represents a quote column)
            for col_idx, amount in enumerate(nums):
                # Use a generic currency; will be normalised in fusion
                items.append({
                    "description": desc,
                    "amount": amount,
                    "currency": "USD",   # placeholder, you can improve by detecting currency symbols earlier
                    "component_id": comp["component_id"] if comp else None,
                    "component_name": comp["component_name"] if comp else None,
                    "match_confidence": comp["match_confidence"] if comp else 0.0,
                    "quote_column": col_idx + 1    # 1‑based index of the quote column
                })
    return items


# ── Quotation section splitting ──
SECTION_SEPARATORS = [
    r'REVISED\s*QUOTATION',
    r'QUOTATION\s*\d*',
    r'INVOICE\s*\d*',
    r'PROFORMA\s*\d*',
    r'Make\s*:\s*\S',   # new claim block
]

def split_into_quotation_sections(text: str) -> List[Dict[str, str]]:
    """
    Split the text into multiple quotation sections.
    Returns a list of dicts with keys 'title' and 'content'.
    """
    lines = text.split('\n')
    sections = []
    current_title = "Default Quotation"
    current_content = []
    for line in lines:
        is_sep = False
        for sep_pattern in SECTION_SEPARATORS:
            if re.search(sep_pattern, line, re.IGNORECASE):
                if current_content:
                    sections.append({
                        "title": current_title,
                        "content": "\n".join(current_content)
                    })
                current_title = line.strip()
                current_content = []
                is_sep = True
                break
        if not is_sep:
            current_content.append(line)
    if current_content:
        sections.append({
            "title": current_title,
            "content": "\n".join(current_content)
        })
    return sections


def extract_all_quotations(text: str) -> List[Dict[str, Any]]:
    """
    High‑level function: normalise abbreviations, split into sections,
    extract cost items from each section (using regex or table fallback),
    and return a structured list of quotation sections.
    """
    # Normalise first
    normalised = normalise_abbreviations(text)

    sections = split_into_quotation_sections(normalised)
    result = []
    for sec in sections:
        # Try regex first
        regex_items = extract_cost_items_from_text(sec["content"])
        if len(regex_items) >= 2:   # at least 2 cost lines suggests a proper quote
            items = regex_items
            method = "regex"
        else:
            # Fall back to table parser
            table_items = extract_table_cost_items(sec["content"])
            items = table_items
            method = "table"
        result.append({
            "section_title": sec["title"],
            "items": items,
            "extraction_method": method
        })
    return result

# ---- Legacy wrapper for backward compatibility ----
def extract_cost_items(text: str, components: List[Dict] = None) -> List[Dict[str, Any]]:
    """Return flat list of cost items (for existing callers)."""
    all_sections = extract_all_quotations(text)
    flat = []
    for sec in all_sections:
        flat.extend(sec["items"])
    return flat

# ---- Anomaly detection (unchanged, works on flat list) ----
def flag_anomalies(cost_items: List[Dict[str, Any]], components: List[Dict[str, Any]] = None) -> List[str]:
    """Return list of anomaly strings."""
    flags = []
    for item in cost_items:
        if not item.get("component_id"):
            continue
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