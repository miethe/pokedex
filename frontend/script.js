// frontend/script.js

document.addEventListener('DOMContentLoaded', () => {
    // --- Configuration & State ---
    const API_BASE_URL = '/api'; // Relative URL, Nginx will proxy this
    let allPokemonData = []; // Holds the full summary list fetched once
    let generationsData = []; // Holds generation info
    let typesData = []; // Holds type info

    // --- DOM Element References ---
    const searchInput = document.getElementById('search-input');
    const generationFilter = document.getElementById('generation-filter');
    const typeFilterContainer = document.getElementById('type-checkboxes-container');
    const typeFilterFieldset = document.getElementById('type-filter'); // For event delegation
    const pokedexList = document.getElementById('pokedex-list');
    const loadingIndicator = document.getElementById('loading-indicator');
    const modal = document.getElementById('pokemon-detail-modal');
    const modalContent = document.getElementById('pokemon-detail-content');
    const detailLoadingIndicator = document.getElementById('detail-loading-indicator');
    const closeModalButton = modal.querySelector('.close-button');

    // --- Initialization ---
    async function initializeApp() {
        console.log("Initializing Pokedex App...");
        showLoading(true);

        try {
            // Fetch initial data in parallel
            const [summary, generations, types] = await Promise.all([
                fetchData(`${API_BASE_URL}/pokedex/summary`),
                fetchData(`${API_BASE_URL}/generations`),
                fetchData(`${API_BASE_URL}/types`)
            ]);

            if (!summary || !generations || !types) {
                 throw new Error("Failed to fetch initial data from the backend API.");
            }

            allPokemonData = summary;
            generationsData = generations.sort((a, b) => a.id - b.id); // Sort generations by ID
            typesData = types.sort((a, b) => a.name.localeCompare(b.name)); // Sort types alphabetically

            console.log(`Fetched ${allPokemonData.length} Pokémon summaries.`);
            console.log(`Fetched ${generationsData.length} generations.`);
            console.log(`Fetched ${typesData.length} types.`);

            populateGenerationsFilter(generationsData);
            populateTypesFilter(typesData);
            renderPokemonList(allPokemonData); // Render initial full list

            setupEventListeners();

        } catch (error) {
            console.error("Initialization failed:", error);
            pokedexList.innerHTML = `<p class="error">Could not load Pokedex data. Please try refreshing the page. (${error.message})</p>`;
        } finally {
            showLoading(false);
        }
    }

    // --- Data Fetching ---
    async function fetchData(url) {
        try {
            const response = await fetch(url);
            if (!response.ok) {
                const errorText = await response.text();
                console.error(`HTTP error ${response.status} for ${url}: ${errorText}`);
                throw new Error(`Failed to fetch ${url} (Status: ${response.status})`);
            }
            return await response.json();
        } catch (error) {
            console.error(`Error fetching ${url}:`, error);
            // Propagate error to be handled by the caller (e.g., initializeApp)
            throw error;
        }
    }

    // --- Rendering Functions ---

    function populateGenerationsFilter(generations) {
        generationFilter.innerHTML = '<option value="">All Generations</option>'; // Reset
        generations.forEach(gen => {
            const option = document.createElement('option');
            option.value = gen.id;
            // Format name like "Generation 1"
            const roman = gen.name.split('-')[1].toUpperCase();
            option.textContent = `Generation ${roman} (${gen.id})`;
            generationFilter.appendChild(option);
        });
    }

    function populateTypesFilter(types) {
        typeFilterContainer.innerHTML = ''; // Clear placeholder/previous checkboxes
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
            label.textContent = type.name.charAt(0).toUpperCase() + type.name.slice(1); // Capitalize

            // Add type background color to label for visual cue
            label.classList.add('type-label', `type-${type.name}`); // Add class for general styling and specific type color

            div.appendChild(checkbox);
            div.appendChild(label);
            typeFilterContainer.appendChild(div);
        });
    }

    function renderPokemonList(pokemonListToRender) {
        pokedexList.innerHTML = ''; // Clear existing list

        if (pokemonListToRender.length === 0) {
             pokedexList.innerHTML = '<p>No Pokémon match the current filters.</p>';
             return;
        }

        const fragment = document.createDocumentFragment();
        pokemonListToRender.forEach(pokemon => {
            const card = document.createElement('div');
            card.classList.add('pokemon-card');
            // Store ID and name for easy access on click
            card.dataset.id = pokemon.id;
            card.dataset.name = pokemon.name;

            // Basic card content (ID, Name, Types)
            // We don't have sprites in the summary data per requirements
            const nameSpan = document.createElement('span');
            nameSpan.textContent = pokemon.name;
            nameSpan.classList.add('pokemon-name');

            const idSpan = document.createElement('span');
            idSpan.textContent = `#${String(pokemon.id).padStart(4, '0')}`; // Pad ID e.g., #0001
            idSpan.classList.add('pokemon-id');

            const typesDiv = document.createElement('div');
            typesDiv.classList.add('pokemon-types');
            pokemon.types.forEach(typeInfo => {
                const typeSpan = document.createElement('span');
                typeSpan.classList.add('type', `type-${typeInfo.name}`);
                typeSpan.textContent = typeInfo.name;
                typesDiv.appendChild(typeSpan);
            });

            // Assemble card
            // Optional: Add placeholder for image if desired
            // const imgPlaceholder = document.createElement('div');
            // imgPlaceholder.style.width = '70px';
            // imgPlaceholder.style.height = '70px';
            // imgPlaceholder.style.backgroundColor = '#eee';
            // imgPlaceholder.style.marginBottom = '5px';
            // card.appendChild(imgPlaceholder);

            card.appendChild(nameSpan);
            card.appendChild(idSpan);
            card.appendChild(typesDiv);

            fragment.appendChild(card);
        });
        pokedexList.appendChild(fragment); // Append all cards at once
    }

    // --- Filtering Logic ---

    function applyFilters() {
        const searchTerm = searchInput.value.toLowerCase().trim();
        const selectedGeneration = generationFilter.value;
        const selectedTypes = Array.from(typeFilterContainer.querySelectorAll('input[type="checkbox"]:checked'))
                                   .map(checkbox => checkbox.value);

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
                                String(pokemon.id).includes(searchTerm); // Allow searching by ID string

            return generationMatch && typeMatch && searchMatch;
        });

        renderPokemonList(filteredPokemon);
    }

    // Debounce function
    function debounce(func, delay) {
        let timeoutId;
        return (...args) => {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => {
                func.apply(this, args);
            }, delay);
        };
    }

    // Debounced version of applyFilters for search input
    const debouncedApplyFilters = debounce(applyFilters, 300); // 300ms delay

    // --- Modal Handling ---

    function renderPokemonDetail(data) {
        modalContent.innerHTML = ''; // Clear previous content/loading indicator

        // Main container for the new layout
        const detailView = document.createElement('div');
        detailView.classList.add('pokemon-detail-view');

        // --- Top Sprite Section ---
        const topSpriteSection = document.createElement('div');
        topSpriteSection.classList.add('detail-top-sprite-section');

        const mainSpriteContainer = document.createElement('div');
        mainSpriteContainer.classList.add('main-sprite-container');
        const mainSprite = document.createElement('img');
        // Prefer official artwork, fallback to front_default
        mainSprite.src = data.sprites?.official_artwork || data.sprites?.front_default || 'placeholder.png'; // Add a placeholder img if none found
        mainSprite.alt = data.name;
        mainSprite.classList.add('main-sprite');
        mainSpriteContainer.appendChild(mainSprite);

        const spriteGallery = document.createElement('div');
        spriteGallery.classList.add('sprite-gallery');
        const gallerySprites = [
            { url: data.sprites.front_default, title: "Default" },
            { url: data.sprites.back_default, title: "Back Default" },
            { url: data.sprites.front_shiny, title: "Shiny" },
            { url: data.sprites.back_shiny, title: "Back Shiny" },
            // Add female sprites if needed and available
        ];
        gallerySprites.forEach(sprite => {
            if (sprite.url) {
                const img = document.createElement('img');
                img.src = sprite.url;
                img.alt = `${data.name} ${sprite.title} Sprite`;
                img.title = sprite.title;
                // Add click handler to potentially change the main sprite? (Optional feature)
                // img.onclick = () => mainSprite.src = sprite.url;
                spriteGallery.appendChild(img);
            }
        });

        topSpriteSection.appendChild(mainSpriteContainer);
        topSpriteSection.appendChild(spriteGallery);
        detailView.appendChild(topSpriteSection);


        // --- Main Content Grid ---
        const mainGrid = document.createElement('div');
        mainGrid.classList.add('detail-main-grid');


        // --- Types Card ---
        const typesCard = document.createElement('div');
        typesCard.classList.add('info-card', 'types-card');
        typesCard.innerHTML = `
            <h3>Types</h3>
            <div class="card-content card-content-types">
                ${data.types.map(t => `<span class="type type-${t.name}">${t.name}</span>`).join(' ')}
            </div>
        `;
        mainGrid.appendChild(typesCard);

        // --- Physical Attributes Card ---
        const physicalCard = document.createElement('div');
        physicalCard.classList.add('info-card', 'physical-card');
        physicalCard.innerHTML = `
            <h3>Physical Attributes</h3>
            <div class="card-content">
                <p><strong>Height:</strong> ${data.height / 10} m</p>
                <p><strong>Weight:</strong> ${data.weight / 10} kg</p>
                <p><strong>Shape:</strong> ${data.shape || 'N/A'}</p>
                <p><strong>Habitat:</strong> ${data.habitat || 'N/A'}</p>
            </div>
        `;
        mainGrid.appendChild(physicalCard);

         // --- Abilities Card ---
        const abilitiesCard = document.createElement('div');
        abilitiesCard.classList.add('info-card', 'abilities-card');
        abilitiesCard.innerHTML = `
            <h3>Abilities</h3>
            <div class="card-content">
                <ul>
                    ${data.abilities.map(a => `<li>${a.name.replace('-', ' ')} ${a.is_hidden ? '(Hidden)' : ''}</li>`).join('')}
                </ul>
            </div>
        `;
        mainGrid.appendChild(abilitiesCard);

        // --- Base Stats Card ---
        const statsCard = document.createElement('div');
        statsCard.classList.add('info-card', 'stats-card');
        let statsHtml = '<h3>Base Stats</h3><div class="card-content"><ul class="stats-list-text">';
        data.stats.forEach(stat => {
            // Format stat name (e.g., 'special-attack' -> 'Sp. attack')
             let statName = stat.name.replace('-', '. ');
             if(statName.includes('.')) {
                statName = statName.split('.').map(word => word.charAt(0).toUpperCase() + '.').join('');
             } else {
                statName = statName.charAt(0).toUpperCase() + statName.slice(1);
             }

            statsHtml += `<li><span>${statName}</span><span>${stat.base_stat}</span></li>`;
        });
        statsHtml += '</ul></div>';
        statsCard.innerHTML = statsHtml;
        mainGrid.appendChild(statsCard);

        // --- Breeding Info Card ---
        const breedingCard = document.createElement('div');
        breedingCard.classList.add('info-card', 'breeding-card');
         // Gender calculation (same as before)
        let genderRatio = 'Genderless';
        if (data.gender_rate >= 0) { // Ensure rate is valid
            if (data.gender_rate === 0) genderRatio = '100% Male';
            else if (data.gender_rate === 8) genderRatio = '100% Female';
            else {
                const femaleChance = (data.gender_rate / 8) * 100;
                genderRatio = `${100 - femaleChance}% Male, ${femaleChance}% Female`;
            }
        }
        // Calculate approximate hatch time (requires hatch_counter from backend)
        // const hatchTime = data.hatch_counter ? `~${(data.hatch_counter + 1) * 255} steps` : 'N/A'; // Example calculation
        breedingCard.innerHTML = `
            <h3>Breeding Info</h3>
            <div class="card-content">
                <p><strong>Gender:</strong> ${genderRatio}</p>
                <p><strong>Egg Groups:</strong> ${data.egg_groups.map(eg => eg.name).join(', ') || 'N/A'}</p>
                <!-- Add Hatch Time when data is available -->
                <!-- <p><strong>Hatch Time:</strong> ${hatchTime}</p> -->
                <p><strong>Hatch Time:</strong> N/A</p> <!-- Placeholder -->
            </div>
        `;
        mainGrid.appendChild(breedingCard);

        // --- Species Info Card ---
        const speciesCard = document.createElement('div');
        speciesCard.classList.add('info-card', 'species-card');
        speciesCard.innerHTML = `
            <h3>Species Info</h3>
            <div class="card-content">
                <p><strong>Genus:</strong> ${data.genus || 'Unknown Genus'}</p>
                <!-- Add Catch Rate when data is available -->
                <!-- <p><strong>Catch Rate:</strong> ${data.catch_rate ?? 'N/A'}</p> -->
                <p><strong>Catch Rate:</strong> N/A</p> <!-- Placeholder -->
                <!-- Add Base Happiness when data is available -->
                <!-- <p><strong>Base Happiness:</strong> ${data.base_happiness ?? 'N/A'}</p> -->
                <p><strong>Base Happiness:</strong> N/A</p> <!-- Placeholder -->
                <p><strong>Growth Rate:</strong> ${data.growth_rate_name ? data.growth_rate_name.replace('-', ' ') : 'N/A'}</p>
                <p><strong>Base Exp:</strong> ${data.base_experience || 'N/A'}</p>
            </div>
        `;
        mainGrid.appendChild(speciesCard);

        // --- Classifications Card ---
        const classificationCard = document.createElement('div');
        classificationCard.classList.add('info-card', 'classification-card');
        // Determine evolves from text (requires evolves_from_species from backend)
        // const evolvesFrom = data.evolves_from_species ? data.evolves_from_species.name : 'N/A';
        classificationCard.innerHTML = `
            <h3>Classifications</h3>
            <div class="card-content">
                <p><strong>Legendary:</strong> ${data.is_legendary ? 'Yes' : 'No'}</p>
                <p><strong>Mythical:</strong> ${data.is_mythical ? 'Yes' : 'No'}</p>
                <!-- Add Baby status when data is available -->
                <!-- <p><strong>Baby:</strong> ${data.is_baby ? 'Yes' : 'No'}</p> -->
                <p><strong>Baby:</strong> N/A</p> <!-- Placeholder -->
                <!-- Add Evolves From when data is available -->
                <!-- <p><strong>Evolves From:</strong> ${evolvesFrom}</p> -->
                 <p><strong>Evolves From:</strong> N/A</p> <!-- Placeholder -->
            </div>
        `;
        mainGrid.appendChild(classificationCard);

        detailView.appendChild(mainGrid); // Add grid to the view

        // --- Description Card ---
        const descriptionCard = document.createElement('div');
        descriptionCard.classList.add('info-card', 'description-card');
        const flavorTextEntry = data.flavor_text_entries?.find(entry => entry.language?.name === 'en');
        descriptionCard.innerHTML = `
            <h3>Description</h3>
            <div class="card-content">
                <p>${flavorTextEntry ? flavorTextEntry.flavor_text.replace(/[\n\f]/g, ' ') : 'No description available.'}</p>
            </div>
        `;
        detailView.appendChild(descriptionCard);

        // --- Evolution Chain Card ---
        const evolutionCard = document.createElement('div');
        evolutionCard.classList.add('info-card', 'evolution-card');
        // Placeholder content, will be filled by renderEvolutionChain
        evolutionCard.innerHTML = `<h3>Evolution Chain</h3><div class="card-content evolution-chain-container"><p>Loading evolution chain...</p></div>`;
        detailView.appendChild(evolutionCard);


        modalContent.appendChild(detailView); // Add the whole new structure to the modal

        // Return the container element for the evolution chain rendering
        return evolutionCard.querySelector('.evolution-chain-container');
    }

    // Updated renderEvolutionChain for the new layout
    function renderEvolutionChain(chainData, containerElement) {
        console.log("Rendering evolution chain:", chainData);
        containerElement.innerHTML = ''; // Clear loading text
        const chainWrapper = document.createElement('div');
        chainWrapper.classList.add('evolution-chain-wrapper'); // Use flexbox

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
            // Use official artwork if available for chain? Or stick to sprites? Let's use sprites for consistency.
             img.src = `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${pokemonId}.png`;
            // Alternative: Official Artwork
            // img.src = `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/${pokemonId}.png`;
            img.alt = pokemonName;
            img.classList.add('evolution-sprite-small'); // New class for smaller sprites
            img.loading = 'lazy';

            const nameSpan = document.createElement('span');
            nameSpan.textContent = pokemonName;

            link.appendChild(img);
            link.appendChild(nameSpan);
            stageDiv.appendChild(link);

             // Append arrow only if it's not the first stage in this sub-chain
            if (parentElement !== chainWrapper) {
                 const arrowSpan = document.createElement('span');
                 arrowSpan.classList.add('evolution-arrow');
                 arrowSpan.textContent = '→';
                 parentElement.appendChild(arrowSpan);
            }

            parentElement.appendChild(stageDiv);


            // Recursively process next links
            if (chainLink.evolves_to && chainLink.evolves_to.length > 0) {
                 // If branching evolution, create a sub-container? For now, just append linearly.
                 // More complex branching might need different layout logic.
                chainLink.evolves_to.forEach(nextLink => processChain(nextLink, parentElement)); // Pass same parent for linear display
            }
        }

        processChain(chainData, chainWrapper); // Start processing
        containerElement.appendChild(chainWrapper);

        // Add event listener (no change needed here, still listens on containerElement)
        containerElement.addEventListener('click', async (event) => {
             const link = event.target.closest('.evolution-link');
            if (link && link.dataset.id) {
                event.preventDefault();
                const targetId = link.dataset.id;
                console.log(`Evolution link clicked: ${targetId}`);
                showDetailLoading(true);
                // Pass the result of renderPokemonDetail back to the recursive call
                const evoContainer = await openPokemonDetailModal(targetId);
                 // This assumes openPokemonDetailModal now returns the evolution container element
                 // We might need to adjust openPokemonDetailModal slightly if not.
                 // For simplicity now, we rely on openPokemonDetailModal handling the full render including the chain fetch.
            }
        });
    }

    // Modified openPokemonDetailModal to pass container to renderEvolutionChain
    async function openPokemonDetailModal(pokemonIdOrName) {
        showDetailLoading(true);
        modal.style.display = 'block';
        modalContent.innerHTML = ''; // Clear previous content

        let evolutionContainerElement = null; // To store the element where the chain should be rendered

        try {
            const pokemonData = await fetchData(`${API_BASE_URL}/pokemon/${pokemonIdOrName}`);
            if (!pokemonData) {
                throw new Error(`Pokémon "${pokemonIdOrName}" not found.`);
            }
            console.log("Fetched detail data:", pokemonData);
            // **renderPokemonDetail now returns the evolution container element**
            evolutionContainerElement = renderPokemonDetail(pokemonData);

            if (pokemonData.evolution_chain_url && evolutionContainerElement) {
                console.log(`Fetching evolution chain from: ${pokemonData.evolution_chain_url}`);
                try {
                    const evolutionData = await fetchData(pokemonData.evolution_chain_url);
                    if (evolutionData && evolutionData.chain) {
                        console.log("Fetched evolution data:", evolutionData);
                        renderEvolutionChain(evolutionData.chain, evolutionContainerElement); // Render into the specific container
                    } else {
                         if (evolutionContainerElement) evolutionContainerElement.innerHTML = '<p>Could not load evolution data.</p>';
                    }
                } catch (evoError) {
                     console.error("Error fetching evolution chain:", evoError);
                      if (evolutionContainerElement) evolutionContainerElement.innerHTML = `<p>Error loading evolution data: ${evoError.message}</p>`;
                }
            } else {
                 if (evolutionContainerElement) evolutionContainerElement.innerHTML = '<p>No evolution chain data available.</p>';
                 else console.warn("Evolution container element not found after rendering details.");
            }

        } catch (error) {
            console.error("Error opening detail modal:", error);
            modalContent.innerHTML = `<p class="error">Could not load details for ${pokemonIdOrName}. ${error.message}</p>`;
             evolutionContainerElement = null; // Ensure it's null on error
        } finally {
            showDetailLoading(false);
        }
         // Return the container element (might be null if initial render failed)
         // This isn't strictly needed anymore if the click just re-runs openPokemonDetailModal fully
         // return evolutionContainerElement;
    }

    function closePokemonDetailModal() {
        modal.style.display = 'none';
        modalContent.innerHTML = ''; // Clear content on close
    }

    // --- Loading Indicators ---
    function showLoading(isLoading) {
        loadingIndicator.style.display = isLoading ? 'block' : 'none';
    }
    function showDetailLoading(isLoading) {
        // Ensure modal content is cleared ONLY if loading is true and there's no content yet
        // Or handle clearing within openPokemonDetailModal
        detailLoadingIndicator.style.display = isLoading ? 'block' : 'none';
    }


    // --- Event Listeners Setup ---
    function setupEventListeners() {
        // Use debounced filter for search input
        searchInput.addEventListener('input', debouncedApplyFilters);

        // Use regular filter for dropdown and checkboxes (immediate change)
        generationFilter.addEventListener('change', applyFilters);

        // Event delegation for type checkboxes
        typeFilterFieldset.addEventListener('change', (event) => {
            if (event.target.matches('input[type="checkbox"].type-filter-checkbox')) {
                applyFilters();
            }
        });

        // Event delegation for clicking Pokémon cards
        pokedexList.addEventListener('click', (event) => {
            const card = event.target.closest('.pokemon-card');
            if (card && card.dataset.id) {
                openPokemonDetailModal(card.dataset.id); // Use ID for fetching detail
            }
        });

        // Modal close button
        closeModalButton.addEventListener('click', closePokemonDetailModal);

        // Close modal if clicking outside the content area
        modal.addEventListener('click', (event) => {
            if (event.target === modal) { // Check if the click is directly on the modal backdrop
                closePokemonDetailModal();
            }
        });

        // Close modal on 'Escape' key press
        window.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && modal.style.display === 'block') {
                closePokemonDetailModal();
            }
        });
    }

    // --- Start the application ---
    initializeApp();

}); // End DOMContentLoaded