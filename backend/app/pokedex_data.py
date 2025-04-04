# backend/app/pokedex_data.py

import logging
from typing import List, Optional
from functools import lru_cache # Consider using Redis cache instead of in-memory lru_cache if needed across instances

from .pokeapi_client import fetch_pokeapi
from .cache import get_cache, set_cache
from .config import settings
from .models import PokemonSummary, PokemonDetail, PokemonType, Generation, PokemonTypeFilter, PokemonAbility, PokemonStat

logger = logging.getLogger(__name__)

POKEDEX_SUMMARY_CACHE_KEY = "pokedex_summary_data"
POKEMON_DETAIL_CACHE_PREFIX = "pokemon_detail_"
GENERATIONS_CACHE_KEY = "generations_data"
TYPES_CACHE_KEY = "types_data"

async def _fetch_pokemon_summary(pokemon_id: int) -> Optional[PokemonSummary]:
    """Fetches and processes summary data for a single Pokémon from PokeAPI."""
    pokemon_data = await fetch_pokeapi(f"/pokemon/{pokemon_id}")
    if not pokemon_data:
        logger.warning(f"Could not fetch data for Pokémon ID: {pokemon_id} from PokeAPI.")
        return None

    species_url = pokemon_data.get('species', {}).get('url')
    if not species_url:
        logger.warning(f"Species URL not found for Pokémon ID: {pokemon_id}.")
        return None

    species_data = await fetch_pokeapi(species_url)
    if not species_data:
        logger.warning(f"Could not fetch species data for Pokémon ID: {pokemon_id} from PokeAPI at {species_url}.")
        return None

    generation_name = species_data.get('generation', {}).get('name')
    generation_id = _generation_name_to_id(generation_name) if generation_name else None

    types = [PokemonType(name=t['type']['name']) for t in pokemon_data.get('types', [])]

    return PokemonSummary(
        id=pokemon_data['id'],
        name=pokemon_data['name'],
        generation_id=generation_id,
        types=types
    )


