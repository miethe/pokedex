// frontend/script.js

document.addEventListener('DOMContentLoaded', () => {
    // --- Configuration & State ---
    const API_BASE_URL = '/api'; // Relative URL, Nginx will proxy
    let allPokemonData = [];
    let generationsData = [];
    let typesData = [];
    let currentDetailPokemon = null; // Keep track of which detail is shown
    let totalPokemonFetched = 0;
    let selectedGenerationId = ""; // Default to "" for "All"

    // --- Sprite Viewer State ---
    let currentGallerySprites = []; // Holds {url, type} for the current Pokemon's gallery
    let currentFullSpriteIndex = 0;
    let isSpriteZoomed = false; // Track zoom state

    // --- DOM Element References ---
    const searchInput = document.getElementById('search-input');
    const generationButtonsContainer = document.getElementById('generation-buttons');
    const typeFilterContainer = document.getElementById('type-checkboxes-container');
    const typeFilterFieldset = document.getElementById('type-filter');
    const statusFilterContainer = document.getElementById('status-checkboxes-container');
    const statusFilterFieldset = document.getElementById('status-filter');
    const pokedexListContainer = document.getElementById('pokedex-list');
    const loadingIndicator = document.getElementById('loading-indicator');
    const resultsCounter = document.getElementById('results-counter');
    const counterText = document.getElementById('counter-text');
    const clearFiltersButton = document.getElementById('clear-filters-button');
    const resetSearchButton = document.getElementById('reset-search-button');
    const scrollToTopButton = document.getElementById('scroll-to-top');

    const errorDisplay = document.getElementById('error-display');
    const errorMessageElement = document.getElementById('error-message');

    // Modal specific elements
    const modal = document.getElementById('pokemon-detail-modal');
    const modalContent = document.getElementById('pokemon-detail-content'); // Content area inside modal

    // --- Sprite Viewer References ---
    const spriteViewerOverlay = document.getElementById('sprite-viewer-overlay');
    const fullSpriteImage = document.getElementById('full-sprite-image');
    const spriteViewerCaption = document.getElementById('sprite-viewer-caption');
    const spriteViewerCloseBtn = document.getElementById('sprite-viewer-close');
    const spriteViewerPrevBtn = document.getElementById('sprite-viewer-prev');
    const spriteViewerNextBtn = document.getElementById('sprite-viewer-next');
    const spriteViewerZoomBtn = document.getElementById('sprite-viewer-zoom');

    const detailLoadingIndicator = document.getElementById('detail-loading-indicator');
    const closeModalButton = modal.querySelector('.close-button');

    // --- Maintenance References ---
    const maintenanceOverlay = document.getElementById('maintenance-overlay');
    const maintenanceMessageElement = document.getElementById('maintenance-message');


    // --- SVG Icons ---
    const zoomInIconSVG = `
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="24" height="24">
            <path d="M10 18a7.952 7.952 0 0 0 4.897-1.688l4.396 4.396 1.414-1.414-4.396-4.396A7.952 7.952 0 0 0 18 10c0-4.411-3.589-8-8-8s-8 3.589-8 8 3.589 8 8 8zm0-14c3.309 0 6 2.691 6 6s-2.691 6-6 6-6-2.691-6-6 2.691-6 6-6z"/>
            <path d="M11 9H9v2H7v-2H5v-2h2V5h2v2h2v2z"/>
        </svg>`;
    const zoomOutIconSVG = `
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="24" height="24">
             <path d="M10 18a7.952 7.952 0 0 0 4.897-1.688l4.396 4.396 1.414-1.414-4.396-4.396A7.952 7.952 0 0 0 18 10c0-4.411-3.589-8-8-8s-8 3.589-8 8 3.589 8 8 8zm0-14c3.309 0 6 2.691 6 6s-2.691 6-6 6-6-2.691-6-6 2.691-6 6-6z"/>
            <path d="M5 9h10v2H5z"/>
        </svg>`;

    // --- Initialization ---
    async function initializeApp() {
        console.log("Initializing Pokedex App...");
        showListLoading(true);
        resultsCounter.style.display = 'none'; // Hide counter initially
        errorDisplay.style.display = 'none'; // Hide error display initially, show loading
        pokedexListContainer.style.display = 'grid'; // Ensure list grid is visible by default layout

        try {
            // Use Promise.allSettled to handle potential maintenance state from one fetch
            const results = await Promise.allSettled([
                 fetchData(`${API_BASE_URL}/pokedex/summary`),
                 fetchData(`${API_BASE_URL}/generations`),
                 fetchData(`${API_BASE_URL}/types`)
             ]);

             if (!results) {
                 throw new Error("Failed to fetch initial data from the backend API.");
             }

             const summaryResult = results[0];
             const generationsResult = results[1];
             const typesResult = results[2];

             // Check if ANY call returned the maintenance signal
             if (results.some(r => r.status === 'fulfilled' && r.value?.maintenance)) {
                  console.log("Initialization halted due to maintenance state.");
                  // Maintenance overlay is already shown by fetchData
                  return; // Stop initialization
             }

            if (!summaryResult || !generationsResult || !typesResult) {
                throw new Error("Failed to fetch initial data from the backend API.");
            }

            // Check for actual fetch errors after filtering out maintenance
            if (summaryResult.status === 'rejected' || !summaryResult.value) {
                 throw summaryResult.reason || new Error("Failed to fetch Pokémon summary.");
            }
             if (generationsResult.status === 'rejected' || !generationsResult.value) {
                 throw generationsResult.reason || new Error("Failed to fetch generations.");
            }
             if (typesResult.status === 'rejected' || !typesResult.value) {
                 throw typesResult.reason || new Error("Failed to fetch types.");
            }

            // If all successful and not maintenance:
            allPokemonData = summaryResult.value;
            totalPokemonFetched = allPokemonData.length;
            generationsData = generationsResult.value.sort((a, b) => a.id - b.id);
            typesData = typesResult.value.sort((a, b) => a.name.localeCompare(b.name));

            console.log(`Fetched ${totalPokemonFetched} Pokémon summaries.`);

            // --- Now populate filters ---
            populateGenerationButtons(generationsData);
            populateTypesFilter(typesData);

            // --- Now render pokemon ---
            renderPokemonList(allPokemonData);
            updateResultsCounter(allPokemonData.length); // Initial counter update
            resultsCounter.style.display = 'flex'; // Show counter after initial load
            setupEventListeners();

        } catch (error) {
            console.error("Initialization failed:", error);
            // Avoid showing generic error if maintenance overlay is already up
            if (maintenanceOverlay.style.display !== 'flex') {
                //pokedexListContainer.innerHTML = `<p class="error">Could not load Pokedex data. Please try refreshing the page. (${error.message})</p>`;
                showInitializationError(error.message); // Show the dedicated error block
            }
        } finally {
            showListLoading(false);
        }
    }

    // --- Data Fetching ---
    async function fetchData(url) {
        try {
            const response = await fetch(url);

            // --- Check for 503 Service Unavailable ---
            if (response.status === 503) {
                try {
                    const errorData = await response.json();
                    if (errorData && errorData.status === 'refreshing') {
                        console.warn("Backend is refreshing data. Displaying maintenance message.");
                        showMaintenanceOverlay(true, errorData.message);
                        // Return a special value or null to indicate handled maintenance state
                        return { maintenance: true }; // Signal maintenance
                    }
                } catch (e) { /* Ignore if body isn't JSON, proceed as normal 503 */ }

                // If it's a 503 but not the specific 'refreshing' status
                throw new Error(`Service temporarily unavailable (Status: 503)`);
            }

            // --- Handle other non-OK responses ---
            if (!response.ok) {
                const errorText = await response.text();
                console.error(`HTTP error ${response.status} for ${url}: ${errorText}`);
                throw new Error(`Failed to fetch ${url} (Status: ${response.status})`);
            }

            // If we reach here, the request was successful (not 503 refreshing)
            // Hide maintenance overlay if it was visible
            showMaintenanceOverlay(false);

            return await response.json();
        } catch (error) {
            console.error(`Error fetching ${url}:`, error);
            // Don't show maintenance overlay for general errors
            // Optionally show a different generic error message to the user here
            throw error; // Re-throw error to be handled by caller
        }
    }

    // --- Rendering Functions (Main List & Filters) ---

    function populateGenerationButtons(generations) {
        generationButtonsContainer.innerHTML = ''; // Clear placeholder

        // 1. Create "All Generations" button
        const allButton = document.createElement('button');
        allButton.classList.add('gen-button', 'active'); // Active by default
        allButton.dataset.genId = ""; // Use empty string for "All"
        allButton.textContent = `All Generations (${totalPokemonFetched})`;
        generationButtonsContainer.appendChild(allButton);

        // 2. Create button for each generation
        generations.forEach(gen => {
            const button = document.createElement('button');
            button.classList.add('gen-button');
            button.dataset.genId = gen.id;

            const roman = formatGenerationId(gen.id).replace('Gen ', ''); // Get 'I', 'II' etc.
            const regionName = gen.region_name.charAt(0).toUpperCase() + gen.region_name.slice(1); // Capitalize region
            // --- Calculate count for this specific generation ---
            const count = allPokemonData.filter(p => p.generation_id === gen.id).length;
            // --------------------------------------------------

            button.textContent = `${regionName} - Gen ${roman} (${count})`;
            generationButtonsContainer.appendChild(button);
        });
    }

    function populateTypesFilter(types) {
        typeFilterContainer.innerHTML = '';
        // const knownIconTypes = ['normal', 'fire', 'water', ...]; // List all types you HAVE icons for
        types.forEach(type => {
            const div = document.createElement('div');
            div.classList.add('type-checkbox-item');

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.id = `type-${type.name}`;
            checkbox.value = type.name;
            checkbox.classList.add('type-filter-checkbox');

            const label = document.createElement('label');
            label.htmlFor = `type-${type.name}`;

            // Label will contain icon OR text

            // --- Create Icon Span ---
            const typeIconSpan = document.createElement('span');
            typeIconSpan.classList.add('type', 'filter-type-icon', `type-${type.name}`); // Add specific class for filter icon styling
            typeIconSpan.title = type.name.charAt(0).toUpperCase() + type.name.slice(1); // Tooltip text

            // --- Create Text Span (Fallback) ---
            const typeTextSpan = document.createElement('span');
            typeTextSpan.classList.add('filter-type-text');
            typeTextSpan.textContent = type.name.charAt(0).toUpperCase() + type.name.slice(1);
            
            // --- Logic: Use Icon or Text ---
            // Simple approach: Assume icon exists, let CSS handle background image.
            // The text span will be hidden by default CSS unless icon fails to load (or use more complex JS check)
            // For now, we add both and rely on CSS to show/hide. A more robust JS check
            // could pre-verify icon existence if needed.
            label.appendChild(typeIconSpan);
            label.appendChild(typeTextSpan);
            
            div.appendChild(checkbox);
            div.appendChild(label);
            typeFilterContainer.appendChild(div);
        });
    }

    // --- Show Initialization Error ---
    function showInitializationError(message) {
        errorMessageElement.textContent = message || "An unexpected error occurred."; // Set error message
        errorDisplay.style.display = 'block'; // Show error block
        // Hide other main content sections
        pokedexListContainer.style.display = 'none';
        resultsCounter.style.display = 'none';
        loadingIndicator.style.display = 'none';
        // Optionally hide controls too?
        // document.querySelector('.controls').style.display = 'none';
    }

    function renderPokemonList(pokemonListToRender) {
        pokedexListContainer.innerHTML = ''; // Clear existing list

        if (pokemonListToRender.length === 0) {
             pokedexListContainer.innerHTML = '<p>No Pokémon match the current filters.</p>';
             return;
        }

        const fragment = document.createDocumentFragment();
        pokemonListToRender.forEach(pokemon => {
            const card = document.createElement('div');
            card.classList.add('pokemon-card');
            card.dataset.id = pokemon.id;
            card.dataset.name = pokemon.name;

            // --- Add Special Status Classes ---
            if (pokemon.is_legendary) {
                card.classList.add('is-legendary');
            } else if (pokemon.is_mythical) { // Typically exclusive with legendary
                card.classList.add('is-mythical');
            }
            if (pokemon.is_baby) {
                card.classList.add('is-baby');
            }

            // --- Replace placeholder with actual image ---
            const img = document.createElement('img');
            img.src = pokemon.sprite_url || 'placeholder-circle.png'; // Use sprite_url, provide fallback image if needed
            img.alt = pokemon.name;
            img.classList.add('card-sprite'); // New class for the actual sprite
            img.loading = 'lazy'; // Lazy load images in the list
            card.appendChild(img);
            // --- End image replacement ---

            const nameSpan = document.createElement('span');
            nameSpan.textContent = pokemon.name;
            nameSpan.classList.add('pokemon-name');

            const idSpan = document.createElement('span');
            idSpan.textContent = `#${String(pokemon.id).padStart(4, '0')}`;
            idSpan.classList.add('pokemon-id');

            const typesDiv = document.createElement('div');
            typesDiv.classList.add('pokemon-types');
            pokemon.types.forEach(typeInfo => {
                const typeSpan = document.createElement('span');
                typeSpan.classList.add('type', `type-${typeInfo.name}`);
                typeSpan.title = typeInfo.name.charAt(0).toUpperCase() + typeInfo.name.slice(1); // Capitalized type
                typesDiv.appendChild(typeSpan);
            });

            card.appendChild(nameSpan);
            card.appendChild(idSpan);
            card.appendChild(typesDiv);

            fragment.appendChild(card);
        });
        pokedexListContainer.appendChild(fragment);
    }

    // --- Filtering Logic ---
    function applyFilters() {
        const searchTerm = searchInput.value.toLowerCase().trim();
        const selectedGeneration = selectedGenerationId; // Use state variable
        const selectedTypes = Array.from(typeFilterContainer.querySelectorAll('input[type="checkbox"]:checked'))
                                   .map(checkbox => checkbox.value);

        const selectedStatuses = Array.from(statusFilterContainer.querySelectorAll('input[type="checkbox"]:checked'))
        .map(checkbox => checkbox.value); // Values are 'is_baby', 'is_legendary', 'is_mythical'

        const filteredPokemon = allPokemonData.filter(pokemon => {
            // 1. Generation Filter
            const generationMatch = !selectedGeneration || pokemon.generation_id === parseInt(selectedGeneration);

            // 2. Type Filter (AND logic)
            const typeMatch = selectedTypes.length === 0 || selectedTypes.every(selectedType =>
                pokemon.types.some(pokemonType => pokemonType.name === selectedType)
            );

            // 3. Search Filter (Name or ID)
            const searchMatch = !searchTerm ||
                                pokemon.name.toLowerCase().includes(searchTerm) ||
                                String(pokemon.id).includes(searchTerm);

            // 4. Status Filter (OR logic between checked statuses)
            // If no status boxes are checked, it matches everything.
            // If one or more are checked, the pokemon must have AT LEAST ONE of the checked statuses set to true.
            const statusMatch = selectedStatuses.length === 0 || selectedStatuses.some(statusKey =>
                 pokemon[statusKey] === true // Check if pokemon property corresponding to the value ('is_baby', etc.) is true
            );
            // ------------------------------------------------------

            // Combine all filters (all must be true)
            return generationMatch && typeMatch && searchMatch && statusMatch;
        });

        renderPokemonList(filteredPokemon);
        // --- Update counter after rendering ---
        updateResultsCounter(filteredPokemon.length);
    }

    // --- Update Results Counter Function ---
    function updateResultsCounter(displayedCount) {
        const selectedGeneration = selectedGenerationId;
        let potentialTotal = totalPokemonFetched; // Start with overall total

        // Adjust potential total if a specific generation is selected
        if (selectedGeneration) {
            potentialTotal = allPokemonData.filter(p => p.generation_id === parseInt(selectedGeneration)).length;
        }
        // Else (All Generations selected), potentialTotal remains totalPokemonFetched

        counterText.textContent = `🔍 ${displayedCount} / ${potentialTotal} Pokémon Displayed`;
        resultsCounter.style.display = 'flex'; // Ensure it's visible
    }

    function debounce(func, delay) {
        let timeoutId;
        return (...args) => {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => { func.apply(this, args); }, delay);
        };
    }
    const debouncedApplyFilters = debounce(applyFilters, 300);

    function formatGenerationId(genId) {
        const romanMap = { 1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V', 6: 'VI', 7: 'VII', 8: 'VIII', 9: 'IX' };
        return `Gen ${romanMap[genId] || genId}`; // Fallback to number if not in map
    }

    // --- MODAL Handling & Rendering ---

    async function openPokemonDetailModal(pokemonIdOrName) {
        modal.style.display = 'block'; // Show modal structure immediately
        showDetailLoading(true); // Show loading indicator
        modalContent.innerHTML = ''; // Clear previous content
        currentDetailPokemon = pokemonIdOrName; // Store ref

        try {
            const pokemonData = await fetchData(`${API_BASE_URL}/pokemon/${pokemonIdOrName}`);
            // Check if the modal is still open for THIS pokemon before rendering
            if (modal.style.display !== 'block' || currentDetailPokemon !== pokemonIdOrName) {
                console.log("Modal closed or changed before details loaded for", pokemonIdOrName);
                return; // Don't render if modal closed or changed
            }
            if (!pokemonData) throw new Error(`Pokémon "${pokemonIdOrName}" not found.`);

            console.log("Fetched detail data:", pokemonData);
            // Render details and get the evolution chain container element
            const evolutionContainerElement = renderPokemonDetail(pokemonData);
            showDetailLoading(false); // Hide loading indicator *after* initial render

            // Fetch and render evolution chain
            if (pokemonData.evolution_chain_url && evolutionContainerElement) {
                console.log(`Fetching evolution chain from: ${pokemonData.evolution_chain_url}`);
                try {
                    const evolutionData = await fetchData(pokemonData.evolution_chain_url);
                    if (evolutionData && evolutionData.chain) {
                        renderEvolutionChain(evolutionData.chain, evolutionContainerElement);
                    } else {
                         evolutionContainerElement.innerHTML = '<p>Could not load evolution data.</p>';
                    }
                } catch (evoError) {
                     console.error("Error fetching evolution chain:", evoError);
                     evolutionContainerElement.innerHTML = `<p>Error loading evolution data.</p>`;
                }
            } else {
                 if (evolutionContainerElement) evolutionContainerElement.innerHTML = '<p>No evolution chain data available.</p>';
            }

        } catch (error) {
            console.error("Error opening detail modal:", error);
             // Only show error if the modal is still meant for this pokemon
             if (modal.style.display === 'block' && currentDetailPokemon === pokemonIdOrName) {
                 modalContent.innerHTML = `<p class="error">Could not load details for ${pokemonIdOrName}. ${error.message}</p>`;
                 showDetailLoading(false);
             }
        }
        // Note: No finally block for hiding loading, it's hidden after initial render or error
    }

    function renderPokemonDetail(data) {
        // NOTE: Assumes backend provides all necessary data including animated sprites, catch_rate etc.
        modalContent.innerHTML = ''; // Clear previous

        // Create the main detail view container
        const detailView = document.createElement('div');
        detailView.classList.add('pokemon-detail-view');

        // --- Title Bar ---
        const titleBar = document.createElement('div');
        titleBar.classList.add('detail-title-bar');
        titleBar.innerHTML = `
            <span class="detail-id">#${String(data.id).padStart(4, '0')}</span>
            <h2 class="detail-name">${data.name}</h2>
        `;
        detailView.appendChild(titleBar);

        // --- Generation & Region Indicator ---
        const indicatorsContainer = document.createElement('div');
        indicatorsContainer.classList.add('detail-indicators');

        const genIndicator = document.createElement('span');
        genIndicator.classList.add('detail-generation-indicator');
        genIndicator.textContent = formatGenerationId(data.generation_id);
        indicatorsContainer.appendChild(genIndicator);

        // Find region name from fetched generations data
        const generationInfo = generationsData.find(g => g.id === data.generation_id);
        const regionName = generationInfo ? generationInfo.region_name.charAt(0).toUpperCase() + generationInfo.region_name.slice(1) : 'Unknown';

        const regionIndicator = document.createElement('span');
        regionIndicator.classList.add('detail-region-indicator');
        regionIndicator.textContent = `Region: ${regionName}`;
        indicatorsContainer.appendChild(regionIndicator);

        detailView.appendChild(indicatorsContainer); // Add container with both indicators

        // --- Top Sprite Section ---
        const topSpriteSection = document.createElement('div');
        topSpriteSection.classList.add('detail-top-sprite-section');

        const mainSpriteContainer = document.createElement('div');
        mainSpriteContainer.classList.add('main-sprite-container');
        const mainSprite = document.createElement('img');
        mainSprite.alt = data.name;
        mainSprite.id = 'main-pokemon-sprite';
        mainSprite.classList.add('main-sprite');

        // Priority: Animated Default > Official Artwork > Default Front Sprite
        const animatedSprite = data.sprites?.animated_front_default; // Use field from updated model
        const officialArtwork = data.sprites?.official_artwork;
        const defaultSprite = data.sprites?.front_default;
        const initialSpriteSrc = animatedSprite || officialArtwork || defaultSprite || 'placeholder.png';
        mainSprite.src = initialSpriteSrc;

        if (animatedSprite) mainSprite.title = "Animated Default";
        else if (officialArtwork) mainSprite.title = "Official Artwork";
        else if (defaultSprite) mainSprite.title = "Default";
        else mainSprite.title = "Placeholder";

        // --- Attach listener to open sprite viewer ---
        mainSprite.addEventListener('click', () => {
            // Pass the same data used to build the gallery
            openSpriteViewer(gallerySpritesData, initialSpriteSrc); // Pass gallery data and current src
        });

        mainSpriteContainer.appendChild(mainSprite);

        // --- Sprite Gallery ---
        const spriteGallery = document.createElement('div');
        spriteGallery.classList.add('sprite-gallery');

        // Define potential sprites with titles and URLs
        const gallerySpritesData = [
            // Add sprites in desired order, checking if URL exists
            { type: "Animated Default", url: data.sprites?.animated_front_default },
            { type: "Official Artwork", url: data.sprites?.official_artwork },
            { type: "Default", url: data.sprites?.front_default },
            { type: "Shiny", url: data.sprites?.front_shiny },
            { type: "Animated Back Default", url: data.sprites?.animated_back_default },
            { type: "Animated Shiny", url: data.sprites?.animated_front_shiny },
            { type: "Animated Back Shiny", url: data.sprites?.animated_back_shiny },
            { type: "Back", url: data.sprites?.back_default },
            { type: "Shiny Back", url: data.sprites?.back_shiny },
            // Optional Female variants
            { type: "Female Default", url: data.sprites?.front_female },
            { type: "Female Shiny", url: data.sprites?.front_shiny_female },
            // Add more if needed (e.g., animated back)
        ].filter(sprite => sprite.url); // Filter out entries without a URL

        gallerySpritesData.forEach((spriteInfo, index) => {
            const img = document.createElement('img');
            img.src = spriteInfo.url;
            img.alt = `${data.name} ${spriteInfo.type} Sprite`;
            img.title = spriteInfo.type; // Tooltip text
            img.classList.add('gallery-sprite');
            // Add 'selected' class if this sprite is the initial main sprite
            if (spriteInfo.url === initialSpriteSrc) {
                 img.classList.add('selected');
            }
            img.addEventListener('click', () => {
                const mainSpriteElement = document.getElementById('main-pokemon-sprite');
                if (mainSpriteElement) {
                    mainSpriteElement.src = spriteInfo.url;
                    mainSpriteElement.title = spriteInfo.type;
                    // Update 'selected' class on thumbnails
                    spriteGallery.querySelectorAll('.gallery-sprite.selected').forEach(el => el.classList.remove('selected'));
                    img.classList.add('selected');
                }
            });
            spriteGallery.appendChild(img);
        });

        topSpriteSection.appendChild(mainSpriteContainer);
        topSpriteSection.appendChild(spriteGallery);
        detailView.appendChild(topSpriteSection);

        // --- Main Content Grid ---
        const mainGrid = document.createElement('div');
        mainGrid.classList.add('detail-main-grid');

        // Helper to create info cards
        const createInfoCard = (title, contentHtml) => {
             const card = document.createElement('div');
             card.classList.add('info-card');
             card.innerHTML = `<h3>${title}</h3><div class="card-content">${contentHtml}</div>`;
             return card;
        };

        // Types Card
        mainGrid.appendChild(createInfoCard('Types', `
            <div class="card-content-types">
                ${data.types.map(t => `
                    <span
                        class="type type-${t.name}"
                        title="${t.name.charAt(0).toUpperCase() + t.name.slice(1)}"
                    ></span>` // Add title, remove text content
                ).join(' ')}
            </div>
        `));

        // Physical Attributes Card
        mainGrid.appendChild(createInfoCard('Physical Attributes', `
            <p><strong>Height:</strong> ${data.height / 10} m</p>
            <p><strong>Weight:</strong> ${data.weight / 10} kg</p>
            ${data.shape ? `<p><strong>Shape:</strong> ${data.shape}</p>` : ''}
            ${data.habitat ? `<p><strong>Habitat:</strong> ${data.habitat}</p>` : ''}
        `));

        // Abilities Card
        mainGrid.appendChild(createInfoCard('Abilities', `
            <ul>
                ${data.abilities.map(a => `<li>${a.name.replace('-', ' ')} ${a.is_hidden ? '(Hidden)' : ''}</li>`).join('')}
            </ul>
        `));

        // --- Base Stats Card ---
        const statsCard = document.createElement('div');
        statsCard.classList.add('info-card', 'stats-card');
        // Use a different list structure to accommodate bars
        let statsHtml = '<h3>Base Stats</h3><div class="card-content"><ul class="stats-list-bars">';
        const MAX_STAT_VALUE = 255; // Standard max base stat for calculation

        data.stats.forEach(stat => {
            // Format stat name (e.g., 'special-attack' -> 'Sp. Attack') - Improved
            let statName = stat.name.replace('-', ' ');
            if (stat.name === 'hp') {
                statName = 'HP';
            } else if (stat.name.startsWith('special-')) {
                 statName = 'Sp. ' + statName.replace('special ', '').charAt(0).toUpperCase() + statName.slice(9); // e.g. Sp. Attack
            } else {
                statName = statName.charAt(0).toUpperCase() + statName.slice(1);
            }

            // Calculate percentage and determine color
            const percentage = Math.max(0, Math.min(100, (stat.base_stat / MAX_STAT_VALUE) * 100)); // Ensure 0-100 range
            let barColorClass = 'stat-bar-red'; // Default: Red (< 25%)
            if (percentage >= 75) barColorClass = 'stat-bar-purple'; // >= 75% Purple
            else if (percentage >= 50) barColorClass = 'stat-bar-green';  // 50-74% Green
            else if (percentage >= 25) barColorClass = 'stat-bar-yellow'; // 25-49% Yellow

            // Build list item HTML with bar elements
            statsHtml += `
                <li>
                    <span class="stat-name">${statName}</span>
                    <span class="stat-value">${stat.base_stat}</span>
                    <div class="stat-bar-container" title="${stat.base_stat}/${MAX_STAT_VALUE}">
                        <div class="stat-bar ${barColorClass}" style="width: ${percentage}%;"></div>
                    </div>
                </li>
            `;
        });
        statsHtml += '</ul></div>';
        statsCard.innerHTML = statsHtml;
        mainGrid.appendChild(statsCard); // Add card to grid

        // Breeding Info Card
        let genderRatio = 'Genderless';
        if (data.gender_rate >= 0) {
            if (data.gender_rate === 0) genderRatio = '100% Male';
            else if (data.gender_rate === 8) genderRatio = '100% Female';
            else genderRatio = `${100 - (data.gender_rate / 8 * 100)}% Male, ${data.gender_rate / 8 * 100}% Female`;
        }
        const hatchTime = data.hatch_counter ? `~${(data.hatch_counter + 1) * 255} steps` : 'N/A';
        mainGrid.appendChild(createInfoCard('Breeding Info', `
            <p><strong>Gender:</strong> ${genderRatio}</p>
            <p><strong>Egg Groups:</strong> ${data.egg_groups?.map(eg => eg.name).join(', ') || 'N/A'}</p>
            <p><strong>Hatch Time:</strong> ${hatchTime}</p>
        `));

        // Species Info Card
        mainGrid.appendChild(createInfoCard('Species Info', `
            <p><strong>Genus:</strong> ${data.genus || 'Unknown Genus'}</p>
            <p><strong>Catch Rate:</strong> ${data.catch_rate ?? 'N/A'}</p>
            <p><strong>Base Happiness:</strong> ${data.base_happiness ?? 'N/A'}</p>
            <p><strong>Growth Rate:</strong> ${data.growth_rate_name ? data.growth_rate_name.replace('-', ' ') : 'N/A'}</p>
            <p><strong>Base Exp:</strong> ${data.base_experience ?? 'N/A'}</p>
        `));

        // Classifications Card
        const evolvesFrom = data.evolves_from_species ? data.evolves_from_species.name : 'N/A';
        mainGrid.appendChild(createInfoCard('Classifications', `
            <p><strong>Legendary:</strong> ${data.is_legendary ? 'Yes' : 'No'}</p>
            <p><strong>Mythical:</strong> ${data.is_mythical ? 'Yes' : 'No'}</p>
            <p><strong>Baby:</strong> ${data.is_baby ? 'Yes' : 'No'}</p>
            <p><strong>Evolves From:</strong> <span style="text-transform: capitalize;">${evolvesFrom}</span></p>
        `));

        detailView.appendChild(mainGrid); // Add grid

        // Description Card
        const flavorTextEntry = data.flavor_text_entries?.find(entry => entry.language?.name === 'en');
        detailView.appendChild(createInfoCard('Description', `
            <p>${flavorTextEntry ? flavorTextEntry.flavor_text.replace(/[\n\f\u00ad\r]/g, ' ').trim() : 'No description available.'}</p>
        `));

        // Evolution Chain Card (placeholder container)
        const evolutionCard = createInfoCard('Evolution Chain', `<div class="evolution-chain-container"><p>Loading...</p></div>`);
        detailView.appendChild(evolutionCard);

        // Append the fully constructed detail view to the modal content area
        modalContent.appendChild(detailView);

        // Return the specific container where the evolution chain should be rendered
        return evolutionCard.querySelector('.evolution-chain-container');
    }

    // Evolution Chain Rendering (Keep the version from the previous step - handles horizontal layout)
    function renderEvolutionChain(chainData, containerElement) {
        containerElement.innerHTML = ''; // Clear loading text
        const chainWrapper = document.createElement('div');
        chainWrapper.classList.add('evolution-chain-wrapper');

        function processChain(chainLink, parentElement) {
            const pokemonName = chainLink.species.name;
            const pokemonId = chainLink.species.url.split('/').filter(Boolean).pop();
            const stageDiv = document.createElement('div');
            stageDiv.classList.add('evolution-stage');
            const link = document.createElement('a');
            link.href = '#';
            link.dataset.id = pokemonId;
            link.classList.add('evolution-link');
            const img = document.createElement('img');
            img.src = `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${pokemonId}.png`;
            img.alt = pokemonName;
            img.classList.add('evolution-sprite-small');
            img.loading = 'lazy';
            const nameSpan = document.createElement('span');
            nameSpan.textContent = pokemonName;
            link.appendChild(img);
            link.appendChild(nameSpan);
            stageDiv.appendChild(link);

            if (parentElement !== chainWrapper) {
                 const arrowSpan = document.createElement('span');
                 arrowSpan.classList.add('evolution-arrow');
                 arrowSpan.textContent = '→';
                 parentElement.appendChild(arrowSpan);
            }
            parentElement.appendChild(stageDiv);

            if (chainLink.evolves_to && chainLink.evolves_to.length > 0) {
                chainLink.evolves_to.forEach(nextLink => processChain(nextLink, parentElement));
            }
        }
        processChain(chainData, chainWrapper);
        containerElement.appendChild(chainWrapper);

        // Re-attach listener as content is replaced
        containerElement.addEventListener('click', async (event) => {
             const link = event.target.closest('.evolution-link');
            if (link && link.dataset.id) {
                event.preventDefault();
                const targetId = link.dataset.id;
                console.log(`Evolution link clicked: ${targetId}`);
                // Instead of complex logic, just re-open the modal for the new ID
                openPokemonDetailModal(targetId);
            }
        });
    }

    function closePokemonDetailModal() {
        modal.style.display = 'none';
        modalContent.innerHTML = ''; // Clear content
        currentDetailPokemon = null; // Reset tracker
    }

    // --- Loading Indicators ---
    function showListLoading(isLoading) {
        loadingIndicator.style.display = isLoading ? 'block' : 'none';
    }
    function showDetailLoading(isLoading) {
        detailLoadingIndicator.style.display = isLoading ? 'block' : 'none';
    }

    // --- Show/Hide Maintenance Overlay ---
    function showMaintenanceOverlay(show, message = "The Pokedex data is being updated. Please check back shortly!") {
        if (show) {
            maintenanceMessageElement.textContent = message;
            maintenanceOverlay.style.display = 'flex'; // Use flex to center content
            // Optionally disable background scroll
            // document.body.style.overflow = 'hidden';
        } else {
            maintenanceOverlay.style.display = 'none';
            // Optionally re-enable background scroll
            // document.body.style.overflow = '';
        }
    }

    // --- Sprite Viewer Functions ---
    function openSpriteViewer(galleryData, currentSpriteSrc) {
        if (!galleryData || galleryData.length === 0) return; // No sprites to view

        currentGallerySprites = galleryData; // Store the list for navigation
        // Find the index of the sprite that was clicked (which is the main sprite's src)
        currentFullSpriteIndex = currentGallerySprites.findIndex(sprite => sprite.url === currentSpriteSrc);
        if (currentFullSpriteIndex === -1) {
            currentFullSpriteIndex = 0; // Default to first if somehow not found
        }

        // --- Reset zoom state when opening ---
        isSpriteZoomed = false;
        fullSpriteImage.classList.remove('zoomed-in');
        spriteViewerZoomBtn.innerHTML = zoomInIconSVG;
        spriteViewerZoomBtn.title = "Zoom In";
        // ----------------------------------

        showSpriteAtIndex(currentFullSpriteIndex); // Display the initial sprite
        // --- Use classList to control visibility ---
        spriteViewerOverlay.classList.add('visible');
        // spriteViewerOverlay.style.display = 'flex'; // Show the overlay
        // Optional: Add keyboard listeners specifically when viewer is open
        document.addEventListener('keydown', handleSpriteViewerKeydown);
    }

    function closeSpriteViewer() {
        spriteViewerOverlay.classList.remove('visible');
        // Reset zoom state visually (already done logically on open)
        fullSpriteImage.classList.remove('zoomed-in');
        isSpriteZoomed = false;
        currentGallerySprites = []; // Clear the list
        currentFullSpriteIndex = 0;
        // Optional: Remove keyboard listeners
        document.removeEventListener('keydown', handleSpriteViewerKeydown);
    }

    function showSpriteAtIndex(index) {
        if (!currentGallerySprites || currentGallerySprites.length === 0) return;
        // Ensure index wraps around
        currentFullSpriteIndex = (index + currentGallerySprites.length) % currentGallerySprites.length;

        const spriteToShow = currentGallerySprites[currentFullSpriteIndex];
        fullSpriteImage.src = spriteToShow.url;
        fullSpriteImage.alt = spriteToShow.type; // Update alt text
        spriteViewerCaption.textContent = spriteToShow.type; // Update caption

        // --- Optional: Reset zoom on sprite change? ---
        // fullSpriteImage.classList.remove('zoomed-in');
        // isSpriteZoomed = false;
        // spriteViewerZoomBtn.innerHTML = zoomInIconSVG;
        // spriteViewerZoomBtn.title = "Zoom In";
        // -----------------------------------------
    }

    function showNextSprite() {
        showSpriteAtIndex(currentFullSpriteIndex + 1);
    }

    function showPrevSprite() {
        showSpriteAtIndex(currentFullSpriteIndex - 1);
    }

    // Handler for keyboard navigation in sprite viewer
    function handleSpriteViewerKeydown(event) {
        if (spriteViewerOverlay.classList.contains('visible')) { // Only act if viewer is open
            if (event.key === 'ArrowRight') {
                showNextSprite();
            } else if (event.key === 'ArrowLeft') {
                showPrevSprite();
            } else if (event.key === 'Escape') {
                closeSpriteViewer();
            }
        }
    }

    // --- Toggle Zoom Function ---
    function toggleSpriteZoom() {
        isSpriteZoomed = !isSpriteZoomed; // Toggle the state
        if (isSpriteZoomed) {
            fullSpriteImage.classList.add('zoomed-in');
            spriteViewerZoomBtn.innerHTML = zoomOutIconSVG; // Set zoom-out icon
            spriteViewerZoomBtn.title = "Zoom Out";
        } else {
            fullSpriteImage.classList.remove('zoomed-in');
            spriteViewerZoomBtn.innerHTML = zoomInIconSVG; // Set zoom-in icon
            spriteViewerZoomBtn.title = "Zoom In";
        }
    }

    // --- Event Listeners Setup ---
    function setupEventListeners() {
        searchInput.addEventListener('input', debouncedApplyFilters);
        
        generationButtonsContainer.addEventListener('click', (event) => {
            const button = event.target.closest('.gen-button'); // Find clicked button
            if (button && !button.classList.contains('active')) { // Check if it's a button and not already active
                // Update state
                selectedGenerationId = button.dataset.genId;

                // Update UI (active class)
                generationButtonsContainer.querySelectorAll('.gen-button.active').forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');

                // Apply filter
                applyFilters();
            }
        });

        typeFilterFieldset.addEventListener('change', (event) => {
            if (event.target.matches('input[type="checkbox"].type-filter-checkbox')) {
                applyFilters();
            }
        });

        // --- Event delegation for status checkboxes ---
        statusFilterFieldset.addEventListener('change', (event) => {
            if (event.target.matches('input[type="checkbox"].status-filter-checkbox')) {
                applyFilters();
            }
        });

        // --- Clear/Reset Button Listeners ---
        clearFiltersButton.addEventListener('click', () => {
            // Clear type checkboxes
            typeFilterContainer.querySelectorAll('input[type="checkbox"]:checked').forEach(cb => cb.checked = false);
            // Clear status checkboxes
            statusFilterContainer.querySelectorAll('input[type="checkbox"]:checked').forEach(cb => cb.checked = false);
            // Re-apply filters
            applyFilters();
        });

        // Click listener for pokemon cards (using event delegation)
        pokedexListContainer.addEventListener('click', (event) => {
            const card = event.target.closest('.pokemon-card');
            if (card && card.dataset.id) {
                openPokemonDetailModal(card.dataset.id);
            }
        });
        // Modal listeners
        closeModalButton.addEventListener('click', closePokemonDetailModal);
        modal.addEventListener('click', (event) => {
            if (event.target === modal) { // Click on backdrop
                closePokemonDetailModal();
            }
        });
        window.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && modal.style.display === 'block') {
                closePokemonDetailModal();
            }
        });

        // --- Sprite Viewer Listeners ---
        spriteViewerCloseBtn.addEventListener('click', closeSpriteViewer);
        spriteViewerNextBtn.addEventListener('click', showNextSprite);
        spriteViewerPrevBtn.addEventListener('click', showPrevSprite);
        spriteViewerZoomBtn.addEventListener('click', toggleSpriteZoom);
        // Keyboard listener added dynamically when viewer opens

        // --- Scroll-to-Top Listener ---
        window.addEventListener('scroll', () => {
            // Show button if scrolled down more than, say, 300 pixels
            if (window.scrollY > 300) {
                scrollToTopButton.style.display = 'block';
            } else {
                scrollToTopButton.style.display = 'none';
            }
        });

        scrollToTopButton.addEventListener('click', () => {
            window.scrollTo({ top: 0, behavior: 'smooth' }); // Smooth scroll to top
        });
    }

    // --- Start the application ---
    initializeApp();

}); // End DOMContentLoaded