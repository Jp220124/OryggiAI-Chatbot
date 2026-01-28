"""
Gateway Message Schemas

Pydantic models for the WebSocket message protocol between
SaaS server and on-premises gateway agents.

Message Flow:
    1. AUTH_REQUEST: Agent authenticates with gateway token
    2. AUTH_RESPONSE: Server confirms authentication
    3. QUERY_REQUEST: Server sends SQL query to execute
    4. QUERY_RESPONSE: Agent returns query results
    5. HEARTBEAT/HEARTBEAT_ACK: Keep-alive mechanism
"""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from uuid import UUID


class MessageType(str, Enum):
    """Types of messages in the gateway protocol"""

    # Authentication
    AUTH_REQUEST = "AUTH_REQUEST"
    AUTH_RESPONSE = "AUTH_RESPONSE"

    # Query execution
    QUERY_REQUEST = "QUERY_REQUEST"
    QUERY_RESPONSE = "QUERY_RESPONSE"

    # Health monitoring
    HEARTBEAT = "HEARTBEAT"
    HEARTBEAT_ACK = "HEARTBEAT_ACK"

    # Connection management
    DISCONNECT = "DISCONNECT"
    ERROR = "ERROR"

    # Database status
    DB_STATUS_UPDATE = "DB_STATUS_UPDATE"

    # REST API execution (Cloud → Agent → Local Oryggi API)
    API_REQUEST = "API_REQUEST"
    API_RESPONSE = "API_RESPONSE"

    # Employee lookup (Cloud → Agent → Local DB)
    EMPLOYEE_LOOKUP_REQUEST = "EMPLOYEE_LOOKUP_REQUEST"
    EMPLOYEE_LOOKUP_RESPONSE = "EMPLOYEE_LOOKUP_RESPONSE"


class AuthStatus(str, Enum):
    """Authentication response status"""
    SUCCESS = "success"
    FAILED = "failed"
    TOKEN_EXPIRED = "token_expired"
    TOKEN_REVOKED = "token_revoked"


class QueryStatus(str, Enum):
    """Query execution status"""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"


class DatabaseStatus(str, Enum):
    """Status of local database connection"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class ApiRequestMethod(str, Enum):
    """HTTP methods for REST API requests"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class ApiStatus(str, Enum):
    """REST API execution status"""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    NOT_CONFIGURED = "not_configured"


class EmployeeLookupStatus(str, Enum):
    """Employee lookup execution status"""
    SUCCESS = "success"
    NOT_FOUND = "not_found"
    MULTIPLE_FOUND = "multiple_found"
    ERROR = "error"
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"


# ===================== Base Message =====================

class GatewayMessage(BaseModel):
    """Base class for all gateway messages"""
    type: MessageType
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True


# ===================== Authentication Messages =====================

class AuthRequest(GatewayMessage):
    """Agent authentication request"""
    type: MessageType = MessageType.AUTH_REQUEST
    gateway_token: str = Field(..., description="API key with gateway scope")
    agent_version: str = Field(..., description="Version of the gateway agent")
    agent_hostname: Optional[str] = Field(None, description="Hostname of agent machine")
    agent_os: Optional[str] = Field(None, description="Operating system")


class AuthResponse(GatewayMessage):
    """Server authentication response"""
    type: MessageType = MessageType.AUTH_RESPONSE
    status: AuthStatus
    session_id: Optional[str] = Field(None, description="Session ID for this connection")
    heartbeat_interval: int = Field(default=30, description="Seconds between heartbeats")
    query_timeout: int = Field(default=60, description="Default query timeout in seconds")
    database_id: Optional[str] = Field(None, description="Associated database ID")
    database_name: Optional[str] = Field(None, description="Associated database name")
    error_message: Optional[str] = None


# ===================== Query Messages =====================

class QueryRequest(GatewayMessage):
    """SQL query request from server to agent"""
    type: MessageType = MessageType.QUERY_REQUEST
    request_id: str = Field(..., description="Unique request identifier")
    sql_query: str = Field(..., description="SQL query to execute")
    timeout: int = Field(default=60, description="Query timeout in seconds")
    max_rows: int = Field(default=1000, description="Maximum rows to return")
    user_id: Optional[str] = Field(None, description="User who initiated the query")
    conversation_id: Optional[str] = Field(None, description="Associated conversation")


