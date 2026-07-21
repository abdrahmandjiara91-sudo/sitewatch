"""
Field-level encryption for sensitive data stored at rest in the database
(e.g. telegram_chat_id). Uses Fernet (AES-128 in CBC mode + HMAC), which is
authenticated symmetric encryption from the `cryptography` package.

The encryption key is separate from the JWT SECRET_KEY (best practice: never
reuse a signing key as an encryption key) and is generated once, then
persisted locally — same approach as auth.py's SECRET_KEY.
"""
import os
import base64
import hashlib
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


def _load_or_create_encryption_key() -> bytes:
    env_key = os.getenv("ENCRYPTION_KEY")
    if env_key:
        # Allow a plain passphrase in the env var; derive a valid Fernet key from it.
        return base64.urlsafe_b64encode(hashlib.sha256(env_key.encode()).digest())

    key_path = Path("data") / "encryption.key"
    key_path.parent.mkdir(exist_ok=True)

    if key_path.exists():
        return key_path.read_bytes()

    new_key = Fernet.generate_key()
    key_path.write_bytes(new_key)
    return new_key


_fernet = Fernet(_load_or_create_encryption_key())


def encrypt_value(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    return _fernet.encrypt(value.encode()).decode()


def decrypt_value(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    try:
        return _fernet.decrypt(value.encode()).decode()
    except InvalidToken:
        # Old/unencrypted plaintext value from before this change, or tampered data.
        return None
