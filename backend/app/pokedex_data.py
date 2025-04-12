# backend/app/pokedex_data.py

import logging
from typing import List, Optional, Any, Dict
import asyncio

from .config import settings
#from .cache_utils import get_backend_cache, set_backend_cache, clear_backend_cache

from pokeapi_lib import (
    get_pokemon, get_species, get_generation, get_type, # Import single functions
    get_all_generations, get_all_types, get_evolution_chain, # Import list functions
    BasePokemon, BaseSpecies, GenerationInfo, TypeInfo, EvolutionChain, # Import library models
    PokeAPIError, ResourceNotFoundError
)
# --- Import Backend Models (needed for frontend response) ---
from .models import (
    PokemonSummary, PokemonDetail, PokemonType, Generation, PokemonTypeFilter,
    PokemonAbility, PokemonStat, PokemonSprites
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

# --- Helpers ---
def _format_generation_id(gen_id):
    romanMap = { 1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V', 6: 'VI', 7: 'VII', 8: 'VIII', 9: 'IX' }
    return romanMap.get(gen_id, str(gen_id))

def _extract_english_genus(genera_list: List[Dict[str, Any]]) -> str:
    for entry in genera_list:
        if isinstance(entry, dict) and entry.get("language", {}).get("name") == "en":
            return entry.get("genus", "Unknown Genus")
    return "Unknown Genus"

def _extract_english_flavor_text(flavor_list: List[Dict[str, Any]]) -> str:
     # Prefer a more recent version if possible, fallback to first English
     preferred_versions = ['scarlet', 'violet', 'sword', 'shield', 'lets-go-pikachu', 'ultra-sun'] # Example order
     english_entries = [e for e in flavor_list if isinstance(e, dict) and e.get('language',{}).get('name') == 'en']
     for version_name in preferred_versions:
          for entry in english_entries:
               if entry.get('version',{}).get('name') == version_name:
                    return entry.get('flavor_text', '').replace('\n', ' ').replace('\f', ' ').strip()
     # Fallback to first English entry found
     if english_entries:
         return english_entries[0].get('flavor_text', '').replace('\n', ' ').replace('\f', ' ').strip()
     return "No description available."

def _calculate_gender_ratio(gender_rate: int) -> str:
     if gender_rate < 0: return 'Genderless'
     if gender_rate == 0: return '100% Male'
     if gender_rate == 8: return '100% Female'
     female_chance = (gender_rate / 8) * 100
     return f"{100 - female_chance:.1f}% Male, {female_chance:.1f}% Female"

def _calculate_hatch_time(hatch_counter: Optional[int]) -> str:
     return f"~{(hatch_counter + 1) * 255} steps" if hatch_counter is not None and hatch_counter >= 0 else 'N/A'

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
    
    BATCH_SIZE = 50 # Process 50 Pokemon at a time (adjust as needed)
    pokemon_ids_to_fetch = range(1, settings.max_pokemon_id_to_fetch + 1)

    async def fetch_single_summary(pokemon_id: int) -> Optional[PokemonSummary]:
        try:
            base_pokemon = await get_pokemon(pokemon_id, client=client)
            base_species = await get_species(pokemon_id, client=client)
            generation_info = await get_generation(base_species.generation.name, client=client) if base_species.generation else None

            sprite_url = base_pokemon.sprites.front_default # Assumes library transformed URL

            return PokemonSummary(
                 id=base_pokemon.id,
                 name=base_pokemon.name,
                 generation_id=generation_info.id if generation_info else 0,
                 types=[PokemonType(name=t.type.name) for t in base_pokemon.types],
                 sprite_url=sprite_url,
                 is_legendary=base_species.is_legendary,
                 is_mythical=base_species.is_mythical,
                 is_baby=base_species.is_baby
            )
        except (ResourceNotFoundError, PokeAPIError, Exception) as e:
            logger.warning(f"Summary fetch skipped for ID {pokemon_id}: {type(e).__name__}")
            return None

    #tasks = [fetch_single_summary(i) for i in range(1, settings.max_pokemon_id_to_fetch + 1)]
    #results = await asyncio.gather(*tasks)
    #all_pokemon_summaries = [summary for summary in results if summary is not None]
    
    for i in range(0, len(pokemon_ids_to_fetch), BATCH_SIZE):
        batch_ids = pokemon_ids_to_fetch[i:i + BATCH_SIZE]
        logger.info(f"Fetching summary batch: IDs {batch_ids[0]} to {batch_ids[-1]}")
        tasks = [fetch_single_summary(pid) for pid in batch_ids]
        results = await asyncio.gather(*tasks)
        batch_summaries = [summary for summary in results if summary is not None]
        all_pokemon_summaries.extend(batch_summaries)
        # Optional short sleep between batches to be nicer to the API
        await asyncio.sleep(0.1) # Sleep 100ms

    if all_pokemon_summaries:
         await set_backend_cache(POKEDEX_SUMMARY_CACHE_KEY, [s.model_dump() for s in all_pokemon_summaries])
         logger.info(f"Pokedex summary data cached in backend ({len(all_pokemon_summaries)} entries).")
         return all_pokemon_summaries
    else: logger.error("Failed to aggregate Pokedex summary data via library."); return None

async def get_pokemon_detail_data(pokemon_id_or_name: str, force_refresh: bool = False) -> Optional[PokemonDetail]:
    """
    Retrieves and caches detailed data for a specific Pokémon.

    Args:
        pokemon_id_or_name: Pokémon ID (int) or name (str).
        force_refresh: If True, bypasses cache and fetches fresh data from PokeAPI.

    Returns:
        A PokemonDetail object, or None if not found or error.
    """
    identifier_str = str(pokemon_id_or_name).lower()
    cache_key = f"{POKEMON_DETAIL_CACHE_PREFIX}{identifier_str}"

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
        # Fetch required data concurrently
        base_pokemon_task = get_pokemon(identifier_str, client=client)
        # Need species ID after getting base_pokemon if identifier was name
        base_pokemon = await base_pokemon_task
        species_task = get_species(base_pokemon.id, client=client)
        base_species = await species_task

        # Fetch evolution chain if URL exists
        evo_chain = None
        evo_chain_url = base_species.evolution_chain['url'] if base_species.evolution_chain else None
        if evo_chain_url:
            try:
                chain_id = int(evo_chain_url.split('/')[-2]) # Extract ID from URL
                evo_chain = await get_evolution_chain(chain_id, client=client)
            except (ValueError, IndexError, PokeAPIError) as evo_err:
                logger.warning(f"Could not fetch/process evolution chain from {evo_chain_url}: {evo_err}")

        # Fetch generation details for region name
        generation_info = None
        if base_species.generation:
            try:
                generation_info = await get_generation(base_species.generation.name, client=client)
            except Exception as gen_err:
                 logger.warning(f"Could not fetch generation details for {base_species.generation.name}: {gen_err}")


        # --- Map Library Models to Backend PokemonDetail ---
        # Sprites: Library handles transformation, pass dict directly
        sprites_data = base_pokemon.sprites.model_dump()

        # Convert height/weight
        height_m = base_pokemon.height
        weight_kg = base_pokemon.weight

        # Extract simple lists of names
        egg_group_names = [eg.name for eg in base_species.egg_groups]

        # Process names/text
        genus = _extract_english_genus(base_species.genera)
        description = _extract_english_flavor_text(base_species.flavor_text_entries)
        gender_ratio_str = _calculate_gender_ratio(base_species.gender_rate)
        hatch_time_str = _calculate_hatch_time(base_species.hatch_counter)
        evolves_from_name = base_species.evolves_from_species.name if base_species.evolves_from_species else None

        detail = PokemonDetail(
            id=base_pokemon.id,
            name=base_pokemon.name,
            genus=genus,
            generation_id=generation_info.id if generation_info else 0, # Default if fetch failed
            region_name=generation_info.region_name.capitalize() if generation_info else "Unknown", # Default
            types=[PokemonType(name=t.type.name) for t in base_pokemon.types],
            abilities=[PokemonAbility(name=a.ability.name, url=a.ability.url, is_hidden=a.is_hidden) for a in base_pokemon.abilities],
            height=height_m,
            weight=weight_kg,
            base_experience=base_pokemon.base_experience,
            stats=[PokemonStat(name=s.stat.name, base_stat=s.base_stat) for s in base_pokemon.stats],
            sprites=PokemonSprites.model_validate(sprites_data), # Validate mapped sprite data
            catch_rate=base_species.capture_rate,
            base_happiness=base_species.base_happiness,
            hatch_time=hatch_time_str,
            is_baby=base_species.is_baby,
            is_legendary=base_species.is_legendary,
            is_mythical=base_species.is_mythical,
            evolves_from=evolves_from_name,
            gender_ratio=gender_ratio_str,
            egg_groups=egg_group_names,
            habitat=base_species.habitat.name if base_species.habitat else None,
            shape=base_species.shape.name if base_species.shape else None,
            growth_rate=base_species.growth_rate.name if base_species.growth_rate else None,
            description=description,
            evolution_chain=evo_chain.chain.model_dump() if evo_chain else None # Pass processed chain data (or define backend model)
        )

        await set_backend_cache(cache_key, detail.model_dump())
        logger.info(f"Successfully fetched and combined details for '{identifier_str}'.")
        return detail

    except ResourceNotFoundError: logger.warning(f"Resource not found via library for '{identifier_str}'."); return None
    except (PokeAPIError, Exception) as e: logger.error(f"Error fetching/processing details via library for '{identifier_str}': {e}", exc_info=True); return None

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
        library_generations = await get_all_generations(client=client) # Use library list function
        if not library_generations: return []

        # Map to backend Generation model (adding count and roman numeral)
        all_pokemon = await get_pokedex_summary_data() # Get summary data for counts
        if all_pokemon is None: all_pokemon = [] # Handle error case

        backend_generations: List[Generation] = []
        for lib_gen in library_generations:
             count = sum(1 for p in all_pokemon if p.generation_id == lib_gen.id)
             backend_gen = Generation(
                  id=lib_gen.id,
                  name=lib_gen.name,
                  region_name=lib_gen.region_name,
                  #roman_numeral=_format_generation_id(lib_gen.id),
                  #count=count
             )
             backend_generations.append(backend_gen)

        await set_backend_cache(GENERATIONS_CACHE_KEY, [g.model_dump() for g in backend_generations])
        logger.info(f"Generations data cached in backend ({len(backend_generations)} entries).")
        return backend_generations

    except (PokeAPIError, Exception) as e: logger.error(f"Failed to get generations via library: {e}", exc_info=True); return None

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
        library_types = await get_all_types(client=client) # Use library list function
        if not library_types: return []

        # Map to backend PokemonTypeFilter model (just name needed)
        backend_types = [PokemonTypeFilter(name=t.name) for t in library_types]

        await set_backend_cache(TYPES_CACHE_KEY, [t.model_dump() for t in backend_types])
        logger.info(f"Types data cached in backend ({len(backend_types)} entries).")
        return backend_types

    except (PokeAPIError, Exception) as e: logger.error(f"Failed to get types via library: {e}", exc_info=True); return None

# Example Usage (for testing within this module)
async def main():
    # Fetch and print Pokedex summary data
    # summary_data = await get_pokedex_summary_data(force_refresh=True) # Force refresh for first run
    # if summary_data:
    #     print(f"Fetched {len(summary_data)} Pokemon summary items.")
    #     # print("First 3 Pokemon Summaries:\n", [s.model_dump_json(indent=2) for s in summary_data[:3]]) # Optional print
    # else:
    #     print("Failed to retrieve Pokedex summary data.")

    # Fetch and print detail for Given Pokemon
    test_pokemon_detail = await get_pokemon_detail_data("venusaur", force_refresh=True) # Force refresh for first run
    if test_pokemon_detail:
        print("\Pokemon Detail:\n", test_pokemon_detail.model_dump_json(indent=2))
    else:
        print("Failed to retrieve Pokemon detail data.")

    # # # Fetch and print generations data
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