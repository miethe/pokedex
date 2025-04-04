# test_redis.py
import asyncio
import redis.asyncio as redis
import os
from dotenv import load_dotenv

async def test_connection():
    # Load .env file from the current directory (backend/)
    load_dotenv()
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0") # Default if not in .env
    print(f"Attempting to connect to Redis at: {redis_url}")

    try:
        # Create a direct connection (no pool needed for a simple test)
        client = redis.from_url(redis_url, decode_responses=True)
        
        # Send a PING command
        response = await client.ping()
        print(f"Redis PING successful! Response: {response}")

        # Optional: Try setting and getting a test key
        await client.set("test_key_from_script", "hello_redis")
        value = await client.get("test_key_from_script")
        print(f"Set and got test key. Value: {value}")
        await client.delete("test_key_from_script") # Clean up

        await client.close() # Close the connection
        print("Connection closed.")

    except redis.RedisError as e:
        print(f"Redis connection failed: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())