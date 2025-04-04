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

    async function openPokemonDetailModal(pokemonIdOrName) {
        showDetailLoading(true);
        modal.style.display = 'block'; // Show modal structure
        modalContent.innerHTML = ''; // Clear previous content immediately

        try {
            const pokemonData = await fetchData(`${API_BASE_URL}/pokemon/${pokemonIdOrName}`);
            if (!pokemonData) {
                throw new Error(`Pokémon "${pokemonIdOrName}" not found.`);
            }
            console.log("Fetched detail data:", pokemonData);
            renderPokemonDetail(pokemonData);

            // Now fetch evolution chain data using the URL from pokemonData
            if (pokemonData.evolution_chain_url) {
                // Add a placeholder for evolution chain while fetching
                const evoPlaceholder = document.createElement('div');
                evoPlaceholder.id = 'evolution-chain-placeholder';
                evoPlaceholder.innerHTML = '<h3>Evolution Chain</h3><p>Loading evolution chain...</p>';
                modalContent.appendChild(evoPlaceholder); // Append to the end of details

                console.log(`Fetching evolution chain from: ${pokemonData.evolution_chain_url}`);
                try {
                    const evolutionData = await fetchData(pokemonData.evolution_chain_url);
                    if (evolutionData) {
                        console.log("Fetched evolution data:", evolutionData);
                        renderEvolutionChain(evolutionData.chain, evoPlaceholder); // Render into the placeholder
                    } else {
                        evoPlaceholder.innerHTML = '<h3>Evolution Chain</h3><p>Could not load evolution data.</p>';
                    }
                } catch (evoError) {
                     console.error("Error fetching evolution chain:", evoError);
                     evoPlaceholder.innerHTML = `<h3>Evolution Chain</h3><p>Error loading evolution data: ${evoError.message}</p>`;
                }
            } else {
                 const noEvoDiv = document.createElement('div');
                 noEvoDiv.innerHTML = '<h3>Evolution Chain</h3><p>No evolution chain data available.</p>';
                 modalContent.appendChild(noEvoDiv);
            }

        } catch (error) {
            console.error("Error opening detail modal:", error);
            modalContent.innerHTML = `<p class="error">Could not load details for ${pokemonIdOrName}. ${error.message}</p>`;
        } finally {
            showDetailLoading(false); // Hide loading indicator regardless of success/failure
        }
    }

    function renderPokemonDetail(data) {
        modalContent.innerHTML = ''; // Clear previous content/loading indicator

        // --- Basic Info Header ---
        const header = document.createElement('div');
        header.classList.add('detail-header');
        header.innerHTML = `
            <h2 class="detail-name">${data.name} (#${String(data.id).padStart(4, '0')})</h2>
            <p class="detail-genus">${data.genus || 'Unknown Genus'}</p>
            <div class="detail-types">
                ${data.types.map(t => `<span class="type type-${t.name}">${t.name}</span>`).join(' ')}
            </div>
        `;
        modalContent.appendChild(header);

        // --- Main Content Grid (Sprites, Physical, etc.) ---
        const mainGrid = document.createElement('div');
        mainGrid.classList.add('detail-main-grid');

        // --- Sprites Section ---
        const spritesSection = document.createElement('div');
        spritesSection.classList.add('detail-sprites');
        spritesSection.innerHTML = `
            <h3>Sprites</h3>
            <div class="sprite-gallery">
                ${data.sprites.official_artwork ? `<img src="${data.sprites.official_artwork}" alt="${data.name} Official Artwork" title="Official Artwork">` : ''}
                ${data.sprites.front_default ? `<img src="${data.sprites.front_default}" alt="${data.name} Default Sprite" title="Default">` : ''}
                ${data.sprites.front_shiny ? `<img src="${data.sprites.front_shiny}" alt="${data.name} Shiny Sprite" title="Shiny">` : ''}
                ${data.sprites.back_default ? `<img src="${data.sprites.back_default}" alt="${data.name} Back Sprite" title="Back Default">` : ''}
                ${data.sprites.back_shiny ? `<img src="${data.sprites.back_shiny}" alt="${data.name} Back Shiny Sprite" title="Back Shiny">` : ''}
                ${!data.sprites.official_artwork && !data.sprites.front_default ? '<p>No sprites available.</p>' : ''}
            </div>
        `;
        mainGrid.appendChild(spritesSection);

        // --- Physical Attributes Section ---
        const physicalSection = document.createElement('div');
        physicalSection.classList.add('detail-physical');
        physicalSection.innerHTML = `
            <h3>Physical Attributes</h3>
            <p><strong>Height:</strong> ${data.height / 10} m</p> <!-- Convert decimeters to meters -->
            <p><strong>Weight:</strong> ${data.weight / 10} kg</p> <!-- Convert hectograms to kilograms -->
            <p><strong>Base Exp:</strong> ${data.base_experience || 'N/A'}</p>
            <p><strong>Growth Rate:</strong> ${data.growth_rate_name ? data.growth_rate_name.replace('-', ' ') : 'N/A'}</p>
            <p><strong>Shape:</strong> ${data.shape || 'N/A'}</p>
            <p><strong>Habitat:</strong> ${data.habitat || 'N/A'}</p>
        `;
        mainGrid.appendChild(physicalSection);

        modalContent.appendChild(mainGrid); // Add grid to modal

        // --- Description Section ---
        const descriptionSection = document.createElement('div');
        descriptionSection.classList.add('detail-description');
        // Find a recent English flavor text (e.g., from a recent game version if possible)
        const flavorTextEntry = data.flavor_text_entries?.find(entry => entry.language?.name === 'en'); // Simple find first english
        // More robust: Find one from a specific version if needed
        // const flavorTextEntry = data.flavor_text_entries?.find(entry => entry.language?.name === 'en' && entry.version?.name === 'scarlet');
        descriptionSection.innerHTML = `
            <h3>Description</h3>
            <p>${flavorTextEntry ? flavorTextEntry.flavor_text.replace(/[\n\f]/g, ' ') : 'No description available.'}</p>
        `;
        modalContent.appendChild(descriptionSection);


        // --- Abilities Section ---
        const abilitiesSection = document.createElement('div');
        abilitiesSection.classList.add('detail-abilities');
        abilitiesSection.innerHTML = `
            <h3>Abilities</h3>
            <ul>
                ${data.abilities.map(a => `<li>${a.name.replace('-', ' ')}</li>`).join('')}
            </ul>
        `;
        modalContent.appendChild(abilitiesSection);

        // --- Base Stats Section ---
        const statsSection = document.createElement('div');
        statsSection.classList.add('detail-stats');
        statsSection.innerHTML = `<h3>Base Stats</h3>`;
        const statsList = document.createElement('ul');
        statsList.classList.add('stats-list');
        const maxStatValue = 255; // Max possible base stat value for scaling bars
        data.stats.forEach(stat => {
            const percentage = (stat.base_stat / maxStatValue) * 100;
            const statItem = document.createElement('li');
            statItem.innerHTML = `
                <span class="stat-name">${stat.name.replace('-', ' ')}:</span>
                <span class="stat-value">${stat.base_stat}</span>
                <div class="stat-bar-container">
                    <div class="stat-bar" style="width: ${percentage}%;"></div>
                </div>
            `;
            statsList.appendChild(statItem);
        });
        statsSection.appendChild(statsList);
        modalContent.appendChild(statsSection);

        // --- Breeding & Classification Section ---
        const breedingSection = document.createElement('div');
        breedingSection.classList.add('detail-breeding');
        // Gender calculation (based on rate: -1 = genderless, 0 = 100% male, 8 = 100% female, 1-7 = ratio)
        let genderRatio = 'Genderless';
        if (data.gender_rate > 0 && data.gender_rate < 8) {
            const femaleChance = (data.gender_rate / 8) * 100;
            const maleChance = 100 - femaleChance;
            genderRatio = `${maleChance}% Male, ${femaleChance}% Female`;
        } else if (data.gender_rate === 0) {
            genderRatio = '100% Male';
        } else if (data.gender_rate === 8) {
            genderRatio = '100% Female';
        }

        breedingSection.innerHTML = `
            <h3>Breeding & Classification</h3>
            <p><strong>Gender Ratio:</strong> ${genderRatio}</p>
            <p><strong>Egg Groups:</strong> ${data.egg_groups.map(eg => eg.name).join(', ') || 'N/A'}</p>
            <p><strong>Classification:</strong> ${data.is_legendary ? 'Legendary' : data.is_mythical ? 'Mythical' : 'Normal'} Pokémon</p>
        `;
        modalContent.appendChild(breedingSection);

        // Evolution Chain placeholder will be populated later
    }

    function renderEvolutionChain(chainData, containerElement) {
        console.log("Rendering evolution chain:", chainData);
        containerElement.innerHTML = '<h3>Evolution Chain</h3>'; // Clear loading text
        const chainList = document.createElement('ul');
        chainList.classList.add('evolution-chain');

        function processChain(chainLink, level = 0) {
            const listItem = document.createElement('li');
            listItem.style.paddingLeft = `${level * 20}px`; // Indent based on level

            const pokemonName = chainLink.species.name;
            const pokemonId = chainLink.species.url.split('/').filter(Boolean).pop(); // Extract ID from URL

            const link = document.createElement('a');
            link.href = '#'; // Prevent navigation
            link.textContent = `${pokemonName} (#${pokemonId})`;
            link.dataset.id = pokemonId; // Store ID for potential click
            link.classList.add('evolution-link');

            // Add basic sprite - fetch it on the fly (simple example)
            const img = document.createElement('img');
            img.src = `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${pokemonId}.png`;
            img.alt = pokemonName;
            img.classList.add('evolution-sprite');
            img.loading = 'lazy'; // Lazy load images

            listItem.appendChild(img);
            listItem.appendChild(link);


            // Basic evolution trigger text (can be expanded with API details if needed)
            if (chainLink.evolution_details && chainLink.evolution_details.length > 0) {
                const details = chainLink.evolution_details[0]; // Usually just one entry
                let triggerText = '';
                 if (details.min_level) triggerText += `Lv. ${details.min_level}`;
                 else if (details.item) triggerText += `Use ${details.item.name.replace('-', ' ')}`;
                 else if (details.trigger) triggerText += `(${details.trigger.name.replace('-', ' ')})`;
                 else triggerText = '(Special)';

                 const triggerSpan = document.createElement('span');
                 triggerSpan.textContent = ` → ${triggerText}`;
                 triggerSpan.classList.add('evolution-trigger');
                 listItem.appendChild(triggerSpan);
            }

            chainList.appendChild(listItem);

            // Recursively process next links in the chain
            if (chainLink.evolves_to && chainLink.evolves_to.length > 0) {
                chainLink.evolves_to.forEach(nextLink => processChain(nextLink, level + 1));
            }
        }

        processChain(chainData); // Start processing from the root of the chain
        containerElement.appendChild(chainList);

        // Add event listener for clicking evolution links within the modal
        chainList.addEventListener('click', async (event) => {
            if (event.target.classList.contains('evolution-link')) {
                event.preventDefault();
                const targetId = event.target.dataset.id;
                if (targetId) {
                    console.log(`Evolution link clicked: ${targetId}`);
                    // Close current modal immediately? Or replace content? Let's replace.
                    showDetailLoading(true); // Show loading indicator again
                    await openPokemonDetailModal(targetId); // Fetch and render the new Pokémon
                }
            }
        });
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