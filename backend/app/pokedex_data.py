# backend/app/pokedex_data.py

import logging
from typing import List, Optional, Any
from functools import lru_cache # Consider using Redis cache instead of in-memory lru_cache if needed across instances
import asyncio

from .config import settings
#from .cache_utils import get_backend_cache, set_backend_cache, clear_backend_cache

from pokeapi_lib import (
    get_pokemon, get_species, get_all_generations, get_all_types, # Import list functions
    BasePokemon, BaseSpecies, GenerationInfo, TypeInfo, # Import library models
    PokeAPIError, ResourceNotFoundError
)
# --- Import Backend Models (needed for frontend response) ---
from .models import (
    PokemonSummary, PokemonDetail, PokemonType, Generation, PokemonTypeFilter,
    PokemonAbility, PokemonStat, PokemonSprites # Need these detailed models
)
# --- Import Backend HTTP client getter ---
from .clients import get_library_client

logger = logging.getLogger(__name__)

POKEDEX_SUMMARY_CACHE_KEY = "pokedex_summary_data"
POKEMON_DETAIL_CACHE_PREFIX = "pokemon_detail_"
GENERATIONS_CACHE_KEY = "generations_data"
TYPES_CACHE_KEY = "types_data"

# --- Local Backend Cache Functions (using library's configured Redis) ---
# These functions now cache the *results from the library* or the *final aggregated objects*
from pokeapi_lib.cache import get_cache as lib_get_cache, set_cache as lib_set_cache

async def get_backend_cache(key: str) -> Optional[Any]:
    # Wrapper potentially adding logging specific to this backend's cache layer
    logger.debug(f"Backend cache GET: {key}")
    return await lib_get_cache(key)

async def set_backend_cache(key: str, value: Any):
    # Use TTL from backend settings
    logger.debug(f"Backend cache SET: {key}")
    await lib_set_cache(key, value, ttl=settings.cache_ttl_seconds)

async def clear_backend_cache(key: str):
     # Need delete function in library's cache module or direct access
     logger.warning(f"Backend cache CLEAR: {key} (delete function needed in lib)")
     # await lib_clear_cache(key) # If implemented
     pass

async def _fetch_pokemon_summary(pokemon_id: int) -> Optional[PokemonSummary]:
    """Fetches and processes summary data for a single Pokémon from PokeAPI, including sprite."""
    pokemon_data = await fetch_pokeapi(f"/pokemon/{pokemon_id}")
    if not pokemon_data:
        logger.warning(f"Could not fetch base data for Pokémon ID: {pokemon_id} from PokeAPI.")
        return None

    species_info = pokemon_data.get('species', {})
    species_url = species_info.get('url') if species_info else None

    species_data = None
    if species_url:
         species_data = await fetch_pokeapi(species_url)
    # Default species_data to empty dict if fetch failed or URL was missing
    if species_data is None:
         species_data = {}

    generation_name = species_data.get('generation', {}).get('name')
    generation_id = _generation_name_to_id(generation_name) if generation_name else 0

    types_list = pokemon_data.get('types', [])
    types = [PokemonType(name=t.get('type', {}).get('name', 'unknown')) for t in types_list]

    # --- Extract Sprite URL ---
    sprite_url = pokemon_data.get('sprites', {}).get('front_default')
    # Ensure HTTPS
    if sprite_url and sprite_url.startswith("http://"):
         sprite_url = sprite_url.replace("http://", "https://", 1)
         
    # --- Extract Status Flags ---
    is_legendary = species_data.get('is_legendary', False)
    is_mythical = species_data.get('is_mythical', False)
    is_baby = species_data.get('is_baby', False)

    # Validate required fields exist before creating summary
    poke_id = pokemon_data.get('id')
    poke_name = pokemon_data.get('name')
    if poke_id is None or poke_name is None:
         logger.error(f"Missing critical ID or Name for Pokemon ID fetch attempt: {pokemon_id}. Skipping summary.")
         return None

    return PokemonSummary(
        id=poke_id,
        name=poke_name,
        generation_id=generation_id,
        types=types,
        sprite_url=sprite_url, # Add the sprite URL
        is_legendary=is_legendary,
        is_mythical=is_mythical,
        is_baby=is_baby
    )
    
