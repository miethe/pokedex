# backend/app/models.py
import logging

from pydantic import BaseModel, Field, validator, root_validator
from typing import List, Optional, Any

from .config import settings, POKEAPI_SPRITE_BASE_URL, LOCAL_SPRITE_BASE_PATH # Import settings & constants

logger = logging.getLogger(__name__)

class PokemonType(BaseModel):
    """Represents a Pokémon type."""
    name: str = Field(..., description="Name of the type")

class PokemonSummary(BaseModel):
    """Summary data for a Pokémon, for list views and filtering."""
    id: int = Field(..., description="Pokémon ID")
    name: str = Field(..., description="Pokémon name")
    generation_id: int = Field(..., description="Generation ID")
    types: List[PokemonType] = Field(..., description="List of Pokémon types")
    sprite_url: Optional[str] = Field(None, description="Default front sprite URL (HTTPS)")
    # --- NEW FLAGS ---
    is_legendary: bool = Field(False, description="Is this a Legendary Pokémon?")
    is_mythical: bool = Field(False, description="Is this a Mythical Pokémon?")
    is_baby: bool = Field(False, description="Is this a Baby Pokémon?")

class PokemonAbility(BaseModel):
    """Represents a Pokémon ability with minimal details for detail view."""
    name: str = Field(..., description="Name of the ability")
    url: str = Field(..., description="URL to ability details on PokeAPI") # Optional: could be used for future features
    is_hidden: bool = Field(False, description="Is this a hidden ability")

class PokemonStat(BaseModel):
    """Represents a base stat for a Pokémon."""
    name: str = Field(..., description="Name of the stat (e.g., 'hp', 'attack')")
    base_stat: int = Field(..., description="Base stat value")

class PokemonSprites(BaseModel):
    """Sprites for a Pokémon, including official artwork and game sprites."""
    # Existing static sprites
    front_default: Optional[str] = None
    back_default: Optional[str] = None
    front_shiny: Optional[str] = None
    back_shiny: Optional[str] = None
    front_female: Optional[str] = None # Add female variants
    back_female: Optional[str] = None
    front_shiny_female: Optional[str] = None
    back_shiny_female: Optional[str] = None

    # Official Artwork (extracted via validator)
    official_artwork: Optional[str] = Field(None, description="URL for official artwork sprite")

    # Animated Sprites (will be populated by root_validator)
    animated_front_default: Optional[str] = None
    animated_back_default: Optional[str] = None
    animated_front_shiny: Optional[str] = None
    animated_back_shiny: Optional[str] = None
    animated_front_female: Optional[str] = None # Just in case they add these later
    animated_back_female: Optional[str] = None
    animated_front_shiny_female: Optional[str] = None
    animated_back_shiny_female: Optional[str] = None

    @root_validator(pre=True)
    def extract_nested_sprites(cls, values: dict):
        """
        Extracts deeply nested sprites (official artwork, animated)
        and adds them to the top level for easier field assignment.
        Runs before individual field validation.
        """
        if not isinstance(values, dict): # Handle case where input isn't a dict
            return values

        # Extract Official Artwork
        official_artwork_url = values.get('other', {}).get('official-artwork', {}).get('front_default')
        if official_artwork_url:
            values['official_artwork'] = official_artwork_url # Add to dict for field assignment

        # Extract Animated Sprites (Gen V Black/White)
        try:
            animated_sprites = values.get('versions', {}).get('generation-v', {}).get('black-white', {}).get('animated', {})
            if animated_sprites: # Check if animated dict exists and is not None
                 values['animated_front_default'] = animated_sprites.get('front_default')
                 values['animated_back_default'] = animated_sprites.get('back_default')
                 values['animated_front_shiny'] = animated_sprites.get('front_shiny')
                 values['animated_back_shiny'] = animated_sprites.get('back_shiny')
                 values['animated_front_female'] = animated_sprites.get('front_female') # Get if exists
                 values['animated_back_female'] = animated_sprites.get('back_female')
                 values['animated_front_shiny_female'] = animated_sprites.get('front_shiny_female')
                 values['animated_back_shiny_female'] = animated_sprites.get('back_shiny_female')
        except Exception as e:
            # Log potential errors during complex extraction, but don't fail validation
            logger.warning(f"Could not extract animated sprites: {e}", exc_info=False) # Set exc_info=False to avoid clutter

        return values

    @validator("*", pre=True, allow_reuse=True)
    def ensure_https_url(cls, value):
        """Ensure sprite URLs are HTTPS for security and browser compatibility."""
        if isinstance(value, str) and value.startswith("http://"):
            return value.replace("http://", "https://", 1) # Replace only the first occurrence
        return value
    
    # --- Post-validation Root Validator for URL Transformation ---
    @root_validator(skip_on_failure=True) # Use default post=True, skip if pre-validators fail
    def transform_urls_if_local(cls, values: dict):
        if settings.sprite_source_mode == 'local':
            logger.debug(f"Transforming sprite URLs to local paths. Base: {LOCAL_SPRITE_BASE_PATH}")
            for key, url in values.items():
                if isinstance(url, str) and url.startswith(POKEAPI_SPRITE_BASE_URL):
                    # Replace base URL with local path base
                    # Example: https://.../master/sprites/pokemon/1.png -> /assets/sprites/sprites/pokemon/1.png
                    relative_path = url.removeprefix(POKEAPI_SPRITE_BASE_URL)
                    values[key] = f"{LOCAL_SPRITE_BASE_PATH}{relative_path}"
                elif isinstance(url, str) and not url.startswith(('/', 'http')):
                     # Handle cases where a relative path might already exist unexpectedly? Optional.
                     logger.warning(f"Sprite URL '{url}' for key '{key}' is not absolute. Skipping transformation.")
        # Else (mode is remote), return values unchanged
        return values
    
    class Config:
         # Add configuration if needed, e.g., validate_assignment=True if modifying fields directly
         pass # Keep empty or add as needed

