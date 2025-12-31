"""
Platform Models Package
SQLAlchemy ORM models for the OryggiAI Platform database (multi-tenant SaaS)
"""

from app.models.platform.base import PlatformBase
from app.models.platform.tenant import Tenant
from app.models.platform.user import TenantUser, RefreshToken
from app.models.platform.database import TenantDatabase, ConnectionMode
from app.models.platform.schema import SchemaCache, FewShotExample
from app.models.platform.metrics import UsageMetrics, AuditLog
from app.models.platform.api_key import ApiKey
from app.models.platform.gateway import GatewaySession, GatewayQueryLog

__all__ = [
    # Base
    "PlatformBase",

    # Core Models
    "Tenant",
    "TenantUser",
    "RefreshToken",
    "TenantDatabase",
    "ConnectionMode",

    # Schema Models
    "SchemaCache",
    "FewShotExample",

    # Tracking Models
    "UsageMetrics",
    "AuditLog",
    "ApiKey",

    # Gateway Models
    "GatewaySession",
    "GatewayQueryLog",
]
