"""
Local REST API Client

Handles HTTP requests to the local Oryggi REST API.
Used by the gateway agent to execute API actions requested by the cloud.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

try:
    import httpx
except ImportError:
    httpx = None

try:
    from httpx_ntlm import HttpNtlmAuth
except ImportError:
    HttpNtlmAuth = None

try:
    import aiohttp
except ImportError:
    aiohttp = None

logger = logging.getLogger(__name__)

# Hardcoded Oryggi API key - same for all installations
ORYGGI_DEFAULT_API_KEY = "uw0RyC0v+aBV6nCWKM0M0Q=="


class LocalApiClient:
    """
    HTTP client for calling local Oryggi REST API.

    Executes REST API calls on behalf of the cloud chatbot.
    Supports all HTTP methods (GET, POST, PUT, DELETE, PATCH).

    Example:
        client = LocalApiClient("http://localhost:32119/OryggiWebApi")
        result = await client.execute("POST", "/api/Employee/Deactivate/12345")
    """

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        default_timeout: int = 30,
        verify_ssl: bool = True,
        use_ntlm: bool = True,
    ):
        """
        Initialize the API client.

        Args:
            base_url: Base URL of the local Oryggi API (e.g., http://localhost:32119/OryggiWebApi)
            api_key: Optional API key for authentication
            default_timeout: Default request timeout in seconds
            verify_ssl: Whether to verify SSL certificates (False for self-signed)
            use_ntlm: Whether to use Windows NTLM authentication (default True for localhost)
        """
        self.base_url = base_url.rstrip("/")
        # Use hardcoded API key if none provided
        self.api_key = api_key if api_key else ORYGGI_DEFAULT_API_KEY
        self.default_timeout = default_timeout
        self.verify_ssl = verify_ssl

        # NTLM is disabled when API key is available (which is always now with hardcoded key)
        is_localhost = "localhost" in base_url.lower() or "127.0.0.1" in base_url
        self.use_ntlm = use_ntlm and is_localhost and HttpNtlmAuth is not None and not self.api_key

        # Validate that we have an HTTP library
        if httpx is None and aiohttp is None:
            raise ImportError(
                "Either 'httpx' or 'aiohttp' is required. "
                "Install with: pip install httpx"
            )

        self._use_httpx = httpx is not None
        auth_method = "NTLM" if self.use_ntlm else ("API Key" if self.api_key else "None")
        logger.info(f"LocalApiClient initialized: {self.base_url} (using {'httpx' if self._use_httpx else 'aiohttp'}, auth: {auth_method})")
        if self.api_key:
            logger.info(f"[API_CLIENT] API Key configured: {self.api_key[:8]}...{self.api_key[-4:]}")

    async def execute(
        self,
        method: str,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[Dict[str, Any]] = None,
        query_params: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Execute a REST API call to the local Oryggi service.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, PATCH)
            endpoint: API endpoint path (e.g., /api/Employee/Deactivate/12345)
            headers: Optional HTTP headers
            body: Optional request body (JSON)
            query_params: Optional URL query parameters
            timeout: Request timeout in seconds (default: 30)

        Returns:
            Dict with:
                - success: bool
                - status_code: int
                - headers: dict
                - body: dict or None
                - error_message: str or None
                - execution_time_ms: int
        """
        # Build full URL
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        # Prepare headers
        request_headers = headers.copy() if headers else {}

        # Add API key if configured (Oryggi uses "APIKey" header - case sensitive!)
        if self.api_key:
            request_headers["APIKey"] = self.api_key

        # Add content-type for requests with body
        if body and "Content-Type" not in request_headers:
            request_headers["Content-Type"] = "application/json"

        # Use specified timeout or default
        request_timeout = timeout or self.default_timeout

        start_time = datetime.utcnow()

        logger.info(f"[API_CLIENT] ======== HTTP REQUEST ========")
        logger.info(f"[API_CLIENT] Method: {method}")
        logger.info(f"[API_CLIENT] URL: {url}")
        logger.info(f"[API_CLIENT] Query Params: {query_params}")
        logger.info(f"[API_CLIENT] Headers: {request_headers}")
        logger.info(f"[API_CLIENT] Body: {body}")
        logger.info(f"[API_CLIENT] Timeout: {request_timeout}s")
        logger.info(f"[API_CLIENT] SSL Verify: {self.verify_ssl}")

        try:
            if self._use_httpx:
                result = await self._execute_httpx(
                    method=method,
                    url=url,
                    headers=request_headers,
                    body=body,
                    query_params=query_params,
                    timeout=request_timeout,
                )
            else:
                result = await self._execute_aiohttp(
                    method=method,
                    url=url,
                    headers=request_headers,
                    body=body,
                    query_params=query_params,
                    timeout=request_timeout,
                )

            execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            result["execution_time_ms"] = execution_time

            logger.info(f"[API_CLIENT] ======== HTTP RESPONSE ========")
            logger.info(f"[API_CLIENT] Status Code: {result.get('status_code')}")
            logger.info(f"[API_CLIENT] Success: {result.get('success')}")
            logger.info(f"[API_CLIENT] Body: {result.get('body')}")
            logger.info(f"[API_CLIENT] Execution Time: {execution_time}ms")
            if result.get('error_message'):
                logger.error(f"[API_CLIENT] Error: {result.get('error_message')}")

            return result

        except asyncio.TimeoutError:
            execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            logger.error(f"API request timeout: {method} {url}")
            return {
                "success": False,
                "status_code": 0,
                "headers": {},
                "body": None,
                "error_message": f"Request timed out after {request_timeout}s",
                "error_code": "TIMEOUT",
                "execution_time_ms": execution_time,
            }
        except Exception as e:
            execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            logger.error(f"API request error: {method} {url} - {e}")
            return {
                "success": False,
                "status_code": 0,
                "headers": {},
                "body": None,
                "error_message": str(e),
                "error_code": "CONNECTION_ERROR",
                "execution_time_ms": execution_time,
            }

    async def _execute_httpx(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: Optional[Dict[str, Any]],
        query_params: Optional[Dict[str, str]],
        timeout: int,
    ) -> Dict[str, Any]:
        """Execute request using httpx"""
        # Check content type to determine how to send body
        content_type = headers.get("Content-Type", "").lower()
        is_form_urlencoded = "x-www-form-urlencoded" in content_type

        # Setup NTLM auth if enabled (uses current Windows user credentials)
        auth = None
        if self.use_ntlm and HttpNtlmAuth is not None:
            # Empty strings = use current Windows credentials via SSPI
            auth = HttpNtlmAuth('', '')
            logger.info(f"[API_CLIENT] Using NTLM authentication")

        async with httpx.AsyncClient(
            timeout=timeout,
            verify=self.verify_ssl,
            auth=auth,
        ) as client:
            if is_form_urlencoded and body:
                # Form-urlencoded: use data= instead of json=
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    data=body,  # httpx encodes dict as form data
                    params=query_params,
                )
            else:
                # JSON (default)
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=body,
                    params=query_params,
                )

            # Parse response body
            response_body = None
            if response.content:
                try:
                    response_body = response.json()
                except Exception:
                    # Not JSON, return as text
                    response_body = {"text": response.text}

            return {
                "success": 200 <= response.status_code < 300,
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response_body,
                "error_message": None if response.status_code < 400 else response.text[:500],
                "error_code": None,
            }

    async def _execute_aiohttp(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: Optional[Dict[str, Any]],
        query_params: Optional[Dict[str, str]],
        timeout: int,
    ) -> Dict[str, Any]:
        """Execute request using aiohttp"""
        # Check content type to determine how to send body
        content_type = headers.get("Content-Type", "").lower()
        is_form_urlencoded = "x-www-form-urlencoded" in content_type

        timeout_obj = aiohttp.ClientTimeout(total=timeout)
        ssl_context = None if self.verify_ssl else False

        async with aiohttp.ClientSession(timeout=timeout_obj) as session:
            # Choose data or json based on content type
            if is_form_urlencoded and body:
                # Form-urlencoded: use data= instead of json=
                async with session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    data=body,  # aiohttp encodes dict as form data
                    params=query_params,
                    ssl=ssl_context,
                ) as response:
                    # Parse response body
                    response_body = None
                    try:
                        response_body = await response.json()
                    except Exception:
                        text = await response.text()
                        response_body = {"text": text} if text else None

                    return {
                        "success": 200 <= response.status < 300,
                        "status_code": response.status,
                        "headers": dict(response.headers),
                        "body": response_body,
                        "error_message": None if response.status < 400 else str(response_body)[:500],
                        "error_code": None,
                    }
            else:
                # JSON (default)
                async with session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=body,
                    params=query_params,
                    ssl=ssl_context,
                ) as response:
                    # Parse response body
                    response_body = None
                    try:
                        response_body = await response.json()
                    except Exception:
                        text = await response.text()
                        response_body = {"text": text} if text else None

                    return {
                        "success": 200 <= response.status < 300,
                        "status_code": response.status,
                        "headers": dict(response.headers),
                        "body": response_body,
                        "error_message": None if response.status < 400 else str(response_body)[:500],
                        "error_code": None,
                    }

    async def test_connection(self) -> Dict[str, Any]:
        """
        Test connection to the local API.

        Returns:
            Dict with success status and API info
        """
        try:
            # Try to access swagger or a health endpoint
            result = await self.execute(
                method="GET",
                endpoint="/swagger/index.html",
                timeout=5,
            )

            if result["status_code"] == 200:
                return {
                    "success": True,
                    "base_url": self.base_url,
                    "message": "API is accessible",
                }

            # Try root endpoint
            result = await self.execute(
                method="GET",
                endpoint="/",
                timeout=5,
            )

            return {
                "success": result["status_code"] in [200, 302, 401, 403],
                "base_url": self.base_url,
                "status_code": result["status_code"],
                "message": "API responded" if result["status_code"] else "API not accessible",
            }

        except Exception as e:
            return {
                "success": False,
                "base_url": self.base_url,
                "error": str(e),
            }

    def get_status(self) -> str:
        """Get client status string"""
        return f"configured ({self.base_url})"
