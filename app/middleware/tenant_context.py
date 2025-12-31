"""
Tenant Context Middleware
Provides tenant isolation and context management for multi-tenant SaaS
"""

import uuid
from contextvars import ContextVar
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from loguru import logger

from app.models.platform import Tenant, TenantDatabase


# Context variables for tenant isolation
_current_tenant_id: ContextVar[Optional[uuid.UUID]] = ContextVar(
    'current_tenant_id', default=None
)
_current_user_id: ContextVar[Optional[uuid.UUID]] = ContextVar(
    'current_user_id', default=None
)
_current_tenant: ContextVar[Optional[Tenant]] = ContextVar(
    'current_tenant', default=None
)


class TenantContext:
    """
    Tenant context manager for multi-tenant operations.

    Provides a request-scoped context for tenant isolation,
    ensuring that all operations within a request are scoped
    to the correct tenant.

    Usage:
        # Set context (done automatically by auth dependency)
        TenantContext.set_current(tenant_id, user_id)

        # Get current tenant ID
        tenant_id = TenantContext.get_tenant_id()

        # Get current user ID
        user_id = TenantContext.get_user_id()

        # Clear context (done at request end)
        TenantContext.clear()
    """

    @staticmethod
    def set_current(
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        tenant: Optional[Tenant] = None
    ) -> None:
        """
        Set the current tenant and user context.

        Args:
            tenant_id: Current tenant's UUID
            user_id: Current user's UUID
            tenant: Optional Tenant object (cached)
        """
        _current_tenant_id.set(tenant_id)
        _current_user_id.set(user_id)
        if tenant:
            _current_tenant.set(tenant)
        logger.debug(f"Tenant context set: tenant={tenant_id}, user={user_id}")

    @staticmethod
    def get_tenant_id() -> Optional[uuid.UUID]:
        """
        Get the current tenant ID.

        Returns:
            Current tenant UUID or None if not set
        """
        return _current_tenant_id.get()

    @staticmethod
    def get_user_id() -> Optional[uuid.UUID]:
        """
        Get the current user ID.

        Returns:
            Current user UUID or None if not set
        """
        return _current_user_id.get()

    @staticmethod
    def get_tenant() -> Optional[Tenant]:
        """
        Get the current tenant object.

        Returns:
            Current Tenant or None if not set
        """
        return _current_tenant.get()

    @staticmethod
    def require_tenant_id() -> uuid.UUID:
        """
        Get the current tenant ID, raising error if not set.

        Returns:
            Current tenant UUID

        Raises:
            RuntimeError: If tenant context is not set
        """
        tenant_id = _current_tenant_id.get()
        if tenant_id is None:
            raise RuntimeError("Tenant context not set. Authentication required.")
        return tenant_id

    @staticmethod
    def require_user_id() -> uuid.UUID:
        """
        Get the current user ID, raising error if not set.

        Returns:
            Current user UUID

        Raises:
            RuntimeError: If user context is not set
        """
        user_id = _current_user_id.get()
        if user_id is None:
            raise RuntimeError("User context not set. Authentication required.")
        return user_id

    @staticmethod
    def clear() -> None:
        """Clear the current tenant context."""
        _current_tenant_id.set(None)
        _current_user_id.set(None)
        _current_tenant.set(None)

    @staticmethod
    def is_set() -> bool:
        """Check if tenant context is set."""
        return _current_tenant_id.get() is not None


