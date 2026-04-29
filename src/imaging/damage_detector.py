# src/imaging/damage_detector.py
"""
Automated damage detection using Hugging Face OWL-ViT (zero-shot).
No training required. Uses component ontology names as text prompts.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import torch
from PIL import Image
from transformers import pipeline

# Lazy-load the detector so it's only initialized when called
_detector = None

def _get_detector():
    global _detector
    if _detector is None:
        # Use the zero-shot object detection pipeline
        # Model: google/owlvit-base-patch32 (free, open-source)
        device = 0 if torch.cuda.is_available() else -1  # GPU if available
        _detector = pipeline(
            "zero-shot-object-detection",
            model="google/owlvit-base-patch32",
            device=device
        )
    return _detector

def detect_damage_on_image(
    image_path: Path,
    candidate_components: List[str],
    confidence_threshold: float = 0.15
) -> List[Dict[str, Any]]:
    """
    Run damage detection on a single image.
    
    Args:
        image_path: path to the JPEG/PNG image.
        candidate_components: list of component prompts (e.g., "damaged left fender").
        confidence_threshold: minimum score to keep detection.
    
    Returns:
        List of dicts with label, bbox {x,y,w,h} (normalized 0-1), confidence.
    """
    if not candidate_components:
        return []

    detector = _get_detector()
    try:
        img = Image.open(image_path).convert("RGB")
        results = detector(img, candidate_labels=candidate_components)
    except Exception as e:
        print(f"Detection failure on {image_path}: {e}")
        return []

    detected = []
    for res in results:
        if res["score"] >= confidence_threshold:
            detected.append({
                "label": res["label"],
                "confidence": round(res["score"], 4),
                "bbox": {
                    "x": res["box"]["xmin"],
                    "y": res["box"]["ymin"],
                    "w": res["box"]["xmax"] - res["box"]["xmin"],
                    "h": res["box"]["ymax"] - res["box"]["ymin"],
                }
            })
    return detected

def build_damage_prompts(components: List[Dict[str, Any]]) -> List[str]:
    """
    Convert component ontology dicts into text prompts the model understands.
    Example: "damaged front bumper", "cracked left headlight"
    """
    prompts = []
    for c in components:
        prompts.append(f"damaged {c['canonical'].lower()}")
        prompts.append(f"broken {c['canonical'].lower()}")
        prompts.append(f"dented {c['canonical'].lower()}")
    # Remove duplicates while preserving order
    return list(dict.fromkeys(prompts))