# --- Helper function to fetch single generation detail ---
async def _fetch_generation_detail(gen_info: dict) -> Optional[Generation]:
    """Fetches details for a single generation to get its region."""
    gen_url = gen_info.get('url')
    if not gen_url:
        logger.warning(f"Missing URL for generation: {gen_info.get('name')}")
        return None

    gen_detail_data = await fetch_pokeapi(gen_url)
    if not gen_detail_data:
        logger.warning(f"Failed to fetch details for generation URL: {gen_url}")
        return None

    gen_id_str = gen_detail_data.get('name') # e.g., generation-i
    gen_id = _generation_name_to_id(gen_id_str)
    region_info = gen_detail_data.get('main_region')
    region_name = region_info.get('name', 'unknown') if region_info else 'unknown' # Default if missing

    if gen_id is None:
         logger.warning(f"Could not parse generation ID from detail fetch: {gen_id_str}")
         return None

    return Generation(
        id=gen_id,
        name=gen_id_str,
        region_name=region_name
    )

async def get_pokedex_summary_data(force_refresh: bool = False) -> Optional[List[PokemonSummary]]:
    """
    Orchestrates calls using the library to build the summary list for all Pokémon.

    Args:
        force_refresh: If True, bypasses cache and fetches fresh data from PokeAPI.

    Returns:
        A list of PokemonSummary objects, or None on failure.
    """
    if not force_refresh:
        cached_summary = await get_backend_cache(POKEDEX_SUMMARY_CACHE_KEY)
        if cached_summary:
            logger.info("Serving Pokedex summary data from backend cache.")
            try:
                # Use model_validate for Pydantic V2
                return [PokemonSummary.model_validate(item) for item in cached_summary]
            except Exception as e:
                logger.error(f"Invalid backend cache for summary: {e}", exc_info=True)
                await clear_backend_cache(POKEDEX_SUMMARY_CACHE_KEY)
                # Fall through

    logger.info("Fetching fresh Pokedex summary data via library...")
    all_pokemon_summaries: List[PokemonSummary] = []
    client = await get_library_client()
    
    async def fetch_single_summary(pokemon_id: int) -> Optional[PokemonSummary]:
         try:
            client = await get_library_client()
            base_pokemon = await get_pokemon(pokemon_id, client=client)
            # --- Need species for generation, flags ---
            species_url_from_lib = base_pokemon.species.get('url')
            if not species_url_from_lib:
                 logger.warning(f"Summary fetch skipped: Missing species URL for {pokemon_id}")
                 return None
            base_species = await get_species(pokemon_id, client=client) # Use ID

            generation_name = base_species.generation
            generation_id = _generation_name_to_id(generation_name) if generation_name else 0

            # Get sprite URL (library model should provide transformed URL if local mode)
            sprite_url = base_pokemon.sprites.front_default # Adjust if library model names differ

            # Map types
            types = [PokemonType(name=t.type.name) for t in base_pokemon.types]

            return PokemonSummary(
                 id=base_pokemon.id,
                 name=base_pokemon.name,
                 generation_id=generation_id,
                 types=types,
                 sprite_url=sprite_url,
                 is_legendary=base_species.is_legendary,
                 is_mythical=base_species.is_mythical,
                 is_baby=base_species.is_baby
            )
         except ResourceNotFoundError:
            logger.warning(f"Summary fetch skipped: Pokemon/Species {pokemon_id} not found via library.")
            return None
         except Exception as e:
             logger.error(f"Failed to fetch summary components for ID {pokemon_id} via library: {e}", exc_info=False)
             return None

    # Fetch summaries concurrently
    tasks = [fetch_single_summary(i) for i in range(1, settings.max_pokemon_id_to_fetch + 1)]
    results = await asyncio.gather(*tasks)

    all_pokemon_summaries = [summary for summary in results if summary is not None]

    if all_pokemon_summaries:
         # Cache the final list of PokemonSummary objects
         await set_backend_cache(POKEDEX_SUMMARY_CACHE_KEY, [s.model_dump() for s in all_pokemon_summaries])
         logger.info(f"Pokedex summary data cached successfully in backend cache ({len(all_pokemon_summaries)} entries).")
         return all_pokemon_summaries
    else:
        logger.error("Failed to aggregate any Pokedex summary data via library.")
        return None