class TenantDatabaseResolver:
    """
    Resolves tenant-specific database connections.

    Provides access to tenant databases configured in OryggiAI_Platform.
    Each tenant can have multiple database connections configured.
    """

    def __init__(self, platform_db: Session):
        """
        Initialize resolver with platform database session.

        Args:
            platform_db: Platform database session
        """
        self.platform_db = platform_db

    def get_tenant_databases(
        self,
        tenant_id: Optional[uuid.UUID] = None
    ) -> list[TenantDatabase]:
        """
        Get all databases configured for a tenant.

        Args:
            tenant_id: Tenant ID (defaults to current context)

        Returns:
            List of TenantDatabase objects
        """
        tenant_id = tenant_id or TenantContext.require_tenant_id()

        return self.platform_db.query(TenantDatabase).filter(
            TenantDatabase.tenant_id == tenant_id,
            TenantDatabase.is_active == True
        ).all()

    def get_default_database(
        self,
        tenant_id: Optional[uuid.UUID] = None
    ) -> Optional[TenantDatabase]:
        """
        Get the default (first active) database for a tenant.

        Args:
            tenant_id: Tenant ID (defaults to current context)

        Returns:
            First active TenantDatabase or None if not configured
        """
        tenant_id = tenant_id or TenantContext.require_tenant_id()

        # Return the first active database (ordered by creation date)
        return self.platform_db.query(TenantDatabase).filter(
            TenantDatabase.tenant_id == tenant_id,
            TenantDatabase.is_active == True
        ).order_by(TenantDatabase.created_at).first()

    def get_database_by_id(
        self,
        database_id: uuid.UUID,
        tenant_id: Optional[uuid.UUID] = None
    ) -> Optional[TenantDatabase]:
        """
        Get a specific database by ID, ensuring tenant scope.

        Args:
            database_id: Database UUID
            tenant_id: Tenant ID (defaults to current context)

        Returns:
            TenantDatabase or None if not found
        """
        tenant_id = tenant_id or TenantContext.require_tenant_id()

        return self.platform_db.query(TenantDatabase).filter(
            TenantDatabase.id == database_id,
            TenantDatabase.tenant_id == tenant_id
        ).first()

    def get_database_by_name(
        self,
        name: str,
        tenant_id: Optional[uuid.UUID] = None
    ) -> Optional[TenantDatabase]:
        """
        Get a database by name within tenant scope.

        Args:
            name: Database name
            tenant_id: Tenant ID (defaults to current context)

        Returns:
            TenantDatabase or None if not found
        """
        tenant_id = tenant_id or TenantContext.require_tenant_id()

        return self.platform_db.query(TenantDatabase).filter(
            TenantDatabase.name == name,
            TenantDatabase.tenant_id == tenant_id
        ).first()


def tenant_scoped_query(query, model, tenant_id_column='tenant_id'):
    """
    Add tenant scope to a SQLAlchemy query.

    Args:
        query: SQLAlchemy query object
        model: Model class being queried
        tenant_id_column: Name of the tenant_id column

    Returns:
        Query filtered by current tenant

    Example:
        query = tenant_scoped_query(
            db.query(SomeModel),
            SomeModel
        )
    """
    tenant_id = TenantContext.get_tenant_id()
    if tenant_id is None:
        raise RuntimeError("Cannot create tenant-scoped query without tenant context")

    return query.filter(getattr(model, tenant_id_column) == tenant_id)


def validate_tenant_access(
    resource_tenant_id: uuid.UUID,
    error_message: str = "Access denied to this resource"
) -> bool:
    """
    Validate that the current tenant has access to a resource.

    Args:
        resource_tenant_id: Tenant ID of the resource being accessed
        error_message: Error message for access denied

    Returns:
        True if access is allowed

    Raises:
        PermissionError: If current tenant doesn't match resource tenant
    """
    current_tenant = TenantContext.get_tenant_id()
    if current_tenant is None:
        raise RuntimeError("Tenant context not set")

    if current_tenant != resource_tenant_id:
        logger.warning(
            f"Tenant access violation: {current_tenant} tried to access "
            f"resource belonging to {resource_tenant_id}"
        )
        raise PermissionError(error_message)

    return True


class TenantAuditLogger:
    """
    Audit logging with automatic tenant context.
    """

    @staticmethod
    def log(
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an audit event with tenant context.

        Args:
            action: Action performed (create, read, update, delete)
            resource_type: Type of resource (tenant, user, database, etc.)
            resource_id: ID of the resource
            details: Additional details to log
        """
        tenant_id = TenantContext.get_tenant_id()
        user_id = TenantContext.get_user_id()

        log_data = {
            "tenant_id": str(tenant_id) if tenant_id else None,
            "user_id": str(user_id) if user_id else None,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details
        }

        logger.bind(AUDIT=True).info(
            f"AUDIT: {action} {resource_type} "
            f"[tenant={tenant_id}, user={user_id}, resource={resource_id}]"
        )

        # TODO: Store in audit_logs table
        # This will be implemented when we add the full audit logging system
