import logging
from pathlib import Path
import PyPDF2
from pdf2image import convert_from_path
import pytesseract
import cv2
import numpy as np

logger = logging.getLogger(__name__)

def preprocess_image(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Apply adaptive thresholding
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, 11, 2)
    denoised = cv2.fastNlMeansDenoising(thresh, h=30)
    return denoised

def extract_pdf_content(pdf_path):
    text = ""
    confidences = []

    # ---- Phase 1: direct text extraction ----
    try:
        reader = PyPDF2.PdfReader(str(pdf_path))
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    except Exception as e:
        logger.warning(f"PyPDF2 error: {e}")

    if len(text.split()) > 50:
        return text, 1.0

    # ---- Phase 2: OCR with multiple attempts ----
    logger.info(f"OCR fallback for {pdf_path}")
    try:
        images = convert_from_path(pdf_path, dpi=300)
    except Exception as e:
        logger.error(f"PDF convert error: {e}")
        return text, 0.0

    for img in images:
        preprocessed = preprocess_image(np.array(img))
        # Try different PSM modes if first attempt yields little
        configs = [
            '--psm 3',   # Fully automatic page segmentation
            '--psm 6',   # Assume a uniform block of text
            '--psm 4',   # Assume a single column of text
        ]
        best_text = ""
        best_conf = []
        for cfg in configs:
            ocr_data = pytesseract.image_to_data(preprocessed, config=cfg,
                                                 output_type=pytesseract.Output.DICT)
            words = []
            confs = []
            for i, word in enumerate(ocr_data["text"]):
                c = int(ocr_data["conf"][i])
                if word.strip() and c > 0:
                    words.append(word)
                    confs.append(c)
            candidate = " ".join(words)
            if len(candidate) > len(best_text):
                best_text = candidate
                best_conf = confs
        text += best_text + "\n"
        confidences.extend(best_conf)

    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    return text, avg_conf