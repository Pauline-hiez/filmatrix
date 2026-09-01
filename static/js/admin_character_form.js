let searchDebounceTimer = null;

const movieSearchInput = document.getElementById("movie-search-input");
const movieResultsBox = document.getElementById("movie-search-results");
const characterResultsBox = document.getElementById("character-search-results");
const contentTypeSelect = document.getElementById("content-type-select");
const characterNameInput = document.getElementById("character-name-input");
const characterImageInput = document.getElementById("character-image-input");

movieSearchInput.addEventListener("input", function () {
    const query = movieSearchInput.value.trim();

    clearTimeout(searchDebounceTimer);

    if (query.length < 2) {
        movieResultsBox.classList.add("hidden");
        movieResultsBox.innerHTML = "";
        return;
    }

    searchDebounceTimer = setTimeout(async function () {
        const response = await fetch(`/admin/api/recherche-film?query=${encodeURIComponent(query)}`);
        const data = await response.json();

        displayMovieResults(data.results);
    }, 350);
});

function displayMovieResults(movies) {
    if (movies.length === 0) {
        movieResultsBox.innerHTML = '<p class="text-sm text-slate-500 px-3 py-2">Aucun résultat.</p>';
        movieResultsBox.classList.remove("hidden");
        return;
    }

    movieResultsBox.innerHTML = "";

    movies.forEach(function (movie) {
        const item = document.createElement("button");
        item.type = "button";
        item.className = "w-full flex items-center gap-3 px-3 py-2 hover:bg-slate-800 transition text-left";

        const thumbnailHtml = movie.thumbnail_url
            ? `<img src="${movie.thumbnail_url}" class="w-8 h-12 object-cover rounded">`
            : `<div class="w-8 h-12 bg-slate-800 rounded flex items-center justify-center text-xs text-slate-500">?</div>`;

        item.innerHTML = `
            ${thumbnailHtml}
            <span class="text-sm text-slate-100">${movie.title} <span class="text-slate-500">(${movie.year})</span></span>
        `;

        item.addEventListener("click", async function () {
            movieResultsBox.classList.add("hidden");
            await loadCharactersForMovie(movie.id);
        });

        movieResultsBox.appendChild(item);
    });

    movieResultsBox.classList.remove("hidden");
}

async function loadCharactersForMovie(movieId) {
    const contentType = contentTypeSelect.value;
    const response = await fetch(`/admin/api/recherche-personnages?movie_id=${movieId}&content_type=${contentType}`);
    const data = await response.json();

    if (!data.success) {
        alert(data.error);
        return;
    }

    displayCharacterResults(data.characters);
}

function displayCharacterResults(characters) {
    if (characters.length === 0) {
        characterResultsBox.innerHTML = '<p class="text-sm text-slate-500 col-span-full">Aucun personnage trouvé avec photo.</p>';
        characterResultsBox.classList.remove("hidden");
        return;
    }

    characterResultsBox.innerHTML = "";

    characters.forEach(function (character) {
        const item = document.createElement("button");
        item.type = "button";
        item.className = "flex flex-col items-center gap-1 p-2 rounded-lg hover:bg-slate-800 transition text-center";
        item.innerHTML = `
            <img src="${character.photo_url}" class="w-16 h-20 object-cover rounded-lg border border-cyan-400/30">
            <span class="text-xs text-slate-200">${character.character_name}</span>
            <span class="text-[10px] text-slate-500">${character.actor_name}</span>
        `;

        item.addEventListener("click", function () {
            characterNameInput.value = character.character_name;
            characterImageInput.value = character.photo_url;

            document.querySelectorAll("#character-search-results button").forEach(function (button) {
                button.classList.remove("bg-cyan-400/20", "border", "border-cyan-400");
            });
            item.classList.add("bg-cyan-400/20", "border", "border-cyan-400");
        });

        characterResultsBox.appendChild(item);
    });

    characterResultsBox.classList.remove("hidden");
}

document.addEventListener("click", function (event) {
    if (!movieSearchInput.contains(event.target) && !movieResultsBox.contains(event.target)) {
        movieResultsBox.classList.add("hidden");
    }
});