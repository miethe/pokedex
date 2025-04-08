# backend/app/main.py

from fastapi import FastAPI, HTTPException, Path, Query, Request, status
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
from typing import List, Optional, Union
import time

# Import necessary components from other modules
from .cache import create_redis_pool, close_redis_pool, redis_pool, clear_cache
from .pokeapi_client import close_client, get_client
from .pokedex_data import (
    get_pokedex_summary_data,
    get_pokemon_detail_data,
    get_all_generations_data,
    get_all_types_data,
    POKEDEX_SUMMARY_CACHE_KEY, # Import cache keys if needed for management endpoints
    GENERATIONS_CACHE_KEY,
    TYPES_CACHE_KEY,
    POKEMON_DETAIL_CACHE_PREFIX
)
from .models import PokemonSummary, PokemonDetail, Generation, PokemonTypeFilter
from .config import settings # If needed for configuration directly

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- Global State Flag ---
IS_REFRESHING: bool = False
MAINTENANCE_MESSAGE = "Pokedex data is currently being refreshed to bring you the latest info. Please try again in a few moments."

# Lifespan context manager (from Step 2)
@asynccontextmanager
async def lifespan(app: FastAPI):
    global IS_REFRESHING # Declare intent to modify global variable
    
    # Startup phase
    logger.info("Application startup...")
    try:
        create_redis_pool()
        logger.info("Redis connection pool created.")
        # You could add a ping check here if desired
        # async with get_redis_connection() as conn:
        #    await conn.ping()
        # logger.info("Redis ping successful.")
    except Exception as e:
        logger.error(f"Failed to initialize Redis during startup: {e}", exc_info=True)
        # Decide if the app should fail to start if Redis is unavailable
        # raise RuntimeError("Could not connect to Redis") from e

    _ = await get_client()
    logger.info("HTTPX client initialized.")

    # --- Pre-populate Cache on Startup (Optional but recommended for summary) ---
    logger.info("Attempting to pre-populate Pokedex summary cache on startup...")
    # Set flag only if we actually need to refresh
    summary_exists = False
    try:
        # Check cache *before* setting the flag
        # Check if summary is already cached, only fetch if not present
        summary_cached_data = await get_pokedex_summary_data(force_refresh=False)
        summary_exists = summary_cached_data is not None
    except Exception as e:
         logger.error(f"Error checking initial cache state: {e}", exc_info=True)
         summary_exists = False # Assume not cached if check fails
    
    if not summary_exists:
        IS_REFRESHING = True # Set flag before long operation
        logger.warning("CACHE REFRESH STARTING (startup): Pokedex summary cache needs population.")
        # time.sleep(15) # Optional: Simulate long refresh for testing
        try:
            logger.info("Pokedex summary not found in cache. Fetching now...")
            await get_pokedex_summary_data(force_refresh=True)
            
            # Optionally pre-populate generations and types too ONLY if summary was missing
            gen_exists = await get_all_generations_data(force_refresh=False) is not None
            if not gen_exists: await get_all_generations_data(force_refresh=True)
            type_exists = await get_all_types_data(force_refresh=False) is not None
            if not type_exists: await get_all_types_data(force_refresh=True)
            
            logger.info("CACHE REFRESH COMPLETED (startup): Pre-population finished.")
        except Exception as e:
            logger.error(f"CACHE REFRESH FAILED (startup): Error during cache pre-population: {e}", exc_info=True)
            # Log the error but allow the application to continue starting
        finally:
            IS_REFRESHING = False # CRITICAL: Always reset flag
            logger.info("Refresh flag reset after startup attempt.")
    else:
        logger.info("Pokedex summary already cached. Skipping pre-population.")
    # --- End Cache Pre-population ---

    yield # Application runs here

    # Shutdown phase
    logger.info("Application shutdown...")
    await close_redis_pool()
    await close_client()
    logger.info("Resources cleaned up.")

# Create FastAPI app instance with lifespan manager
app = FastAPI(
    title="Pokedex API",
    description="API for fetching and caching Pokemon data from PokeAPI",
    version="1.0.0",
    lifespan=lifespan,
    # Define API prefix for all routes in this app
    # Useful if deploying behind a reverse proxy expecting a base path
    # root_path="/api" # Uncomment if needed, ensure Nginx proxy handles this
)

