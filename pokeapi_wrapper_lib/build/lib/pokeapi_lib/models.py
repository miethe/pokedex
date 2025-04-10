# pokeapi_lib/models.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# Example simple models returned by the library's core functions
# These focus on providing structured data, not necessarily every single raw field

class TypeInfo(BaseModel):
    """Represents basic info about a Pokemon Type."""
    name: str
    url: str

class PokemonTypeSlot(BaseModel):
    slot: int
    type: TypeInfo

class AbilityInfo(BaseModel):
    name: str
    url: str

class PokemonAbilitySlot(BaseModel):
    slot: int
    is_hidden: bool
    ability: AbilityInfo

class StatInfo(BaseModel):
    name: str
    url: str

class PokemonStatData(BaseModel):
    stat: StatInfo
    base_stat: int
    effort: int

class SpriteData(BaseModel):
     """A simplified sprite model, library user can access specific URLs."""
     front_default: Optional[str] = None
     front_shiny: Optional[str] = None
     # Add others as needed by library users, keep it focused
     official_artwork_front: Optional[str] = None # Example simplified name

class BasePokemon(BaseModel):
    """Core Pokemon data returned by the library."""
    id: int
    name: str
    height: int
    weight: int
    base_experience: Optional[int] = None
    order: int
    is_default: bool
    location_area_encounters: str # URL
    types: List[PokemonTypeSlot]
    abilities: List[PokemonAbilitySlot]
    stats: List[PokemonStatData]
    sprites: SpriteData # Use the simplified sprite model
    # Store the raw dictionary provided by the API for species
    species: Dict[str, str] = Field(..., description="Dict containing 'name' and 'url' for the species")
    # We will extract the URL later when needed, or access via pokemon.species['url']
    #species_url: str = Field(..., alias='species', validation_alias='species.url') # Example extracting URL

    class Config:
        populate_by_name = True

class BaseSpecies(BaseModel):
     """Core Species data returned by the library."""
     id: int
     name: str
     order: int
     gender_rate: int
     capture_rate: int
     base_happiness: Optional[int] = None
     is_baby: bool
     is_legendary: bool
     is_mythical: bool
     hatch_counter: Optional[int] = None
     generation: str = Field(..., validation_alias='generation.name') # Example: Extract nested name
     evolves_from_species: Optional[Dict[str, Any]] = None # Keep simple for now
     evolution_chain_url: str = Field(..., validation_alias='evolution_chain.url')
     # Add more fields as needed (egg_groups, flavor_text, genera, habitat, shape, etc.)

     class Config:
         populate_by_name = True

# Add models for Generation, Type, EvolutionChain etc. as needed by core functions
class GenerationInfo(BaseModel):
    """Represents basic info about a Pokemon Generation."""
    id: int
    name: str # e.g., generation-i
    region_name: str # e.g., kanto