class QueryResponse(GatewayMessage):
    """Query result from agent to server"""
    type: MessageType = MessageType.QUERY_RESPONSE
    request_id: str = Field(..., description="Matching request ID")
    status: QueryStatus
    columns: Optional[List[str]] = Field(None, description="Column names")
    rows: Optional[List[Dict[str, Any]]] = Field(None, description="Result rows")
    row_count: int = Field(default=0, description="Number of rows returned")
    execution_time_ms: Optional[int] = Field(None, description="Query execution time")
    error_message: Optional[str] = None
    error_code: Optional[str] = None


# ===================== REST API Messages =====================

class ApiRequest(GatewayMessage):
    """
    REST API request from server to agent.

    Used to execute actions on the local Oryggi REST API through the gateway agent.
    The agent receives this request via WebSocket, calls the local API, and returns ApiResponse.

    Example:
        POST /api/Employee/Deactivate/12345
        → Deactivates employee with ECode 12345
    """
    type: MessageType = MessageType.API_REQUEST
    request_id: str = Field(..., description="Unique request identifier for response matching")
    method: ApiRequestMethod = Field(..., description="HTTP method (GET, POST, PUT, DELETE, PATCH)")
    endpoint: str = Field(..., description="API endpoint path (e.g., /api/Employee/Deactivate/12345)")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers to include")
    body: Optional[Dict[str, Any]] = Field(None, description="Request body for POST/PUT/PATCH")
    query_params: Optional[Dict[str, str]] = Field(None, description="URL query parameters")
    timeout: int = Field(default=30, description="Request timeout in seconds")
    user_id: Optional[str] = Field(None, description="User who initiated the request")
    conversation_id: Optional[str] = Field(None, description="Associated conversation")


class ApiResponse(GatewayMessage):
    """
    REST API response from agent to server.

    Contains the result of calling the local Oryggi REST API.
    Sent by the agent after executing an ApiRequest.
    """
    type: MessageType = MessageType.API_RESPONSE
    request_id: str = Field(..., description="Matching request ID")
    status: ApiStatus = Field(..., description="Execution status")
    status_code: int = Field(..., description="HTTP status code from local API")
    headers: Dict[str, str] = Field(default_factory=dict, description="Response headers")
    body: Optional[Union[Dict[str, Any], str]] = Field(None, description="Response body (JSON or string)")
    execution_time_ms: int = Field(default=0, description="Request execution time in milliseconds")
    error_message: Optional[str] = Field(None, description="Error description if failed")
    error_code: Optional[str] = Field(None, description="Error code if failed")


# ===================== Employee Lookup Messages =====================

class EmployeeLookupRequest(GatewayMessage):
    """
    Employee lookup request from server to agent.

    Used to look up employee details from the local Oryggi database through the gateway agent.
    Supports lookup by CorpEmpCode, name, or card number.
    """
    type: MessageType = MessageType.EMPLOYEE_LOOKUP_REQUEST
    request_id: str = Field(..., description="Unique request identifier for response matching")
    identifier: str = Field(..., description="Employee identifier (code, name, or card number)")
    lookup_type: str = Field(default="auto", description="Lookup type: auto, code, name, card")
    timeout: int = Field(default=10, description="Lookup timeout in seconds")
    user_id: Optional[str] = Field(None, description="User who initiated the request")
    conversation_id: Optional[str] = Field(None, description="Associated conversation")


class EmployeeData(BaseModel):
    """Employee data returned by lookup"""
    ecode: int = Field(..., description="Internal employee code")
    corp_emp_code: str = Field(..., description="Corporate employee code")
    name: str = Field(..., description="Employee name")
    department: Optional[str] = Field(None, description="Department name")
    designation: Optional[str] = Field(None, description="Job designation")
    card_no: Optional[str] = Field(None, description="Access card number")
    email: Optional[str] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    active: bool = Field(default=True, description="Whether employee is active")


class EmployeeLookupResponse(GatewayMessage):
    """
    Employee lookup response from agent to server.

    Contains the employee details found in the local database.
    """
    type: MessageType = MessageType.EMPLOYEE_LOOKUP_RESPONSE
    request_id: str = Field(..., description="Matching request ID")
    status: EmployeeLookupStatus = Field(..., description="Lookup status")
    employee: Optional[EmployeeData] = Field(None, description="Employee data if found")
    employees: Optional[List[EmployeeData]] = Field(None, description="Multiple employees if multiple found")
    execution_time_ms: int = Field(default=0, description="Lookup execution time in milliseconds")
    error_message: Optional[str] = Field(None, description="Error description if failed")


