"""
Encryption Module
Handles symmetric encryption using Fernet for sensitive data like database credentials
"""

import base64
import hashlib
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from loguru import logger

from app.config import settings


# Cached Fernet instance
_fernet_instance: Optional[Fernet] = None


def get_encryption_key() -> bytes:
    """
    Get or generate a valid Fernet encryption key.

    The key is derived from the ENCRYPTION_KEY setting.
    If the setting is not a valid Fernet key, we derive one using SHA-256.

    Returns:
        32-byte URL-safe base64-encoded key

    Example:
        >>> key = get_encryption_key()
        >>> len(base64.urlsafe_b64decode(key))
        32
    """
    raw_key = settings.encryption_key

    # Check if it's already a valid Fernet key (44 chars, URL-safe base64)
    try:
        # Valid Fernet keys are 32 bytes, base64 encoded = 44 characters
        if len(raw_key) == 44:
            # Try to decode and validate
            decoded = base64.urlsafe_b64decode(raw_key)
            if len(decoded) == 32:
                return raw_key.encode() if isinstance(raw_key, str) else raw_key
    except Exception:
        pass

    # Derive a key from the raw_key using SHA-256
    # This ensures we always have a valid 32-byte key
    hash_bytes = hashlib.sha256(raw_key.encode()).digest()
    derived_key = base64.urlsafe_b64encode(hash_bytes)

    logger.debug("Derived encryption key from configuration")
    return derived_key


def _get_fernet() -> Fernet:
    """
    Get or create the Fernet encryption instance.

    Returns:
        Fernet instance for encryption/decryption
    """
    global _fernet_instance

    if _fernet_instance is None:
        key = get_encryption_key()
        _fernet_instance = Fernet(key)

    return _fernet_instance


def encrypt_string(plaintext: str) -> str:
    """
    Encrypt a string using Fernet symmetric encryption.

    Args:
        plaintext: String to encrypt

    Returns:
        Base64-encoded encrypted string

    Example:
        >>> encrypted = encrypt_string("my-secret-password")
        >>> decrypted = decrypt_string(encrypted)
        >>> decrypted == "my-secret-password"
        True
    """
    if not plaintext:
        return ""

    fernet = _get_fernet()
    encrypted_bytes = fernet.encrypt(plaintext.encode('utf-8'))
    return encrypted_bytes.decode('utf-8')


def decrypt_string(ciphertext: str) -> str:
    """
    Decrypt a Fernet-encrypted string.

    Args:
        ciphertext: Base64-encoded encrypted string

    Returns:
        Decrypted plaintext string

    Raises:
        InvalidToken: If decryption fails (wrong key or corrupted data)

    Example:
        >>> encrypted = encrypt_string("secret")
        >>> decrypt_string(encrypted)
        'secret'
    """
    if not ciphertext:
        return ""

    try:
        fernet = _get_fernet()
        decrypted_bytes = fernet.decrypt(ciphertext.encode('utf-8'))
        return decrypted_bytes.decode('utf-8')

    except InvalidToken:
        logger.error("Decryption failed: Invalid token or wrong encryption key")
        raise

    except Exception as e:
        logger.error(f"Decryption error: {str(e)}")
        raise


def encrypt_dict_values(data: dict, keys_to_encrypt: list) -> dict:
    """
    Encrypt specific values in a dictionary.

    Args:
        data: Dictionary containing values to encrypt
        keys_to_encrypt: List of keys whose values should be encrypted

    Returns:
        Dictionary with specified values encrypted

    Example:
        >>> data = {"host": "localhost", "password": "secret"}
        >>> encrypted = encrypt_dict_values(data, ["password"])
        >>> encrypted["host"]
        'localhost'
        >>> encrypted["password"] != "secret"
        True
    """
    result = data.copy()

    for key in keys_to_encrypt:
        if key in result and result[key]:
            result[key] = encrypt_string(str(result[key]))

    return result


def decrypt_dict_values(data: dict, keys_to_decrypt: list) -> dict:
    """
    Decrypt specific values in a dictionary.

    Args:
        data: Dictionary containing encrypted values
        keys_to_decrypt: List of keys whose values should be decrypted

    Returns:
        Dictionary with specified values decrypted

    Example:
        >>> encrypted = encrypt_dict_values({"password": "secret"}, ["password"])
        >>> decrypted = decrypt_dict_values(encrypted, ["password"])
        >>> decrypted["password"]
        'secret'
    """
    result = data.copy()

    for key in keys_to_decrypt:
        if key in result and result[key]:
            try:
                result[key] = decrypt_string(str(result[key]))
            except Exception as e:
                logger.warning(f"Failed to decrypt {key}: {str(e)}")
                # Keep the original value if decryption fails
                pass

    return result


def generate_fernet_key() -> str:
    """
    Generate a new Fernet encryption key.
    Use this to generate keys for configuration.

    Returns:
        URL-safe base64-encoded 32-byte key

    Example:
        >>> new_key = generate_fernet_key()
        >>> len(new_key)
        44
    """
    return Fernet.generate_key().decode()


def is_encrypted(value: str) -> bool:
    """
    Check if a string appears to be Fernet-encrypted.
    Fernet tokens have a specific format.

    Args:
        value: String to check

    Returns:
        True if string appears to be encrypted

    Example:
        >>> is_encrypted("plain text")
        False
        >>> is_encrypted(encrypt_string("test"))
        True
    """
    if not value or len(value) < 40:
        return False

    try:
        # Fernet tokens start with 'gAAAAA' (version + timestamp)
        # and are valid base64
        return value.startswith('gAAAAA') and len(value) >= 100
    except Exception:
        return False


def rotate_encryption_key(old_ciphertext: str, new_fernet: Fernet) -> str:
    """
    Re-encrypt data with a new key (key rotation).

    Args:
        old_ciphertext: Data encrypted with the current key
        new_fernet: Fernet instance with the new key

    Returns:
        Data re-encrypted with the new key

    Example:
        >>> # When rotating keys:
        >>> new_key = generate_fernet_key()
        >>> new_fernet = Fernet(new_key.encode())
        >>> new_ciphertext = rotate_encryption_key(old_encrypted, new_fernet)
    """
    # Decrypt with current key
    plaintext = decrypt_string(old_ciphertext)

    # Encrypt with new key
    new_ciphertext = new_fernet.encrypt(plaintext.encode('utf-8'))
    return new_ciphertext.decode('utf-8')
