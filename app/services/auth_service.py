"""
Authentication Service
Business logic for user authentication, registration, and token management
"""

import re
import uuid
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session
from loguru import logger

from app.models.platform import Tenant, TenantUser, RefreshToken
from app.security.password import hash_password, verify_password
from app.security.jwt_handler import (
    create_access_token,
    create_refresh_token,
    verify_token,
    decode_token,
    TokenType
)
from app.config import settings


class AuthenticationError(Exception):
    """Custom exception for authentication errors"""
    pass


class RegistrationError(Exception):
    """Custom exception for registration errors"""
    pass


def generate_slug(name: str) -> str:
    """
    Generate a URL-friendly slug from a name.

    Args:
        name: The name to convert to a slug

    Returns:
        URL-friendly slug
    """
    # Convert to lowercase
    slug = name.lower()

    # Replace spaces and special chars with hyphens
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)

    # Remove multiple consecutive hyphens
    slug = re.sub(r'-+', '-', slug)

    # Remove leading/trailing hyphens
    slug = slug.strip('-')

    return slug


def register_tenant(
    db: Session,
    tenant_name: str,
    email: str,
    password: str,
    full_name: str,
    tenant_slug: Optional[str] = None
) -> Tuple[Tenant, TenantUser, str, str]:
    """
    Register a new tenant and create the owner account.

    Args:
        db: Database session
        tenant_name: Name of the tenant organization
        email: Owner's email address
        password: Owner's password (plain text)
        full_name: Owner's full name
        tenant_slug: Optional URL slug (auto-generated if not provided)

    Returns:
        Tuple of (tenant, user, access_token, refresh_token)

    Raises:
        RegistrationError: If registration fails
    """
    # Generate slug if not provided
    if not tenant_slug:
        tenant_slug = generate_slug(tenant_name)

    # Check if tenant slug already exists
    existing_tenant = db.query(Tenant).filter(
        Tenant.slug == tenant_slug
    ).first()
    if existing_tenant:
        # Append UUID suffix to make unique
        tenant_slug = f"{tenant_slug}-{str(uuid.uuid4())[:8]}"

    # Check if email already exists
    existing_user = db.query(TenantUser).filter(
        TenantUser.email == email.lower()
    ).first()
    if existing_user:
        raise RegistrationError(f"Email {email} is already registered")

    try:
        # Create tenant
        tenant = Tenant(
            name=tenant_name,
            slug=tenant_slug,
            admin_email=email.lower(),  # Set admin email
            status='active',
            max_users=10,  # Default limit
            max_databases=3  # Default limit
        )
        db.add(tenant)
        db.flush()  # Get the tenant ID

        logger.info(f"Created tenant: {tenant.name} ({tenant.id})")

        # Parse full_name into first/last
        name_parts = full_name.strip().split(maxsplit=1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        # Create owner user
        user = TenantUser(
            tenant_id=tenant.id,
            email=email.lower(),
            password_hash=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            display_name=full_name,
            role='owner',
            is_active=True,
            is_verified=False  # Will need email verification flow
        )
        db.add(user)
        db.flush()  # Get the user ID

        logger.info(f"Created owner user: {user.email} ({user.id})")

        # Generate tokens
        access_token = create_access_token(
            user_id=user.id,
            tenant_id=tenant.id,
            email=user.email,
            role=user.role
        )

        refresh_token_str, token_hash, expires_at = create_refresh_token(
            user_id=user.id,
            tenant_id=tenant.id
        )

        # Store refresh token
        refresh_token = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at
        )
        db.add(refresh_token)

        db.commit()

        logger.info(f"Tenant registration complete: {tenant.name}")

        return tenant, user, access_token, refresh_token_str

    except RegistrationError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Registration failed: {str(e)}")
        raise RegistrationError(f"Registration failed: {str(e)}")