async def get_pokemon_detail_data(pokemon_id_or_name: str, force_refresh: bool = False) -> Optional[PokemonDetail]:
    """
    Retrieves and caches detailed data for a specific Pokémon.

    Args:
        pokemon_id_or_name: Pokémon ID (int) or name (str).
        force_refresh: If True, bypasses cache and fetches fresh data from PokeAPI.

    Returns:
        A PokemonDetail object, or None if not found or error.
    """
    cache_key = f"{POKEMON_DETAIL_CACHE_PREFIX}{pokemon_id_or_name}"
    identifier_str = str(pokemon_id_or_name).lower()

    if not force_refresh:
        cached_detail = await get_backend_cache(cache_key)
        if cached_detail:
            logger.info(f"Serving Pokémon detail data for '{identifier_str}' from cache.")
            try:
                # Use model_validate for Pydantic V2
                return PokemonDetail.model_validate(cached_detail)
            except Exception as e:
                logger.error(f"Invalid backend cache for {cache_key}: {e}", exc_info=True)
                await clear_backend_cache(cache_key) # Clear bad cache entry
                # Fall through to fetch fresh data

    logger.info(f"Fetching fresh Pokémon detail data for '{identifier_str}' via library...")
    try:
        client = await get_library_client()

        # Fetch base Pokemon data and species data concurrently using the library
        # Species might use ID or name, library handles this if implemented consistently
        # Need species ID. Get it from pokemon data if identifier was name.
        # Or fetch pokemon first, then species using pokemon.id
        base_pokemon = await get_pokemon(identifier_str, client=client)
        
        # --- Get species URL from the species dictionary ---
        species_url_from_lib = base_pokemon.species.get('url') if base_pokemon.species else None
        if not species_url_from_lib:
             # Handle case where species dict or URL might be missing
             logger.error(f"Species URL missing in BasePokemon object for {identifier_str}")
             # Decide how to handle: raise error, return None, or continue with missing data?
             # For now, let's try to continue but some fields will be missing
             base_species = BaseSpecies(id=base_pokemon.id, name=base_pokemon.species.get('name', ''), # Minimal BaseSpecies if fetch fails
                                         order=-1, gender_rate=-1, capture_rate=0, is_baby=False,
                                         is_legendary=False, is_mythical=False, generation='unknown',
                                         evolution_chain_url='')
        else:
            # Fetch species using the extracted URL (or ID)
            base_species = await get_species(base_pokemon.id, client=client) # Fetching by ID is usually safer

        # --- TODO: Fetch other data via library if needed ---
        # e.g., evolution_chain = await get_evolution_chain(...)
        # e.g., generation_detail = await get_generation(...) to get region name reliably
        # For now, we rely on data available in BasePokemon and BaseSpecies

        # --- Combine data into the frontend's PokemonDetail model ---
        # This requires mapping fields from BasePokemon/BaseSpecies to PokemonDetail
        generation_name = base_species.generation # Name extracted by library model
        generation_id = _generation_name_to_id(generation_name) if generation_name else 0

        # Extract sprites (library model provides simplified structure)
        # The library's PokemonSprites model validator already handles URL transformation
        # We might need to adapt PokemonSprites in *this* backend's models.py
        # to match the structure returned by the library's BasePokemon.sprites
        # OR adapt the library's BasePokemon.sprites to match this backend's PokemonSprites.
        # Let's assume for now library returns URLs directly and we map them.
        # This part needs careful alignment between library models and backend models.

        # Example mapping (ADJUST BASED ON ACTUAL LIBRARY MODELS)
        sprites_for_detail = PokemonSprites(
             front_default=base_pokemon.sprites.front_default,
             front_shiny=base_pokemon.sprites.front_shiny,
             official_artwork=base_pokemon.sprites.official_artwork_front,
             # Add animated etc. based on library's BasePokemon.sprites fields
        )
        # The library's validator should handle URL transformation based on settings.sprite_source_mode

        detail_data_dict = {
            "id": base_pokemon.id,
            "name": base_pokemon.name,
            "genus": "Unknown Genus", # TODO: Get from species genera list if added to BaseSpecies
            "generation_id": generation_id,
            "types": [{"name": t.type.name} for t in base_pokemon.types], # Map from library structure
            "abilities": [
                PokemonAbility(name=a.ability.name, url=a.ability.url, is_hidden=a.is_hidden)
                for a in base_pokemon.abilities
            ], # Map from library structure
            "height": base_pokemon.height,
            "weight": base_pokemon.weight,
            "base_experience": base_pokemon.base_experience,
            "stats": [
                 PokemonStat(name=s.stat.name, base_stat=s.base_stat) for s in base_pokemon.stats
            ], # Map from library structure
            "sprites": sprites_for_detail.model_dump(), # Use the mapped sprites
            "species_url": species_url_from_lib or "", # Use the URL obtained from BasePokemon
            "evolution_chain_url": base_species.evolution_chain_url if base_species else "", # Get from BaseSpecies
            "flavor_text_entries": [], # TODO: Get from species flavor text if added to BaseSpecies
            "catch_rate": base_species.capture_rate if base_species else None,
            "base_happiness": base_species.base_happiness if base_species else None,
            "hatch_counter": base_species.hatch_counter,
            "is_baby": base_species.is_baby,
            "is_legendary": base_species.is_legendary,
            "is_mythical": base_species.is_mythical,
            "evolves_from_species": base_species.evolves_from_species,
            "gender_rate": base_species.gender_rate,
            "egg_groups": [], # TODO: Get from species egg_groups if added to BaseSpecies
            "habitat": None, # TODO: Get from species habitat if added to BaseSpecies
            "shape": None, # TODO: Get from species shape if added to BaseSpecies
            "growth_rate_name": None, # TODO: Get from species growth_rate if added to BaseSpecies
        }

        # Validate final combined data against the detailed backend model
        pokemon_detail = PokemonDetail.model_validate(detail_data_dict)

        # Cache the final PokemonDetail object
        await set_backend_cache(cache_key, pokemon_detail.model_dump())
        logger.info(f"Successfully fetched and combined details for '{identifier_str}'.")
        return pokemon_detail

    except ResourceNotFoundError:
        logger.warning(f"Resource not found via library for '{identifier_str}'.")
        return None # Propagate not found
    except (PokeAPIError, Exception) as e:
        logger.error(f"Error fetching/processing details via library for '{identifier_str}': {e}", exc_info=True)
        return None # Return None on other library errors or processing errors

