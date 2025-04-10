# backend/app/clients.py
import httpx
import logging
from typing import Optional
# Assuming the library defines this, otherwise define it here
from pokeapi_lib.client import DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)

# --- Library Client Instance ---
# Create a single client instance for the backend to use with the library
# Library functions require passing the client instance
_lib_httpx_client: Optional[httpx.AsyncClient] = None

async def get_library_client() -> httpx.AsyncClient:
    """Gets or creates the httpx client for the PokeAPI library."""
    global _lib_httpx_client
    if _lib_httpx_client is None or _lib_httpx_client.is_closed: # Also check if closed
        logger.info("Creating/Recreating httpx client for PokeAPI library.")
        # Consider making timeout configurable via settings if needed
        _lib_httpx_client = httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT, # Use timeout defined (e.g., in pokeapi_lib)
            follow_redirects=True,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20) # Example limits
            )
    return _lib_httpx_client

async def close_library_client():
    """Closes the httpx client used for the PokeAPI library."""
    global _lib_httpx_client
    if _lib_httpx_client and not _lib_httpx_client.is_closed:
        await _lib_httpx_client.aclose()
        _lib_httpx_client = None # Clear reference
        logger.info("PokeAPI library httpx client closed.")
    elif _lib_httpx_client:
        _lib_httpx_client = None # Clear reference if already closed somehow
        logger.warning("PokeAPI library httpx client was already closed.")