def register_user(
    db: Session,
    tenant_id: uuid.UUID,
    email: str,
    password: str,
    full_name: str,
    role: str = 'user'
) -> TenantUser:
    """
    Register a new user within an existing tenant.

    Args:
        db: Database session
        tenant_id: ID of the tenant
        email: User's email address
        password: User's password (plain text)
        full_name: User's full name
        role: User role (admin, manager, user, viewer)

    Returns:
        Created user

    Raises:
        RegistrationError: If registration fails
    """
    # Check if tenant exists
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise RegistrationError("Tenant not found")

    if tenant.status != 'active':
        raise RegistrationError("Tenant is not active")

    # Check user limit
    user_count = db.query(TenantUser).filter(
        TenantUser.tenant_id == tenant_id,
        TenantUser.is_active == True
    ).count()
    if user_count >= tenant.max_users:
        raise RegistrationError("Tenant has reached maximum user limit")

    # Check if email already exists in this tenant
    existing_user = db.query(TenantUser).filter(
        TenantUser.email == email.lower(),
        TenantUser.tenant_id == tenant_id
    ).first()
    if existing_user:
        raise RegistrationError(f"Email {email} is already registered in this tenant")

    try:
        # Parse full_name into first/last
        name_parts = full_name.strip().split(maxsplit=1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        # Create user
        user = TenantUser(
            tenant_id=tenant_id,
            email=email.lower(),
            password_hash=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            display_name=full_name,
            role=role,
            is_active=True,
            is_verified=False
        )
        db.add(user)
        db.commit()

        logger.info(f"Created user: {user.email} in tenant {tenant.name}")

        return user

    except Exception as e:
        db.rollback()
        logger.error(f"User registration failed: {str(e)}")
        raise RegistrationError(f"User registration failed: {str(e)}")


def authenticate_user(
    db: Session,
    email: str,
    password: str
) -> Tuple[TenantUser, Tenant, str, str]:
    """
    Authenticate a user and return tokens.

    Args:
        db: Database session
        email: User's email
        password: User's password

    Returns:
        Tuple of (user, tenant, access_token, refresh_token)

    Raises:
        AuthenticationError: If authentication fails
    """
    # Find user by email
    user = db.query(TenantUser).filter(
        TenantUser.email == email.lower()
    ).first()

    if not user:
        logger.warning(f"Login attempt for non-existent email: {email}")
        raise AuthenticationError("Invalid email or password")

    # Verify password
    if not verify_password(password, user.password_hash):
        logger.warning(f"Invalid password for user: {email}")
        raise AuthenticationError("Invalid email or password")

    # Check if user is active
    if not user.is_active:
        logger.warning(f"Login attempt for inactive user: {email}")
        raise AuthenticationError("User account is deactivated")

    # Get tenant
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    if not tenant or tenant.status != 'active':
        logger.warning(f"Login attempt for user in inactive tenant: {email}")
        raise AuthenticationError("Tenant account is not active")

    # Update last login
    user.last_login_at = datetime.utcnow()
    db.commit()

    # Generate tokens
    access_token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        role=user.role
    )

    refresh_token_str, token_hash, expires_at = create_refresh_token(
        user_id=user.id,
        tenant_id=user.tenant_id
    )

    # Store refresh token
    refresh_token = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at
    )
    db.add(refresh_token)
    db.commit()

    logger.info(f"User logged in: {email}")

    return user, tenant, access_token, refresh_token_str


