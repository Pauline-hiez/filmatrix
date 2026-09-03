let searchDebounceTimer = null;

const movieSearchInput = document.getElementById("movie-search-input");
const movieResultsBox = document.getElementById("movie-search-results");
const characterResultsBox = document.getElementById("character-search-results");
const contentTypeSelect = document.getElementById("content-type-select");
const characterNameInput = document.getElementById("character-name-input");
const characterImageInput = document.getElementById("character-image-input");
const characterImagePreview = document.getElementById("character-image-preview");
let framePreview = document.getElementById("character-frame-preview");
let imagePreview = characterImagePreview ? characterImagePreview.querySelector("img:not(#character-frame-preview)") : null;
const imageX = document.getElementById("image-x");
const imageY = document.getElementById("image-y");
const imageScale = document.getElementById("image-scale");
const frameX = document.getElementById("frame-x");
const frameY = document.getElementById("frame-y");
const frameScale = document.getElementById("frame-scale");
const imageXValue = document.getElementById("image-x-value");
const imageYValue = document.getElementById("image-y-value");
const imageScaleValue = document.getElementById("image-scale-value");
const frameXValue = document.getElementById("frame-x-value");
const frameYValue = document.getElementById("frame-y-value");
const frameScaleValue = document.getElementById("frame-scale-value");
const frameSettingsLabel = document.getElementById("image-settings-label");

function updateFramePreview() {
    imagePreview = characterImagePreview ? characterImagePreview.querySelector("img:not(#character-frame-preview)") : null;
    framePreview = characterImagePreview ? characterImagePreview.querySelector("#character-frame-preview") : null;
    if (!imagePreview || !framePreview) return;
    const ix = Number(imageX.value);
    const iy = Number(imageY.value);
    const is = Number(imageScale.value);
    const fx = Number(frameX.value);
    const fy = Number(frameY.value);
    const fs = Number(frameScale.value);
    imagePreview.style.width = `${is}%`;
    imagePreview.style.height = `${is}%`;
    imagePreview.style.left = `${50 + ix - is / 2}%`;
    imagePreview.style.top = `${50 + iy - is / 2}%`;
    imagePreview.style.zIndex = "1";
    framePreview.style.width = `${fs}%`;
    framePreview.style.height = `${fs}%`;
    framePreview.style.left = `${50 + fx - fs / 2}%`;
    framePreview.style.top = `${50 + fy - fs / 2}%`;
    framePreview.style.zIndex = "2";
    imageXValue.value = ix;
    imageYValue.value = iy;
    imageScaleValue.value = is;
    frameXValue.value = fx;
    frameYValue.value = fy;
    frameScaleValue.value = fs;
    frameSettingsLabel.textContent = `Image : ${ix} / ${iy} · ${is}% — Cadre : ${fx} / ${fy} · ${fs}%`;
}

[imageX, imageY, imageScale, frameX, frameY, frameScale].forEach(function (control) {
    if (control) control.addEventListener("input", updateFramePreview);
});
updateFramePreview();

if (characterImageInput && characterImagePreview) {
    characterImageInput.addEventListener("change", function () {
        const file = characterImageInput.files[0];
        if (!file) return;

        const imageUrl = URL.createObjectURL(file);
        characterImagePreview.innerHTML = `
            <img src="${imageUrl}" alt="Aperçu du personnage" class="absolute object-cover" style="inset: 0; width: 100%; height: 100%; z-index: 1;">
            <img id="character-frame-preview" src="/static/images/habillage/rarete.png" alt="Cadre de rareté" class="pointer-events-none absolute object-contain" style="width: 100%; height: 100%; left: 0; top: 0; z-index: 2;">
        `;
        updateFramePreview();
    });
}

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

        const isSerie = movie.media_type === "serie";
        const typeBadge = isSerie
            ? '<span class="ml-auto shrink-0 rounded-full border border-emerald-400/40 bg-emerald-400/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-emerald-300">Série</span>'
            : '<span class="ml-auto shrink-0 rounded-full border border-cyan-400/40 bg-cyan-400/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-cyan-300">Film</span>';

        item.innerHTML = `
            ${thumbnailHtml}
            <span class="min-w-0 flex-1 truncate text-sm text-slate-100">${movie.title} <span class="text-slate-500">(${movie.year})</span></span>
            ${typeBadge}
        `;

        item.addEventListener("click", async function () {
            // Le casting TMDB dépend du type : une série doit interroger
            // l'endpoint /tv, sinon aucun personnage n'est trouvé.
            if (contentTypeSelect) {
                contentTypeSelect.value = isSerie ? "serie" : "film";
            }
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
            if (characterImagePreview) {
                characterImagePreview.innerHTML = `
                    <img src="${character.photo_url}" alt="Aperçu du personnage" class="absolute object-cover" style="inset: 0; width: 100%; height: 100%; z-index: 1;">
                    <img id="character-frame-preview" src="/static/images/habillage/rarete.png" alt="Cadre de rareté" class="pointer-events-none absolute object-contain" style="width: 100%; height: 100%; left: 0; top: 0; z-index: 2;">
                `;
                updateFramePreview();
            }

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

// ---- Fragments requis : auto-remplissage selon la rareté ----

// Miroir JS de RARITY_FRAGMENT_COSTS (filmatrix/catalog_rarities.py).
const RARITY_FRAGMENT_COSTS = {
    commun: 3,
    rare: 5,
    epique: 7,
    legendaire: 8,
    mythique: 9,
};

const raritySelect = document.getElementById("rarity-select");
const fragmentsInput = document.getElementById("fragments-required-input");
const fragmentsHint = document.getElementById("fragments-hint");
const autoFragmentsCheckbox = document.getElementById("auto-fragments");

function applyRarityFragments() {
    if (!raritySelect || !fragmentsInput) return;
    const cost = RARITY_FRAGMENT_COSTS[raritySelect.value];
    if (!cost) return;

    fragmentsInput.value = cost;
    if (fragmentsHint) {
        const labels = {
            commun: "Commun",
            rare: "Rare",
            epique: "Épique",
            legendaire: "Légendaire",
            mythique: "Mythique",
        };
        fragmentsHint.textContent = `Valeur par défaut « ${labels[raritySelect.value]} » : ${cost} fragments (modifiable en décochant l'auto).`;
    }
}

if (raritySelect && fragmentsInput && autoFragmentsCheckbox) {
    raritySelect.addEventListener("change", function () {
        if (autoFragmentsCheckbox.checked) {
            applyRarityFragments();
        }
    });

    // Passer en manuel dès que l'admin touche au champ lui-même.
    fragmentsInput.addEventListener("input", function () {
        autoFragmentsCheckbox.checked = false;
        if (fragmentsHint) fragmentsHint.textContent = "";
    });

    autoFragmentsCheckbox.addEventListener("change", function () {
        if (autoFragmentsCheckbox.checked) {
            applyRarityFragments();
        } else if (fragmentsHint) {
            fragmentsHint.textContent = "";
        }
    });

    // À l'ouverture : en création, la rareté affichée s'applique tout de
    // suite. En modification, une valeur qui ne correspond plus à la rareté
    // est un choix manuel historique : on repasse en manuel pour le respecter.
    const formAction = document.querySelector("form[action]")?.action || "";
    const isEdit = formAction.includes("character_id=");
    const currentCost = RARITY_FRAGMENT_COSTS[raritySelect.value];
    if (currentCost && Number(fragmentsInput.value) !== currentCost) {
        if (isEdit) {
            autoFragmentsCheckbox.checked = false;
        } else {
            applyRarityFragments();
        }
    }
}