# backend/tests/test_main_endpoints.py

import pytest
from httpx import AsyncClient
import respx # Import respx if mocking HTTP calls

# Import your FastAPI app instance
# Make sure tests can import from the app package
# Requires backend/ to be in PYTHONPATH or running pytest from backend/ parent
from app.main import app
# Import library exceptions if needed for mocking
from pokeapi_lib import ResourceNotFoundError


# Use pytest-asyncio decorator for async tests
@pytest.mark.asyncio
async def test_read_root():
    """Test the root endpoint '/'."""
    # Use AsyncClient to make requests to the app
    # base_url is important for relative paths
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 200
    json_response = response.json()
    assert json_response["message"] == "Welcome to the Pokedex API!"
    assert "documentation" in json_response
    # Check status based on how lifespan runs in tests (might need adjustment/mocking)
    assert "redis_status" in json_response


# Example testing the detail endpoint (requires mocking external API)
@pytest.mark.asyncio
@respx.mock # Activate respx mocking for this test
async def test_get_pokemon_detail_found():
    """Test GET /api/pokemon/{id} when found."""

    # --- Mock the external API calls made by pokeapi_lib ---
    # 1. Mock the call to /pokemon/pikachu
    respx.get("https://pokeapi.co/api/v2/pokemon/pikachu").mock(
        return_value=httpx.Response(
            200,
            json={ # Simplified mock data matching BasePokemon structure needs
                "id": 25, "name": "pikachu", "height": 4, "weight": 60,
                "base_experience": 112, "order": 35, "is_default": True,
                "location_area_encounters": "/api/v2/pokemon/25/encounters",
                "types": [{"slot": 1, "type": {"name": "electric", "url": "..."}}],
                "abilities": [{"slot": 1, "is_hidden": False, "ability": {"name": "static", "url": "..."}}],
                "stats": [{"stat": {"name": "hp", "url": "..."}, "base_stat": 35, "effort": 0}],
                "sprites": {"front_default": "url_ignored_by_lib_model_anyway", "other": {"official-artwork": {"front_default":"..."}}}, # Provide structure lib model expects
                "species": {"name": "pikachu", "url": "https://pokeapi.co/api/v2/pokemon-species/25/"}
            }
        )
    )
    # 2. Mock the call to /pokemon-species/25 (triggered by pokedex_data)
    respx.get("https://pokeapi.co/api/v2/pokemon-species/25/").mock(
         return_value=httpx.Response(
             200,
             json={ # Simplified mock data matching BaseSpecies needs
                 "id": 25, "name": "pikachu", "order": 21, "gender_rate": 1,
                 "capture_rate": 190, "base_happiness": 70, "is_baby": False,
                 "is_legendary": False, "is_mythical": False, "hatch_counter": 10,
                 "generation": {"name": "generation-i", "url": "..."},
                 "evolves_from_species": {"name": "pichu", "url": "..."},
                 "evolution_chain": {"url": "https://pokeapi.co/api/v2/evolution-chain/10/"},
                 "egg_groups": [{"name": "ground", "url":"..."},{"name": "fairy", "url":"..."}],
                 "flavor_text_entries": [{"flavor_text": "Mouse Pokemon.", "language": {"name": "en"}, "version": {"name": "red"}}],
                 "genera": [{"genus": "Mouse Pokémon", "language": {"name": "en"}}],
                 "habitat": {"name": "forest"}, "shape": {"name": "quadruped"},
                 "growth_rate": {"name": "medium"}
             }
         )
     )
     # 3. Mock other calls if needed (evolution chain, generation details)
    # ------------------------------------------------------------

    async with AsyncClient(app=app, base_url="http://test") as client:
        # Make request to YOUR API endpoint
        response = await client.get("/api/pokemon/pikachu")

    assert response.status_code == 200
    json_response = response.json()
    assert json_response["name"] == "pikachu"
    assert json_response["id"] == 25
    assert json_response["genus"] == "Mouse Pokémon" # Check mapped data
    assert json_response["region_name"] # Should be populated if gen mocked

# Example testing the detail endpoint for Not Found
@pytest.mark.asyncio
@respx.mock
async def test_get_pokemon_detail_not_found():
    """Test GET /api/pokemon/{id} when NOT found."""
    # Mock the external calls to return 404
    respx.get("https://pokeapi.co/api/v2/pokemon/notapokemon").mock(return_value=httpx.Response(404))
    # No need to mock species if pokemon fails first

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/pokemon/notapokemon")

    assert response.status_code == 404 # Check your API returns 404 correctly
    assert "not found" in response.json()["detail"].lower()