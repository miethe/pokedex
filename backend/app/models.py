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
    front_default: Optional[str] = None
    back_default: Optional[str] = None
    front_shiny: Optional[str] = None
    back_shiny: Optional[str] = None
    front_female: Optional[str] = None
    back_female: Optional[str] = None
    front_shiny_female: Optional[str] = None
    back_shiny_female: Optional[str] = None
    official_artwork: Optional[str] = None # Naming matches library model output
    official_artwork_front: Optional[str] = None # Naming matches library model output
    animated_front_default: Optional[str] = None # Naming matches library model output
    animated_front_shiny: Optional[str] = None # Naming matches library model output

    # Animated Sprites 
    animated_back_default: Optional[str] = None
    animated_back_shiny: Optional[str] = None
    animated_front_female: Optional[str] = None # Just in case they add these later
    animated_back_female: Optional[str] = None
    animated_front_shiny_female: Optional[str] = None
    animated_back_shiny_female: Optional[str] = None

class PokemonDetail(BaseModel):
    id: int
    name: str
    genus: str # Needs to be extracted in pokedex_data.py now
    generation_id: int
    region_name: str # Added
    types: List[PokemonType] # Use simple backend type model
    abilities: List[PokemonAbility] # Use backend ability model (with is_hidden)
    height: int # Meters (calculated in pokedex_data.py)
    weight: int # Kilograms (calculated in pokedex_data.py)
    base_experience: Optional[int]
    stats: List[PokemonStat] # Use backend stat model
    sprites: PokemonSprites # Use updated backend sprite model
    # --- Data pulled/calculated from species ---
    catch_rate: Optional[int]
    base_happiness: Optional[int]
    hatch_time: str # Calculated steps string
    is_baby: bool
    is_legendary: bool
    is_mythical: bool
    evolves_from: Optional[str] # Just the name
    gender_ratio: str # Calculated string
    egg_groups: List[str] # Just list of names
    habitat: Optional[str] # Just the name
    shape: Optional[str] # Just the name
    growth_rate: Optional[str] # Just the name
    description: str # Combined/selected flavor text
    # --- Evolution Chain (structure might need its own backend model) ---
    evolution_chain: Optional[Any] = None # Placeholder - define structure later if needed
    
    #has_gender_differences: bool = Field(False, description="Whether Pokémon has visual gender differences") 
    #growth_rate_name: Optional[str] = Field(None, description="Growth rate name") 
    #capture_rate: Optional[int] = Field(None, alias='capture_rate', description="Base capture rate; up to 255")
    #hatch_counter: Optional[int] = Field(None, description="Cycles required to hatch, used for step calculation") 

    class Config:
        pass

class Generation(BaseModel):
    """Represents a Pokemon Generation for filter options."""
    id: int
    name: str # e.g., generation-i
    region_name: str
    #roman_numeral: str # e.g., I, V, IX
    #count: int # Added count

class PokemonTypeFilter(BaseModel):
    """Represents a Pokemon Type for filter options."""
    name: str

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