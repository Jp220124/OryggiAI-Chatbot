"""
Query Router

Routes SQL queries to either the gateway agent or direct connection
based on database configuration and gateway availability.
"""

from typing import Dict, Any, List, Optional
from loguru import logger

from app.gateway.connection_manager import gateway_manager
from app.gateway.schemas import QueryStatus
from app.gateway.exceptions import (
    GatewayNotConnectedError,
    GatewayTimeoutError,
    GatewayQueryError,
)
from app.database.tenant_connection import tenant_db_manager
from app.models.platform import TenantDatabase


class ConnectionMode:
    """Database connection mode constants"""
    AUTO = "auto"  # Try direct first, fallback to gateway
    GATEWAY_ONLY = "gateway_only"  # Only use gateway
    DIRECT_ONLY = "direct_only"  # Only use direct connection


class QueryRouter:
    """
    Routes queries to appropriate connection method

    Connection Modes:
    - AUTO: Try direct connection first, fallback to gateway if connected
    - GATEWAY_ONLY: Only use gateway (for firewalled databases)
    - DIRECT_ONLY: Only use direct connection (legacy behavior)

    The router automatically detects which method works and uses it.
    """

    def __init__(self):
        self._gateway_manager = gateway_manager
        self._direct_manager = tenant_db_manager
        logger.info("QueryRouter initialized")

    async def execute_query(
        self,
        tenant_database: TenantDatabase,
        query: str,
        params: Optional[dict] = None,
        timeout: int = 60,
        max_rows: int = 1000,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute a query using the appropriate connection method

        Args:
            tenant_database: TenantDatabase model instance
            query: SQL query string
            params: Query parameters (for direct connection)
            timeout: Query timeout in seconds
            max_rows: Maximum rows to return
            user_id: User who initiated query
            conversation_id: Associated conversation

        Returns:
            List of result rows as dictionaries

        Raises:
            GatewayNotConnectedError: If gateway required but not connected
            GatewayTimeoutError: If query times out
            Exception: For other query errors
        """
        database_id = str(tenant_database.id)
        connection_mode = getattr(tenant_database, "connection_mode", ConnectionMode.AUTO)

        # Determine connection strategy
        use_gateway = self._should_use_gateway(tenant_database, connection_mode)

        if use_gateway:
            return await self._execute_via_gateway(
                database_id=database_id,
                query=query,
                timeout=timeout,
                max_rows=max_rows,
                user_id=user_id,
                conversation_id=conversation_id,
            )
        else:
            return self._execute_direct(
                tenant_database=tenant_database,
                query=query,
                params=params,
            )

    def _should_use_gateway(
        self,
        tenant_database: TenantDatabase,
        connection_mode: str,
    ) -> bool:
        """
        Determine if gateway should be used for this database

        Args:
            tenant_database: Database configuration
            connection_mode: Connection mode setting

        Returns:
            True if gateway should be used
        """
        database_id = str(tenant_database.id)
        gateway_connected = self._gateway_manager.is_connected(database_id)

        if connection_mode == ConnectionMode.GATEWAY_ONLY:
            # Must use gateway
            if not gateway_connected:
                raise GatewayNotConnectedError(
                    database_name=tenant_database.name,
                    details={
                        "database_id": database_id,
                        "connection_mode": connection_mode,
                    },
                )
            return True

        elif connection_mode == ConnectionMode.DIRECT_ONLY:
            # Never use gateway
            return False

        else:  # AUTO mode
            # Prefer gateway if connected, otherwise try direct
            if gateway_connected:
                logger.debug(f"Using gateway for database {database_id}")
                return True

            # Check if direct connection is possible
            # (e.g., host is accessible)
            try:
                # Quick connectivity test
                self._direct_manager.test_connection(tenant_database)
                logger.debug(f"Using direct connection for database {database_id}")
                return False
            except Exception as e:
                logger.warning(f"Direct connection not available: {e}")
                # Direct failed, gateway not connected - raise error
                raise GatewayNotConnectedError(
                    database_name=tenant_database.name,
                    details={
                        "database_id": database_id,
                        "direct_error": str(e),
                        "gateway_connected": False,
                    },
                )

    async def _execute_via_gateway(
        self,
        database_id: str,
        query: str,
        timeout: int,
        max_rows: int,
        user_id: Optional[str],
        conversation_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Execute query through gateway agent"""
        logger.debug(f"Executing query via gateway for database {database_id}")

        response = await self._gateway_manager.execute_query(
            database_id=database_id,
            sql_query=query,
            timeout=timeout,
            max_rows=max_rows,
            user_id=user_id,
            conversation_id=conversation_id,
        )

        if response.status == QueryStatus.SUCCESS:
            return response.rows or []
        elif response.status == QueryStatus.TIMEOUT:
            raise GatewayTimeoutError(
                f"Query timed out after {timeout} seconds",
                details={"request_id": response.request_id},
            )
        else:
            raise GatewayQueryError(
                f"Query failed: {response.error_message}",
                details={
                    "request_id": response.request_id,
                    "error_code": response.error_code,
                },
            )

    def _execute_direct(
        self,
        tenant_database: TenantDatabase,
        query: str,
        params: Optional[dict],
    ) -> List[Dict[str, Any]]:
        """Execute query via direct database connection"""
        logger.debug(f"Executing query via direct connection for {tenant_database.name}")
        return self._direct_manager.execute_query(
            tenant_database=tenant_database,
            query=query,
            params=params,
        )

    def get_connection_status(
        self,
        tenant_database: TenantDatabase,
    ) -> Dict[str, Any]:
        """
        Get connection status for a database

        Returns:
            Dict with connection status information
        """
        database_id = str(tenant_database.id)
        connection_mode = getattr(tenant_database, "connection_mode", ConnectionMode.AUTO)
        gateway_connected = self._gateway_manager.is_connected(database_id)
        gateway_session = self._gateway_manager.get_session_info(database_id)

        # Test direct connection
        direct_status = None
        try:
            result = self._direct_manager.test_connection(tenant_database)
            direct_status = "connected" if result.get("success") else "failed"
        except Exception as e:
            direct_status = f"error: {str(e)}"

        return {
            "database_id": database_id,
            "database_name": tenant_database.name,
            "connection_mode": connection_mode,
            "gateway": {
                "connected": gateway_connected,
                "session": gateway_session.model_dump() if gateway_session else None,
            },
            "direct": {
                "status": direct_status,
            },
            "effective_method": "gateway" if gateway_connected else "direct",
        }


# Global query router instance
query_router = QueryRouter()
