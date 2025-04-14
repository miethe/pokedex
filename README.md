# Modern Pokedex Web Application (v2 - Refactored)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A dynamic Pokedex web application featuring a Python/FastAPI backend API that consumes a dedicated PokeAPI wrapper library (`pokeapi_wrapper_lib`), utilizes Redis caching, serves a separate HTML/CSS/JavaScript frontend via Nginx, and is orchestrated using Docker Compose (or Podman Compose).

This project displays detailed Pokémon information with advanced filtering and optimized performance.

**Note:** This project depends on the separate `pokeapi_wrapper_lib` library. See its repository for details on the library itself: [Link to your library repo if separate, otherwise reference local path]

## Table of Contents

-   [Features](#features)
-   [Architecture Overview](#architecture-overview)
-   [Technology Stack](#technology-stack)
-   [API Endpoints](#api-endpoints)
-   [Project Structure](#project-structure)
-   [Getting Started](#getting-started)
    -   [Prerequisites](#prerequisites)
    -   [Installation & Setup](#installation--setup)
-   [Running the Application](#running-the-application)
    -   [Development (Docker Compose w/ Override)](#development-docker-compose-w-override)
    -   [Production (Docker Compose)](#production-docker-compose)
-   [Cache Management](#cache-management)
-   [Contributing](#contributing)
-   [License](#license)
-   [Acknowledgements](#acknowledgements)

## Features

*   **Full Pokemon Listing:** Displays a filterable grid of all Pokémon up to the configured generation, including default sprites and status indicators (Legendary ★, Mythical ✧, Baby 🍼).
*   **Detailed View:** Modal popup showing comprehensive details for a selected Pokémon:
    *   Header with Name & National Pokédex ID.
    *   Generation & Region indicators.
    *   Interactive Sprite Gallery (Animated preferred, Official Artwork, Static fallback, Shiny, etc.) with hover titles and click-to-view main sprite update.
    *   Full-size Sprite Viewer (Lightbox) activated by clicking the main sprite, with navigation arrows and zoom toggle.
    *   Info cards for Types, Physical Attributes, Abilities, Base Stats (with colored bars), Breeding Info, Species Info, Classifications.
    *   Flavor Text Description.
    *   Clickable Evolution Chain.
*   **Advanced Filtering & UI:**
    *   Search by Name or National Pokédex ID.
    *   Filter by Generation using dedicated buttons (showing Region name & count).
    *   Filter by Type(s) using icons with hover text (AND logic).
    *   Filter by Status (Baby, Legendary, Mythical) using checkboxes (OR logic between statuses).
    *   Results counter displaying shown/total Pokémon based on filters.
    *   "Clear Filters" and "Reset Search" buttons.
    *   Scroll-to-top button.
*   **Performance Optimization:**
    *   Backend caching using **Redis** for aggregated list data and final Pokémon detail objects.
    *   **PokeAPI calls are handled by the `pokeapi_wrapper_lib`, which has its own caching layer.**
    *   Configurable (long) cache TTL. Manual refresh capability.
    *   Frontend lazy loading of list images.
*   **Error Handling:** User-friendly maintenance screen during cache refreshes, custom 404/50x error pages served by Nginx.
*   **Containerized & Environment-Specific:** Fully containerized with distinct configurations for Development (live reload, code mounting) and Production (optimized builds, PyPI dependency).

## Architecture Overview

This application uses a decoupled architecture enhanced by a dedicated data access library:

1.  **Frontend (HTML/CSS/JS):** UI layer served by Nginx. Interacts *only* with this project's Backend API.
2.  **Web Server / Reverse Proxy (Nginx):** Serves static frontend files, routes `/api/` requests to the Backend API, serves custom error pages.
3.  **Backend API (Python/FastAPI):**
    *   Provides the RESTful API (`/api/...`) consumed by the frontend.
    *   **Consumes `pokeapi_wrapper_lib`:** Calls the library to get structured Pokémon data.
    *   **Aggregates & Maps:** Combines data from library calls (e.g., base pokemon + species) and maps it to the specific `PokemonDetail`/`PokemonSummary` models required by the frontend.
    *   **Caches Final Objects:** Caches the fully processed `PokemonDetail` and `PokemonSummary` list in Redis for fast frontend responses.
    *   Handles application-level logic (e.g., maintenance state).
4.  **PokeAPI Wrapper Library (`pokeapi_wrapper_lib`):** (External Dependency)
    *   Handles all direct communication with the external `pokeapi.co`.
    *   Provides Python functions (`get_pokemon`, `get_species`, etc.) returning Pydantic models (`BasePokemon`, `BaseSpecies`).
    *   Contains its *own* Redis caching layer for raw/semi-processed PokeAPI responses.
    *   Handles sprite URL transformation (local vs. remote).
5.  **Cache (Redis):** Used by *both* the library (for PokeAPI responses) and the backend API (for final aggregated objects). Single Redis instance shared via Docker networking.
6.  **Container Orchestration (Docker Compose / Podman Compose):** Manages all containers (Backend, Frontend/Nginx, Redis).


## Technology Stack

*   **Backend:** Python 3.10+, FastAPI, Uvicorn, Pydantic, HTTPX (for client used with library), python-dotenv
*   **Frontend:** HTML5, CSS3, Vanilla JavaScript (ES6+)
*   **Data Access Library:** `pokeapi_wrapper_lib` (separate Python package)
*   **Caching:** Redis 7+
*   **Web Server / Proxy:** Nginx (stable-alpine)
*   **Containerization:** Docker / Podman, Docker Compose / Podman Compose

## API Endpoints

The backend API (`pokedex_project/backend`) provides the following endpoints (accessed via Nginx at `/api/...`):

| Method | Path                             | Description                                                                                                  | Query Params                 | Response Model              |
| :----- | :------------------------------- | :----------------------------------------------------------------------------------------------------------- | :--------------------------- | :-------------------------- |
| `GET`  | `/` (Backend Root)               | Basic health check / welcome message for the API itself.                                                     | -                            | JSON `{message: str, ...}`  |
| `GET`  | `/api/pokedex/summary`           | Get aggregated summary data (ID, Name, Gen, Types, Sprite URL, Status Flags) for all Pokémon.            | `force_refresh` (bool)       | `List[PokemonSummary]`      |
| `GET`  | `/api/pokemon/{id_or_name}`      | Get detailed data mapped for the frontend for a specific Pokémon by ID or name.                        | `force_refresh` (bool)       | `PokemonDetail`             |
| `GET`  | `/api/generations`               | Get a list of all Pokémon generations mapped for the frontend (incl. region, count, roman numeral).                             | `force_refresh` (bool)       | `List[Generation]`          |
| `GET`  | `/api/types`                     | Get a list of all Pokémon types mapped for the frontend filter.                                 | `force_refresh` (bool)       | `List[PokemonTypeFilter]`   |
| `POST` | `/api/admin/cache/refresh`       | **(Optional)** Manually trigger a refresh of this backend's cache keys (e.g., `pokedex_summary_data_v2`).            | `cache_key` (str, required)  | JSON `{message: str}`       |

*(See `backend/app/main.py` and `backend/app/models.py` for response models specific to this backend API.)*

## Project Structure

<pre>
pokedex_project/
├── backend/
│   ├── app/                         # Core FastAPI application consuming the library
│   │   ├── __init__.py
│   │   ├── clients.py               # Manages httpx client used for the library
│   │   ├── cache_utils.py           # (Optional) Wrapper for backend caching
│   │   ├── config.py                # Backend configuration (Redis URL, Sprite Mode)
│   │   ├── main.py                  # FastAPI app, endpoints, lifespan, middleware
│   │   ├── models.py                # Pydantic models for the frontend API response
│   │   └── pokedex_data.py          # Calls library, aggregates/maps data, caches results
│   ├── requirements.txt             # Production dependencies (incl. published library)
│   ├── requirements-dev.txt         # Dev dependencies (incl. local editable library)
│   └── .env                         # Gitignored
├── frontend/
│   ├── assets/                      # Static assets
│   │   ├── icons/color/             # Type icons
│   │   │   └── *.svg
│   │   ├── images/
│   │   │   └── logo.png             
│   │   └── sprites/                 # Cloned PokeAPI sprites repo (gitignored or handled separately)
│   ├── index.html                   
│   ├── style.css                    
│   ├── script.js                    # JavaScript logic for dynamic rendering
│   ├── 404.html                     
│   ├── 50x.html                     
│   └── nginx.conf                   
├── Dockerfile.backend              # Multi-stage Dockerfile for Backend service
├── Dockerfile.frontend            # Dockerfile for Nginx + Frontend service
├── docker-compose.yml             # Base Docker Compose file (prod-like)
├── docker-compose.override.yml    # Development overrides (volume mounts, dev commands)
├── docker-compose.prod.yml        # (Optional) Production-specific overrides
└── README.md                      
</pre>

### Assumed Sibling Directory (referenced in requirements-dev.txt and override.yml)
../pokeapi_wrapper_lib/

## Getting Started

### Prerequisites

*   **Docker** or **Podman:** For running the containerized application.
    *   Install Docker: [https://docs.docker.com/get-docker/](https://docs.docker.com/get-docker/)
    *   Install Podman (for Fedora/RHEL/CentOS): `sudo dnf install podman`
*   **Docker Compose** or **Podman Compose:** For orchestrating the containers.
    *   Docker Compose is usually included with Docker Desktop. Standalone install: [https://docs.docker.com/compose/install/](https://docs.docker.com/compose/install/)
    *   Install Podman Compose (for Fedora/RHEL/CentOS): `sudo dnf install podman-compose`
*   **Git:** For cloning the repository.
*   **(Optional Dev) Python 3.10+ and pip:** If you want to run the backend locally for development without Docker.
*   **(Optional Dev) Redis Client:** (`redis-cli`) for inspecting the cache directly.
*   **(Required for Dev)** Local clone of the `pokeapi_wrapper_lib` repository placed *sibling* to this `pokedex_project` directory.
*   **(Required for Local Sprites) Cloned Sprite Assets:** If you want to use a local copy of the Pokémon sprites, you must clone the repository into the `frontend/assets` (location is important!) directory. The repo is large (~1.5GB), so only recommended for production. You can also use the remote api instead:
    ```bash
    cd pokedex_project/frontend # Navigate to frontend directory
    mkdir -p assets
    git clone https://github.com/PokeAPI/sprites.git ./assets/sprites
    cd .. # Go back to project root
    ```

### Installation & Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/miethe/pokedex.git
    cd pokedex_project
    ```

2.  **Clone the Library Repo (for Dev):** Ensure `pokeapi_wrapper_lib` is cloned in the directory *above* `pokedex_project`.
    ```bash
    # Example if starting from parent directory
    git clone https://github.com/<your-username>/pokeapi_wrapper_lib.git
    ```

3.  **Clone Sprites Repo:** (See Prerequisites).

4.  **Configure Environment Variables:**
    *   Copy the example environment file (if one is provided) or create `backend/.env`.
    *   Ensure the `backend/.env` file contains at least:
        ```dotenv
        # backend/.env
        REDIS_URL=redis://redis:6379/0
        ```
        (This URL uses the service name `redis` defined in `docker-compose.yml` and the standard Redis port `6379`.)
    *   **Important:** Add `backend/.env` to your `.gitignore` file if it's not already there to avoid committing sensitive information.
    *   **(Optional) Configure Sprite Serving:** To serve sprites locally instead of using remote URLs (recommended for performance/production), add the following line to `backend/.env`:
        ```dotenv
        SPRITE_SOURCE_MODE=local
        ```
        (If omitted or set to `remote`, the application will use URLs from PokeAPI).

## Running the Application

### Development (Docker Compose w/ Override)

This uses `docker-compose.override.yml` for live reloading and local code mounting.

1.  **Navigate to `pokedex_project` root.**
2.  **Run:**
    *   `docker-compose up --build`
    *   `podman-compose up --build`
    *   (`-d` flag can be added to run detached).
3.  **Access:** `http://localhost:8080`. Backend API also accessible directly at `http://localhost:8001`.
4.  **Changes:** Python code changes in `backend` or the sibling `pokeapi_wrapper_lib` will trigger backend reload. Frontend file changes (HTML, CSS, JS, assets) are reflected on browser refresh.

### Production (Docker Compose)

This uses the `production` stage of the Dockerfile and expects the library dependency to be correctly specified for production in `backend/requirements.txt` (e.g., from PyPI or a Git tag).

1.  **Ensure `backend/requirements.txt` points to the stable library version.**
2.  **Navigate to `pokedex_project` root.**
3.  **Run:**
    *   `docker-compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d`
    *   `podman-compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d`
    *   (The `-f docker-compose.prod.yml` is optional if the base `docker-compose.yml` is sufficient and no extra prod overrides are needed).
4.  **Access:** `http://<your-server-ip>:8080`.

5.  **View Logs:**
    *   `docker-compose logs -f` / `podman-compose logs -f` (Follow logs for all services)
    *   `docker-compose logs <service_name>` / `podman-compose logs <service_name>` (e.g., `backend`, `frontend`, `redis`)

6.  **Stop the Application:**
    *   `docker-compose down` / `podman-compose down` (Stops and removes containers, network. Add `-v` to also remove named volumes like Redis data).

7.  **Updating a Single Service (e.g., after backend code changes):**
    *   `docker-compose up --build -d backend`
    *   `podman-compose up --build -d backend`

**Development Note:** The provided `docker-compose.yml` includes an optional volume mount for the `./frontend` directory. This allows you to make changes to HTML, CSS, JavaScript, or the locally cloned sprites in `frontend/assets/sprites` and see the changes reflected in your browser after a refresh, without needing to rebuild the `frontend` Docker image (`podman-compose up -d frontend`). For production builds, this volume mount should typically be removed, and the `COPY` instructions in `Dockerfile.frontend` will be used.

### Local Backend Development (Optional)

If you prefer to run the backend directly on your host machine for faster development iterations (without rebuilding the container each time):

1.  **Ensure Prerequisites:** Python 3.10+, pip, and a running Redis instance (either native or in Docker).
2.  **Navigate to the `backend` directory:**
    ```bash
    cd backend
    ```
3.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Linux/macOS
    # .\venv\Scripts\activate # Windows
    ```
4.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
5.  **Configure `.env`:** Ensure `backend/.env` points to your locally accessible Redis instance (e.g., `REDIS_URL=redis://localhost:6379/0`).
6.  **Run the FastAPI server:**
    ```bash
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    ```
    *   `--reload`: Enables auto-reloading on code changes.
7.  **Accessing:**
    *   The backend API will be available at `http://localhost:8000`.
    *   You would typically still run the Nginx frontend via Compose (`podman-compose up -d frontend redis`) and configure its `nginx.conf` to proxy `/api/` to `http://<your-host-ip>:8000` instead of `http://backend:8000`. Alternatively, use browser extensions to handle CORS if accessing the local backend directly from `index.html` opened as a file (not recommended).

## Cache Management

*   **Dual Caching:** The `pokeapi_wrapper_lib` caches raw/semi-processed data from PokeAPI. This application's backend caches the *final aggregated/mapped* objects (`PokemonSummary`, `PokemonDetail`) it generates before sending to the frontend. Both use the same Redis instance but different key prefixes.
*   **Cache Population:** The backend attempts to pre-populate the main Pokedex summary cache on startup if it's empty.
*   **Cache TTL:** Data is cached with a default TTL of 24 hours (configurable in `backend/app/config.py`). Configured via `CACHE_TTL_SECONDS` (default: 30 days).
*   **Manual Refresh:** The optional `/api/admin/cache/refresh` (POST) endpoint can be used to force-refresh specific cache keys (e.g., `pokedex_summary_data`, `pokemon_detail_pikachu`). Use tools like `curl` or Postman to send POST requests to this endpoint (see [API Endpoints](#api-endpoints)). This does *not* automatically clear the underlying library cache.
    1. `curl -X POST "http://<your-fedora-vm-ip>:8080/api/admin/cache/refresh?cache_key=pokedex_summary_data"`
    2. `curl -X POST "http://<your-fedora-vm-ip>:8080/api/admin/cache/refresh?cache_key=generations_data"`
    3. `curl -X POST "http://<your-fedora-vm-ip>:8080/api/admin/cache/refresh?cache_key=types_data"`
    4. `curl -X POST "http://<your-fedora-vm-ip>:8080/api/admin/cache/refresh?cache_key=pokemon_detail_bulbasaur`
    Or using ID `curl -X POST "http://localhost:8080/api/admin/cache/refresh?cache_key=pokemon_detail_1"`
*   **Clearing Redis:** You can connect to the Redis container (`docker exec -it pokedex_redis redis-cli` or `podman exec ...`) and use commands like `FLUSHDB` (clears current DB) or `DEL <key_name>` to manage the cache directly if needed.

## Contributing

Contributions are welcome! If you'd like to contribute, please follow these steps:

1.  **Fork the repository** on GitHub.
2.  **Clone your fork** locally (`git clone ...`).
3.  **Create a new branch** for your feature or bug fix (`git checkout -b feature/your-feature-name` or `bugfix/issue-description`).
4.  **Make your changes.** Ensure code follows project style guidelines (e.g., use a linter like Black/Flake8 for Python).
5.  **Test your changes** thoroughly. Add unit/integration tests if applicable.
6.  **Commit your changes** (`git commit -am 'Add some feature'`).
7.  **Push to your branch** (`git push origin feature/your-feature-name`).
8.  **Create a new Pull Request** on GitHub, detailing your changes. 

Please ensure your pull request adheres to the following guidelines:

*   Explain the problem and your solution.
*   Include screenshots or GIFs for UI changes if relevant.
*   Make sure all tests pass (if tests are set up).

## License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

## Acknowledgements

*   **PokeAPI (pokeapi.co):** For providing the incredible and free Pokémon data API that powers this application.
*   **FastAPI:** For the high-performance Python web framework.
*   **Redis:** For the efficient caching solution.
*   **Nginx:** For the reliable web server and reverse proxy.
*   **Docker/Podman:** For simplifying development and deployment through containerization.
