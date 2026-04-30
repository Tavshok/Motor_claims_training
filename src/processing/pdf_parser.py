import logging
from pathlib import Path
import PyPDF2
from pdf2image import convert_from_path
import pytesseract
import cv2
import numpy as np

logger = logging.getLogger(__name__)

def preprocess_image_heavy(img):
    """Aggressive preprocessing for very poor scans."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Try Otsu threshold
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # If Otsu gives very little white area, use adaptive
    white_pixels = np.sum(otsu == 255)
    if white_pixels < (gray.size * 0.05):   # less than 5% white
        otsu = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY, 11, 2)
    denoised = cv2.fastNlMeansDenoising(otsu, h=30)
    return denoised

def extract_pdf_content(pdf_path):
    text = ""
    confidences = []

    # ---- Phase 1: direct text ----
    try:
        reader = PyPDF2.PdfReader(str(pdf_path))
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    except Exception as e:
        logger.warning(f"PyPDF2 failed: {e}")

    if len(text.split()) > 50:
        return text, 1.0

    # ---- Phase 2: OCR with multiple DPI attempts ----
    images = None
    for dpi in [300, 200, 150]:
        try:
            images = convert_from_path(pdf_path, dpi=dpi)
            break
        except Exception:
            continue

    if not images:
        logger.error(f"Cannot convert PDF to images: {pdf_path}")
        return text, 0.0

    for img in images:
        img_np = np.array(img)
        # Try heavy preprocessing first
        processed = preprocess_image_heavy(img_np)
        
        # OCR with multiple configs
        best_text = ""
        best_conf = []
        for psm in [3, 6, 4]:
            data = pytesseract.image_to_data(processed, config=f'--psm {psm}',
                                             output_type=pytesseract.Output.DICT)
            words = []
            confs = []
            for i, word in enumerate(data["text"]):
                c = int(data["conf"][i])
                if word.strip() and c > 20:   # lower threshold to catch weak text
                    words.append(word)
                    confs.append(c)
            candidate = " ".join(words)
            if len(candidate) > len(best_text):
                best_text = candidate
                best_conf = confs

        # If we got very little, try on grayscale directly
        if len(best_text.split()) < 10:
            gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
            data = pytesseract.image_to_data(gray, config='--psm 3',
                                             output_type=pytesseract.Output.DICT)
            words = []
            confs = []
            for i, word in enumerate(data["text"]):
                c = int(data["conf"][i])
                if word.strip() and c > 20:
                    words.append(word)
                    confs.append(c)
            fallback = " ".join(words)
            if len(fallback) > len(best_text):
                best_text = fallback
                best_conf = confs

        text += best_text + "\n"
        confidences.extend(best_conf)

    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    return text, avg_conf