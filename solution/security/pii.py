
import os
import base64
import hmac
import hashlib

from pathlib import Path
from dotenv import load_dotenv
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# Load environment variables from project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def load_key(variable_name: str) -> bytes:
    """Load and validate a 32-byte secret key."""

    value = os.getenv(variable_name)

    if not value:
        raise RuntimeError(f"Missing environment variable: {variable_name}")

    try:
        key = base64.b64decode(value, validate=True)
    except Exception as exc:
        raise RuntimeError(f"Invalid key encoding: {variable_name}") from exc

    if len(key) != 32:
        raise RuntimeError(f"{variable_name} must be 32 bytes")

    return key


AES_KEY = load_key("AES_SECRET_KEY")
HMAC_KEY = load_key("HMAC_SECRET_KEY")


def encrypt_text(plaintext: str) -> bytes:
    """Encrypt text using AES-256-GCM."""

    if not isinstance(plaintext, str):
        raise TypeError("Plaintext must be a string")

    nonce = os.urandom(12)
    aes = AESGCM(AES_KEY)

    ciphertext = aes.encrypt(
        nonce,
        plaintext.encode("utf-8"),
        None
    )

    # Store nonce together with ciphertext
    return nonce + ciphertext


def decrypt_text(encrypted_data: bytes) -> str:
    """Decrypt text previously encrypted using AES-256-GCM."""

    if len(encrypted_data) < 28:
        raise ValueError("Invalid encrypted data")

    nonce = encrypted_data[:12]
    ciphertext = encrypted_data[12:]

    aes = AESGCM(AES_KEY)

    plaintext = aes.decrypt(
        nonce,
        ciphertext,
        None
    )

    return plaintext.decode("utf-8")


def hash_phone(canonical_phone: str) -> str:
    """Generate a deterministic HMAC fingerprint for a phone."""

    return hmac.new(
        HMAC_KEY,
        canonical_phone.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
