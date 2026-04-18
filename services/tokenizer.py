"""
PII Tokenizer Service
Replaces detected PII entities with deterministic tokens and maintains
a reversible mapping for de-tokenization during query responses.
"""


class PIITokenizer:
    """Replaces PII with tokens (e.g., PERSON_001) and supports reverse mapping."""

    def __init__(self):
        self._counters: dict[str, int] = {}
        self._token_to_original: dict[str, str] = {}
        self._original_to_token: dict[str, str] = {}

    def tokenize(self, text: str, entities: list[dict]) -> tuple[str, dict[str, str]]:
        """
        Replace PII entities in text with deterministic tokens.

        Args:
            text: Original text containing PII.
            entities: List of detected PII entities from PIIDetector.

        Returns:
            Tuple of (tokenized_text, token_mapping).
            token_mapping maps token → original value.
        """
        # Sort entities by start position in REVERSE order
        # so replacing from end doesn't shift earlier positions
        sorted_entities = sorted(entities, key=lambda e: e["start"], reverse=True)

        tokenized = text
        token_mapping: dict[str, str] = {}

        for entity in sorted_entities:
            original = entity["text"]
            entity_type = entity["type"]

            # Re-use existing token if same PII value was seen before
            if original in self._original_to_token:
                token = self._original_to_token[original]
            else:
                self._counters[entity_type] = self._counters.get(entity_type, 0) + 1
                token = f"{entity_type}_{self._counters[entity_type]:03d}"
                self._token_to_original[token] = original
                self._original_to_token[original] = token

            tokenized = tokenized[:entity["start"]] + token + tokenized[entity["end"]:]
            token_mapping[token] = original

        return tokenized, token_mapping

    def detokenize(self, text: str, token_mapping: dict[str, str]) -> str:
        """
        Replace tokens back with original PII values.

        Args:
            text: Text containing tokens (e.g., PERSON_001).
            token_mapping: Mapping of token → original value.

        Returns:
            Text with tokens replaced by original PII values.
        """
        result = text
        # Sort by token length (longest first) to avoid partial replacements
        for token in sorted(token_mapping.keys(), key=len, reverse=True):
            result = result.replace(token, token_mapping[token])
        return result

    def get_all_mappings(self) -> dict[str, str]:
        """Return the complete token → original mapping."""
        return dict(self._token_to_original)

    def load_mappings(self, mappings: dict[str, str]):
        """
        Load existing token mappings (e.g., from decrypted vault).

        Args:
            mappings: Dictionary of token → original value.
        """
        self._token_to_original.update(mappings)
        for token, original in mappings.items():
            self._original_to_token[original] = token
            # Update counters based on loaded tokens
            parts = token.rsplit("_", 1)
            if len(parts) == 2:
                entity_type = parts[0]
                try:
                    num = int(parts[1])
                    current = self._counters.get(entity_type, 0)
                    self._counters[entity_type] = max(current, num)
                except ValueError:
                    pass

    def reset(self):
        """Clear all mappings and counters."""
        self._counters.clear()
        self._token_to_original.clear()
        self._original_to_token.clear()
