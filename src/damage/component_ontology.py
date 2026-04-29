# src/damage/component_ontology.py
"""
Comprehensive vehicle component ontology for African motor claims.
Each component has aliases, category, and typical repair/replace cost ranges (ZAR).
Extend or adjust to match your local market.
"""

COMPONENT_ONTOLOGY = [
    # ── Body Panels ──
    {"component_id": "front_bumper",    "canonical": "Front Bumper",    "aliases": ["front bumper", "bumper front", "fr bumper", "front bar"], "category": "body", "repair_cost_estimates": {"replace": (2500, 8000), "repair": (800, 2500)}},
    {"component_id": "rear_bumper",     "canonical": "Rear Bumper",     "aliases": ["rear bumper", "bumper rear", "rr bumper", "rear bar"], "category": "body", "repair_cost_estimates": {"replace": (2200, 7500), "repair": (700, 2200)}},
    {"component_id": "bonnet",          "canonical": "Bonnet",           "aliases": ["bonnet", "hood", "engine hood"], "category": "body", "repair_cost_estimates": {"replace": (3000, 10000), "repair": (1000, 3000)}},
    {"component_id": "boot_lid",        "canonical": "Boot Lid",         "aliases": ["boot lid", "trunk lid", "boot door", "tailgate"], "category": "body", "repair_cost_estimates": {"replace": (2000, 8000), "repair": (800, 2000)}},
    {"component_id": "left_fender",     "canonical": "Left Fender",      "aliases": ["left fender", "lh fender", "fender left", "driver fender"], "category": "body", "repair_cost_estimates": {"replace": (1800, 6000), "repair": (600, 1800)}},
    {"component_id": "right_fender",    "canonical": "Right Fender",     "aliases": ["right fender", "rh fender", "fender right", "passenger fender"], "category": "body", "repair_cost_estimates": {"replace": (1800, 6000), "repair": (600, 1800)}},
    {"component_id": "left_front_door", "canonical": "Left Front Door",  "aliases": ["left front door", "lh front door", "driver door", "lf door"], "category": "body", "repair_cost_estimates": {"replace": (2500, 9000), "repair": (1000, 3000)}},
    {"component_id": "right_front_door","canonical": "Right Front Door", "aliases": ["right front door", "rh front door", "passenger front door", "rf door"], "category": "body", "repair_cost_estimates": {"replace": (2500, 9000), "repair": (1000, 3000)}},
    {"component_id": "left_rear_door",  "canonical": "Left Rear Door",   "aliases": ["left rear door", "lh rear door", "lr door", "rear left door"], "category": "body", "repair_cost_estimates": {"replace": (2300, 8500), "repair": (900, 2800)}},
    {"component_id": "right_rear_door", "canonical": "Right Rear Door",  "aliases": ["right rear door", "rh rear door", "rr door", "rear right door"], "category": "body", "repair_cost_estimates": {"replace": (2300, 8500), "repair": (900, 2800)}},
    {"component_id": "left_side_mirror","canonical": "Left Side Mirror", "aliases": ["left mirror", "lh mirror", "driver mirror", "left wing mirror", "door mirror left"], "category": "body", "repair_cost_estimates": {"replace": (800, 3500), "repair": (300, 800)}},
    {"component_id": "right_side_mirror","canonical": "Right Side Mirror","aliases": ["right mirror", "rh mirror", "passenger mirror", "right wing mirror", "door mirror right"], "category": "body", "repair_cost_estimates": {"replace": (800, 3500), "repair": (300, 800)}},
    {"component_id": "roof",            "canonical": "Roof",             "aliases": ["roof", "roof panel", "top body"], "category": "body", "repair_cost_estimates": {"replace": (4000, 15000), "repair": (1500, 5000)}},
    {"component_id": "grille",          "canonical": "Grille",           "aliases": ["grille", "grill", "front grille", "radiator grille"], "category": "body", "repair_cost_estimates": {"replace": (800, 3000)}},
    {"component_id": "left_quarter_panel","canonical": "Left Quarter Panel", "aliases": ["left quarter panel", "lh quarter", "rear quarter left"], "category": "body", "repair_cost_estimates": {"replace": (2200, 7000), "repair": (800, 2500)}},
    {"component_id": "right_quarter_panel","canonical": "Right Quarter Panel","aliases": ["right quarter panel", "rh quarter", "rear quarter right"], "category": "body", "repair_cost_estimates": {"replace": (2200, 7000), "repair": (800, 2500)}},

    # ── Lighting ──
    {"component_id": "left_headlight",  "canonical": "Left Headlight",   "aliases": ["left headlight", "lh headlight", "headlight left", "driver headlight"], "category": "lighting", "repair_cost_estimates": {"replace": (1500, 5000)}},
    {"component_id": "right_headlight", "canonical": "Right Headlight",  "aliases": ["right headlight", "rh headlight", "headlight right", "passenger headlight"], "category": "lighting", "repair_cost_estimates": {"replace": (1500, 5000)}},
    {"component_id": "left_tail_light", "canonical": "Left Tail Light",  "aliases": ["left tail light", "lh tail light", "rear light left", "tail lamp left"], "category": "lighting", "repair_cost_estimates": {"replace": (800, 3000)}},
    {"component_id": "right_tail_light","canonical": "Right Tail Light", "aliases": ["right tail light", "rh tail light", "rear light right", "tail lamp right"], "category": "lighting", "repair_cost_estimates": {"replace": (800, 3000)}},
    {"component_id": "fog_light",       "canonical": "Fog Light",        "aliases": ["fog light", "fog lamp", "front fog"], "category": "lighting", "repair_cost_estimates": {"replace": (500, 2000)}},
    {"component_id": "indicator_left",  "canonical": "Left Indicator",   "aliases": ["left indicator", "lh indicator", "turn signal left"], "category": "lighting", "repair_cost_estimates": {"replace": (300, 1200)}},
    {"component_id": "indicator_right", "canonical": "Right Indicator",  "aliases": ["right indicator", "rh indicator", "turn signal right"], "category": "lighting", "repair_cost_estimates": {"replace": (300, 1200)}},

    # ── Glass ──
    {"component_id": "windscreen",      "canonical": "Windscreen",       "aliases": ["windscreen", "windshield", "front glass", "wind screen"], "category": "glass", "repair_cost_estimates": {"replace": (2000, 8000), "repair": (500, 2000)}},
    {"component_id": "rear_window",     "canonical": "Rear Window",      "aliases": ["rear window", "back window", "rear glass", "back glass"], "category": "glass", "repair_cost_estimates": {"replace": (1800, 7000)}},
    {"component_id": "left_front_window","canonical": "Left Front Window","aliases": ["left front window", "lh front window", "driver window"], "category": "glass", "repair_cost_estimates": {"replace": (1000, 4000)}},
    {"component_id": "right_front_window","canonical": "Right Front Window","aliases": ["right front window", "rh front window", "passenger window"], "category": "glass", "repair_cost_estimates": {"replace": (1000, 4000)}},
    {"component_id": "sunroof",         "canonical": "Sunroof",          "aliases": ["sunroof", "moonroof"], "category": "glass", "repair_cost_estimates": {"replace": (3000, 10000)}},

    # ── Mechanical / Cooling ──
    {"component_id": "radiator",        "canonical": "Radiator",         "aliases": ["radiator", "cooling radiator", "rad", "water radiator"], "category": "engine_cooling", "repair_cost_estimates": {"replace": (1500, 6000), "repair": (300, 1500)}},
    {"component_id": "condenser",       "canonical": "Condenser",        "aliases": ["condenser", "ac condenser", "aircon condenser"], "category": "engine_cooling", "repair_cost_estimates": {"replace": (1200, 4500)}},
    {"component_id": "intercooler",     "canonical": "Intercooler",      "aliases": ["intercooler", "charge cooler"], "category": "engine_cooling", "repair_cost_estimates": {"replace": (1500, 5000)}},
    {"component_id": "engine",          "canonical": "Engine",           "aliases": ["engine", "motor", "power unit"], "category": "mechanical", "repair_cost_estimates": {"replace": (25000, 80000), "repair": (5000, 25000)}},
    {"component_id": "gearbox",         "canonical": "Gearbox",          "aliases": ["gearbox", "transmission", "auto box", "manual box"], "category": "mechanical", "repair_cost_estimates": {"replace": (15000, 45000), "repair": (4000, 15000)}},
    {"component_id": "exhaust",         "canonical": "Exhaust",          "aliases": ["exhaust", "silencer", "muffler", "catalytic converter", "cat"], "category": "mechanical", "repair_cost_estimates": {"replace": (2000, 8000), "repair": (500, 2000)}},

    # ── Suspension / Steering ──
    {"component_id": "left_shock",      "canonical": "Left Shock Absorber","aliases": ["left shock", "lh shock", "front left shock", "damper left"], "category": "suspension", "repair_cost_estimates": {"replace": (1200, 4000)}},
    {"component_id": "right_shock",     "canonical": "Right Shock Absorber","aliases": ["right shock", "rh shock", "front right shock", "damper right"], "category": "suspension", "repair_cost_estimates": {"replace": (1200, 4000)}},
    {"component_id": "control_arm_left","canonical": "Left Control Arm",  "aliases": ["left control arm", "lh control arm", "lower arm left", "wishbone left"], "category": "suspension", "repair_cost_estimates": {"replace": (1800, 6000)}},
    {"component_id": "control_arm_right","canonical": "Right Control Arm","aliases": ["right control arm", "rh control arm", "lower arm right", "wishbone right"], "category": "suspension", "repair_cost_estimates": {"replace": (1800, 6000)}},
    {"component_id": "steering_rack",   "canonical": "Steering Rack",    "aliases": ["steering rack", "rack and pinion", "steer rack"], "category": "suspension", "repair_cost_estimates": {"replace": (4000, 15000), "repair": (1500, 5000)}},
    {"component_id": "tie_rod_end",     "canonical": "Tie Rod End",      "aliases": ["tie rod end", "tie rod", "track rod end"], "category": "suspension", "repair_cost_estimates": {"replace": (400, 1500)}},
    {"component_id": "wheel_bearing",   "canonical": "Wheel Bearing",    "aliases": ["wheel bearing", "hub bearing"], "category": "suspension", "repair_cost_estimates": {"replace": (800, 3000)}},

    # ── Interior / Airbags ──
    {"component_id": "dashboard",       "canonical": "Dashboard",        "aliases": ["dashboard", "dash", "instrument panel"], "category": "interior", "repair_cost_estimates": {"replace": (5000, 20000), "repair": (1500, 5000)}},
    {"component_id": "steering_wheel",  "canonical": "Steering Wheel",   "aliases": ["steering wheel", "steer wheel", "wheel"], "category": "interior", "repair_cost_estimates": {"replace": (2000, 8000)}},
    {"component_id": "driver_airbag",   "canonical": "Driver Airbag",    "aliases": ["driver airbag", "airbag driver", "steering airbag"], "category": "safety", "repair_cost_estimates": {"replace": (4000, 12000)}},
    {"component_id": "passenger_airbag","canonical": "Passenger Airbag", "aliases": ["passenger airbag", "airbag passenger", "dash airbag"], "category": "safety", "repair_cost_estimates": {"replace": (4000, 12000)}},
    {"component_id": "seatbelt_left",   "canonical": "Left Seatbelt",    "aliases": ["left seatbelt", "driver seatbelt", "lh seatbelt"], "category": "safety", "repair_cost_estimates": {"replace": (1500, 5000)}},
    {"component_id": "seatbelt_right",  "canonical": "Right Seatbelt",   "aliases": ["right seatbelt", "passenger seatbelt", "rh seatbelt"], "category": "safety", "repair_cost_estimates": {"replace": (1500, 5000)}},
]

