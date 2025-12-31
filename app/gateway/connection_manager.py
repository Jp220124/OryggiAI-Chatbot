"""
Gateway Connection Manager

Manages WebSocket connections from on-premises gateway agents.
Provides connection pooling, session management, and health monitoring.
"""

from typing import Dict, Optional, Any, Callable, Awaitable
from datetime import datetime, timedelta
from uuid import uuid4
import asyncio
import json

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger

from app.gateway.schemas import (
    GatewayMessage,
    MessageType,
    AuthRequest,
    AuthResponse,
    AuthStatus,
    QueryRequest,
    QueryResponse,
    QueryStatus,
    Heartbeat,
    HeartbeatAck,
    DatabaseStatus,
    GatewaySessionInfo,
    ErrorMessage,
    parse_gateway_message,
)
from app.gateway.exceptions import (
    GatewayAuthenticationError,
    GatewayConnectionError,
    GatewayTimeoutError,
    GatewayNotConnectedError,
)


class GatewayConnection:
    """Represents a single gateway agent connection"""

    def __init__(
        self,
        websocket: WebSocket,
        session_id: str,
        database_id: str,
        tenant_id: str,
        agent_version: str,
        agent_hostname: Optional[str] = None,
    ):
        self.websocket = websocket
        self.session_id = session_id
        self.database_id = database_id
        self.tenant_id = tenant_id
        self.agent_version = agent_version
        self.agent_hostname = agent_hostname
        self.connected_at = datetime.utcnow()
        self.last_heartbeat = datetime.utcnow()
        self.db_status = DatabaseStatus.CONNECTED
        self.queries_executed = 0
        self.is_active = True
        self._pending_queries: Dict[str, asyncio.Future] = {}

    async def send_message(self, message: GatewayMessage):
        """Send a message to the gateway agent"""
        try:
            await self.websocket.send_json(message.model_dump(mode="json"))
        except Exception as e:
            logger.error(f"Failed to send message to gateway {self.session_id}: {e}")
            self.is_active = False
            raise GatewayConnectionError(f"Failed to send message: {e}")

    async def execute_query(
        self,
        sql_query: str,
        timeout: int = 60,
        max_rows: int = 1000,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> QueryResponse:
        """
        Execute a SQL query through the gateway agent

        Args:
            sql_query: SQL query to execute
            timeout: Query timeout in seconds
            max_rows: Maximum rows to return
            user_id: User who initiated the query
            conversation_id: Associated conversation ID

        Returns:
            QueryResponse with results or error

        Raises:
            GatewayTimeoutError: If query times out
            GatewayConnectionError: If connection fails
        """
        request_id = str(uuid4())

        # Create query request
        query_request = QueryRequest(
            request_id=request_id,
            sql_query=sql_query,
            timeout=timeout,
            max_rows=max_rows,
            user_id=user_id,
            conversation_id=conversation_id,
        )

        # Create future for response
        response_future: asyncio.Future = asyncio.Future()
        self._pending_queries[request_id] = response_future

        try:
            # Send query request
            await self.send_message(query_request)
            logger.debug(f"Sent query request {request_id} to gateway {self.session_id}")

            # Wait for response with timeout
            response = await asyncio.wait_for(response_future, timeout=timeout + 5)
            self.queries_executed += 1
            return response

        except asyncio.TimeoutError:
            logger.warning(f"Query {request_id} timed out on gateway {self.session_id}")
            raise GatewayTimeoutError(
                f"Query timed out after {timeout} seconds",
                details={"request_id": request_id, "session_id": self.session_id},
            )
        finally:
            self._pending_queries.pop(request_id, None)

    def handle_query_response(self, response: QueryResponse):
        """Handle incoming query response from agent"""
        request_id = response.request_id
        future = self._pending_queries.get(request_id)

        if future and not future.done():
            future.set_result(response)
            logger.debug(f"Received query response for {request_id}")
        else:
            logger.warning(f"Received response for unknown/completed request: {request_id}")

    def update_heartbeat(self, heartbeat: Heartbeat):
        """Update connection state from heartbeat"""
        self.last_heartbeat = datetime.utcnow()
        self.db_status = heartbeat.db_status
        self.queries_executed = heartbeat.queries_executed

    def get_session_info(self) -> GatewaySessionInfo:
        """Get session information"""
        return GatewaySessionInfo(
            session_id=self.session_id,
            database_id=self.database_id,
            tenant_id=self.tenant_id,
            connected_at=self.connected_at,
            last_heartbeat=self.last_heartbeat,
            agent_version=self.agent_version,
            agent_hostname=self.agent_hostname,
            db_status=self.db_status,
            queries_executed=self.queries_executed,
            is_active=self.is_active,
        )


class GatewayConnectionManager:
    """
    Manages all gateway agent connections

    Provides:
    - Connection pooling by database ID
    - Authentication handling
    - Query routing to appropriate agent
    - Health monitoring and cleanup
    """

    def __init__(self, heartbeat_timeout: int = 90):
        """
        Initialize connection manager

        Args:
            heartbeat_timeout: Seconds before connection considered dead
        """
        # Map: database_id -> GatewayConnection
        self._connections: Dict[str, GatewayConnection] = {}
        # Map: session_id -> database_id (for reverse lookup)
        self._session_to_db: Dict[str, str] = {}
        self._heartbeat_timeout = timedelta(seconds=heartbeat_timeout)
        self._lock = asyncio.Lock()
        self._auth_handler: Optional[Callable[[AuthRequest], Awaitable[tuple]]] = None

        logger.info("GatewayConnectionManager initialized")

    def set_auth_handler(
        self, handler: Callable[[AuthRequest], Awaitable[tuple]]
    ):
        """
        Set the authentication handler function

        Handler should return: (success: bool, database_id: str, tenant_id: str, error_msg: str)
        """
        self._auth_handler = handler

    async def connect(
        self,
        websocket: WebSocket,
        auth_request: AuthRequest,
    ) -> Optional[GatewayConnection]:
        """
        Authenticate and register a new gateway connection

        Args:
            websocket: WebSocket connection
            auth_request: Authentication request from agent

        Returns:
            GatewayConnection if authenticated, None otherwise
        """
        session_id = str(uuid4())

        # Authenticate the gateway token
        if not self._auth_handler:
            logger.error("No authentication handler configured")
            await self._send_auth_response(
                websocket, AuthStatus.FAILED, error_message="Server misconfiguration"
            )
            return None

        try:
            success, database_id, tenant_id, db_name, error_msg = await self._auth_handler(
                auth_request
            )

            if not success:
                logger.warning(f"Gateway auth failed: {error_msg}")
                await self._send_auth_response(
                    websocket, AuthStatus.FAILED, error_message=error_msg
                )
                return None

        except Exception as e:
            logger.error(f"Auth handler error: {e}")
            await self._send_auth_response(
                websocket, AuthStatus.FAILED, error_message="Authentication error"
            )
            return None

        async with self._lock:
            # Check for existing connection to this database
            if database_id in self._connections:
                old_conn = self._connections[database_id]
                logger.info(
                    f"Replacing existing gateway connection for database {database_id}"
                )
                old_conn.is_active = False
                self._session_to_db.pop(old_conn.session_id, None)

            # Create new connection
            connection = GatewayConnection(
                websocket=websocket,
                session_id=session_id,
                database_id=database_id,
                tenant_id=tenant_id,
                agent_version=auth_request.agent_version,
                agent_hostname=auth_request.agent_hostname,
            )

            self._connections[database_id] = connection
            self._session_to_db[session_id] = database_id

        # Send success response
        await self._send_auth_response(
            websocket,
            AuthStatus.SUCCESS,
            session_id=session_id,
            database_id=database_id,
            database_name=db_name,
        )

        logger.info(
            f"Gateway connected: session={session_id}, database={database_id}, "
            f"agent={auth_request.agent_version}, host={auth_request.agent_hostname}"
        )

        return connection

    async def disconnect(self, session_id: str):
        """Remove a gateway connection"""
        async with self._lock:
            database_id = self._session_to_db.pop(session_id, None)
            if database_id:
                connection = self._connections.pop(database_id, None)
                if connection:
                    connection.is_active = False
                    logger.info(f"Gateway disconnected: session={session_id}, database={database_id}")

    def get_connection(self, database_id: str) -> Optional[GatewayConnection]:
        """Get active connection for a database"""
        connection = self._connections.get(database_id)
        if connection and connection.is_active:
            return connection
        return None

    def is_connected(self, database_id: str) -> bool:
        """Check if a gateway is connected for the database"""
        connection = self.get_connection(database_id)
        if not connection:
            return False

        # Check if heartbeat is recent
        if datetime.utcnow() - connection.last_heartbeat > self._heartbeat_timeout:
            logger.warning(f"Gateway {database_id} heartbeat timeout")
            return False

        return True

    async def execute_query(
        self,
        database_id: str,
        sql_query: str,
        timeout: int = 60,
        max_rows: int = 1000,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> QueryResponse:
        """
        Execute a query through the gateway for a specific database

        Args:
            database_id: Target database ID
            sql_query: SQL query to execute
            timeout: Query timeout
            max_rows: Max rows to return
            user_id: User who initiated query
            conversation_id: Associated conversation

        Returns:
            QueryResponse with results

        Raises:
            GatewayNotConnectedError: If no gateway connected
            GatewayTimeoutError: If query times out
        """
        connection = self.get_connection(database_id)
        if not connection:
            raise GatewayNotConnectedError(
                database_name=database_id,
                details={"database_id": database_id},
            )

        return await connection.execute_query(
            sql_query=sql_query,
            timeout=timeout,
            max_rows=max_rows,
            user_id=user_id,
            conversation_id=conversation_id,
        )

    async def handle_message(
        self, session_id: str, message_data: dict
    ) -> Optional[GatewayMessage]:
        """
        Handle incoming message from a gateway agent

        Args:
            session_id: Session that sent the message
            message_data: Raw message data

        Returns:
            Response message to send back (if any)
        """
        database_id = self._session_to_db.get(session_id)
        if not database_id:
            logger.warning(f"Message from unknown session: {session_id}")
            return ErrorMessage(
                error_code="UNKNOWN_SESSION",
                error_message="Session not found",
            )

        connection = self._connections.get(database_id)
        if not connection:
            return ErrorMessage(
                error_code="CONNECTION_NOT_FOUND",
                error_message="Connection not found",
            )

        try:
            message = parse_gateway_message(message_data)
        except ValueError as e:
            logger.warning(f"Invalid message format: {e}")
            return ErrorMessage(
                error_code="INVALID_MESSAGE",
                error_message=str(e),
            )

        # Handle message by type
        if isinstance(message, Heartbeat):
            connection.update_heartbeat(message)
            return HeartbeatAck(session_id=session_id)

        elif isinstance(message, QueryResponse):
            connection.handle_query_response(message)
            return None  # No response needed

        else:
            logger.warning(f"Unexpected message type from agent: {message.type}")
            return None

    def get_all_sessions(self) -> list[GatewaySessionInfo]:
        """Get info for all active sessions"""
        return [
            conn.get_session_info()
            for conn in self._connections.values()
            if conn.is_active
        ]

    def get_session_info(self, database_id: str) -> Optional[GatewaySessionInfo]:
        """Get session info for a database"""
        connection = self.get_connection(database_id)
        if connection:
            return connection.get_session_info()
        return None

    async def cleanup_stale_connections(self):
        """Remove connections that haven't sent heartbeats"""
        async with self._lock:
            now = datetime.utcnow()
            stale = []

            for db_id, conn in self._connections.items():
                if now - conn.last_heartbeat > self._heartbeat_timeout:
                    stale.append(db_id)
                    conn.is_active = False

            for db_id in stale:
                conn = self._connections.pop(db_id, None)
                if conn:
                    self._session_to_db.pop(conn.session_id, None)
                    logger.info(f"Removed stale gateway connection: {db_id}")

    async def _send_auth_response(
        self,
        websocket: WebSocket,
        status: AuthStatus,
        session_id: Optional[str] = None,
        database_id: Optional[str] = None,
        database_name: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        """Send authentication response"""
        response = AuthResponse(
            status=status,
            session_id=session_id,
            database_id=database_id,
            database_name=database_name,
            heartbeat_interval=30,
            query_timeout=60,
            error_message=error_message,
        )
        await websocket.send_json(response.model_dump(mode="json"))


# Global connection manager instance
gateway_manager = GatewayConnectionManager()
