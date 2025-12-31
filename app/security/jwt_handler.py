"""
JWT Handler Module
Manages JSON Web Token creation, verification, and decoding
"""

import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any

import jwt
from pydantic import BaseModel, Field
from loguru import logger

from app.config import settings


class TokenType(str, Enum):
    """Token type enumeration"""
    ACCESS = "access"
    REFRESH = "refresh"


class TokenPayload(BaseModel):
    """JWT Token Payload Schema"""
    sub: str = Field(..., description="Subject (user ID)")
    tenant_id: str = Field(..., description="Tenant ID")
    email: Optional[str] = Field(None, description="User email (access tokens only)")
    role: Optional[str] = Field(None, description="User role (access tokens only)")
    type: str = Field(..., description="Token type (access/refresh)")
    exp: Optional[datetime] = Field(None, description="Expiration time")
    iat: Optional[datetime] = Field(None, description="Issued at time")
    jti: Optional[str] = Field(None, description="JWT ID (unique identifier)")

    class Config:
        json_schema_extra = {
            "example": {
                "sub": "550e8400-e29b-41d4-a716-446655440000",
                "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "user@example.com",
                "role": "admin",
                "type": "access"
            }
        }


def create_access_token(
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    email: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[Dict[str, Any]] = None
) -> str:
    """
    Create a JWT access token.

    Args:
        user_id: User's UUID
        tenant_id: Tenant's UUID
        email: User's email
        role: User's role
        expires_delta: Custom expiration time (default: from settings)
        additional_claims: Extra claims to include in token

    Returns:
        JWT token string

    Example:
        >>> token = create_access_token(
        ...     user_id=uuid.uuid4(),
        ...     tenant_id=uuid.uuid4(),
        ...     email="user@example.com",
        ...     role="admin"
        ... )
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)

    now = datetime.utcnow()
    expire = now + expires_delta

    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "email": email,
        "role": role,
        "type": TokenType.ACCESS.value,
        "iat": now,
        "exp": expire,
        "jti": str(uuid.uuid4())  # Unique token ID
    }

    # Add any additional claims
    if additional_claims:
        payload.update(additional_claims)

    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )

    return token


def create_refresh_token(
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    expires_delta: Optional[timedelta] = None
) -> tuple:
    """
    Create a JWT refresh token.

    Args:
        user_id: User's UUID
        tenant_id: Tenant's UUID
        expires_delta: Custom expiration time (default: from settings)

    Returns:
        Tuple of (token_string, token_hash, expires_at)
        - token_string: The JWT token to give to the client
        - token_hash: SHA-256 hash for storage
        - expires_at: Token expiration datetime

    Example:
        >>> token, token_hash, expires = create_refresh_token(
        ...     user_id=uuid.uuid4(),
        ...     tenant_id=uuid.uuid4()
        ... )
    """
    import hashlib

    if expires_delta is None:
        expires_delta = timedelta(days=settings.jwt_refresh_token_expire_days)

    now = datetime.utcnow()
    expire = now + expires_delta
    jti = str(uuid.uuid4())

    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "type": TokenType.REFRESH.value,
        "iat": now,
        "exp": expire,
        "jti": jti
    }

    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )

    # Hash the token for storage
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    return token, token_hash, expire


def verify_token(token: str, token_type: TokenType = TokenType.ACCESS) -> Optional[TokenPayload]:
    """
    Verify and decode a JWT token.

    Args:
        token: JWT token string
        token_type: Expected token type (access/refresh)

    Returns:
        TokenPayload if valid, None if invalid

    Raises:
        jwt.ExpiredSignatureError: If token is expired
        jwt.InvalidTokenError: If token is invalid

    Example:
        >>> payload = verify_token(token)
        >>> if payload:
        ...     print(f"User: {payload.email}")
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )

        # Verify token type
        if payload.get("type") != token_type.value:
            logger.warning(f"Token type mismatch: expected {token_type.value}, got {payload.get('type')}")
            return None

        return TokenPayload(**payload)

    except jwt.ExpiredSignatureError:
        logger.debug("Token has expired")
        raise

    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {str(e)}")
        raise


def decode_token(token: str, verify_exp: bool = True) -> Optional[Dict[str, Any]]:
    """
    Decode a JWT token without full validation.
    Useful for extracting payload even from expired tokens.

    Args:
        token: JWT token string
        verify_exp: Whether to verify expiration (default: True)

    Returns:
        Decoded payload dictionary or None if invalid

    Example:
        >>> payload = decode_token(expired_token, verify_exp=False)
    """
    try:
        options = {"verify_exp": verify_exp}
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options=options
        )
        return payload

    except jwt.InvalidTokenError as e:
        logger.warning(f"Failed to decode token: {str(e)}")
        return None


def get_token_expiry(token: str) -> Optional[datetime]:
    """
    Get the expiration time of a token.

    Args:
        token: JWT token string

    Returns:
        Expiration datetime or None if invalid

    Example:
        >>> expiry = get_token_expiry(token)
        >>> if expiry and expiry < datetime.utcnow():
        ...     print("Token expired")
    """
    payload = decode_token(token, verify_exp=False)
    if payload and "exp" in payload:
        return datetime.fromtimestamp(payload["exp"])
    return None


def is_token_expired(token: str) -> bool:
    """
    Check if a token is expired.

    Args:
        token: JWT token string

    Returns:
        True if expired or invalid, False if still valid
    """
    try:
        jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        return False
    except jwt.ExpiredSignatureError:
        return True
    except jwt.InvalidTokenError:
        return True


def extract_user_id(token: str) -> Optional[uuid.UUID]:
    """
    Extract user ID from a token.

    Args:
        token: JWT token string

    Returns:
        User UUID or None if invalid
    """
    payload = decode_token(token, verify_exp=False)
    if payload and "sub" in payload:
        try:
            return uuid.UUID(payload["sub"])
        except ValueError:
            return None
    return None


def extract_tenant_id(token: str) -> Optional[uuid.UUID]:
    """
    Extract tenant ID from a token.

    Args:
        token: JWT token string

    Returns:
        Tenant UUID or None if invalid
    """
    payload = decode_token(token, verify_exp=False)
    if payload and "tenant_id" in payload:
        try:
            return uuid.UUID(payload["tenant_id"])
        except ValueError:
            return None
    return None
