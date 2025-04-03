# backend/app/cache.py

import redis.asyncio as redis
import json
import logging
from typing import Optional, Any
from contextlib import asynccontextmanager

from .config import settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

redis_pool = None

def create_redis_pool():
    """Creates an asynchronous Redis connection pool."""
    global redis_pool
    try:
        logger.info(f"Attempting to connect to Redis at: {settings.redis_url}")
        # Using from_url handles parsing the connection string
        redis_pool = redis.ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True, # Decode responses to strings automatically
            max_connections=20     # Adjust max connections as needed
        )
        logger.info("Redis connection pool created successfully.")
        return redis_pool
    except Exception as e:
        logger.error(f"Failed to create Redis connection pool: {e}", exc_info=True)
        raise # Re-raise the exception to indicate failure

async def close_redis_pool():
    """Closes the Redis connection pool."""
    global redis_pool
    if redis_pool:
        try:
            # Newer redis-py versions (>4.3.0) recommend using redis_pool.disconnect()
            # Check if disconnect method exists
            if hasattr(redis_pool, 'disconnect'):
                await redis_pool.disconnect(inuse_connections=True)
                logger.info("Redis connection pool disconnected.")
            else:
                # Older versions might rely on implicit closing or different methods
                 logger.warning("Redis pool does not have a 'disconnect' method. Relying on garbage collection.")
            redis_pool = None
        except Exception as e:
            logger.error(f"Error closing Redis pool: {e}", exc_info=True)

@asynccontextmanager
async def get_redis_connection():
    """Provides a Redis connection from the pool using an async context manager."""
    if redis_pool is None:
        raise ConnectionError("Redis pool is not initialized.")

    conn = None
    try:
        conn = redis.Redis(connection_pool=redis_pool)
        yield conn
    except redis.RedisError as e:
        logger.error(f"Redis connection error: {e}", exc_info=True)
        raise # Re-raise to signal the error upstream
    finally:
        # The connection is managed by the pool, explicit closing is usually not needed here
        # unless specific commands require it, or if not using ConnectionPool correctly.
        # logger.debug("Redis connection returned to pool (implicitly).")
        pass # Connection is automatically returned to pool when using redis.Redis(connection_pool=...)

async def get_cache(key: str) -> Optional[Any]:
    """Retrieves data from Redis cache."""
    try:
        async with get_redis_connection() as conn:
            cached_data = await conn.get(key)
            if cached_data:
                logger.debug(f"Cache HIT for key: {key}")
                try:
                    # Assuming data is stored as JSON string
                    return json.loads(cached_data)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to decode JSON from cache for key: {key}. Returning raw data.")
                    return cached_data # Or return None/raise error? Decide based on need
            else:
                logger.debug(f"Cache MISS for key: {key}")
                return None
    except redis.RedisError as e:
        logger.error(f"Redis GET error for key '{key}': {e}", exc_info=True)
        return None # Fail gracefully on cache error

async def set_cache(key: str, value: Any, ttl: int = settings.cache_ttl_seconds):
    """Stores data in Redis cache with a TTL."""
    if value is None:
        logger.warning(f"Attempted to cache None value for key: {key}. Skipping.")
        return False

    try:
        # Serialize data to JSON string before storing
        json_value = json.dumps(value)
    except (TypeError, OverflowError) as e:
        logger.error(f"Failed to serialize data to JSON for key '{key}': {e}", exc_info=True)
        return False # Cannot cache non-serializable data

    try:
        async with get_redis_connection() as conn:
            await conn.setex(key, ttl, json_value)
            logger.debug(f"Cache SET for key: {key} with TTL: {ttl}s")
            return True
    except redis.RedisError as e:
        logger.error(f"Redis SET error for key '{key}': {e}", exc_info=True)
        return False # Fail gracefully on cache error

async def clear_cache(key: str):
    """Removes a specific key from the Redis cache."""
    try:
        async with get_redis_connection() as conn:
            result = await conn.delete(key)
            if result > 0:
                logger.info(f"Cache CLEARED for key: {key}")
                return True
            else:
                logger.info(f"Cache key not found for deletion: {key}")
                return False
    except redis.RedisError as e:
        logger.error(f"Redis DELETE error for key '{key}': {e}", exc_info=True)
        return False

# Example Usage (for testing within this module)
# async def main():
#     create_redis_pool()
#     test_key = "my_test_key"
#     test_data = {"name": "Pikachu", "type": "Electric"}
#
#     await set_cache(test_key, test_data, ttl=60)
#     cached = await get_cache(test_key)
#     print(f"Retrieved from cache: {cached}")
#     await clear_cache(test_key)
#     cached_after_clear = await get_cache(test_key)
#     print(f"Retrieved after clear: {cached_after_clear}")
#     await close_redis_pool()
#
# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(main())