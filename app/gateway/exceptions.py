"""
Gateway Exception Classes

Custom exceptions for the On-Premises Data Gateway system.
"""


class GatewayException(Exception):
    """Base exception for gateway operations"""

    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class GatewayAuthenticationError(GatewayException):
    """Raised when gateway agent authentication fails"""

    def __init__(self, message: str = "Gateway authentication failed", details: dict = None):
        super().__init__(message, details)


class GatewayConnectionError(GatewayException):
    """Raised when gateway connection issues occur"""

    def __init__(self, message: str = "Gateway connection error", details: dict = None):
        super().__init__(message, details)


class GatewayTimeoutError(GatewayException):
    """Raised when gateway operation times out"""

    def __init__(self, message: str = "Gateway operation timed out", details: dict = None):
        super().__init__(message, details)


class GatewayQueryError(GatewayException):
    """Raised when query execution through gateway fails"""

    def __init__(self, message: str = "Gateway query execution failed", details: dict = None):
        super().__init__(message, details)


class GatewayNotConnectedError(GatewayException):
    """Raised when database requires gateway but none is connected"""

    def __init__(self, database_name: str, details: dict = None):
        message = f"Gateway required but not connected for database: {database_name}"
        super().__init__(message, details)


class GatewayProtocolError(GatewayException):
    """Raised when message protocol is violated"""

    def __init__(self, message: str = "Invalid gateway message format", details: dict = None):
        super().__init__(message, details)
