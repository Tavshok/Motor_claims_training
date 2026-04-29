# src/fusion/evidence_fusion.py
"""
Multi‑currency aware evidence fusion.
Normalizes all costs to USD as the stable base, while preserving
original currency and amount. Currency rates can be updated on the fly.
"""

from typing import List, Dict, Any, Optional

# ── Exchange rates to USD (approximate, for dataset generation only) ──
# Add or modify entries as currencies change. ZIG is included as placeholder.
CURRENCY_TO_USD = {
    "USD": 1.0,
    "$": 1.0,
    "ZAR": 0.054,        # 1 ZAR ≈ $0.054
    "R": 0.054,
    "BWP": 0.074,        # Botswana pula
    "P": 0.074,
    "ZMW": 0.044,        # Zambian kwacha
    "K": 0.044,
    "EUR": 1.07,
    "€": 1.07,
    "GBP": 1.24,
    "£": 1.24,
    "ZIG": 0.14,         # Zimbabwe Gold – adjust as official rate changes
    "ZWL": 0.0001,       # Old Zimbabwe dollar (practically defunct)
    "NGN": 0.0012,       # Nigerian naira
    "GHS": 0.088,        # Ghanaian cedi
}

# Default currency if symbol not recognised
DEFAULT_CURRENCY = "USD"
DEFAULT_RATE = 1.0

def get_rate(currency_code: str) -> float:
    """Return USD exchange rate for a given currency code."""
    return CURRENCY_TO_USD.get(currency_code.upper(), DEFAULT_RATE)

def normalize_to_usd(amount: float, currency_code: str) -> Dict[str, Any]:
    """
    Returns a dict with original amount, currency, and USD equivalent.
    """
    rate = get_rate(currency_code)
    usd_amount = round(amount * rate, 2) if rate else amount
    return {
        "original_amount": amount,
        "original_currency": currency_code.upper(),
        "amount_usd": usd_amount,
        "rate_used": rate
    }

def fuse_claim_data(
    file_name: str,
    text: str,
    extracted_fields: Dict[str, Any],
    vehicle: Dict[str, Optional[str]],
    components: List[Dict[str, Any]],
    cost_items: List[Dict[str, Any]],
    images: List[Dict[str, Any]],
    fraud: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Combine all claim evidence into a single nested dictionary,
    with all costs normalized to USD.
    """
    # Normalize cost items to USD
    normalized_costs = []
    for item in cost_items:
        currency_info = normalize_to_usd(item["amount"], item["currency"])
        normalized_costs.append({
            "description": item["description"],
            **currency_info,
            "component_id": item["component_id"],
            "component_name": item["component_name"],
            "match_confidence": item["match_confidence"],
        })

    # Enrich components with linked image detections
    enriched_components = []
    for comp in components:
        linked_images = []
        for img_meta in images:
            for det in img_meta.get("detections", []):
                if comp["canonical"].lower() in det["label"].lower():
                    linked_images.append({
                        "image_path": img_meta["image_path"],
                        "page_number": img_meta["page_number"],
                        "confidence": det["confidence"],
                        "bbox": det["bbox"],
                    })
        enriched_components.append({
            "component_id": comp["component_id"],
            "canonical_name": comp["canonical"],
            "category": comp["category"],
            "text_confidence": comp["confidence"],
            "linked_image_detections": linked_images,
            "repair_estimates": comp.get("repair_estimates", {}),
        })

    # Build the final claim object
    claim = {
        "file_name": file_name,
        "vehicle": {
            "make": vehicle.get("make"),
            "model": vehicle.get("model"),
            "year": vehicle.get("year"),
            "registration": extracted_fields.get("vehicle_reg"),
        },
        "policy_number": extracted_fields.get("policy_number"),
        "claim_number": extracted_fields.get("claim_number"),
        "accident_date": extracted_fields.get("accident_date"),
        "ocr_confidence": None,   # will be filled by caller
        "fraud": fraud,
        "damage_components": enriched_components,
        "cost_breakdown": normalized_costs,
        "images": images,
        "extracted_text_summary": text[:500]
    }
    return claim