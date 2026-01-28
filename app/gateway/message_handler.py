"""
Gateway Message Handler

Processes incoming WebSocket messages from gateway agents.
Handles authentication, query execution, and heartbeat management.
"""

from typing import Optional, Tuple
from datetime import datetime
import json

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger
from sqlalchemy.orm import Session

from app.gateway.schemas import (
    MessageType,
    AuthRequest,
    AuthResponse,
    AuthStatus,
    QueryResponse,
    Heartbeat,
    HeartbeatAck,
    ErrorMessage,
    parse_gateway_message,
)
from app.gateway.connection_manager import GatewayConnectionManager, gateway_manager
from app.gateway.exceptions import GatewayProtocolError


class GatewayMessageHandler:
    """
    Handles WebSocket message processing for gateway agents

    Responsibilities:
    - Process authentication requests
    - Route messages to appropriate handlers
    - Manage connection lifecycle
    """

    def __init__(self, connection_manager: GatewayConnectionManager = None):
        self.manager = connection_manager or gateway_manager

    async def handle_connection(
        self,
        websocket: WebSocket,
        get_db: callable,
    ):
        """
        Main handler for a gateway WebSocket connection

        Args:
            websocket: The WebSocket connection
            get_db: Callable to get database session
        """
        await websocket.accept()
        logger.info("New gateway connection accepted, awaiting authentication")

        connection = None

        try:
            # Wait for authentication message
            auth_message = await self._receive_with_timeout(websocket, timeout=30)

            if not auth_message or auth_message.get("type") != MessageType.AUTH_REQUEST:
                await self._send_error(websocket, "INVALID_AUTH", "Expected AUTH_REQUEST")
                await websocket.close(code=4001, reason="Authentication required")
                return

            # Parse auth request
            try:
                auth_request = AuthRequest(**auth_message)
            except Exception as e:
                await self._send_error(websocket, "INVALID_MESSAGE", f"Invalid auth request: {e}")
                await websocket.close(code=4002, reason="Invalid authentication")
                return

            # Set up auth handler with database access
            async def auth_handler(req: AuthRequest) -> Tuple[bool, str, str, str, str]:
                """Authenticate gateway token and return database info"""
                return await self._authenticate_gateway_token(req, get_db)

            self.manager.set_auth_handler(auth_handler)

            # Attempt connection
            connection = await self.manager.connect(websocket, auth_request)

            if not connection:
                await websocket.close(code=4003, reason="Authentication failed")
                return

            # Main message loop
            await self._message_loop(websocket, connection.session_id)

        except WebSocketDisconnect:
            logger.info("Gateway WebSocket disconnected")
        except Exception as e:
            logger.error(f"Gateway connection error: {e}")
        finally:
            if connection:
                await self.manager.disconnect(connection.session_id)

    async def _message_loop(self, websocket: WebSocket, session_id: str):
        """Main message processing loop"""
        while True:
            try:
                data = await websocket.receive_json()
                response = await self.manager.handle_message(session_id, data)

                if response:
                    await websocket.send_json(response.model_dump(mode="json"))

            except WebSocketDisconnect:
                raise
            except json.JSONDecodeError:
                await self._send_error(websocket, "INVALID_JSON", "Invalid JSON message")
            except Exception as e:
                logger.error(f"Message processing error: {e}")
                await self._send_error(websocket, "PROCESSING_ERROR", str(e))

    async def _authenticate_gateway_token(
        self,
        auth_request: AuthRequest,
        get_db: callable,
    ) -> Tuple[bool, str, str, str, str]:
        """
        Authenticate the gateway token

        Args:
            auth_request: Authentication request from agent
            get_db: Database session factory

        Returns:
            Tuple of (success, database_id, tenant_id, database_name, error_message)
        """
        from app.models.platform import ApiKey, TenantDatabase
        import hashlib

        db: Session = None
        try:
            db = next(get_db())

            # Gateway tokens start with "gw_" prefix
            token = auth_request.gateway_token

            # Check if it's a raw token (gw_...) - we need to hash it
            if token.startswith("gw_"):
                # This is the raw token, compute hash to find in DB
                key_hash = hashlib.sha256(token.encode()).hexdigest()
                api_key = db.query(ApiKey).filter(
                    ApiKey.key_hash == key_hash,
                    ApiKey.is_active == True,
                ).first()
            else:
                # Legacy: check if token matches key_prefix for identification
                api_key = db.query(ApiKey).filter(
                    ApiKey.key_prefix == token[:12] if len(token) >= 12 else token,
                    ApiKey.is_active == True,
                ).first()

                # If found, verify against hash
                if api_key and not ApiKey.verify_key(token, api_key.key_hash):
                    api_key = None

            if not api_key:
                return False, None, None, None, "Invalid or inactive gateway token"

            # Check if key has gateway scope
            scopes = api_key.get_scopes()
            if "gateway" not in scopes and "admin" not in scopes:
                return False, None, None, None, "Token does not have gateway scope"

            # Check expiration
            if api_key.expires_at and api_key.expires_at < datetime.utcnow():
                return False, None, None, None, "Gateway token expired"

            # Find associated database
            # The gateway_api_key_id field links the database to this token
            tenant_db = db.query(TenantDatabase).filter(
                TenantDatabase.gateway_api_key_id == api_key.id,
                TenantDatabase.is_active == True,
            ).first()

            if not tenant_db:
                # Fallback: check if token's tenant has any gateway-mode database
                tenant_db = db.query(TenantDatabase).filter(
                    TenantDatabase.tenant_id == api_key.tenant_id,
                    TenantDatabase.connection_mode.in_(["gateway_only", "auto"]),
                    TenantDatabase.is_active == True,
                ).first()

            if not tenant_db:
                return False, None, None, None, "No database associated with this gateway token"

            # Update last used
            api_key.record_usage()
            tenant_db.gateway_connected = True
            tenant_db.gateway_connected_at = datetime.utcnow()
            db.commit()

            return (
                True,
                str(tenant_db.id),
                str(tenant_db.tenant_id),
                tenant_db.name,
                None,
            )

        except Exception as e:
            logger.error(f"Gateway authentication error: {e}")
            return False, None, None, None, f"Authentication error: {str(e)}"
        finally:
            # Always close the session to prevent connection leak
            if db is not None:
                db.close()

    async def _receive_with_timeout(
        self,
        websocket: WebSocket,
        timeout: int = 30,
    ) -> Optional[dict]:
        """Receive message with timeout"""
        import asyncio

        try:
            data = await asyncio.wait_for(websocket.receive_json(), timeout=timeout)
            return data
        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for gateway message")
            return None
        except Exception as e:
            logger.error(f"Error receiving message: {e}")
            return None

    async def _send_error(
        self,
        websocket: WebSocket,
        code: str,
        message: str,
    ):
        """Send error message to client"""
        error = ErrorMessage(
            error_code=code,
            error_message=message,
        )
        try:
            await websocket.send_json(error.model_dump(mode="json"))
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")


# Global message handler instance
message_handler = GatewayMessageHandler()