import re
from typing import List, Dict, Any

def match_damage_description(text: str) -> List[Dict[str, Any]]:
    """
    Scan text for mentions of vehicle components.
    Returns a list of dicts with component_id, canonical name, matched alias, confidence.
    """
    text_lower = text.lower()
    matches = []
    for comp in COMPONENT_ONTOLOGY:
        for alias in comp["aliases"]:
            if alias in text_lower:
                # Simple confidence boost if damage words are nearby
                confidence = 0.85
                damage_keywords = [
                    "broken", "damaged", "dented", "cracked", "smashed",
                    "replace", "repair", "scratched", "missing", "loose",
                    "twisted", "crushed", "deformed", "leaking"
                ]
                if any(word in text_lower for word in damage_keywords):
                    confidence += 0.05

                # Avoid duplicate component entries
                if not any(m["component_id"] == comp["component_id"] for m in matches):
                    matches.append({
                        "component_id": comp["component_id"],
                        "canonical": comp["canonical"],
                        "matched_alias": alias,
                        "category": comp["category"],
                        "confidence": min(confidence, 1.0),
                        "repair_estimates": comp.get("repair_cost_estimates", {})
                    })
                break  # one alias match per component is enough
    return matches


if __name__ == "__main__":
    sample = "The left fender and front bumper were severely dented. The radiator needs replacement and the driver airbag deployed."
    print(match_damage_description(sample))