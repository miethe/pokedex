# backend/app/main.py

from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging

# Import necessary components from other modules
from .cache import create_redis_pool, close_redis_pool, redis_pool # Import redis_pool to check if initialized
from .pokeapi_client import close_client, get_client # Import get_client to initialize it on startup

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup phase
    logger.info("Application startup...")
    # Create Redis pool
    try:
        create_redis_pool()
        # Optionally check connection
        # async with get_redis_connection() as conn:
        #    await conn.ping()
        # logger.info("Redis connection successful.")
    except Exception as e:
        logger.error(f"Failed to initialize Redis during startup: {e}", exc_info=True)
        # Decide if the app should fail to start if Redis is unavailable
        # raise RuntimeError("Could not connect to Redis") from e

    # Initialize HTTPX client (it's created lazily, but we can ensure it's ready)
    _ = await get_client() # This ensures the client instance is created
    logger.info("HTTPX client initialized.")

    yield # Application runs here

    # Shutdown phase
    logger.info("Application shutdown...")
    # Close Redis pool
    await close_redis_pool()
    # Close HTTPX client
    await close_client()
    logger.info("Resources cleaned up.")

# Create FastAPI app instance with lifespan manager
app = FastAPI(
    title="Pokedex API",
    description="API for fetching and caching Pokemon data from PokeAPI",
    version="1.0.0",
    lifespan=lifespan # Register the lifespan context manager
)

@app.get("/")
async def read_root():
    """ Basic root endpoint to check if the API is running. """
    # Optionally check resource status
    redis_status = "connected" if redis_pool else "not connected"
    return {
        "message": "Welcome to the Pokedex API!",
        "redis_status": redis_status
        }

# API endpoints will be added here later...

# Example of how to run directly (though we'll use docker-compose)
# if __name__ == "__main__":
#    import uvicorn
#    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)