async def get_all_generations_data(force_refresh: bool = False) -> Optional[List[Generation]]:
    """
    Retrieves list of all Generations using the library, maps to backend model,
    and caches the result in the backend cache.
    """
    if not force_refresh:
        cached_data = await get_backend_cache(GENERATIONS_CACHE_KEY)
        if cached_data:
            logger.info("Serving Pokemon generations data from backend cache.")
            try:
                # Validate against *backend's* Generation model
                return [Generation.model_validate(item) for item in cached_data]
            except Exception as e:
                logger.error(f"Invalid backend cache for generations: {e}", exc_info=True)
                await clear_backend_cache(GENERATIONS_CACHE_KEY)
                # Fall through

    logger.info("Fetching fresh generations data via library...")
    try:
        client = await get_library_client()
        # Call the library function to get all generations
        library_generations: List[GenerationInfo] = await get_all_generations(client=client)

        if not library_generations:
            logger.warning("Library returned no generation data.")
            return [] # Return empty list if none found

        # Map from library's GenerationInfo to backend's Generation model
        backend_generations: List[Generation] = []
        for lib_gen in library_generations:
             try:
                  # Assuming backend's Generation model is identical or subset for now
                  backend_gen = Generation.model_validate(lib_gen.model_dump())
                  backend_generations.append(backend_gen)
             except Exception as map_err:
                  logger.error(f"Failed to map library generation '{lib_gen.name}' to backend model: {map_err}")
                  continue # Skip this generation if mapping fails

        # Cache the backend model list
        await set_backend_cache(GENERATIONS_CACHE_KEY, [g.model_dump() for g in backend_generations])
        logger.info(f"Generations data cached successfully in backend cache ({len(backend_generations)} entries).")
        return backend_generations

    except (PokeAPIError, Exception) as e:
        logger.error(f"Failed to get generations via library: {e}", exc_info=True)
        return None # Return None on failure

