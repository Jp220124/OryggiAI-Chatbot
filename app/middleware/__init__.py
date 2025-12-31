"""
Middleware Package
Provides role-based access control, data scoping, and multi-tenant context management
"""

from app.middleware.rbac import RBACMiddleware, rbac_middleware
from app.middleware.audit_logger import AuditLogger, audit_logger
from app.middleware.tenant_context import (
    TenantContext,
    TenantDatabaseResolver,
    TenantAuditLogger,
    tenant_scoped_query,
    validate_tenant_access
)

__all__ = [
    "RBACMiddleware",
    "rbac_middleware",
    "AuditLogger",
    "audit_logger",
    "TenantContext",
    "TenantDatabaseResolver",
    "TenantAuditLogger",
    "tenant_scoped_query",
    "validate_tenant_access"
]
