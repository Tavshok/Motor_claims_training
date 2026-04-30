# src/fusion/evidence_fusion.py
"""
Multi‑quotation aware evidence fusion.
Normalises all costs to USD, keeps original currency and amount.
"""

from typing import List, Dict, Any, Optional

# ── Exchange rates to USD (same as before) ──
CURRENCY_TO_USD = {
    "USD": 1.0,
    "$": 1.0,
    "ZAR": 0.054,
    "R": 0.054,
    "BWP": 0.074,
    "P": 0.074,
    "ZMW": 0.044,
    "K": 0.044,
    "EUR": 1.07,
    "€": 1.07,
    "GBP": 1.24,
    "£": 1.24,
    "ZIG": 0.14,
    "ZWL": 0.0001,
    "NGN": 0.0012,
    "GHS": 0.088,
}

def get_rate(currency_code: str) -> float:
    """Return USD exchange rate for a given currency code."""
    return CURRENCY_TO_USD.get(currency_code.upper(), 1.0)

def normalize_to_usd(amount: float, currency_code: str) -> Dict[str, Any]:
    """Return original amount, currency, and USD equivalent."""
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
    cost_sections: List[Dict[str, Any]],   # <-- list of quotation sections
    images: List[Dict[str, Any]],
    fraud: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Combine all claim evidence into a single nested dictionary,
    with all costs normalized to USD and grouped by quotation section.
    """
    # Normalise cost items per section
    enriched_sections = []
    for sec in cost_sections:
        norm_items = []
        for item in sec.get("items", []):
            currency_info = normalize_to_usd(item["amount"], item["currency"])
            norm_items.append({
                "description": item["description"],
                **currency_info,
                "component_id": item.get("component_id"),
                "component_name": item.get("component_name"),
                "match_confidence": item.get("match_confidence", 0.0),
                "quote_column": item.get("quote_column")
            })
        enriched_sections.append({
            "section_title": sec["section_title"],
            "items": norm_items,
            "extraction_method": sec.get("extraction_method", "unknown")
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

    claim = {
        "file_name": file_name,
        "vehicle": vehicle,
        "policy_number": extracted_fields.get("policy_number"),
        "claim_number": extracted_fields.get("claim_number"),
        "accident_date": extracted_fields.get("accident_date"),
        "ocr_confidence": None,  # will be filled by caller
        "fraud": fraud,
        "damage_components": enriched_components,
        "cost_breakdown_sections": enriched_sections,
        "images": images,
        "extracted_text_summary": text[:500]
    }
    return claim