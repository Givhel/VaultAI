"""
Vault Encryption Service
AES-256-GCM encryption with PBKDF2 key derivation for secure PII vault storage.
Each encryption uses a unique salt and nonce for maximum security.
"""

import os
import json
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from config import Config


class VaultEncryption:
    """AES-256-GCM encryption with PBKDF2 key derivation for vault data."""

    def __init__(self):
        self._iterations = Config.PBKDF2_ITERATIONS
        self._key_length = Config.AES_KEY_LENGTH

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """
        Derive an AES key from a password using PBKDF2.

        Args:
            password: User-provided vault password.
            salt: Random salt for key derivation.

        Returns:
            Derived key bytes.
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self._key_length,
            salt=salt,
            iterations=self._iterations,
        )
        return kdf.derive(password.encode("utf-8"))

    def encrypt(self, data: dict, password: str) -> bytes:
        """
        Encrypt vault data using AES-256-GCM.

        Format: [16 bytes salt][12 bytes nonce][ciphertext + tag]

        Args:
            data: Dictionary to encrypt (token mappings, metadata).
            password: User-provided vault password.

        Returns:
            Encrypted bytes blob.
        """
        salt = os.urandom(16)
        key = self._derive_key(password, salt)
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        return salt + nonce + ciphertext

    def decrypt(self, encrypted_data: bytes, password: str) -> dict:
        """
        Decrypt vault data using AES-256-GCM.

        Args:
            encrypted_data: Encrypted bytes blob from encrypt().
            password: User-provided vault password.

        Returns:
            Decrypted dictionary.

        Raises:
            ValueError: If password is wrong or data is corrupted.
        """
        if len(encrypted_data) < 28:
            raise ValueError("Invalid encrypted data: too short")

        salt = encrypted_data[:16]
        nonce = encrypted_data[16:28]
        ciphertext = encrypted_data[28:]

        key = self._derive_key(password, salt)
        aesgcm = AESGCM(key)

        try:
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            return json.loads(plaintext.decode("utf-8"))
        except Exception:
            raise ValueError("Decryption failed — wrong password or corrupted data")
