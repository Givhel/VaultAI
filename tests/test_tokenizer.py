"""Tests for PII Tokenizer service."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.tokenizer import PIITokenizer


class TestPIITokenizer:
    """Test PII tokenization and de-tokenization."""

    def setup_method(self):
        self.tokenizer = PIITokenizer()

    def test_basic_tokenization(self):
        text = "John Smith works at ACME Corp."
        entities = [
            {"type": "PERSON", "start": 0, "end": 10, "score": 0.9, "text": "John Smith"},
        ]
        tokenized, mapping = self.tokenizer.tokenize(text, entities)
        assert "John Smith" not in tokenized
        assert "PERSON_001" in tokenized
        assert mapping["PERSON_001"] == "John Smith"

    def test_detokenization(self):
        mapping = {"PERSON_001": "John Smith"}
        text = "PERSON_001 works at ACME Corp."
        result = self.tokenizer.detokenize(text, mapping)
        assert result == "John Smith works at ACME Corp."

    def test_multiple_entities(self):
        text = "John Smith emailed jane@example.com."
        entities = [
            {"type": "PERSON", "start": 0, "end": 10, "score": 0.9, "text": "John Smith"},
            {"type": "EMAIL_ADDRESS", "start": 19, "end": 35, "score": 0.95, "text": "jane@example.com"},
        ]
        tokenized, mapping = self.tokenizer.tokenize(text, entities)
        assert "John Smith" not in tokenized
        assert "jane@example.com" not in tokenized
        assert len(mapping) == 2

    def test_roundtrip(self):
        text = "Contact John Smith at john@email.com or 555-123-4567."
        entities = [
            {"type": "PERSON", "start": 8, "end": 18, "score": 0.9, "text": "John Smith"},
            {"type": "EMAIL_ADDRESS", "start": 22, "end": 36, "score": 0.95, "text": "john@email.com"},
            {"type": "PHONE_NUMBER", "start": 40, "end": 52, "score": 0.9, "text": "555-123-4567"},
        ]
        tokenized, mapping = self.tokenizer.tokenize(text, entities)
        restored = self.tokenizer.detokenize(tokenized, mapping)
        assert restored == text

    def test_duplicate_entity_reuses_token(self):
        text = "John Smith met John Smith at the park."
        entities = [
            {"type": "PERSON", "start": 0, "end": 10, "score": 0.9, "text": "John Smith"},
            {"type": "PERSON", "start": 15, "end": 25, "score": 0.9, "text": "John Smith"},
        ]
        tokenized, mapping = self.tokenizer.tokenize(text, entities)
        # Same PII should get same token
        assert tokenized.count("PERSON_001") == 2
        assert len(mapping) == 1

    def test_load_mappings(self):
        existing = {"PERSON_001": "Alice", "EMAIL_001": "alice@mail.com"}
        self.tokenizer.load_mappings(existing)

        text = "Alice sent an email."
        entities = [
            {"type": "PERSON", "start": 0, "end": 5, "score": 0.9, "text": "Alice"},
        ]
        tokenized, mapping = self.tokenizer.tokenize(text, entities)
        assert "PERSON_001" in tokenized  # Reused existing mapping

    def test_reset(self):
        text = "John Smith is here."
        entities = [{"type": "PERSON", "start": 0, "end": 10, "score": 0.9, "text": "John Smith"}]
        self.tokenizer.tokenize(text, entities)

        self.tokenizer.reset()
        assert self.tokenizer.get_all_mappings() == {}

    def test_empty_entities(self):
        text = "No PII here."
        tokenized, mapping = self.tokenizer.tokenize(text, [])
        assert tokenized == text
        assert mapping == {}
