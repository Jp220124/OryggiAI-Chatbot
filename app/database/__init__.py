"""
Database Module
Handles database connections and operations

This module provides three database connections:
1. Main Database (Oryggi) - Default tenant business data
2. Platform Database (OryggiAI_Platform) - Multi-tenant SaaS metadata
3. Tenant Database Manager - Dynamic connections to tenant databases
"""

# Main database connection (tenant business data)
from app.database.connection import (
    db_manager,
    get_db,
    init_database,
    close_database,
    Base
)

# Platform database connection (multi-tenant SaaS metadata)
from app.database.platform_connection import (
    platform_db,
    get_platform_db,
    init_platform_database,
    close_platform_database,
    PlatformDatabaseManager
)

# Tenant database connection (dynamic multi-tenant connections)
from app.database.tenant_connection import (
    tenant_db_manager,
    TenantDatabaseManager,
    TenantConnectionPool
)

__all__ = [
    # Main database
    "db_manager",
    "get_db",
    "init_database",
    "close_database",
    "Base",

    # Platform database
    "platform_db",
    "get_platform_db",
    "init_platform_database",
    "close_platform_database",
    "PlatformDatabaseManager",

    # Tenant database
    "tenant_db_manager",
    "TenantDatabaseManager",
    "TenantConnectionPool"
]
