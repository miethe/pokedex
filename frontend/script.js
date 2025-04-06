// frontend/script.js

document.addEventListener('DOMContentLoaded', () => {
    // --- Configuration & State ---
    const API_BASE_URL = '/api'; // Relative URL, Nginx will proxy
    let allPokemonData = [];
    let generationsData = [];
    let typesData = [];
    let currentDetailPokemon = null; // Keep track of which detail is shown

    // --- DOM Element References ---
    const searchInput = document.getElementById('search-input');
    const generationFilter = document.getElementById('generation-filter');
    const typeFilterContainer = document.getElementById('type-checkboxes-container');
    const typeFilterFieldset = document.getElementById('type-filter');
    const pokedexListContainer = document.getElementById('pokedex-list');
    const loadingIndicator = document.getElementById('loading-indicator');

    // Modal specific elements
    const modal = document.getElementById('pokemon-detail-modal');
    const modalContent = document.getElementById('pokemon-detail-content'); // Content area inside modal
    const detailLoadingIndicator = document.getElementById('detail-loading-indicator');
    const closeModalButton = modal.querySelector('.close-button');

    // --- Initialization ---
    async function initializeApp() {
        console.log("Initializing Pokedex App...");
        showListLoading(true);

        try {
            const [summary, generations, types] = await Promise.all([
                fetchData(`${API_BASE_URL}/pokedex/summary`),
                fetchData(`${API_BASE_URL}/generations`),
                fetchData(`${API_BASE_URL}/types`)
            ]);

            if (!summary || !generations || !types) {
                throw new Error("Failed to fetch initial data from the backend API.");
            }

            allPokemonData = summary;
            generationsData = generations.sort((a, b) => a.id - b.id);
            typesData = types.sort((a, b) => a.name.localeCompare(b.name));

            console.log(`Fetched ${allPokemonData.length} Pokémon summaries.`);
            populateGenerationsFilter(generationsData);
            populateTypesFilter(typesData);
            renderPokemonList(allPokemonData);
            setupEventListeners();

        } catch (error) {
            console.error("Initialization failed:", error);
            pokedexListContainer.innerHTML = `<p class="error">Could not load Pokedex data. Please try refreshing the page. (${error.message})</p>`;
        } finally {
            showListLoading(false);
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
            throw error;
        }
    }

    // --- Rendering Functions (Main List & Filters) ---

    function populateGenerationsFilter(generations) {
        generationFilter.innerHTML = '<option value="">All Generations</option>';
        generations.forEach(gen => {
            const option = document.createElement('option');
            option.value = gen.id;
            const roman = gen.name.split('-')[1]?.toUpperCase() || gen.id; // Handle potential missing part
            option.textContent = `Generation ${roman}`; // Simpler name
            generationFilter.appendChild(option);
        });
    }

    function populateTypesFilter(types) {
        typeFilterContainer.innerHTML = '';
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
            label.textContent = type.name;
            div.appendChild(checkbox);
            div.appendChild(label);
            typeFilterContainer.appendChild(div);
        });
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
                typeSpan.textContent = typeInfo.name;
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
        const selectedGeneration = generationFilter.value;
        const selectedTypes = Array.from(typeFilterContainer.querySelectorAll('input[type="checkbox"]:checked'))
                                   .map(checkbox => checkbox.value);

        const filteredPokemon = allPokemonData.filter(pokemon => {
            const generationMatch = !selectedGeneration || pokemon.generation_id === parseInt(selectedGeneration);
            const typeMatch = selectedTypes.length === 0 || selectedTypes.every(selectedType =>
                pokemon.types.some(pokemonType => pokemonType.name === selectedType)
            );
            const searchMatch = !searchTerm ||
                                pokemon.name.toLowerCase().includes(searchTerm) ||
                                String(pokemon.id).includes(searchTerm);
            return generationMatch && typeMatch && searchMatch;
        });
        renderPokemonList(filteredPokemon);
    }

    function debounce(func, delay) {
        let timeoutId;
        return (...args) => {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => { func.apply(this, args); }, delay);
        };
    }
    const debouncedApplyFilters = debounce(applyFilters, 300);

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

        // Create the main detail view container
        const detailView = document.createElement('div');
        detailView.classList.add('pokemon-detail-view');

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

        mainSpriteContainer.appendChild(mainSprite);

        // --- Sprite Gallery ---
        const spriteGallery = document.createElement('div');
        spriteGallery.classList.add('sprite-gallery');
        const gallerySpritesData = [
            // Add sprites in desired order, checking if URL exists
            { type: "Animated Default", url: data.sprites?.animated_front_default },
            { type: "Default", url: data.sprites?.front_default },
            { type: "Shiny", url: data.sprites?.front_shiny },
            { type: "Animated Shiny", url: data.sprites?.animated_front_shiny },
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
                ${data.types.map(t => `<span class="type type-${t.name}">${t.name}</span>`).join(' ')}
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

    // --- Event Listeners Setup ---
    function setupEventListeners() {
        searchInput.addEventListener('input', debouncedApplyFilters);
        generationFilter.addEventListener('change', applyFilters);
        typeFilterFieldset.addEventListener('change', (event) => {
            if (event.target.matches('input[type="checkbox"].type-filter-checkbox')) {
                applyFilters();
            }
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
    }

    // --- Start the application ---
    initializeApp();

}); // End DOMContentLoaded