async def get_pokedex_summary_data(force_refresh: bool = False) -> Optional[List[PokemonSummary]]:
    """
    Retrieves and caches the aggregated summary data for all Pokémon.

    Args:
        force_refresh: If True, bypasses cache and fetches fresh data from PokeAPI.

    Returns:
        A list of PokemonSummary objects, or None on failure.
    """
    if not force_refresh:
        cached_summary = await get_cache(POKEDEX_SUMMARY_CACHE_KEY)
        if cached_summary:
            logger.info("Serving Pokedex summary data from cache.")
            try:
                # Validate cached data against the PokedexSummary model
                return [PokemonSummary(**item) for item in cached_summary] # Rehydrate as Pydantic objects
            except Exception as e:
                logger.error(f"Error validating cached Pokedex summary data, refreshing from PokeAPI. Error: {e}", exc_info=True)
                # Fallback to fetching fresh data if cache validation fails
                force_refresh = True # Proceed to refresh

    if force_refresh:
        logger.info("Fetching fresh Pokedex summary data from PokeAPI...")
        all_pokemon_summaries: List[PokemonSummary] = []
        for pokemon_id in range(1, settings.max_pokemon_id_to_fetch + 1): # Iterate through Pokemon IDs
            summary = await _fetch_pokemon_summary(pokemon_id)
            if summary: # Only append if summary data was successfully fetched
                all_pokemon_summaries.append(summary)

        if all_pokemon_summaries:
            # Store the *serialized* data in cache (list of dicts)
            if await set_cache(POKEDEX_SUMMARY_CACHE_KEY, [s.model_dump() for s in all_pokemon_summaries]): # Serialize to JSON-compatible dicts
                logger.info(f"Pokedex summary data cached successfully for key: {POKEDEX_SUMMARY_CACHE_KEY}")
            else:
                logger.warning(f"Failed to cache Pokedex summary data for key: {POKEDEX_SUMMARY_CACHE_KEY}")
            return all_pokemon_summaries
        else:
            logger.error("Failed to aggregate Pokedex summary data from PokeAPI.")
            return None # Indicate failure

    return None # Should not reach here under normal circumstances, but for type safety


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

    if not force_refresh:
        cached_detail = await get_cache(cache_key)
        if cached_detail:
            logger.info(f"Serving Pokémon detail data for '{pokemon_id_or_name}' from cache.")
            try:
                return PokemonDetail(**cached_detail) # Rehydrate from cached dict
            except Exception as e:
                logger.error(f"Error validating cached Pokemon detail data for '{pokemon_id_or_name}', refreshing from PokeAPI. Error: {e}", exc_info=True)
        force_refresh = True # Fallback to refresh

    if force_refresh:
        logger.info(f"Fetching fresh Pokémon detail data for '{pokemon_id_or_name}' from PokeAPI...")
        pokemon_data = await fetch_pokeapi(f"/pokemon/{pokemon_id_or_name}")
        if not pokemon_data:
            logger.warning(f"Could not fetch Pokemon data for '{pokemon_id_or_name}' from PokeAPI.")
            return None

        species_url = pokemon_data.get('species', {}).get('url')
        if not species_url:
            logger.warning(f"Species URL not found for Pokémon '{pokemon_id_or_name}'.")
            return None

        species_data = await fetch_pokeapi(species_url)
        if not species_data:
            logger.warning(f"Could not fetch species data for '{pokemon_id_or_name}' from PokeAPI at {species_url}.")
            return None

        evolution_chain_url = species_data # Pass species_data to validator to extract from there
        generation_name = species_data.get('generation', {}).get('name')
        generation_id = _generation_name_to_id(generation_name) if generation_name else None

        pokemon_detail = PokemonDetail(
            id=pokemon_data['id'],
            name=pokemon_data['name'],
            genus=species_data.get('genera', []), # Pass genera list for validator
            generation_id=generation_id,
            types=[PokemonType(name=t['type']['name']) for t in pokemon_data.get('types', [])],
            abilities=[PokemonAbility(name=ability['ability']['name'], url=ability['ability']['url']) for ability in pokemon_data.get('abilities', [])],
            height=pokemon_data.get('height'),
            weight=pokemon_data.get('weight'),
            base_experience=pokemon_data.get('base_experience'),
            stats=[PokemonStat(name=stat['stat']['name'], base_stat=stat['base_stat']) for stat in pokemon_data.get('stats', [])],
            sprites=pokemon_data.get('sprites'), # Pass full sprites dict for validator to handle nested official artwork
            species_url=species_url,
            evolution_chain_url=evolution_chain_url, # Pass species data to validator for extraction
            flavor_text_entries=species_data.get('flavor_text_entries', []), # Pass full list for validator
            gender_rate=species_data.get('gender_rate'),
            egg_groups=species_data.get('egg_groups', []),
            habitat=species_data.get('habitat', {}).get('name'), # Habitat is nested
            is_legendary=species_data.get('is_legendary', False),
            is_mythical=species_data.get('is_mythical', False),
            shape=species_data.get('shape', {}).get('name'), # Shape is nested
            growth_rate_name=species_data.get('growth_rate', {}).get('name') # Growth rate is nested
        )

        if pokemon_detail:
            if await set_cache(cache_key, pokemon_detail.model_dump()): # Serialize to JSON-compatible dict
                logger.info(f"Pokemon detail data for '{pokemon_id_or_name}' cached successfully.")
            else:
                logger.warning(f"Failed to cache Pokemon detail data for '{pokemon_id_or_name}'.")
            return pokemon_detail
        else:
            logger.error(f"Failed to fetch and process Pokemon detail data for '{pokemon_id_or_name}' from PokeAPI.")
            return None
    return None # Should not reach here, but for type safety


