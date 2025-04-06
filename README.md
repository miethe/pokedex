# Modern Pokedex Web Application

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A dynamic Pokedex web application built from scratch, featuring a Python/FastAPI backend with Redis caching, consumed by a separate HTML/CSS/JavaScript frontend, and orchestrated using Docker Compose (or Podman Compose).

This project serves as a modern replacement for simpler static Pokedex implementations, offering better performance, scalability, and extensibility.

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
    -   [Using Docker Compose / Podman Compose (Recommended)](#using-docker-compose--podman-compose-recommended)
    -   [Local Backend Development (Optional)](#local-backend-development-optional)
-   [Cache Management](#cache-management)
-   [Contributing](#contributing)
-   [License](#license)
-   [Acknowledgements](#acknowledgements)

## Features

*   **Full Pokemon Listing:** Displays a filterable list of all Pokémon up to the configured generation.
*   **Detailed View:** Modal popup showing comprehensive details for a selected Pokémon:
    *   ID, Name, Genus, Types
    *   Interactive Sprite Gallery (Animated preferred, Static fallback, Shiny, Other variants with hover titles)
    *   Physical Attributes (Height, Weight, Shape, Habitat)
    *   Abilities (including Hidden)
    *   Base Stats with **colored percentage bars**
    *   Breeding Information (Gender Ratio, Egg Groups, Hatch Time)
    *   Species Information (Catch Rate, Base Happiness, Growth Rate, Base Exp)
    *   Classifications (Legendary, Mythical, Baby, Evolves From)
    *   Flavor Text Description
    *   Clickable Evolution Chain
*   **Advanced Filtering:**
    *   Search by Name or National Pokédex ID.
    *   Filter by Generation (Dropdown).
    *   Filter by Type(s) using checkboxes with AND logic.
    *   Filter by Status: Checkboxes for **Baby, Legendary, and Mythical** Pokémon (OR logic between statuses).
*   **Performance Optimization:**
    *   Backend caching using **Redis** for both the aggregated Pokémon summary list and individual Pokémon details to minimize external API calls to PokeAPI.
    *   Configurable cache TTL (default 24 hours).
    *   Efficient frontend rendering and lazy loading of list images.
*   **Containerized Deployment:** Fully containerized using **Docker/Podman** and orchestrated with **Docker Compose/Podman Compose** for easy setup and deployment.
*   **Clean Architecture:** Separation of concerns between the frontend (UI presentation), backend (business logic, data fetching/caching), and external API.
*   **API Documentation:** Backend includes automatic OpenAPI (Swagger UI) documentation at `/docs`.

## Architecture Overview

The application follows a decoupled architecture:

1.  **Frontend (HTML/CSS/JS):**
    *   Responsible for the user interface and user interaction.
    *   Served as static files by the Nginx container.
    *   Communicates *only* with the application's own Backend API (via Nginx proxy) to fetch data.
    *   Implements filtering logic based on data received from the backend summary endpoint.
    *   Renders the Pokémon list and detail modal.

2.  **Backend (Python/FastAPI):**
    *   Provides a RESTful API for the frontend.
    *   Aggregates and processes data fetched from the external `pokeapi.co`.
    *   Implements robust caching logic using **Redis** via `redis-py`.
    *   Uses `httpx` for asynchronous requests to the external PokeAPI.
    *   Handles data validation using Pydantic models.

3.  **Cache (Redis):**
    *   An in-memory data store used to cache responses from `pokeapi.co`.
    *   Significantly reduces latency and load on the external API.
    *   Runs in its own dedicated container.

4.  **Web Server / Reverse Proxy (Nginx):**
    *   Serves the static frontend files (HTML, CSS, JS).
    *   Acts as a reverse proxy, routing requests starting with `/api/` to the backend FastAPI container. This avoids CORS issues and provides a single entry point for the browser.
    *   Runs in its own container alongside the frontend files.

5.  **Container Orchestration (Docker Compose / Podman Compose):**
    *   Defines and manages the multi-container application (Backend, Frontend/Nginx, Redis).
    *   Sets up networking between containers.
    *   Manages volumes for persistent data (e.g., Redis data).
    
## Technology Stack

*   **Backend:** Python 3.10+, FastAPI, Uvicorn, Pydantic, HTTPX, Redis-py, python-dotenv
*   **Frontend:** HTML5, CSS3, Vanilla JavaScript (ES6+)
*   **Caching:** Redis 7+
*   **Web Server / Proxy:** Nginx (stable-alpine)
*   **Containerization:** Docker / Podman, Docker Compose / Podman Compose

## API Endpoints

The backend provides the following endpoints, accessible via the Nginx proxy (e.g., `http://localhost:8080/api/...` by default when running via Compose).

| Method | Path                             | Description                                                                    | Query Params                 | Response Model              |
| :----- | :------------------------------- | :----------------------------------------------------------------------------- | :--------------------------- | :-------------------------- |
| `GET`  | `/` (Backend Root)               | Basic health check / welcome message for the API itself.                       | -                            | JSON `{message: str, ...}`  |
| `GET`  | `/api/pokedex/summary`           | Get aggregated summary data (ID, Name, Gen, Types, Sprite, Status Flags) for all Pokémon.    | `force_refresh` (bool)       | `List[PokemonSummary]`      |
| `GET`  | `/api/pokemon/{id_or_name}`      | Get detailed data for a specific Pokémon by ID or name.                        | `force_refresh` (bool)       | `PokemonDetail`             |
| `GET`  | `/api/generations`               | Get a list of all Pokémon generations for filtering.                             | `force_refresh` (bool)       | `List[Generation]`          |
| `GET`  | `/api/types`                     | Get a list of all Pokémon types for filtering.                                 | `force_refresh` (bool)       | `List[PokemonTypeFilter]`   |
| `POST` | `/api/admin/cache/refresh`       | **(Optional)** Manually trigger a cache refresh for a specific key.            | `cache_key` (str, required)  | JSON `{message: str}`       |

*(See `backend/app/main.py` and `backend/app/models.py` for detailed response models and validation.)*

Backend API documentation (Swagger UI) is automatically available at `/docs` relative to the backend service URL (e.g., `http://localhost:8000/docs` if backend port 8000 is exposed directly, or via the Nginx proxy if configured).

## Project Structure
pokedex_project/
├── backend/
│ ├── app/ # Core FastAPI application
│ │ ├── init.py
│ │ ├── cache.py # Redis caching logic
│ │ ├── config.py # Configuration management (Pydantic Settings)
│ │ ├── main.py # FastAPI app instance and API endpoints
│ │ ├── models.py # Pydantic data models
│ │ ├── pokedex_data.py # Data fetching, aggregation, processing logic
│ │ └── pokeapi_client.py # HTTPX client for external PokeAPI calls
│ ├── requirements.txt # Python dependencies
│ └── .env # Environment variables (e.g., REDIS_URL) - Gitignored
├── frontend/
│ ├── index.html # Main HTML file
│ ├── style.css # CSS styles
│ ├── script.js # JavaScript logic
│ └── nginx.conf # Custom Nginx configuration
├── Dockerfile.backend # Dockerfile for the Backend service
├── Dockerfile.frontend # Dockerfile for the Nginx + Frontend service
├── docker-compose.yml # Docker Compose / Podman Compose file
└── README.md # This file


## Getting Started

### Prerequisites

*   **Docker** or **Podman:** For running the containerized application.
    *   Install Docker: [https://docs.docker.com/get-docker/](https://docs.docker.com/get-docker/)
    *   Install Podman (for Fedora/RHEL/CentOS): `sudo dnf install podman`
*   **Docker Compose** or **Podman Compose:** For orchestrating the containers.
    *   Docker Compose is usually included with Docker Desktop. Standalone install: [https://docs.docker.com/compose/install/](https://docs.docker.com/compose/install/)
    *   Install Podman Compose (for Fedora/RHEL/CentOS): `sudo dnf install podman-compose`
*   **Git:** For cloning the repository.
*   **(Optional) Python 3.10+ and pip:** If you want to run the backend locally for development without Docker.
*   **(Optional) Redis Client:** (`redis-cli`) for inspecting the cache directly.

### Installation & Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/miethe/pokedex.git
    cd <your-repo-name>
    ```

2.  **Configure Environment Variables:**
    *   Copy the example environment file (if one is provided) or create `backend/.env`.
    *   Ensure the `backend/.env` file contains at least:
        ```dotenv
        # backend/.env
        REDIS_URL=redis://redis:6379/0
        ```
        (This URL uses the service name `redis` defined in `docker-compose.yml` and the standard Redis port `6379`.)
    *   **Important:** Add `backend/.env` to your `.gitignore` file if it's not already there to avoid committing sensitive information.

## Running the Application

### Using Docker Compose / Podman Compose (Recommended)

This is the easiest way to run the entire application stack (frontend, backend, Redis).

1.  **Navigate to the project root directory** (where `docker-compose.yml` is located).

2.  **Build and start the services:**
    *   Using Docker Compose:
        ```bash
        docker-compose up --build -d
        ```
    *   Using Podman Compose:
        ```bash
        podman-compose up --build -d
        ```
    *   `--build`: Forces rebuilding images if Dockerfiles or code have changed.
    *   `-d`: Runs containers in detached mode (background).

3.  **Access the Application:** Open your web browser and navigate to `http://localhost:8080` (or `http://<your-vm-ip>:8080` if running on a VM).

4.  **View Logs:**
    *   `docker-compose logs -f` / `podman-compose logs -f` (Follow logs for all services)
    *   `docker-compose logs <service_name>` / `podman-compose logs <service_name>` (e.g., `backend`, `frontend`, `redis`)

5.  **Stop the Application:**
    *   `docker-compose down` / `podman-compose down` (Stops and removes containers, network. Add `-v` to also remove named volumes like Redis data).

6.  **Updating a Single Service (e.g., after backend code changes):**
    *   `docker-compose up --build -d backend`
    *   `podman-compose up --build -d backend`

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

*   **Cache Population:** The backend attempts to pre-populate the main Pokedex summary cache on startup if it's empty.
*   **Cache TTL:** Data is cached with a default TTL of 24 hours (configurable in `backend/app/config.py`).
*   **Manual Refresh:** The optional `/api/admin/cache/refresh` (POST) endpoint can be used to force-refresh specific cache keys (e.g., `pokedex_summary_data`, `pokemon_detail_pikachu`). Use tools like `curl` or Postman to send POST requests to this endpoint (see [API Endpoints](#api-endpoints)).
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