async def get_all_types_data(force_refresh: bool = False) -> Optional[List[PokemonTypeFilter]]:
    """
    Retrieves list of all Types using the library, maps to backend model,
    and caches the result in the backend cache.
    """
    if not force_refresh:
        cached_data = await get_backend_cache(TYPES_CACHE_KEY)
        if cached_data:
            logger.info("Serving Pokemon types data from backend cache.")
            try:
                # Validate against *backend's* PokemonTypeFilter model
                return [PokemonTypeFilter.model_validate(item) for item in cached_data]
            except Exception as e:
                logger.error(f"Invalid backend cache for types: {e}", exc_info=True)
                await clear_backend_cache(TYPES_CACHE_KEY)
                # Fall through

    logger.info("Fetching fresh types data via library...")
    try:
        client = await get_library_client()
        # Call the library function to get all types
        library_types: List[TypeInfo] = await get_all_types(client=client)

        if not library_types:
            logger.warning("Library returned no type data.")
            return []

        # Map from library's TypeInfo to backend's PokemonTypeFilter model
        # In this case, they both likely only need 'name'
        backend_types: List[PokemonTypeFilter] = []
        for lib_type in library_types:
             try:
                  backend_type = PokemonTypeFilter(name=lib_type.name)
                  backend_types.append(backend_type)
             except Exception as map_err:
                  logger.error(f"Failed to map library type '{lib_type.name}' to backend model: {map_err}")
                  continue

        # Cache the backend model list
        await set_backend_cache(TYPES_CACHE_KEY, [t.model_dump() for t in backend_types])
        logger.info(f"Types data cached successfully in backend cache ({len(backend_types)} entries).")
        return backend_types

    except (PokeAPIError, Exception) as e:
        logger.error(f"Failed to get types via library: {e}", exc_info=True)
        return None # Return None on failure

# Example Usage (for testing within this module)
async def main():
    # Fetch and print Pokedex summary data
    """ summary_data = await get_pokedex_summary_data(force_refresh=True) # Force refresh for first run
    if summary_data:
        print(f"Fetched {len(summary_data)} Pokemon summary items.")
        # print("First 3 Pokemon Summaries:\n", [s.model_dump_json(indent=2) for s in summary_data[:3]]) # Optional print
    else:
        print("Failed to retrieve Pokedex summary data.") """

    # Fetch and print detail for Bulbasaur
    bulbasaur_detail = await get_pokemon_detail_data("bulbasaur", force_refresh=True) # Force refresh for first run
    if bulbasaur_detail:
        print("\nBulbasaur Detail:\n", bulbasaur_detail.model_dump_json(indent=2))
    else:
        print("Failed to retrieve Bulbasaur detail data.")

    # # Fetch and print generations data
    # generations = await get_all_generations_data(force_refresh=True)
    # if generations:
    #     print(f"\nFetched {len(generations)} generations.")
    #     # print("Generations:\n", [g.model_dump_json(indent=2) for g in generations])
    # else:
    #     print("Failed to retrieve generations data.")

    # # Fetch and print types data
    # types = await get_all_types_data(force_refresh=True)
    # if types:
    #     print(f"\nFetched {len(types)} types.")
    #     # print("Types:\n", [t.model_dump_json(indent=2) for t in types])
    # else:
    #     print("Failed to retrieve types data.")

if __name__ == "__main__":
    import asyncio
    import time

    async def measure_time(coro_func, *args, **kwargs):
        start_time = time.time()
        result = await coro_func(*args, **kwargs)
        end_time = time.time()
        duration = end_time - start_time
        print(f"Function '{coro_func.__name__}' execution time: {duration:.4f} seconds")
        return result

    async def main_with_timing():
        await measure_time(main) # Run main function and measure its total time

    asyncio.run(main_with_timing())