class PokemonDetail(BaseModel):
    """Detailed data for a single Pokémon."""
    id: int = Field(..., description="Pokémon ID")
    name: str = Field(..., description="Pokémon name")
    genus: str = Field(..., description="Species genus (e.g., Seed Pokémon)")
    generation_id: int = Field(..., description="Generation ID")
    types: List[PokemonType] = Field(..., description="List of Pokémon types")
    abilities: List[PokemonAbility] = Field(..., description="List of abilities")
    height: int = Field(..., description="Height in decimeters")
    weight: int = Field(..., description="Weight in hectograms")
    base_experience: int = Field(..., description="Base experience points")
    stats: List[PokemonStat] = Field(..., description="List of base stats")
    sprites: PokemonSprites = Field(..., description="Pokémon sprites")
    species_url: str = Field(..., description="URL to species data for more info (description, evolution chain)")
    
    # Fields from Species data
    evolution_chain_url: Optional[str] = Field(..., description="URL to evolution chain data")
    evolves_from_species: Optional[dict] = Field(None, description="The Pokémon species that evolves into this Pokemon_species")
    flavor_text_entries: List[dict] = Field(..., description="List of flavor text entries (descriptions)") 
    gender_rate: int = Field(..., description="Gender rate (for breeding info)") # -1 genderless, 0 male only, 8 female only, 1-7 ratio
    egg_groups: List[dict] = Field(..., description="List of egg groups") 
    habitat: Optional[str] = Field(None, description="Habitat name, if any") 
    is_baby: Optional[bool] = Field(False, description="Whether it's a baby Pokémon") 
    is_legendary: bool = Field(False, description="Whether it's a legendary Pokémon") 
    is_mythical: bool = Field(False, description="Whether it's a mythical Pokémon") 
    has_gender_differences: bool = Field(False, description="Whether Pokémon has visual gender differences") 
    shape: Optional[str] = Field(None, description="Pokémon shape name") 
    growth_rate_name: Optional[str] = Field(None, description="Growth rate name") 
    capture_rate: Optional[int] = Field(None, alias='capture_rate', description="Base capture rate; up to 255")
    base_happiness: Optional[int] = Field(None, description="The happiness when caught by a normal Pokéball; up to 255") 
    hatch_counter: Optional[int] = Field(None, description="Cycles required to hatch, used for step calculation") 

    @validator("genus", pre=True, allow_reuse=True)
    def extract_genus(cls, value):
        """Extract genus from species flavor text entries."""
        # Handle cached value
        if isinstance(value, str):
            return value
        if not isinstance(value, list):
             # Log or handle the unexpected type. Return a default.
             logger.warning(f"Unexpected type for genus validator input: {type(value)}. Expected list.")
             return "Unknown Genus" # Or None if genus is Optional

        for entry in value: # Now 'entry' should be a dictionary
             if not isinstance(entry, dict):
                 logger.warning(f"Unexpected item type in genus list: {type(entry)}. Expected dict.")
                 continue # Skip non-dict items

             lang_info = entry.get("language", {}) # Safe get for language dict
             if lang_info and lang_info.get("name") == "en": # Safe get for name
                 return entry.get("genus", "Unknown Genus") # Default if genus key missing
        return "Unknown Genus" # Fallback if no English genus found
    
    @validator("flavor_text_entries", pre=True, allow_reuse=True)
    def filter_english_flavor_text(cls, value):
        """Filter flavor text entries to keep only English versions."""
        if not isinstance(value, list):
             logger.warning(f"Unexpected type for flavor_text_entries validator: {type(value)}. Expected list.")
             return [] # Return empty list if input is not a list
        
        filtered_entries = []
        for entry in value:
            if not isinstance(entry, dict):
                logger.warning(f"Unexpected item type in flavor_text_entries list: {type(entry)}. Expected dict.")
                continue 
            
            lang_info = entry.get("language", {})
            if lang_info and lang_info.get("name") == "en": # Check lang_info exists
                filtered_entries.append(entry)
        return filtered_entries

    @validator("evolution_chain_url", pre=True, allow_reuse=True)
    def extract_evolution_chain_url(cls, value):
        """Extract evolution chain URL from species data."""
        # Handle cached value
        if isinstance(value, str):
            return value
        if isinstance(value, dict) and "evolution_chain" in value:
             evo_chain_info = value["evolution_chain"]
             # Ensure it's a dict and has 'url' before returning
             return evo_chain_info.get("url") if isinstance(evo_chain_info, dict) else None
        return None # Or raise ValueError, depending on how critical this is

    @validator("growth_rate_name", pre=True, allow_reuse=True)
    def extract_growth_rate_name(cls, value):
        """Extract growth rate name from nested structure if needed"""
        # Passed from pokedex_data directly now, but validator could handle nesting:
        # if isinstance(value, dict) and "growth_rate" in value:
        #     return value.get("growth_rate", {}).get("name")
        # return value # Assuming already extracted name is passed
        # Safest: Expect the extracted name string or None
        return value if isinstance(value, str) else None
    
    class Config:
        populate_by_name = True # Important: Allows using 'alias' and field names

