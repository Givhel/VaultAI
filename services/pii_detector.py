"""
PII Detection Service
Hybrid approach:
  ▸ Always initializes Presidio + spaCy en_core_web_sm.
  ▸ When USE_TRAINED_NER=true AND models/ner_pii/ exists, also loads
    the fine-tuned spaCy NER model and runs BOTH detectors, merging
    results so that entities detected by *either* system are captured.
  ▸ This specifically fixes missing PERSON detections: Presidio's
    base spaCy model is strong on names, while the fine-tuned model
    may miss them due to limited training data.
"""

import os
import re
from pathlib import Path
from presidio_analyzer import AnalyzerEngine

_FAKE_LOCATIONS = {
    "mobile", "phone", "email", "fax", "web", "url",
    "fasting blood sugar", "blood sugar", "blood pressure",
    "total cholesterol", "lab results", "lab result",
    "morning", "night", "afternoon", "evening",
    "high", "low", "normal", "borderline high",
}
_FAKE_DATETIMES = {"morning", "night", "afternoon", "evening", "once", "twice", "daily", "weekly"}
_FAKE_PHONE_RE  = re.compile(r'^(\d{9}|\d{4}-\d{6}|\d{3}-\d{6}|\d{4,5})$')
_ENTITY_PRIORITY = {
    "CREDIT_CARD": 3, "US_SSN": 3, "US_PASSPORT": 3, "EMAIL_ADDRESS": 3,
    "PHONE_NUMBER": 2, "US_BANK_NUMBER": 2,
    "US_DRIVER_LICENSE": 1, "PERSON": 2, "LOCATION": 1, "DATE_TIME": 1,
}

SUPPORTED_ENTITIES = [
    "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD",
    "US_SSN", "IBAN_CODE", "IP_ADDRESS", "DATE_TIME", "LOCATION",
    "NRP", "MEDICAL_LICENSE", "US_BANK_NUMBER", "US_DRIVER_LICENSE", "US_PASSPORT",
]

TRAINED_MODEL_DIR = Path(__file__).resolve().parent.parent / "models" / "ner_pii"


def _is_false_positive(entity: dict, text: str) -> bool:
    raw, cleaned, etype = entity["text"].strip(), entity["text"].strip().lower(), entity["type"]
    if etype == "LOCATION":
        if cleaned in _FAKE_LOCATIONS: return True
        if len(raw.split()) == 1 and raw.islower(): return True
    if etype == "DATE_TIME":
        if cleaned in _FAKE_DATETIMES: return True
        if re.match(r'^\d{1,4}$', raw): return True
    if etype == "PHONE_NUMBER":
        d = re.sub(r'\D', '', raw)
        if _FAKE_PHONE_RE.match(d) or len(d) == 9: return True
    if etype == "US_DRIVER_LICENSE":
        d = re.sub(r'\D', '', raw)
        ctx = text[max(0, entity["start"]-30):min(len(text), entity["end"]+30)].lower()
        if len(d) <= 6 and any(w in ctx for w in ["policy", "id", "bahi", "aetna", "hlt"]): return True
    return False


def _remove_overlaps(entities: list) -> list:
    if not entities: return []
    entities = sorted(entities, key=lambda e: (e["start"], -e["score"]))
    result = []
    for entity in entities:
        dominated = False
        new_result = []
        for kept in result:
            if entity["start"] < kept["end"] and entity["end"] > kept["start"]:
                pn = _ENTITY_PRIORITY.get(entity["type"], 0)
                pk = _ENTITY_PRIORITY.get(kept["type"], 0)
                if pn > pk or (pn == pk and entity["score"] > kept["score"]):
                    continue
                else:
                    dominated = True
            new_result.append(kept)
        if not dominated:
            result = new_result + [entity]
        else:
            result = new_result + [k for k in result if k not in new_result]
    return sorted(result, key=lambda e: e["start"])


def _merge_entity_lists(primary: list, secondary: list) -> list:
    """Merge two entity lists: keep all primary, add non-overlapping secondary."""
    merged = list(primary)
    for sec in secondary:
        overlaps = False
        for pri in primary:
            # Check if spans overlap
            if sec["start"] < pri["end"] and sec["end"] > pri["start"]:
                overlaps = True
                break
        if not overlaps:
            merged.append(sec)
    return merged


class PIIDetector:
    """
    Detects PII using a hybrid approach:
    - Always runs Presidio for reliable baseline detection.
    - When USE_TRAINED_NER=true, also runs the fine-tuned NER model
      and merges results, ensuring entities from both systems are captured.
    """
    def __init__(self):
        # Always initialize Presidio
        self._analyzer = AnalyzerEngine()

        # Optionally load trained NER model
        use_trained = os.getenv("USE_TRAINED_NER", "false").lower() == "true"
        self._has_trained = False
        if use_trained and TRAINED_MODEL_DIR.exists():
            try:
                import spacy
                self._nlp = spacy.load(str(TRAINED_MODEL_DIR))
                self._has_trained = True
            except Exception as e:
                print(f"WARNING: Could not load trained NER model: {e}")
        elif use_trained and not TRAINED_MODEL_DIR.exists():
            print("WARNING: USE_TRAINED_NER=true but models/ner_pii/ not found. Run train_ner.py first.")

        self._mode = "hybrid" if self._has_trained else "presidio"

    @property
    def mode(self) -> str:
        return self._mode

    def detect(self, text: str, language: str = "en", score_threshold: float = 0.4) -> list:
        # Always run Presidio
        presidio_entities = self._detect_presidio(text, language, score_threshold)

        if self._has_trained:
            # Also run trained NER and merge
            trained_entities = self._detect_trained(text)
            # Merge: use trained as primary (domain-tuned), add non-overlapping Presidio results
            entities = _merge_entity_lists(trained_entities, presidio_entities)
        else:
            entities = presidio_entities

        entities = [e for e in entities if not _is_false_positive(e, text)]
        entities = _remove_overlaps(entities)
        return entities

    def _detect_presidio(self, text, language, score_threshold):
        results = self._analyzer.analyze(text=text, entities=SUPPORTED_ENTITIES,
                                         language=language, score_threshold=score_threshold)
        return [{"type": r.entity_type, "start": r.start, "end": r.end,
                 "score": round(r.score, 3), "text": text[r.start:r.end]} for r in results]

    def _detect_trained(self, text):
        doc = self._nlp(text)
        return [{"type": ent.label_, "start": ent.start_char, "end": ent.end_char,
                 "score": 0.85, "text": ent.text}
                for ent in doc.ents if ent.label_ in SUPPORTED_ENTITIES]

    def get_entity_summary(self, entities: list) -> dict:
        summary = {}
        for e in entities:
            summary[e["type"]] = summary.get(e["type"], 0) + 1
        return summary