def refresh_access_token(
    db: Session,
    refresh_token_str: str
) -> Tuple[str, str]:
    """
    Refresh an access token using a refresh token.

    Args:
        db: Database session
        refresh_token_str: The refresh token string

    Returns:
        Tuple of (new_access_token, new_refresh_token)

    Raises:
        AuthenticationError: If token is invalid or expired
    """
    try:
        # Verify the refresh token
        payload = verify_token(refresh_token_str, TokenType.REFRESH)
        if not payload:
            raise AuthenticationError("Invalid refresh token")

        user_id = uuid.UUID(payload.sub)
        tenant_id = uuid.UUID(payload.tenant_id)

        # Hash the token to compare with stored hash
        token_hash = hashlib.sha256(refresh_token_str.encode()).hexdigest()

        # Find the stored refresh token
        stored_token = db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash,
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False
        ).first()

        if not stored_token:
            raise AuthenticationError("Refresh token not found or revoked")

        if stored_token.expires_at < datetime.utcnow():
            raise AuthenticationError("Refresh token has expired")

        # Get user and tenant
        user = db.query(TenantUser).filter(TenantUser.id == user_id).first()
        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive")

        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant or tenant.status != 'active':
            raise AuthenticationError("Tenant not found or inactive")

        # Revoke old refresh token
        stored_token.is_revoked = True
        stored_token.revoked_at = datetime.utcnow()

        # Generate new tokens
        new_access_token = create_access_token(
            user_id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            role=user.role
        )

        new_refresh_token_str, new_token_hash, expires_at = create_refresh_token(
            user_id=user.id,
            tenant_id=user.tenant_id
        )

        # Store new refresh token
        new_refresh_token = RefreshToken(
            user_id=user.id,
            token_hash=new_token_hash,
            expires_at=expires_at
        )
        db.add(new_refresh_token)
        db.commit()

        logger.info(f"Token refreshed for user: {user.email}")

        return new_access_token, new_refresh_token_str

    except AuthenticationError:
        raise
    except Exception as e:
        logger.error(f"Token refresh failed: {str(e)}")
        raise AuthenticationError("Token refresh failed")


def logout_user(
    db: Session,
    user_id: uuid.UUID,
    refresh_token_str: Optional[str] = None
) -> bool:
    """
    Logout a user by revoking their refresh tokens.

    Args:
        db: Database session
        user_id: User's ID
        refresh_token_str: Optional specific refresh token to revoke

    Returns:
        True if logout successful
    """
    try:
        if refresh_token_str:
            # Revoke specific token
            token_hash = hashlib.sha256(refresh_token_str.encode()).hexdigest()
            token = db.query(RefreshToken).filter(
                RefreshToken.token_hash == token_hash,
                RefreshToken.user_id == user_id
            ).first()
            if token:
                token.is_revoked = True
                token.revoked_at = datetime.utcnow()
        else:
            # Revoke all user tokens
            db.query(RefreshToken).filter(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked == False
            ).update({
                "is_revoked": True,
                "revoked_at": datetime.utcnow()
            })

        db.commit()
        logger.info(f"User logged out: {user_id}")
        return True

    except Exception as e:
        db.rollback()
        logger.error(f"Logout failed: {str(e)}")
        return False


def change_password(
    db: Session,
    user_id: uuid.UUID,
    current_password: str,
    new_password: str
) -> bool:
    """
    Change a user's password.

    Args:
        db: Database session
        user_id: User's ID
        current_password: Current password
        new_password: New password

    Returns:
        True if password changed successfully

    Raises:
        AuthenticationError: If current password is wrong
    """
    user = db.query(TenantUser).filter(TenantUser.id == user_id).first()
    if not user:
        raise AuthenticationError("User not found")

    # Verify current password
    if not verify_password(current_password, user.password_hash):
        raise AuthenticationError("Current password is incorrect")

    # Update password
    user.password_hash = hash_password(new_password)

    # Revoke all refresh tokens (force re-login)
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.is_revoked == False
    ).update({
        "is_revoked": True,
        "revoked_at": datetime.utcnow()
    })

    db.commit()
    logger.info(f"Password changed for user: {user.email}")

    return True


def get_user_by_id(db: Session, user_id: uuid.UUID) -> Optional[TenantUser]:
    """Get a user by their ID"""
    return db.query(TenantUser).filter(TenantUser.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[TenantUser]:
    """Get a user by their email"""
    return db.query(TenantUser).filter(
        TenantUser.email == email.lower()
    ).first()


def get_tenant_by_id(db: Session, tenant_id: uuid.UUID) -> Optional[Tenant]:
    """Get a tenant by their ID"""
    return db.query(Tenant).filter(Tenant.id == tenant_id).first()
