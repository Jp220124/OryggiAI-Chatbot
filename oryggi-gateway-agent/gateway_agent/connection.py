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
    from .api_client import LocalApiClient
    from . import __version__
except ImportError:
    try:
        # Frozen exe (PyInstaller)
        from gateway_agent.config import GatewayConfig
        from gateway_agent.database import LocalDatabaseManager
        from gateway_agent.api_client import LocalApiClient
        from gateway_agent import __version__
    except ImportError:
        # Standalone script
        from config import GatewayConfig
        from database import LocalDatabaseManager
        from api_client import LocalApiClient
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
        api_client: Optional[LocalApiClient] = None,
    ):
        self.config = config
        self.database = database
        self._api_client = api_client
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
        elif msg_type == "API_REQUEST":
            await self._handle_api_request(message)
        elif msg_type == "EMPLOYEE_LOOKUP_REQUEST":
            await self._handle_employee_lookup_request(message)
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

    async def _handle_api_request(self, message: dict):
        """
        Execute REST API request to local Oryggi API and send response

        Handles API_REQUEST messages from the cloud, forwards them to
        the local Oryggi REST API via api_client, and returns API_RESPONSE.
        """
        request_id = message.get("request_id")
        method = message.get("method", "GET")
        endpoint = message.get("endpoint", "")
        headers = message.get("headers", {})
        body = message.get("body")
        query_params = message.get("query_params")
        timeout = message.get("timeout", 30)

        logger.info(f"[API] ======== API REQUEST START ========")
        logger.info(f"[API] Request ID: {request_id}")
        logger.info(f"[API] Method: {method}")
        logger.info(f"[API] Endpoint: {endpoint}")
        logger.info(f"[API] Query Params: {query_params}")
        logger.info(f"[API] Headers: {headers}")
        logger.info(f"[API] Body: {body}")
        logger.info(f"[API] Timeout: {timeout}s")

        # Check if API client is available
        if not self._api_client:
            error_response = {
                "type": "API_RESPONSE",
                "request_id": request_id,
                "status": "not_configured",  # Required field
                "status_code": 503,
                "body": {"error": "API client not initialized. Local Oryggi API not configured."},
                "error_message": "API client not available",
                "error_code": "NOT_CONFIGURED",
                "execution_time_ms": 0,
                "headers": {},
                "timestamp": datetime.utcnow().isoformat(),
            }
            await self._websocket.send(json.dumps(error_response))
            logger.error(f"[API] API client not available for request {request_id}")
            return

        try:
            # Execute API request via local api_client
            result = await self._api_client.execute(
                method=method,
                endpoint=endpoint,
                headers=headers,
                body=body,
                query_params=query_params,
                timeout=timeout,
            )

            # Determine status based on result
            status_code = result.get("status_code", 200)
            if result.get("success", True) and 200 <= status_code < 300:
                api_status = "success"
            elif result.get("error_code") == "TIMEOUT":
                api_status = "timeout"
            elif result.get("error_code") == "CONNECTION_ERROR":
                api_status = "connection_error"
            else:
                api_status = "error"

            # Build response with required status field
            response = {
                "type": "API_RESPONSE",
                "request_id": request_id,
                "status": api_status,  # Required field
                "status_code": status_code,
                "body": result.get("body"),
                "headers": result.get("headers", {}),
                "execution_time_ms": result.get("execution_time_ms", 0),
                "error_message": result.get("error_message"),
                "error_code": result.get("error_code"),
                "timestamp": datetime.utcnow().isoformat(),
            }

            logger.info(
                f"[API] Request {request_id} completed: "
                f"status={api_status}, http_code={status_code}, time={result.get('execution_time_ms', 0)}ms"
            )

        except Exception as e:
            # Build error response with required status field
            response = {
                "type": "API_RESPONSE",
                "request_id": request_id,
                "status": "error",  # Required field
                "status_code": 500,
                "body": {"error": str(e)},
                "headers": {},
                "execution_time_ms": 0,
                "error_message": str(e),
                "error_code": "EXCEPTION",
                "timestamp": datetime.utcnow().isoformat(),
            }
            logger.error(f"[API] Request {request_id} failed: {e}")

        # Send response back to cloud
        await self._websocket.send(json.dumps(response))
        logger.debug(f"[API] Sent response for request: {request_id}")

    async def _handle_employee_lookup_request(self, message: dict):
        """
        Look up employee details from local Oryggi database

        Handles EMPLOYEE_LOOKUP_REQUEST messages from the cloud,
        executes the lookup query on the local database, and returns EMPLOYEE_LOOKUP_RESPONSE.
        """
        request_id = message.get("request_id")
        identifier = message.get("identifier", "")
        lookup_type = message.get("lookup_type", "auto")
        timeout = message.get("timeout", 10)

        logger.info(f"[EMPLOYEE_LOOKUP] ======== LOOKUP REQUEST ========")
        logger.info(f"[EMPLOYEE_LOOKUP] Request ID: {request_id}")
        logger.info(f"[EMPLOYEE_LOOKUP] Identifier: {identifier}")
        logger.info(f"[EMPLOYEE_LOOKUP] Lookup Type: {lookup_type}")

        start_time = datetime.utcnow()

        try:
            employee = None
            employees = []

            # Strategy 1: Try exact match on CorpEmpCode
            if lookup_type in ("auto", "code"):
                query = """
                    SELECT
                        e.Ecode,
                        e.CorpEmpCode,
                        e.EmpName,
                        des.DesName as Designation,
                        ecr.CardNo,
                        e.E_mail,
                        e.Telephone1,
                        e.Active
                    FROM EmployeeMaster e
                    LEFT JOIN DesignationMaster des ON e.DesCode = des.DesCode
                    LEFT JOIN Employee_Card_Relation ecr ON e.Ecode = ecr.ECode AND ecr.Status = 1
                    WHERE e.CorpEmpCode = ?
                """
                result = self.database.execute_query(query, timeout=timeout, params=(identifier,))
                if result["success"] and result.get("rows"):
                    employee = self._row_to_employee_data(result["rows"][0])
                    logger.info(f"[EMPLOYEE_LOOKUP] Found by CorpEmpCode: {employee['name']}")

            # Strategy 2: Try exact match on card number
            if not employee and lookup_type in ("auto", "card"):
                query = """
                    SELECT
                        e.Ecode,
                        e.CorpEmpCode,
                        e.EmpName,
                        des.DesName as Designation,
                        ecr.CardNo,
                        e.E_mail,
                        e.Telephone1,
                        e.Active
                    FROM EmployeeMaster e
                    LEFT JOIN DesignationMaster des ON e.DesCode = des.DesCode
                    LEFT JOIN Employee_Card_Relation ecr ON e.Ecode = ecr.ECode AND ecr.Status = 1
                    WHERE ecr.CardNo = ?
                """
                result = self.database.execute_query(query, timeout=timeout, params=(identifier,))
                if result["success"] and result.get("rows"):
                    employee = self._row_to_employee_data(result["rows"][0])
                    logger.info(f"[EMPLOYEE_LOOKUP] Found by CardNo: {employee['name']}")

            # Strategy 3: Try name search
            if not employee and lookup_type in ("auto", "name"):
                # First try exact name match
                query = """
                    SELECT
                        e.Ecode,
                        e.CorpEmpCode,
                        e.EmpName,
                        des.DesName as Designation,
                        ecr.CardNo,
                        e.E_mail,
                        e.Telephone1,
                        e.Active
                    FROM EmployeeMaster e
                    LEFT JOIN DesignationMaster des ON e.DesCode = des.DesCode
                    LEFT JOIN Employee_Card_Relation ecr ON e.Ecode = ecr.ECode AND ecr.Status = 1
                    WHERE LOWER(e.EmpName) = LOWER(?)
                """
                result = self.database.execute_query(query, timeout=timeout, params=(identifier,))
                if result["success"] and result.get("rows"):
                    if len(result["rows"]) == 1:
                        employee = self._row_to_employee_data(result["rows"][0])
                        logger.info(f"[EMPLOYEE_LOOKUP] Found by exact name: {employee['name']}")
                    else:
                        employees = [self._row_to_employee_data(row) for row in result["rows"]]
                        logger.info(f"[EMPLOYEE_LOOKUP] Multiple found by exact name: {len(employees)}")

                # If no exact match, try partial match
                if not employee and not employees:
                    query_partial = """
                        SELECT TOP 5
                            e.Ecode,
                            e.CorpEmpCode,
                            e.EmpName,
                            des.DesName as Designation,
                            ecr.CardNo,
                            e.E_mail,
                            e.Telephone1,
                            e.Active
                        FROM EmployeeMaster e
                        LEFT JOIN DesignationMaster des ON e.DesCode = des.DesCode
                        LEFT JOIN Employee_Card_Relation ecr ON e.Ecode = ecr.ECode AND ecr.Status = 1
                        WHERE LOWER(e.EmpName) LIKE LOWER(?)
                    """
                    result = self.database.execute_query(query_partial, timeout=timeout, params=(f"%{identifier}%",))
                    if result["success"] and result.get("rows"):
                        if len(result["rows"]) == 1:
                            employee = self._row_to_employee_data(result["rows"][0])
                            logger.info(f"[EMPLOYEE_LOOKUP] Found by partial name: {employee['name']}")
                        else:
                            employees = [self._row_to_employee_data(row) for row in result["rows"]]
                            logger.info(f"[EMPLOYEE_LOOKUP] Multiple found by partial name: {len(employees)}")

            # Calculate execution time
            execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # Build response based on results
            if employee:
                response = {
                    "type": "EMPLOYEE_LOOKUP_RESPONSE",
                    "request_id": request_id,
                    "status": "success",
                    "employee": employee,
                    "employees": None,
                    "execution_time_ms": execution_time,
                    "error_message": None,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            elif employees:
                response = {
                    "type": "EMPLOYEE_LOOKUP_RESPONSE",
                    "request_id": request_id,
                    "status": "multiple_found",
                    "employee": employees[0],  # Return first as primary
                    "employees": employees,
                    "execution_time_ms": execution_time,
                    "error_message": f"Multiple employees found ({len(employees)})",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            else:
                response = {
                    "type": "EMPLOYEE_LOOKUP_RESPONSE",
                    "request_id": request_id,
                    "status": "not_found",
                    "employee": None,
                    "employees": None,
                    "execution_time_ms": execution_time,
                    "error_message": f"No employee found for identifier: {identifier}",
                    "timestamp": datetime.utcnow().isoformat(),
                }

            logger.info(f"[EMPLOYEE_LOOKUP] Request {request_id} completed: status={response['status']}, time={execution_time}ms")

        except Exception as e:
            execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            response = {
                "type": "EMPLOYEE_LOOKUP_RESPONSE",
                "request_id": request_id,
                "status": "error",
                "employee": None,
                "employees": None,
                "execution_time_ms": execution_time,
                "error_message": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }
            logger.error(f"[EMPLOYEE_LOOKUP] Request {request_id} failed: {e}")

        # Send response back to cloud
        await self._websocket.send(json.dumps(response))
        logger.debug(f"[EMPLOYEE_LOOKUP] Sent response for request: {request_id}")

    def _row_to_employee_data(self, row: dict) -> dict:
        """Convert database row to employee data dict"""
        return {
            "ecode": row.get("Ecode") or row.get("ecode", 0),
            "corp_emp_code": str(row.get("CorpEmpCode") or row.get("corp_emp_code", "")),
            "name": row.get("EmpName") or row.get("empname") or row.get("name", "Unknown"),
            "department": row.get("Department") or row.get("department"),
            "designation": row.get("Designation") or row.get("designation"),
            "card_no": row.get("CardNo") or row.get("card_no"),
            "email": row.get("E_mail") or row.get("email"),
            "phone": row.get("Telephone1") or row.get("phone"),
            "active": bool(row.get("Active", True)),
        }

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

                # Determine API status
                api_status = "connected" if self._api_client else "not_configured"

                heartbeat = {
                    "type": "HEARTBEAT",
                    "session_id": self._session_id,
                    "db_status": self.database.get_status(),
                    "api_status": api_status,
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
