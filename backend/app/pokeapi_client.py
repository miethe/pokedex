# backend/app/pokeapi_client.py

import httpx
import logging
from typing import Optional, Dict, Any

from .config import settings

logger = logging.getLogger(__name__)

# Base URL for PokeAPI
BASE_URL = settings.pokeapi_base_url

# Create a reusable async HTTP client instance
# Recommended practice for performance (connection pooling)
# Set reasonable timeouts
_client = httpx.AsyncClient(
    base_url=BASE_URL,
    timeout=httpx.Timeout(10.0, connect=5.0), # 10s total timeout, 5s connect timeout
    follow_redirects=True,
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=20) # Adjust limits as needed
)

async def get_client() -> httpx.AsyncClient:
    """Returns the shared httpx AsyncClient instance."""
    return _client

async def close_client():
    """Closes the shared httpx AsyncClient instance."""
    global _client
    if _client:
        try:
            await _client.aclose()
            logger.info("HTTPX client closed successfully.")
            _client = None # Ensure it's marked as closed
        except Exception as e:
            logger.error(f"Error closing HTTPX client: {e}", exc_info=True)

async def fetch_pokeapi(endpoint: str) -> Optional[Dict[str, Any]]:
    """
    Fetches data from a specific PokeAPI endpoint.

    Args:
        endpoint: The API endpoint path (e.g., "/pokemon/pikachu" or full URL if needed).

    Returns:
        A dictionary containing the JSON response, or None if an error occurs.
    """
    client = await get_client()
    url = endpoint # Assumes endpoint includes leading slash or is a full URL
    if not endpoint.startswith("http"):
        # Ensure relative endpoints start correctly or handle base URL logic
        if not endpoint.startswith('/'):
             endpoint = '/' + endpoint
        url = f"{BASE_URL}{endpoint}" # Use configured base URL if relative

    logger.debug(f"Fetching data from PokeAPI: {url}")
    try:
        response = await client.get(url)
        response.raise_for_status() # Raise an exception for 4xx or 5xx status codes
        logger.debug(f"Successfully fetched data from {url}, status: {response.status_code}")
        return response.json()
    except httpx.TimeoutException:
        logger.error(f"Request timed out for PokeAPI endpoint: {url}")
        return None
    except httpx.RequestError as e:
        logger.error(f"An error occurred while requesting {e.request.url!r}: {e}")
        return None
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred: {e.response.status_code} {e.response.reason_phrase} for url {e.request.url!r}")
        # You might want to handle specific statuses differently (e.g., 404 Not Found)
        if e.response.status_code == 404:
            logger.warning(f"Resource not found at {e.request.url!r}")
        return None
    except Exception as e:
        # Catch any other unexpected errors
        logger.error(f"An unexpected error occurred during PokeAPI fetch for {url}: {e}", exc_info=True)
        return None

# Example Usage (for testing within this module)
# async def main():
#     # Example: Fetch Bulbasaur data
#     bulbasaur_data = await fetch_pokeapi("/pokemon/bulbasaur")
#     if bulbasaur_data:
#         print(f"Fetched data for Bulbasaur: ID {bulbasaur_data.get('id')}, Name {bulbasaur_data.get('name')}")
#     else:
#         print("Failed to fetch Bulbasaur data.")
#
#     # Example: Fetch first 20 Pokemon list
#     pokemon_list = await fetch_pokeapi("/pokemon?limit=20&offset=0")
#     if pokemon_list:
#         print(f"Fetched {len(pokemon_list.get('results', []))} Pokemon names.")
#     else:
#         print("Failed to fetch Pokemon list.")
#
#     await close_client() # Remember to close the client when done
#
# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(main())