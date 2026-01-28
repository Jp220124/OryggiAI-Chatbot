"""
Local REST API Discovery

Auto-discovers the local Oryggi REST API by probing common ports and paths.
Used during agent initialization to find the API without manual configuration.
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any

try:
    import httpx
except ImportError:
    httpx = None

try:
    import aiohttp
except ImportError:
    aiohttp = None

logger = logging.getLogger(__name__)


class ApiDiscovery:
    """
    Auto-discover local Oryggi REST API.

    Probes common ports and URL paths to find where the Oryggi API is running.
    Validates by checking for Swagger endpoints or known API patterns.

    Example:
        discovery = ApiDiscovery()
        base_url = await discovery.discover()
        if base_url:
            print(f"Found API at: {base_url}")
    """

    # Common ports where Oryggi API might be running
    # 443 first (HTTPS) since most Oryggi installations use HTTPS
    KNOWN_PORTS = [443, 80, 32119, 5000, 8080, 8000, 5001]

    # Common path prefixes for Oryggi API
    KNOWN_PATHS = [
        "/OryggiWebServceCoreApi/OryggiWebApi",  # Nested API path (most common)
        "/OryggiXpertAPI",  # Primary Oryggi API path
        "/OryggiWebServceCoreApi",
        "/OryggiWebApi",
        "/OryggiApi",
        "/api",
        "",  # Root path
    ]

    # Endpoints that indicate a valid Oryggi API
    # These MUST return non-404 for the path to be considered valid
    VALIDATION_ENDPOINTS = [
        "/deActivateEmployee",  # Known Oryggi endpoint - MUST exist
        "/GetEmployees",  # Common Oryggi endpoint
        "/swagger/v1/swagger.json",
        "/swagger/index.html",
    ]

    def __init__(
        self,
        hosts: Optional[List[str]] = None,
        timeout: int = 5,
    ):
        """
        Initialize API discovery.

        Args:
            hosts: List of hosts to probe (default: ['localhost', '127.0.0.1'])
            timeout: Connection timeout in seconds
        """
        self.hosts = hosts or ["localhost", "127.0.0.1"]
        self.timeout = timeout

        # Validate HTTP library availability
        if httpx is None and aiohttp is None:
            raise ImportError(
                "Either 'httpx' or 'aiohttp' is required for API discovery. "
                "Install with: pip install httpx"
            )

        self._use_httpx = httpx is not None

    async def discover(self) -> Optional[str]:
        """
        Discover the local Oryggi REST API.

        Probes all combinations of hosts, ports, and paths to find the API.

        Returns:
            Base URL of the discovered API, or None if not found
        """
        logger.info("Starting API discovery...")

        # Generate all possible URLs to probe
        urls_to_probe = []
        for host in self.hosts:
            for port in self.KNOWN_PORTS:
                for path in self.KNOWN_PATHS:
                    if port == 443:
                        base_url = f"https://{host}{path}"
                    elif port == 80:
                        base_url = f"http://{host}{path}"
                    else:
                        base_url = f"http://{host}:{port}{path}"
                    urls_to_probe.append(base_url)

        logger.debug(f"Probing {len(urls_to_probe)} possible URLs...")

        # Probe URLs concurrently (in batches to avoid overwhelming the system)
        batch_size = 10
        for i in range(0, len(urls_to_probe), batch_size):
            batch = urls_to_probe[i:i + batch_size]
            results = await asyncio.gather(
                *[self._validate_api(url) for url in batch],
                return_exceptions=True
            )

            for url, result in zip(batch, results):
                if result is True:
                    logger.info(f"Discovered API at: {url}")
                    return url

        logger.warning("API discovery failed - no API found")
        return None

    async def _validate_api(self, base_url: str) -> bool:
        """
        Validate if a URL is a valid Oryggi API.

        Args:
            base_url: Base URL to validate

        Returns:
            True if URL appears to be a valid Oryggi API
        """
        for endpoint in self.VALIDATION_ENDPOINTS:
            url = f"{base_url.rstrip('/')}{endpoint}"

            try:
                status_code = await self._probe_url(url)
                # 404 means endpoint doesn't exist - NOT a valid API path
                # Accept 200 (OK), 302/301 (redirect), 401/403 (auth required), 405 (method not allowed)
                if status_code in [200, 302, 301, 401, 403, 405]:
                    logger.debug(f"Valid response from: {url} ({status_code})")
                    return True
                elif status_code == 404:
                    logger.debug(f"Endpoint not found (404): {url} - trying next path")
                    break  # This base_url doesn't have the endpoint, try next KNOWN_PATH
            except Exception:
                continue

        return False

    async def _probe_url(self, url: str) -> int:
        """
        Probe a URL and return status code.

        Args:
            url: URL to probe

        Returns:
            HTTP status code, or 0 if connection failed
        """
        if self._use_httpx:
            return await self._probe_httpx(url)
        else:
            return await self._probe_aiohttp(url)

    async def _probe_httpx(self, url: str) -> int:
        """Probe URL using httpx"""
        async with httpx.AsyncClient(
            timeout=self.timeout,
            verify=False,  # Don't verify SSL for local discovery
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            return response.status_code

    async def _probe_aiohttp(self, url: str) -> int:
        """Probe URL using aiohttp"""
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, ssl=False, allow_redirects=True) as response:
                return response.status

    async def discover_with_details(self) -> Dict[str, Any]:
        """
        Discover API and return detailed information.

        Returns:
            Dict with discovery results including:
            - success: bool
            - base_url: str or None
            - swagger_url: str or None
            - endpoints_found: list
            - scan_time_ms: int
        """
        import time
        start_time = time.time()

        result = {
            "success": False,
            "base_url": None,
            "swagger_url": None,
            "endpoints_found": [],
            "ports_scanned": len(self.KNOWN_PORTS),
            "paths_scanned": len(self.KNOWN_PATHS),
        }

        base_url = await self.discover()

        if base_url:
            result["success"] = True
            result["base_url"] = base_url

            # Try to find swagger
            for swagger_path in ["/swagger/v1/swagger.json", "/swagger/index.html"]:
                swagger_url = f"{base_url.rstrip('/')}{swagger_path}"
                try:
                    status = await self._probe_url(swagger_url)
                    if status == 200:
                        result["swagger_url"] = swagger_url
                        break
                except Exception:
                    pass

            # Check for known endpoints
            endpoints = ["/api/Employee", "/api/Device", "/api/Attendance"]
            for endpoint in endpoints:
                try:
                    url = f"{base_url.rstrip('/')}{endpoint}"
                    status = await self._probe_url(url)
                    if status in [200, 401, 403]:
                        result["endpoints_found"].append(endpoint)
                except Exception:
                    pass

        result["scan_time_ms"] = int((time.time() - start_time) * 1000)
        return result


async def auto_discover_api() -> Optional[str]:
    """
    Convenience function to auto-discover API.

    Returns:
        Base URL of discovered API, or None
    """
    discovery = ApiDiscovery()
    return await discovery.discover()


def discover_api_sync() -> Optional[str]:
    """
    Synchronous wrapper for API discovery.

    For use in non-async contexts.

    Returns:
        Base URL of discovered API, or None
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If event loop is running, create a new task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, auto_discover_api())
                return future.result(timeout=60)
        else:
            return loop.run_until_complete(auto_discover_api())
    except Exception as e:
        logger.error(f"Sync discovery failed: {e}")
        return None


# Alias for backward compatibility (sync version for use in service.py)
discover_oryggi_api = discover_api_sync
