# src/dataset/flat_dataset.py
"""
Convert enriched claims into a flat training table.
Each row = one component‑image pair (or component‑only if no image).
"""

import pandas as pd
from typing import List, Dict, Any

def generate_flat_dataset(enriched_claims: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for claim in enriched_claims:
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
        cost_items = claim.get("cost_breakdown", [])
        images = claim.get("images", [])

        # If no components, create one row per image with placeholder component info
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
                    "cost_amount_usd": None,
                    "cost_original_amount": None,
                    "cost_original_currency": None,
                })
                rows.append(row)
        else:
            for comp in components:
                # Collect all images linked to this component
                linked_imgs = comp.get("linked_image_detections", [])
                if not linked_imgs:
                    # Component without image → one row
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
                    })
                    # Attach cost if any
                    cost = next((c for c in cost_items if c.get("component_id") == comp["component_id"]), None)
                    if cost:
                        row["cost_amount_usd"] = cost["amount_usd"]
                        row["cost_original_amount"] = cost["original_amount"]
                        row["cost_original_currency"] = cost["original_currency"]
                    else:
                        row["cost_amount_usd"] = None
                        row["cost_original_amount"] = None
                        row["cost_original_currency"] = None
                    rows.append(row)
                else:
                    # One row per linked image
                    for img in linked_imgs:
                        row = base.copy()
                        row.update({
                            "component_id": comp["component_id"],
                            "component_name": comp["canonical_name"],
                            "component_category": comp["category"],
                            "component_text_confidence": comp["text_confidence"],
                            "image_path": img["image_path"],
                            "image_page": img["page_number"],
                            "detection_label": None,  # We could aggregate the detection label that matched
                            "detection_confidence": img["confidence"],
                            "detection_bbox_x": img["bbox"]["x"],
                            "detection_bbox_y": img["bbox"]["y"],
                            "detection_bbox_w": img["bbox"]["w"],
                            "detection_bbox_h": img["bbox"]["h"],
                        })
                        # Attach cost if any
                        cost = next((c for c in cost_items if c.get("component_id") == comp["component_id"]), None)
                        if cost:
                            row["cost_amount_usd"] = cost["amount_usd"]
                            row["cost_original_amount"] = cost["original_amount"]
                            row["cost_original_currency"] = cost["original_currency"]
                        else:
                            row["cost_amount_usd"] = None
                            row["cost_original_amount"] = None
                            row["cost_original_currency"] = None
                        rows.append(row)

    return pd.DataFrame(rows)