# src/cost/cost_breakdown.py
"""
Multi‑quotation, table‑aware cost extraction with abbreviation normalisation.
Now captures repair costs from assessor report formats and ignores template noise.
"""

import re
from typing import List, Dict, Any, Optional
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
    for abbr, full in ABBREVIATIONS.items():
        text = re.sub(r'\b' + re.escape(abbr) + r'\b', full, text, flags=re.IGNORECASE)
    return text


# ── Vehicle extraction ──
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


# ── Cost line patterns ──
COST_LINE_PATTERNS = [
    # "REPAIR COST $1610.00" or "REPAIR COST $ 1610.00"
    r'(?:REPAIR|REPAIR\s*COST)\s*\$?\s*(?P<amount>[\d,]+\.?\d{0,2})',
    # "NET COST $1260.00"
    r'NET\s*COST\s*\$?\s*(?P<amount>[\d,]+\.?\d{0,2})',
    # "Cost Agreed $927.45"
    r'Cost\s*Agreed\s*\$?\s*(?P<amount>[\d,]+\.?\d{0,2})',
    # "Market Value : $7 000.00   REPAIR COST"
    r'Market\s*Value\s*[:\-]?\s*\$?\s*(?P<amount>[\d,\s]+\.?\d{0,2})',
    # Standard: "Front bumper – R1 200"
    r'(?P<desc>[A-Za-z\s/&-]+?)\s*[-–:]\s*(?P<currency>[Rr$ZzAaUuSsDd]+)\s*(?P<amount>[\d\s,]+\.?\d{0,2})',
    # "R1 200 for front bumper"
    r'(?P<currency>[Rr$ZzAaUuSsDd]+)\s*(?P<amount>[\d\s,]+\.?\d{0,2})\s*(?:for|of)\s+(?P<desc>[A-Za-z\s/&-]+)',
    # "Amount: R1200.00 (Front bumper)"
    r'Amount\s*[:\-]?\s*(?P<currency>[Rr$ZzAaUuSsDd]+)\s*(?P<amount>[\d\s,]+\.?\d{0,2})\s*\((?P<desc>[^)]+)\)',
    # Simple dollar amount: "$ 1610.00" standing alone
    r'\$\s*(?P<amount>[\d,]+\.?\d{2})',
]

# Ignore amounts that are clearly not costs
EXCLUDED_DESCRIPTIONS = [
    "rev", "issued", "speedo", "reading", "token", "contact details",
    "date", "time", "year", "excess", "betterment"
]
MIN_COST_AMOUNT = 5.0         # ignore amounts < $5
MAX_COST_AMOUNT = 100000.0    # ignore amounts > $100,000 (likely not a repair cost)

def _clean_amount(amount_str: str) -> float:
    clean = amount_str.replace(" ", "").replace(",", "")
    try:
        return float(clean)
    except:
        return 0.0


def _map_component(desc: str) -> Optional[Dict[str, Any]]:
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


def _check_implausible(item: Dict[str, Any]) -> bool:
    if item["amount"] > 10000:
        return True
    if item.get("component_id"):
        comp = next((c for c in COMPONENT_ONTOLOGY if c["component_id"] == item["component_id"]), None)
        if comp:
            hi_replace = comp.get("repair_cost_estimates", {}).get("replace", (0, 0))[1]
            if hi_replace > 0 and item["amount"] > hi_replace * 3:
                return True
    return False


def _is_excluded_description(desc: str) -> bool:
    """Return True if the description is a known template line."""
    desc_lower = desc.strip().lower()
    for excluded in EXCLUDED_DESCRIPTIONS:
        if excluded in desc_lower:
            return True
    # Also exclude if desc is just a date pattern
    if re.match(r'^\d{2,4}$', desc_lower):
        return True
    return False


def extract_cost_items_from_text(text: str) -> List[Dict[str, Any]]:
    items = []
    seen_amounts = set()  # avoid duplicates

    for pattern in COST_LINE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            amount = _clean_amount(match.group("amount"))
            # Sanity checks
            if amount < MIN_COST_AMOUNT or amount > MAX_COST_AMOUNT:
                continue
            if amount in seen_amounts:
                continue

            # Determine description
            desc = ""
            currency = "$"
            try:
                desc = match.group("desc").strip().lower()
            except IndexError:
                desc = "_repair_cost_"  # placeholder for patterns without desc
            try:
                currency = match.group("currency").upper()
            except IndexError:
                currency = "$"

            if _is_excluded_description(desc):
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
            item["implausible"] = _check_implausible(item)
            items.append(item)
            seen_amounts.add(amount)
    return items


def extract_table_cost_items(text: str) -> List[Dict[str, Any]]:
    """Fallback table parser – only for amounts that look like repair costs."""
    items = []
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Skip known non‑cost lines
        if _is_excluded_description(line):
            continue
        tokens = line.split()
        nums = []
        for tok in tokens:
            clean = tok.replace(",", "")
            try:
                val = float(clean)
                nums.append(val)
            except ValueError:
                pass
        if len(nums) >= 1:
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
            if not desc or _is_excluded_description(desc):
                continue
            comp = _map_component(desc)
            for col_idx, amount in enumerate(nums):
                if amount < MIN_COST_AMOUNT or amount > MAX_COST_AMOUNT:
                    continue
                item = {
                    "description": desc,
                    "amount": amount,
                    "currency": "USD",
                    "component_id": comp["component_id"] if comp else None,
                    "component_name": comp["component_name"] if comp else None,
                    "match_confidence": comp["match_confidence"] if comp else 0.0,
                    "quote_column": col_idx + 1
                }
                item["implausible"] = _check_implausible(item)
                items.append(item)
    return items


# ── Quotation section splitting ──
SECTION_SEPARATORS = [
    r'REVISED\s*QUOTATION',
    r'QUOTATION\s*\d*',
    r'INVOICE\s*\d*',
    r'PROFORMA\s*\d*',
    r'Make\s*:\s*\S',
]

def split_into_quotation_sections(text: str) -> List[Dict[str, str]]:
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
    normalised = normalise_abbreviations(text)
    sections = split_into_quotation_sections(normalised)
    result = []
    for sec in sections:
        regex_items = extract_cost_items_from_text(sec["content"])
        if len(regex_items) >= 2:
            items = regex_items
            method = "regex"
        else:
            table_items = extract_table_cost_items(sec["content"])
            items = table_items
            method = "table"
        result.append({
            "section_title": sec["title"],
            "items": items,
            "extraction_method": method
        })
    return result


# ---- Legacy wrapper ----
def extract_cost_items(text: str, components: List[Dict] = None) -> List[Dict[str, Any]]:
    all_sections = extract_all_quotations(text)
    flat = []
    for sec in all_sections:
        flat.extend(sec["items"])
    return flat

# ---- Anomaly detection ----
def flag_anomalies(cost_items: List[Dict[str, Any]], components: List[Dict[str, Any]] = None) -> List[str]:
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