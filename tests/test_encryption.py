"""Tests for Vault Encryption service."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from services.encryption import VaultEncryption


class TestVaultEncryption:
    """Test AES-256-GCM encryption and decryption."""

    def setup_method(self):
        self.encryptor = VaultEncryption()

    def test_encrypt_decrypt_roundtrip(self):
        data = {"token_mappings": {"PERSON_001": "John Smith", "EMAIL_001": "john@example.com"}}
        password = "testpassword123"

        encrypted = self.encryptor.encrypt(data, password)
        decrypted = self.encryptor.decrypt(encrypted, password)

        assert decrypted == data

    def test_wrong_password_fails(self):
        data = {"key": "value"}
        encrypted = self.encryptor.encrypt(data, "correct_password")

        with pytest.raises(ValueError, match="Decryption failed"):
            self.encryptor.decrypt(encrypted, "wrong_password")

    def test_different_encryptions_produce_different_output(self):
        data = {"key": "value"}
        password = "testpassword123"

        enc1 = self.encryptor.encrypt(data, password)
        enc2 = self.encryptor.encrypt(data, password)

        # Different due to random salt and nonce
        assert enc1 != enc2

    def test_both_decrypt_to_same_data(self):
        data = {"key": "value"}
        password = "testpassword123"

        enc1 = self.encryptor.encrypt(data, password)
        enc2 = self.encryptor.encrypt(data, password)

        assert self.encryptor.decrypt(enc1, password) == self.encryptor.decrypt(enc2, password)

    def test_empty_dict(self):
        data = {}
        password = "testpassword123"
        encrypted = self.encryptor.encrypt(data, password)
        decrypted = self.encryptor.decrypt(encrypted, password)
        assert decrypted == data

    def test_nested_data(self):
        data = {
            "token_mappings": {"PERSON_001": "Alice"},
            "documents": {"doc1": {"filename": "test.pdf", "count": 5}},
            "metadata": {"epsilon": 1.0},
        }
        password = "secure_password_123"
        encrypted = self.encryptor.encrypt(data, password)
        decrypted = self.encryptor.decrypt(encrypted, password)
        assert decrypted == data

    def test_unicode_data(self):
        data = {"name": "José García", "city": "München"}
        password = "testpassword123"
        encrypted = self.encryptor.encrypt(data, password)
        decrypted = self.encryptor.decrypt(encrypted, password)
        assert decrypted == data

    def test_corrupted_data_fails(self):
        data = {"key": "value"}
        encrypted = self.encryptor.encrypt(data, "password")

        corrupted = encrypted[:-5] + b"XXXXX"
        with pytest.raises(ValueError):
            self.encryptor.decrypt(corrupted, "password")

    def test_too_short_data_fails(self):
        with pytest.raises(ValueError, match="too short"):
            self.encryptor.decrypt(b"short", "password")
