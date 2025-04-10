# pokeapi_lib/__init__.py

# Expose core functions and models for easy import
from .core import (
    get_pokemon, get_species, get_generation, get_type, # Add new singles
    get_all_generations, get_all_types # Add new list functions
)
from .models import BasePokemon, BaseSpecies, GenerationInfo, TypeInfo # Expose main models
from .exceptions import PokeAPIError, ResourceNotFoundError, PokeAPIConnectionError, CacheError
from .cache import configure_redis, close_redis_pool

# Optional: Define __all__ for explicit export control
__all__ = [
    # Core Functions
    "get_pokemon", "get_species", "get_generation", "get_type",
    "get_all_generations", "get_all_types",
    # Config/Close
    "configure_redis", "close_redis_pool",
    # Models
    "BasePokemon", "BaseSpecies", "GenerationInfo", "TypeInfo",
    # Exceptions
    "PokeAPIError", "ResourceNotFoundError", "PokeAPIConnectionError", "CacheError",
]

__version__ = "0.1.0" # Keep version consistent with pyproject.toml