class Generation(BaseModel):
    """Represents a Pokemon Generation for filter options."""
    id: int = Field(..., description="Generation ID (1-9)")
    name: str = Field(..., description="Generation Name (e.g., generation-i)")

class PokemonTypeFilter(BaseModel):
    """Represents a Pokemon Type for filter options."""
    name: str = Field(..., description="Type Name (e.g., fire)")

# Example usage (for testing models):
if __name__ == "__main__":
    # Example PokemonSummary data
    summary_data = {
        "id": 25,
        "name": "pikachu",
        "generation_id": 1,
        "types": [{"name": "electric"}]
    }
    pokemon_summary = PokemonSummary(**summary_data)
    print("Pokemon Summary:", pokemon_summary.model_dump_json(indent=2))

    # Example PokemonDetail data (minimal, you'd populate from PokeAPI response)
    detail_data = {
        "id": 1,
        "name": "bulbasaur",
        "genus": [{"genus": "Seed Pokémon", "language": {"name": "en"}}],
        "generation_id": 1,
        "types": [{"name": "grass"}, {"name": "poison"}],
        "abilities": [{"name": "overgrow", "url": "url/overgrow"}],
        "height": 7,
        "weight": 69,
        "base_experience": 64,
        "stats": [{"name": "hp", "base_stat": 45}],
        "sprites": {
            "front_default": "sprite_url",
            "other": {"official-artwork": {"front_default": "artwork_url"}}
        },
        "species_url": "species_url",
        "evolution_chain_url": {"url": "evolution_chain_url"}, # Nested structure to test validator
        "flavor_text_entries": [
            {"flavor_text": "A strange seed...", "language": {"name": "en"}},
            {"flavor_text": "Un étrange graine...", "language": {"name": "fr"}}
        ],
        "gender_rate": 1,
        "egg_groups": [{"name": "monster"}],
        "habitat": "grassland",
        "is_legendary": False,
        "is_mythical": False,
        "shape": "quadruped",
        "growth_rate_name": "medium-slow"
    }
    pokemon_detail = PokemonDetail(**detail_data)
    print("\nPokemon Detail:", pokemon_detail.model_dump_json(indent=2))