async def get_all_generations_data(force_refresh: bool = False) -> Optional[List[Generation]]:
    """Fetches and caches data for all Pokemon generations."""
    if not force_refresh:
        cached_generations = await get_cache(GENERATIONS_CACHE_KEY)
        if cached_generations:
            logger.info("Serving Pokemon generations data from cache.")
            try:
                return [Generation(**item) for item in cached_generations]
            except Exception as e:
                logger.error(f"Error validating cached generations data, refreshing from PokeAPI. Error: {e}", exc_info=True)
                force_refresh = True

    if force_refresh:
        logger.info("Fetching fresh Pokemon generations data from PokeAPI...")
        generations_data = await fetch_pokeapi("/generation?limit=100") # Limit large enough to get all generations
        if generations_data and generations_data.get('results'):
            generations = []
            for gen_data in generations_data['results']:
                gen_name = gen_data['name']
                gen_id = _generation_name_to_id(gen_name)
                if gen_id: # Ensure we get a valid ID
                    generations.append(Generation(id=gen_id, name=gen_name))

            if generations:
                if await set_cache(GENERATIONS_CACHE_KEY, [g.model_dump() for g in generations]):
                    logger.info("Pokemon generations data cached successfully.")
                else:
                    logger.warning("Failed to cache Pokemon generations data.")
                return generations
        else:
            logger.error("Failed to fetch Pokemon generations data from PokeAPI.")
            return None
    return None

async def get_all_types_data(force_refresh: bool = False) -> Optional[List[PokemonTypeFilter]]:
    """Fetches and caches data for all Pokemon types."""
    if not force_refresh:
        cached_types = await get_cache(TYPES_CACHE_KEY)
        if cached_types:
            logger.info("Serving Pokemon types data from cache.")
            try:
                return [PokemonTypeFilter(**item) for item in cached_types]
            except Exception as e:
                logger.error(f"Error validating cached types data, refreshing from PokeAPI. Error: {e}", exc_info=True)
                force_refresh = True

    if force_refresh:
        logger.info("Fetching fresh Pokemon types data from PokeAPI...")
        types_data = await fetch_pokeapi("/type?limit=100") # Limit large enough for all types
        if types_data and types_data.get('results'):
            types = [PokemonTypeFilter(name=type_data['name']) for type_data in types_data['results']]
            if types:
                if await set_cache(TYPES_CACHE_KEY, [t.model_dump() for t in types]):
                    logger.info("Pokemon types data cached successfully.")
                else:
                    logger.warning("Failed to cache Pokemon types data.")
                return types
        else:
            logger.error("Failed to fetch Pokemon types data from PokeAPI.")
            return None
    return None


@lru_cache(maxsize=16) # Cache results for generation names
def _generation_name_to_id(generation_name: Optional[str]) -> Optional[int]:
    """
    Helper function to convert generation name (e.g., 'generation-i', 'generation-ix')
    to its corresponding integer ID (e.g., 1, 9).
    Handles Roman numerals I through IX.
    """
    if not generation_name:
        logger.warning("Received empty generation name.")
        return None

    # Mapping for Roman numerals used in PokeAPI generation names
    roman_to_int_map = {
        "i": 1,
        "ii": 2,
        "iii": 3,
        "iv": 4,
        "v": 5,
        "vi": 6,
        "vii": 7,
        "viii": 8,
        "ix": 9,
        # Add more mappings here if new generations use Roman numerals
    }

    try:
        # Split the string, e.g., "generation-ix" -> ["generation", "ix"]
        parts = generation_name.lower().split('-')
        if len(parts) != 2 or not parts[1]:
            logger.warning(f"Could not parse Roman numeral from generation name: {generation_name}")
            return None

        roman_numeral = parts[1]

        # Look up the Roman numeral in our map
        generation_id = roman_to_int_map.get(roman_numeral)

        if generation_id is None:
            logger.warning(f"Unknown or unsupported Roman numeral '{roman_numeral}' in generation name: {generation_name}")
            return None # Return None if the Roman numeral is not in our map

        return generation_id

    except Exception as e: # Catch potential errors during split or processing
        logger.error(f"Error converting generation name '{generation_name}' to ID: {e}", exc_info=True)
        return None


# Example Usage (for testing within this module)
async def main():
    # Fetch and print Pokedex summary data
    summary_data = await get_pokedex_summary_data(force_refresh=True) # Force refresh for first run
    if summary_data:
        print(f"Fetched {len(summary_data)} Pokemon summary items.")
        # print("First 3 Pokemon Summaries:\n", [s.model_dump_json(indent=2) for s in summary_data[:3]]) # Optional print
    else:
        print("Failed to retrieve Pokedex summary data.")

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