"""Tests for PII Detector service — works with both Presidio and trained NER mode."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.pii_detector import PIIDetector


class TestPIIDetector:

    def setup_method(self):
        self.detector = PIIDetector()

    def test_detect_person_name(self):
        text = "John Smith called the office yesterday."
        entities = self.detector.detect(text)
        assert "PERSON" in [e["type"] for e in entities]

    def test_detect_email(self):
        text = "Contact us at support@example.com for assistance."
        entities = self.detector.detect(text)
        assert "EMAIL_ADDRESS" in [e["type"] for e in entities]

    def test_detect_phone(self):
        text = "Call me at +1 415 234 5678 for more info."
        entities = self.detector.detect(text)
        assert "PHONE_NUMBER" in [e["type"] for e in entities]

    def test_detect_credit_card(self):
        text = "My card number is 4111-1111-1111-1111."
        entities = self.detector.detect(text)
        assert "CREDIT_CARD" in [e["type"] for e in entities]

    def test_no_pii_returns_empty(self):
        text = "The sky is blue and the grass is green."
        entities = self.detector.detect(text)
        assert len(entities) == 0

    def test_multiple_entities(self):
        text = "John Smith (john@email.com) called from +1 415 234 5678."
        entities = self.detector.detect(text)
        assert len(entities) >= 2

    def test_no_false_positive_medical_terms(self):
        text = "Fasting Blood Sugar: 204 mg/dL. Blood Pressure: 162/98 mmHg."
        entities = self.detector.detect(text)
        locations = [e for e in entities if e["type"] == "LOCATION"]
        assert not any("blood" in e["text"].lower() for e in locations)

    def test_no_false_positive_time_of_day(self):
        text = "Take medication once per day in the morning."
        entities = self.detector.detect(text)
        datetimes = [e for e in entities if e["type"] == "DATE_TIME"]
        assert not any(e["text"].lower() in {"morning", "once"} for e in datetimes)

    def test_entity_summary(self):
        entities = [
            {"type": "PERSON",        "text": "John", "start": 0,  "end": 4,  "score": 0.9},
            {"type": "PERSON",        "text": "Jane", "start": 10, "end": 14, "score": 0.9},
            {"type": "EMAIL_ADDRESS", "text": "a@b.com", "start": 20, "end": 27, "score": 0.95},
        ]
        summary = self.detector.get_entity_summary(entities)
        assert summary["PERSON"] == 2
        assert summary["EMAIL_ADDRESS"] == 1

    def test_entities_sorted_by_position(self):
        text = "Contact James Carter at james.carter@techcorp.com or +1 415 234 5678."
        entities = self.detector.detect(text)
        positions = [e["start"] for e in entities]
        assert positions == sorted(positions)

    def test_detector_mode(self):
        assert self.detector.mode in {"presidio", "trained"}
