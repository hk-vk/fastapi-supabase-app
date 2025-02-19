import aiohttp
from typing import Optional

http_session: Optional[aiohttp.ClientSession] = None

async def get_http_session() -> aiohttp.ClientSession:
    global http_session
    if http_session is None:
        http_session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(
                limit=100,  # Maximum number of concurrent connections
                ttl_dns_cache=300,  # DNS cache TTL in seconds
                use_dns_cache=True,
                keepalive_timeout=60  # Keep connections alive for 60 seconds
            )
        )
    return http_session

async def cleanup_http_session():
    global http_session
    if http_session:
        await http_session.close()
        http_session = None