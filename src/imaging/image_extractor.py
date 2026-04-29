# src/imaging/image_extractor.py
"""
Extract images from a PDF – embedded images first, then full‑page fallback.
Saves images and returns metadata for evidence fusion.
"""

from pathlib import Path
from typing import List, Dict, Any
import PyPDF2
from pdf2image import convert_from_path
import hashlib
import cv2
import numpy as np

def _save_image(image_bytes: bytes, filename: str, folder: Path) -> Path:
    """Save raw bytes as an image file, return its path."""
    save_path = folder / filename
    with open(save_path, "wb") as f:
        f.write(image_bytes)
    return save_path

def extract_images_from_pdf(pdf_path: Path, output_dir: Path) -> List[Dict[str, Any]]:
    """
    Extract images from a PDF. Returns list of image metadata dicts.
    """
    stem = pdf_path.stem
    img_folder = output_dir / f"{stem}_images"
    img_folder.mkdir(parents=True, exist_ok=True)

    extracted = []

    # ---- Phase 1: try to extract embedded images ----
    try:
        reader = PyPDF2.PdfReader(str(pdf_path))
        for page_idx, page in enumerate(reader.pages):
            page_num = page_idx + 1
            if hasattr(page, 'images'):
                for img_idx, image in enumerate(page.images):
                    try:
                        img_bytes = image.data
                        img_hash = hashlib.md5(img_bytes).hexdigest()[:12]
                        ext = "png" if b'PNG' in img_bytes[:8] else "jpg"
                        filename = f"page{page_num}_img{img_idx+1}_{img_hash}.{ext}"
                        save_path = _save_image(img_bytes, filename, img_folder)
                        extracted.append({
                            "image_id": img_hash,
                            "page_number": page_num,
                            "image_path": str(save_path.relative_to(output_dir.parent)),
                            "bbox": {"x": 0, "y": 0, "w": 1, "h": 1},
                            "damage_label": "",
                            "source": "embedded"
                        })
                    except:
                        continue
    except:
        pass

    # ---- Phase 2: if no embedded images, render whole pages ----
    if not extracted:
        try:
            # Render each page at 150 DPI (good balance quality/size)
            images = convert_from_path(pdf_path, dpi=150)
            for page_idx, pil_img in enumerate(images):
                page_num = page_idx + 1
                # Convert PIL to OpenCV image, then to JPEG bytes
                opencv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
                success, jpg_bytes = cv2.imencode(".jpg", opencv_img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                if not success:
                    continue
                img_bytes = jpg_bytes.tobytes()
                img_hash = hashlib.md5(img_bytes).hexdigest()[:12]
                filename = f"page{page_num}_full_{img_hash}.jpg"
                save_path = _save_image(img_bytes, filename, img_folder)
                extracted.append({
                    "image_id": img_hash,
                    "page_number": page_num,
                    "image_path": str(save_path.relative_to(output_dir.parent)),
                    "bbox": {"x": 0, "y": 0, "w": 1, "h": 1},
                    "damage_label": "",
                    "source": "full_page_render"
                })
        except Exception as e:
            # poppler missing?
            pass

    return extracted