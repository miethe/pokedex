# backend/app/config.py

import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
# Useful for local development
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=env_path)

class Settings(BaseSettings):
    """Application settings."""

    # Redis configuration
    # Reads REDIS_URL from environment or .env file
    # Default value is provided for cases where it's not set
    redis_url: str = "redis://localhost:6379/0"

    # PokeAPI base URL
    pokeapi_base_url: str = "https://pokeapi.co/api/v2"

    # Default cache TTL (Time To Live) in seconds (24 hours)
    cache_ttl_seconds: int = 60 * 60 * 24

    # Max Pokemon ID to fetch for summary (adjust as new generations are added)
    # Gen 9 ends at 1025 (as of early 2024), let's add some buffer
    max_pokemon_id_to_fetch: int = 1025 # Example: covers up to Paldean Pokémon + some buffer

    class Config:
        # Specifies the .env file encoding
        env_file_encoding = 'utf-8'
        # If you use a different name for your .env file, specify it here
        # env_file = '.env'


# Create a single instance of the settings to be imported in other modules
settings = Settings()

# Example usage (optional, for testing):
if __name__ == "__main__":
    print(f"Redis URL: {settings.redis_url}")
    print(f"PokeAPI Base URL: {settings.pokeapi_base_url}")
    print(f"Default Cache TTL: {settings.cache_ttl_seconds} seconds")
    print(f"Max Pokemon ID: {settings.max_pokemon_id_to_fetch}")