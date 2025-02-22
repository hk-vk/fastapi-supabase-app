from aiohttp import ClientSession, TCPConnector, ClientTimeout
from typing import Optional
import logging

logger = logging.getLogger(__name__)

_session: Optional[ClientSession] = None

async def get_http_session() -> ClientSession:
    """Get or create a shared aiohttp session with connection pooling"""
    global _session
    if _session is None or _session.closed:
        connector = TCPConnector(
            limit=100,  # Maximum number of concurrent connections
            limit_per_host=20,  # Maximum number of concurrent connections per host
            keepalive_timeout=120,  # Keep connections alive for 120 seconds
            force_close=False,  # Don't force close connections
            enable_cleanup_closed=True,  # Clean up closed connections
            ssl=False  # Disable SSL verification for development
        )
        timeout = ClientTimeout(
            total=30,  # Total timeout
            connect=10,  # Connection timeout
            sock_connect=10,  # Socket connect timeout
            sock_read=10  # Socket read timeout
        )
        _session = ClientSession(
            connector=connector,
            timeout=timeout,
            raise_for_status=True,
            headers={
                'Connection': 'keep-alive',
                'Keep-Alive': 'timeout=120'
            }
        )
        logger.info("Created new persistent HTTP session with connection pooling")
    return _session

async def cleanup_http_session():
    """Cleanup the shared HTTP session"""
    global _session
    if (_session and not _session.closed):
        await _session.close()
        _session = None
        logger.info("Closed persistent HTTP session")