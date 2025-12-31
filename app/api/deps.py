"""
API Dependencies
FastAPI dependencies for authentication and authorization
"""

import uuid
from typing import Optional, Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from loguru import logger
import jwt

from app.database.platform_connection import get_platform_db
from app.security.jwt_handler import verify_token, TokenType, TokenPayload
from app.models.platform import TenantUser, Tenant
from app.services.auth_service import get_user_by_id, get_tenant_by_id
from app.middleware.tenant_context import TenantContext


# HTTP Bearer token scheme
security = HTTPBearer(
    scheme_name="JWT",
    description="Enter your JWT access token",
    auto_error=True
)


class CurrentUser:
    """Container for authenticated user context"""

    def __init__(
        self,
        user: TenantUser,
        tenant: Tenant,
        token_payload: TokenPayload
    ):
        self.user = user
        self.tenant = tenant
        self.token_payload = token_payload

    @property
    def user_id(self) -> uuid.UUID:
        return self.user.id

    @property
    def tenant_id(self) -> uuid.UUID:
        return self.tenant.id

    @property
    def email(self) -> str:
        return self.user.email

    @property
    def role(self) -> str:
        return self.user.role

    @property
    def full_name(self) -> str:
        return self.user.full_name


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_platform_db)
) -> CurrentUser:
    """
    Validate JWT token and return current user context.

    Usage:
        @app.get("/protected")
        async def protected_route(current_user: CurrentUser = Depends(get_current_user)):
            return {"user": current_user.email}
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials

    try:
        # Verify and decode the token
        payload = verify_token(token, TokenType.ACCESS)
        if payload is None:
            raise credentials_exception

        user_id = uuid.UUID(payload.sub)
        tenant_id = uuid.UUID(payload.tenant_id)

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {str(e)}")
        raise credentials_exception
    except ValueError as e:
        logger.warning(f"Invalid UUID in token: {str(e)}")
        raise credentials_exception

    # Get user from database
    user = get_user_by_id(db, user_id)
    if user is None:
        logger.warning(f"User not found for token: {user_id}")
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get tenant from database
    tenant = get_tenant_by_id(db, tenant_id)
    if tenant is None:
        logger.warning(f"Tenant not found for token: {tenant_id}")
        raise credentials_exception

    if tenant.status != 'active':
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant account is not active",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Set tenant context for the current request
    TenantContext.set_current(
        tenant_id=tenant.id,
        user_id=user.id,
        tenant=tenant
    )

    return CurrentUser(user=user, tenant=tenant, token_payload=payload)


async def get_current_active_user(
    current_user: CurrentUser = Depends(get_current_user)
) -> CurrentUser:
    """
    Get current active user (alias for get_current_user with active check).
    """
    return current_user


def require_role(*allowed_roles: str):
    """
    Dependency factory for role-based access control.

    Usage:
        @app.get("/admin-only")
        async def admin_route(
            current_user: CurrentUser = Depends(require_role("owner", "admin"))
        ):
            return {"message": "Admin access granted"}
    """
    async def role_checker(
        current_user: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {', '.join(allowed_roles)}"
            )
        return current_user

    return role_checker


def require_owner():
    """Require owner role"""
    return require_role("owner")


def require_admin():
    """Require owner or admin role"""
    return require_role("owner", "admin")


def require_manager():
    """Require owner, admin, or manager role"""
    return require_role("owner", "admin", "manager")


# Type aliases for cleaner dependency injection
CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
OwnerDep = Annotated[CurrentUser, Depends(require_owner())]
AdminDep = Annotated[CurrentUser, Depends(require_admin())]
ManagerDep = Annotated[CurrentUser, Depends(require_manager())]


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: Session = Depends(get_platform_db)
) -> Optional[CurrentUser]:
    """
    Get current user if authenticated, None otherwise.
    Useful for routes that work differently for authenticated vs anonymous users.

    Usage:
        @app.get("/public-or-private")
        async def flexible_route(
            current_user: Optional[CurrentUser] = Depends(get_optional_user)
        ):
            if current_user:
                return {"message": f"Hello, {current_user.email}"}
            return {"message": "Hello, anonymous user"}
    """
    if credentials is None:
        return None

    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None
