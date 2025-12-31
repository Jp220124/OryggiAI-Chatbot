"""
Password Security Module
Handles password hashing and verification using bcrypt
"""

import secrets
import string
from typing import Optional

from passlib.context import CryptContext
from loguru import logger


# Configure bcrypt password context
# Using bcrypt with recommended settings
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # Adjust rounds for security/performance balance
)


def hash_password(password: str) -> str:
    """
    Hash a plain text password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Hashed password string

    Example:
        >>> hashed = hash_password("mypassword123")
        >>> hashed.startswith("$2b$")
        True
    """
    if not password:
        raise ValueError("Password cannot be empty")

    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a hashed password.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against

    Returns:
        True if password matches, False otherwise

    Example:
        >>> hashed = hash_password("mypassword123")
        >>> verify_password("mypassword123", hashed)
        True
        >>> verify_password("wrongpassword", hashed)
        False
    """
    if not plain_password or not hashed_password:
        return False

    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.warning(f"Password verification error: {str(e)}")
        return False


def generate_random_password(
    length: int = 16,
    include_special: bool = True
) -> str:
    """
    Generate a cryptographically secure random password.

    Args:
        length: Length of password (default: 16, min: 8)
        include_special: Include special characters (default: True)

    Returns:
        Random password string

    Example:
        >>> pwd = generate_random_password(20)
        >>> len(pwd)
        20
    """
    if length < 8:
        length = 8

    # Character sets
    chars = string.ascii_letters + string.digits

    if include_special:
        chars += "!@#$%^&*()-_=+[]{}|;:,.<>?"

    # Generate password
    password = ''.join(secrets.choice(chars) for _ in range(length))

    return password


def check_password_strength(password: str) -> dict:
    """
    Check password strength and return analysis.

    Args:
        password: Password to analyze

    Returns:
        Dictionary with strength analysis:
        - score: 0-5 strength score
        - feedback: List of improvement suggestions
        - is_strong: Boolean indicating if password meets minimum requirements
    """
    score = 0
    feedback = []

    if not password:
        return {
            "score": 0,
            "feedback": ["Password is required"],
            "is_strong": False
        }

    # Length check
    if len(password) >= 8:
        score += 1
    else:
        feedback.append("Password should be at least 8 characters")

    if len(password) >= 12:
        score += 1

    # Uppercase check
    if any(c.isupper() for c in password):
        score += 1
    else:
        feedback.append("Add uppercase letters")

    # Lowercase check
    if any(c.islower() for c in password):
        score += 1
    else:
        feedback.append("Add lowercase letters")

    # Digit check
    if any(c.isdigit() for c in password):
        score += 1
    else:
        feedback.append("Add numbers")

    # Special character check
    special_chars = set("!@#$%^&*()-_=+[]{}|;:,.<>?/~`")
    if any(c in special_chars for c in password):
        score += 1
    else:
        feedback.append("Add special characters")

    return {
        "score": min(score, 5),
        "feedback": feedback,
        "is_strong": score >= 4 and len(password) >= 8
    }


def needs_rehash(hashed_password: str) -> bool:
    """
    Check if a hashed password needs to be rehashed.
    This happens when the hashing algorithm or parameters change.

    Args:
        hashed_password: The hashed password to check

    Returns:
        True if password needs rehashing
    """
    return pwd_context.needs_update(hashed_password)
