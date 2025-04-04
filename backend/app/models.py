# backend/app/models.py
import logging

from pydantic import BaseModel, Field, validator
from typing import List, Optional

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

class PokemonAbility(BaseModel):
    """Represents a Pokémon ability with minimal details for detail view."""
    name: str = Field(..., description="Name of the ability")
    url: str = Field(..., description="URL to ability details on PokeAPI") # Optional: could be used for future features

class PokemonStat(BaseModel):
    """Represents a base stat for a Pokémon."""
    name: str = Field(..., description="Name of the stat (e.g., 'hp', 'attack')")
    base_stat: int = Field(..., description="Base stat value")

class PokemonSprites(BaseModel):
    """Sprites for a Pokémon, including official artwork and game sprites."""
    front_default: Optional[str] = Field(None, description="Default front sprite")
    back_default: Optional[str] = Field(None, description="Default back sprite")
    front_shiny: Optional[str] = Field(None, description="Shiny front sprite")
    back_shiny: Optional[str] = Field(None, description="Shiny back sprite")
    official_artwork: Optional[str] = Field(None, description="URL for official artwork sprite")
    # Add other sprite fields as needed (e.g., for female, other games, etc.)

    @validator("official_artwork", pre=True, allow_reuse=True)
    def extract_official_artwork(cls, value):
        """Extract official artwork from nested sprite structure if present."""
        if isinstance(value, dict) and "other" in value and "official-artwork" in value["other"]:
            return value["other"]["official-artwork"].get("front_default")
        return value # Return original if not in expected nested structure

    @validator("*", pre=True, allow_reuse=True)
    def ensure_https_url(cls, value):
        """Ensure sprite URLs are HTTPS for security and browser compatibility."""
        if isinstance(value, str) and value.startswith("http://"):
            return value.replace("http://", "https://", 1) # Replace only the first occurrence
        return value


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
    evolution_chain_url: str = Field(..., description="URL to evolution chain data") # Extracted from species
    evolves_from_species: Optional[dict] = Field(..., description="The Pokémon species that evolves into this Pokemon_species") # Extracted from species
    flavor_text_entries: List[dict] = Field(..., description="List of flavor text entries (descriptions)") # From species
    gender_rate: int = Field(..., description="Gender rate (for breeding info)") # From species
    egg_groups: List[dict] = Field(..., description="List of egg groups") # From species
    habitat: Optional[str] = Field(None, description="Habitat name, if any") # From species
    is_baby: Optional[bool] = Field(False, description="Whether it's a baby Pokémon") # From species
    is_legendary: bool = Field(False, description="Whether it's a legendary Pokémon") # From species
    is_mythical: bool = Field(False, description="Whether it's a mythical Pokémon") # From species
    has_gender_differences: bool = Field(False, description="Whether Pokémon has visual gender differences") # From species
    shape: Optional[str] = Field(None, description="Pokémon shape name") # From species
    growth_rate_name: Optional[str] = Field(None, description="Growth rate name") # From species
    capture_rate: Optional[int] = Field(None, description="The base capture rate; up to 255") # From species
    base_happiness: Optional[int] = Field(None, description="The happiness when caught by a normal Pokéball; up to 255") # From species

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
             if lang_info.get("name") == "en": # Safe get for name
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
            if lang_info.get("name") == "en":
                filtered_entries.append(entry)
        return filtered_entries

    @validator("evolution_chain_url", pre=True, allow_reuse=True)
    def extract_evolution_chain_url(cls, value):
        """Extract evolution chain URL from species data."""
        # Handle cached value
        if isinstance(value, str):
            return value
        if isinstance(value, dict) and "evolution_chain" in value:
            return value["evolution_chain"].get("url")
        return None # Or raise ValueError, depending on how critical this is


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