# --- Maintenance Middleware ---
@app.middleware("http")
async def check_refresh_status_middleware(request: Request, call_next):
    global IS_REFRESHING
    # Check if refresh is ongoing and requested path is an API endpoint (not docs/openapi)
    is_api_request = request.url.path.startswith("/api/")
    is_docs_request = request.url.path.startswith(("/docs", "/openapi.json"))

    if IS_REFRESHING and is_api_request:
        logger.warning(f"Request to {request.url.path} returning 503 due to ongoing cache refresh.")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "refreshing", "message": MAINTENANCE_MESSAGE}
        )
    # Proceed with the request if not refreshing or not an API call
    response = await call_next(request)
    return response

# --- API Endpoints ---

@app.get("/")
async def read_root():
    """ Basic root endpoint to check if the API is running. """
    redis_status = "connected" if redis_pool else "not connected"
    return {
        "message": "Welcome to the Pokedex API!",
        "documentation": "/docs",
        "redis_status": redis_status
    }

@app.get(
    "/api/pokedex/summary",
    response_model=List[PokemonSummary],
    summary="Get Summarized Data for All Pokémon",
    description="Returns a list of all Pokémon with basic details (ID, Name, Generation, Types) suitable for filtering and list display. Data is cached.",
    tags=["Pokedex"]
)
async def get_pokedex_summary(
    force_refresh: bool = Query(False, description="Force refresh data from PokeAPI, bypassing the cache.")
):
    """
    Retrieves the cached or freshly fetched summary data for all Pokémon.
    """
    logger.info(f"Received request for Pokedex summary. force_refresh={force_refresh}")
    summary_data = await get_pokedex_summary_data(force_refresh=force_refresh)
    if summary_data is None:
        logger.error("Failed to retrieve Pokedex summary data.")
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve Pokedex summary data. The external API might be down or data aggregation failed."
        )
    logger.info(f"Returning {len(summary_data)} Pokémon summaries.")
    return summary_data

@app.get(
    "/api/pokemon/{pokemon_id_or_name}",
    response_model=PokemonDetail,
    summary="Get Detailed Data for a Specific Pokémon",
    description="Returns detailed information for a single Pokémon identified by its National Pokédex ID or name. Data is cached.",
    tags=["Pokemon"]
)
async def get_pokemon_details(
    pokemon_id_or_name: Union[int, str] = Path(
        ...,
        description="The National Pokédex ID (integer) or name (string, lowercase) of the Pokémon.",
        examples=["pikachu", 25, "charizard", 6]
    ),
    force_refresh: bool = Query(False, description="Force refresh data from PokeAPI, bypassing the cache.")
):
    """
    Retrieves the cached or freshly fetched detailed data for a specific Pokémon.
    Handles both integer IDs and string names.
    """
    # Normalize input name to lowercase if it's a string
    identifier = str(pokemon_id_or_name).lower() if isinstance(pokemon_id_or_name, str) else pokemon_id_or_name
    logger.info(f"Received request for Pokémon details: '{identifier}'. force_refresh={force_refresh}")

    pokemon_data = await get_pokemon_detail_data(identifier, force_refresh=force_refresh)

    if pokemon_data is None:
        logger.warning(f"Pokémon details not found for identifier: '{identifier}'")
        raise HTTPException(
            status_code=404,
            detail=f"Pokémon with ID or name '{identifier}' not found."
        )
    logger.info(f"Returning details for Pokémon: {pokemon_data.name} (ID: {pokemon_data.id})")
    return pokemon_data

@app.get(
    "/api/generations",
    response_model=List[Generation],
    summary="Get All Pokémon Generations",
    description="Returns a list of all Pokémon generations with their IDs and names. Useful for populating filters. Data is cached.",
    tags=["Metadata"]
)
async def get_generations(
    force_refresh: bool = Query(False, description="Force refresh data from PokeAPI, bypassing the cache.")
):
    """
    Retrieves the list of Pokémon generations.
    """
    logger.info(f"Received request for generations list. force_refresh={force_refresh}")
    generations = await get_all_generations_data(force_refresh=force_refresh)
    if generations is None:
        logger.error("Failed to retrieve generations data.")
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve Pokémon generations data."
        )
    logger.info(f"Returning {len(generations)} generations.")
    return generations

