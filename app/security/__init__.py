"""
Security Module
Handles authentication, authorization, and encryption for multi-tenant SaaS
"""

from app.security.password import (
    hash_password,
    verify_password,
    generate_random_password
)

from app.security.jwt_handler import (
    create_access_token,
    create_refresh_token,
    verify_token,
    decode_token,
    TokenType,
    TokenPayload
)

from app.security.encryption import (
    encrypt_string,
    decrypt_string,
    get_encryption_key
)

__all__ = [
    # Password utilities
    "hash_password",
    "verify_password",
    "generate_random_password",

    # JWT utilities
    "create_access_token",
    "create_refresh_token",
    "verify_token",
    "decode_token",
    "TokenType",
    "TokenPayload",

    # Encryption utilities
    "encrypt_string",
    "decrypt_string",
    "get_encryption_key"
]