# ===================== Heartbeat Messages =====================

class Heartbeat(GatewayMessage):
    """Agent heartbeat to maintain connection"""
    type: MessageType = MessageType.HEARTBEAT
    session_id: str
    db_status: DatabaseStatus = DatabaseStatus.CONNECTED
    api_status: str = Field(default="not_configured", description="REST API status: connected, error, not_configured")
    queries_executed: int = Field(default=0, description="Queries since last heartbeat")
    api_requests_executed: int = Field(default=0, description="API requests since last heartbeat")
    uptime_seconds: int = Field(default=0, description="Agent uptime")
    memory_mb: Optional[float] = Field(None, description="Memory usage")
    cpu_percent: Optional[float] = Field(None, description="CPU usage")


class HeartbeatAck(GatewayMessage):
    """Server acknowledgment of heartbeat"""
    type: MessageType = MessageType.HEARTBEAT_ACK
    session_id: str
    server_time: datetime = Field(default_factory=datetime.utcnow)


# ===================== Status Messages =====================

class DatabaseStatusUpdate(GatewayMessage):
    """Agent reports database status change"""
    type: MessageType = MessageType.DB_STATUS_UPDATE
    session_id: str
    status: DatabaseStatus
    error_message: Optional[str] = None
    db_version: Optional[str] = None


class ErrorMessage(GatewayMessage):
    """Error notification"""
    type: MessageType = MessageType.ERROR
    error_code: str
    error_message: str
    request_id: Optional[str] = None  # If error is related to a specific request


class DisconnectMessage(GatewayMessage):
    """Clean disconnect notification"""
    type: MessageType = MessageType.DISCONNECT
    session_id: str
    reason: str = "normal_shutdown"


# ===================== Message Parsing =====================

def parse_gateway_message(data: dict) -> GatewayMessage:
    """
    Parse incoming message data into appropriate message type

    Args:
        data: Dictionary containing message data

    Returns:
        Appropriate GatewayMessage subclass instance

    Raises:
        ValueError: If message type is unknown or invalid
    """
    msg_type = data.get("type")

    if not msg_type:
        raise ValueError("Message missing 'type' field")

    message_classes = {
        MessageType.AUTH_REQUEST: AuthRequest,
        MessageType.AUTH_RESPONSE: AuthResponse,
        MessageType.QUERY_REQUEST: QueryRequest,
        MessageType.QUERY_RESPONSE: QueryResponse,
        MessageType.API_REQUEST: ApiRequest,
        MessageType.API_RESPONSE: ApiResponse,
        MessageType.EMPLOYEE_LOOKUP_REQUEST: EmployeeLookupRequest,
        MessageType.EMPLOYEE_LOOKUP_RESPONSE: EmployeeLookupResponse,
        MessageType.HEARTBEAT: Heartbeat,
        MessageType.HEARTBEAT_ACK: HeartbeatAck,
        MessageType.DB_STATUS_UPDATE: DatabaseStatusUpdate,
        MessageType.ERROR: ErrorMessage,
        MessageType.DISCONNECT: DisconnectMessage,
    }

    # Handle string type values
    if isinstance(msg_type, str):
        try:
            msg_type = MessageType(msg_type)
        except ValueError:
            raise ValueError(f"Unknown message type: {msg_type}")

    message_class = message_classes.get(msg_type)
    if not message_class:
        raise ValueError(f"Unknown message type: {msg_type}")

    return message_class(**data)


# ===================== Gateway Session Info =====================

class GatewaySessionInfo(BaseModel):
    """Information about an active gateway session"""
    session_id: str
    database_id: str
    tenant_id: str
    connected_at: datetime
    last_heartbeat: datetime
    agent_version: str
    agent_hostname: Optional[str]
    db_status: DatabaseStatus = DatabaseStatus.CONNECTED
    api_status: str = "not_configured"  # REST API status: connected, error, not_configured
    queries_executed: int = 0
    api_requests_executed: int = 0
    is_active: bool = True
