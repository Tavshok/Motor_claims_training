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
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return cv2.fastNlMeansDenoising(thresh, h=30)

def extract_pdf_content(pdf_path):
    text = ""
    confidences = []
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

    logger.info(f"OCR fallback for {pdf_path}")
    try:
        images = convert_from_path(pdf_path, dpi=300)
    except Exception as e:
        logger.error(f"PDF convert error: {e}")
        return text, 0.0

    for img in images:
        preprocessed = preprocess_image(np.array(img))
        data = pytesseract.image_to_data(preprocessed, output_type=pytesseract.Output.DICT)
        words = []
        for i, w in enumerate(data["text"]):
            conf = int(data["conf"][i])
            if w.strip() and conf > 0:
                words.append(w)
                confidences.append(conf)
        text += " ".join(words) + "\n"

    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    return text, avg_conf
