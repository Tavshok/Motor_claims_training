# src/dataset/flat_dataset.py
"""
Convert enriched claims into a flat training table.
Each row = one component‑image pair (or component‑only if no image).
Optionally require valid vehicle info (make & model) for cost rows.
"""

import pandas as pd
from typing import List, Dict, Any

def generate_flat_dataset(
    enriched_claims: List[Dict[str, Any]],
    require_vehicle: bool = True
) -> pd.DataFrame:
    """
    Args:
        enriched_claims: list of enriched claim dicts from evidence_fusion.
        require_vehicle: if True, omit rows where vehicle make or model is None.

    Returns:
        DataFrame with one row per component‑image‑cost combination.
    """
    rows = []
    for claim in enriched_claims:
        # Check vehicle requirement early – if enforced and missing, skip the whole claim's cost rows
        if require_vehicle:
            make = claim["vehicle"].get("make")
            model = claim["vehicle"].get("model")
            if not make or not model:
                # Still emit a minimal row without cost if you want component/image data;
                # here we'll simply skip this claim's cost rows entirely.
                # If you prefer to keep component/image rows without costs, you can set
                # a flag. But for pure cost training, skipping is correct.
                continue

        base = {
            "claim_file": claim["file_name"],
            "policy_number": claim.get("policy_number"),
            "claim_number": claim.get("claim_number"),
            "accident_date": claim.get("accident_date"),
            "vehicle_make": claim["vehicle"].get("make"),
            "vehicle_model": claim["vehicle"].get("model"),
            "vehicle_year": claim["vehicle"].get("year"),
            "vehicle_registration": claim["vehicle"].get("registration"),
            "ocr_confidence": claim.get("ocr_confidence"),
            "fraud_risk_score": claim["fraud"].get("risk_score"),
            "fraud_flags": ",".join(claim["fraud"].get("flags", [])),
        }

        components = claim.get("damage_components", [])
        cost_sections = claim.get("cost_breakdown_sections", [])
        images = claim.get("images", [])

        # Flatten cost sections into a list of items with section info
        all_cost_items = []
        for sec in cost_sections:
            for item in sec["items"]:
                item_with_section = dict(item)
                item_with_section["section_title"] = sec["section_title"]
                all_cost_items.append(item_with_section)

        # If no components, create one row per image (if any) with placeholder component info
        if not components:
            for img_meta in images:
                row = base.copy()
                row.update({
                    "component_id": None,
                    "component_name": None,
                    "component_category": None,
                    "component_text_confidence": None,
                    "image_path": img_meta.get("image_path"),
                    "image_page": img_meta.get("page_number"),
                    "detection_label": None,
                    "detection_confidence": None,
                    "detection_bbox_x": None,
                    "detection_bbox_y": None,
                    "detection_bbox_w": None,
                    "detection_bbox_h": None,
                    "section_title": None,
                    "cost_amount_usd": None,
                    "cost_original_amount": None,
                    "cost_original_currency": None,
                    "quote_column": None,
                })
                rows.append(row)
        else:
            for comp in components:
                linked_imgs = comp.get("linked_image_detections", [])
                # Find cost items for this component
                comp_costs = [c for c in all_cost_items if c.get("component_id") == comp["component_id"]]
                if not comp_costs:
                    comp_costs = [{}]  # placeholder for one row without cost
                for cost in comp_costs:
                    if not linked_imgs:
                        row = base.copy()
                        row.update({
                            "component_id": comp["component_id"],
                            "component_name": comp["canonical_name"],
                            "component_category": comp["category"],
                            "component_text_confidence": comp["text_confidence"],
                            "image_path": None,
                            "image_page": None,
                            "detection_label": None,
                            "detection_confidence": None,
                            "detection_bbox_x": None,
                            "detection_bbox_y": None,
                            "detection_bbox_w": None,
                            "detection_bbox_h": None,
                            "section_title": cost.get("section_title"),
                            "cost_amount_usd": cost.get("amount_usd"),
                            "cost_original_amount": cost.get("original_amount"),
                            "cost_original_currency": cost.get("original_currency"),
                            "quote_column": cost.get("quote_column"),
                        })
                        rows.append(row)
                    else:
                        for img in linked_imgs:
                            row = base.copy()
                            row.update({
                                "component_id": comp["component_id"],
                                "component_name": comp["canonical_name"],
                                "component_category": comp["category"],
                                "component_text_confidence": comp["text_confidence"],
                                "image_path": img["image_path"],
                                "image_page": img["page_number"],
                                "detection_label": None,
                                "detection_confidence": img["confidence"],
                                "detection_bbox_x": img["bbox"]["x"],
                                "detection_bbox_y": img["bbox"]["y"],
                                "detection_bbox_w": img["bbox"]["w"],
                                "detection_bbox_h": img["bbox"]["h"],
                                "section_title": cost.get("section_title"),
                                "cost_amount_usd": cost.get("amount_usd"),
                                "cost_original_amount": cost.get("original_amount"),
                                "cost_original_currency": cost.get("original_currency"),
                                "quote_column": cost.get("quote_column"),
                            })
                            rows.append(row)
    return pd.DataFrame(rows)