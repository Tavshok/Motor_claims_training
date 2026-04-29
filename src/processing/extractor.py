import re
import logging
import spacy
from config.settings import PATTERNS

logger = logging.getLogger(__name__)
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    logger.error("spaCy model missing. Run: python -m spacy download en_core_web_sm")
    nlp = None

def extract_with_regex(text):
    fields = {}
    for name, pattern in PATTERNS.items():
        match = re.search(pattern, text, re.IGNORECASE)
        fields[name] = match.group(1).strip() if match else None
    return fields

def extract_with_spacy(text):
    if nlp is None:
        return {}
    doc = nlp(text[:100000])
    entities = {}
    for ent in doc.ents:
        if ent.label_ == "DATE" and "accident_date" not in entities:
            entities["accident_date"] = ent.text
        elif ent.label_ == "MONEY" and "claim_amount" not in entities:
            entities["claim_amount"] = ent.text
    return entities

def hybrid_extraction(text):
    regex_fields = extract_with_regex(text)
    if nlp:
        spacy_fields = extract_with_spacy(text)
        merged = {**spacy_fields, **regex_fields}
    else:
        merged = regex_fields
    return merged
