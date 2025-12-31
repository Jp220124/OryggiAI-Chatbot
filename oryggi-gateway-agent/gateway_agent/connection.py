"""
WebSocket Connection to OryggiAI SaaS

Handles the outbound WebSocket connection to the SaaS platform,
including authentication, reconnection, and message handling.
"""

import asyncio
import json
import ssl
import platform
import socket
import logging
from datetime import datetime
from typing import Optional, Callable, Awaitable

import websockets
from websockets.client import WebSocketClientProtocol

try:
    from .config import GatewayConfig
    from .database import LocalDatabaseManager
    from . import __version__
except ImportError:
    try:
        # Frozen exe (PyInstaller)
        from gateway_agent.config import GatewayConfig
        from gateway_agent.database import LocalDatabaseManager
        from gateway_agent import __version__
    except ImportError:
        # Standalone script
        from config import GatewayConfig
        from database import LocalDatabaseManager
        __version__ = "2.0.0"

logger = logging.getLogger(__name__)


class GatewayConnection:
    """
    Manages WebSocket connection to OryggiAI SaaS

    Responsibilities:
    - Connect and authenticate with gateway token
    - Handle reconnection on disconnect
    - Process incoming query requests
    - Send query responses
    - Maintain heartbeat
    """

    def __init__(
        self,
        config: GatewayConfig,
        database: LocalDatabaseManager,
    ):
        self.config = config
        self.database = database
        self._websocket: Optional[WebSocketClientProtocol] = None
        self._session_id: Optional[str] = None
        self._running = False
        self._connected = False
        self._reconnect_count = 0
        self._start_time: Optional[datetime] = None
        self._queries_executed = 0

    async def connect(self) -> bool:
        """
        Connect to the SaaS gateway

        Returns:
            True if connection and authentication successful
        """
        logger.info(f"Connecting to {self.config.saas_url}")

        try:
            # Configure SSL
            ssl_context = None
            if self.config.saas_url.startswith("wss://"):
                ssl_context = ssl.create_default_context()
                if not self.config.ssl_verify:
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE

            # Connect to WebSocket
            self._websocket = await websockets.connect(
                self.config.saas_url,
                ssl=ssl_context,
                ping_interval=None,  # We handle our own heartbeat
                close_timeout=10,
            )

            # Send authentication request
            auth_request = {
                "type": "AUTH_REQUEST",
                "gateway_token": self.config.gateway_token,
                "agent_version": __version__,
                "agent_hostname": socket.gethostname(),
                "agent_os": f"{platform.system()} {platform.release()}",
                "timestamp": datetime.utcnow().isoformat(),
            }

            await self._websocket.send(json.dumps(auth_request))
            logger.debug("Sent authentication request")

            # Wait for auth response
            response_data = await asyncio.wait_for(
                self._websocket.recv(),
                timeout=30,
            )
            response = json.loads(response_data)

            if response.get("type") == "AUTH_RESPONSE":
                if response.get("status") == "success":
                    self._session_id = response.get("session_id")
                    self._connected = True
                    self._reconnect_count = 0
                    self._start_time = datetime.utcnow()
                    logger.info(f"Authenticated successfully. Session: {self._session_id}")
                    logger.info(f"Connected to database: {response.get('database_name')}")
                    return True
                else:
                    error = response.get("error_message", "Unknown error")
                    logger.error(f"Authentication failed: {error}")
                    return False
            else:
                logger.error(f"Unexpected response type: {response.get('type')}")
                return False

        except asyncio.TimeoutError:
            logger.error("Connection timed out")
            return False
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    async def disconnect(self):
        """Disconnect from the gateway"""
        self._running = False
        self._connected = False

        if self._websocket:
            try:
                # Send disconnect message
                disconnect_msg = {
                    "type": "DISCONNECT",
                    "session_id": self._session_id,
                    "reason": "normal_shutdown",
                    "timestamp": datetime.utcnow().isoformat(),
                }
                await self._websocket.send(json.dumps(disconnect_msg))
                await self._websocket.close()
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
            finally:
                self._websocket = None

        logger.info("Disconnected from gateway")

    async def run(self):
        """
        Main run loop - connect and process messages

        Automatically reconnects on disconnect.
        """
        self._running = True

        while self._running:
            # Connect if not connected
            if not self._connected:
                if await self.connect():
                    # Start message handler and heartbeat
                    try:
                        await asyncio.gather(
                            self._message_loop(),
                            self._heartbeat_loop(),
                        )
                    except Exception as e:
                        logger.error(f"Connection error: {e}")
                        self._connected = False
                else:
                    self._reconnect_count += 1
                    if (
                        self.config.max_reconnect_attempts > 0
                        and self._reconnect_count >= self.config.max_reconnect_attempts
                    ):
                        logger.error("Max reconnect attempts reached. Stopping.")
                        break

            # Wait before reconnecting
            if self._running and not self._connected:
                delay = self.config.reconnect_delay
                logger.info(f"Reconnecting in {delay} seconds...")
                await asyncio.sleep(delay)

    async def _message_loop(self):
        """Process incoming messages from the server"""
        while self._running and self._connected and self._websocket:
            try:
                message_data = await self._websocket.recv()
                message = json.loads(message_data)
                await self._handle_message(message)
            except websockets.ConnectionClosed:
                logger.warning("Connection closed by server")
                self._connected = False
                break
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON message: {e}")
            except Exception as e:
                logger.error(f"Message handling error: {e}")

    async def _handle_message(self, message: dict):
        """Handle incoming message based on type"""
        msg_type = message.get("type")

        if msg_type == "QUERY_REQUEST":
            await self._handle_query_request(message)
        elif msg_type == "HEARTBEAT_ACK":
            logger.debug("Received heartbeat acknowledgment")
        elif msg_type == "ERROR":
            logger.error(f"Server error: {message.get('error_message')}")
        else:
            logger.warning(f"Unknown message type: {msg_type}")

    async def _handle_query_request(self, message: dict):
        """Execute query and send response"""
        request_id = message.get("request_id")
        sql_query = message.get("sql_query")
        timeout = message.get("timeout", 60)
        max_rows = message.get("max_rows", 1000)

        logger.info(f"Executing query: {request_id}")
        logger.debug(f"Query: {sql_query[:100]}...")

        # Execute query on local database
        result = self.database.execute_query(
            query=sql_query,
            timeout=timeout,
            max_rows=max_rows,
        )

        # Build response
        if result["success"]:
            response = {
                "type": "QUERY_RESPONSE",
                "request_id": request_id,
                "status": "success",
                "columns": result.get("columns", []),
                "rows": result.get("rows", []),
                "row_count": result.get("row_count", 0),
                "execution_time_ms": result.get("execution_time_ms"),
                "timestamp": datetime.utcnow().isoformat(),
            }
            self._queries_executed += 1
        else:
            response = {
                "type": "QUERY_RESPONSE",
                "request_id": request_id,
                "status": "error",
                "error_message": result.get("error"),
                "error_code": result.get("error_code"),
                "timestamp": datetime.utcnow().isoformat(),
            }

        # Send response
        await self._websocket.send(json.dumps(response))
        logger.info(f"Sent response for query: {request_id}")

    async def _heartbeat_loop(self):
        """Send periodic heartbeats to keep connection alive"""
        while self._running and self._connected and self._websocket:
            try:
                await asyncio.sleep(self.config.heartbeat_interval)

                if not self._connected:
                    break

                uptime = 0
                if self._start_time:
                    uptime = int((datetime.utcnow() - self._start_time).total_seconds())

                heartbeat = {
                    "type": "HEARTBEAT",
                    "session_id": self._session_id,
                    "db_status": self.database.get_status(),
                    "queries_executed": self._queries_executed,
                    "uptime_seconds": uptime,
                    "timestamp": datetime.utcnow().isoformat(),
                }

                await self._websocket.send(json.dumps(heartbeat))
                logger.debug("Sent heartbeat")

            except Exception as e:
                logger.warning(f"Heartbeat error: {e}")
                self._connected = False
                break

    @property
    def is_connected(self) -> bool:
        """Check if connected to gateway"""
        return self._connected

    @property
    def session_id(self) -> Optional[str]:
        """Get current session ID"""
        return self._session_id

    @property
    def queries_executed(self) -> int:
        """Get total queries executed"""
        return self._queries_executed