@app.get(
    "/api/types",
    response_model=List[PokemonTypeFilter],
    summary="Get All Pokémon Types",
    description="Returns a list of all Pokémon types with their names. Useful for populating filters. Data is cached.",
    tags=["Metadata"]
)
async def get_types(
    force_refresh: bool = Query(False, description="Force refresh data from PokeAPI, bypassing the cache.")
):
    """
    Retrieves the list of Pokémon types.
    """
    logger.info(f"Received request for types list. force_refresh={force_refresh}")
    types = await get_all_types_data(force_refresh=force_refresh)
    if types is None:
        logger.error("Failed to retrieve types data.")
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve Pokémon types data."
        )
    logger.info(f"Returning {len(types)} types.")
    return types


# --- Management Endpoint (Optional) ---
# Simple endpoint to manually trigger cache refresh for specific keys
@app.post(
    "/api/admin/cache/refresh",
    status_code=202, # Accepted
    summary="Trigger Cache Refresh (Admin)",
    description="Manually triggers a refresh of specified cached data (e.g., summary, generations, types). Use with caution.",
    tags=["Admin"]
)
async def trigger_cache_refresh(
    cache_key: str = Query(..., description=f"The cache key to refresh. Options: '{POKEDEX_SUMMARY_CACHE_KEY}', '{GENERATIONS_CACHE_KEY}', '{TYPES_CACHE_KEY}', or '{POKEMON_DETAIL_CACHE_PREFIX}<id_or_name>'.")
):
    global IS_REFRESHING # Declare intent to modify
    if IS_REFRESHING: # Optional: Prevent starting a new refresh if one is already running
        logger.warning("Admin refresh request ignored: Another refresh is already in progress.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A cache refresh operation is already in progress. Please wait."
        )
    
    logger.warning(f"Received admin request to refresh cache for key: {cache_key}")
    refreshed = False
    IS_REFRESHING = True # Set flag before performing refresh
    logger.warning(f"CACHE REFRESH STARTING (admin): Key: {cache_key}")
    # time.sleep(10) # Optional: Simulate long refresh for testing
    try:
        # Use force_refresh=True within the data fetching functions
        if cache_key == POKEDEX_SUMMARY_CACHE_KEY:
            result = await get_pokedex_summary_data(force_refresh=True)
            refreshed = result is not None
        elif cache_key == GENERATIONS_CACHE_KEY:
            result = await get_all_generations_data(force_refresh=True)
            refreshed = result is not None
        elif cache_key == TYPES_CACHE_KEY:
            result = await get_all_types_data(force_refresh=True)
            refreshed = result is not None
        elif cache_key.startswith(POKEMON_DETAIL_CACHE_PREFIX):
             pokemon_id_or_name = cache_key.replace(POKEMON_DETAIL_CACHE_PREFIX, "", 1)
             result = await get_pokemon_detail_data(pokemon_id_or_name, force_refresh=True)
             refreshed = result is not None
        else:
            # Reset flag immediately if key is invalid before raising HTTPEx
            IS_REFRESHING = False
            raise HTTPException(status_code=400, detail=f"Invalid cache key specified: {cache_key}")

        if refreshed:
            logger.info(f"Successfully refreshed cache for key: {cache_key}")
            return {"message": f"Cache refresh triggered successfully for '{cache_key}'."}
        else:
            logger.error(f"Failed to refresh cache for key: {cache_key}")
            # Return 202 anyway, as the request was accepted, but indicate failure in message
            return {"message": f"Cache refresh trigger for '{cache_key}' completed, but underlying fetch failed."}

    except HTTPException as http_exc:
        # Reset flag before re-raising known HTTP exceptions
        IS_REFRESHING = False
        logger.warning(f"CACHE REFRESH ABORTED (admin HTTP Exception): Key: {cache_key}")
        raise http_exc # Re-raise HTTP exceptions from validation etc.
    except Exception as e:
        # Reset flag on unexpected errors
        IS_REFRESHING = False
        logger.error(f"Error during admin cache refresh for '{cache_key}': {e}", exc_info=True)
        # Return a 500 instead of 202 to indicate failure
        raise HTTPException(status_code=500, detail=f"An error occurred while refreshing cache for '{cache_key}'.")
    finally:
        # --- CRITICAL: Ensure flag is always reset ---
        if IS_REFRESHING: # Only reset if it wasn't reset in except blocks
             IS_REFRESHING = False
             logger.info(f"Refresh flag reset after admin attempt for key: {cache_key}")


# Example of how to run directly (though we'll use docker-compose)
# if __name__ == "__main__":
#    import uvicorn
#    # Note: reload=True might cause issues with lifespan startup/shutdown logic
#    # Use reload only for development convenience, disable for stability testing
#    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False, lifespan="on")