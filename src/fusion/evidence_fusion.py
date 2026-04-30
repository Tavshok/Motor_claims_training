# src/fusion/evidence_fusion.py
"""
Multi‑quotation aware evidence fusion.
Normalises all costs to USD, keeps original currency and amount.
"""

from typing import List, Dict, Any, Optional
from .currency import get_rate, normalize_to_usd   # if you have a currency module, else define inline

# (Keep your existing CURRENCY_TO_USD and normalize functions)

def fuse_claim_data(
    file_name: str,
    text: str,
    extracted_fields: Dict[str, Any],
    vehicle: Dict[str, Optional[str]],
    components: List[Dict[str, Any]],
    cost_sections: List[Dict[str, Any]],   # <-- changed to list of sections
    images: List[Dict[str, Any]],
    fraud: Dict[str, Any]
) -> Dict[str, Any]:
    # Normalise costs per section
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
                "quote_column": item.get("quote_column")   # optional
            })
        enriched_sections.append({
            "section_title": sec["section_title"],
            "items": norm_items,
            "extraction_method": sec.get("extraction_method", "unknown")
        })

    # Enrich components with linked image detections (unchanged)
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
        "ocr_confidence": None,
        "fraud": fraud,
        "damage_components": enriched_components,
        "cost_breakdown_sections": enriched_sections,   # renamed field
        "images": images,
        "extracted_text_summary": text[:500]
    }
    return claim