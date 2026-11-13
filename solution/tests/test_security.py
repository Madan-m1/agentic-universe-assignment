
from solution.security.pii import (
    encrypt_text,
    decrypt_text,
    hash_phone
)


def test_encryption_and_decryption():
    original = "Aarav Menon"

    encrypted = encrypt_text(original)
    decrypted = decrypt_text(encrypted)

    assert encrypted != original.encode()
    assert decrypted == original


def test_encryption_uses_random_nonce():
    original = "+919876543210"

    encrypted_one = encrypt_text(original)
    encrypted_two = encrypt_text(original)

    assert encrypted_one != encrypted_two

    assert decrypt_text(encrypted_one) == original
    assert decrypt_text(encrypted_two) == original


def test_phone_hash_is_deterministic():
    phone = "+919876543210"

    hash_one = hash_phone(phone)
    hash_two = hash_phone(phone)

    assert hash_one == hash_two


def test_phone_hash_does_not_expose_phone():
    phone = "+919876543210"

    fingerprint = hash_phone(phone)

    assert phone not in fingerprint
    assert len(fingerprint) == 64
