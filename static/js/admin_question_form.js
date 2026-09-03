// Enveloppé dans une IIFE : ce script est réinjecté à chaque ouverture de la
// modale d'édition (static/js/admin_question_modal.js), avec un paramètre
// anti-cache qui force le navigateur à le réexécuter. Sans cette IIFE, les
// "const" du haut de fichier entreraient en collision avec ceux de
// l'exécution précédente ("Identifier ... has already been declared") dès la
// deuxième ouverture de la modale.
(function () {
const modeSelect = document.getElementById("mode-select");
const allModeFieldGroups = document.querySelectorAll(".mode-fields");
const form = document.getElementById("question-form");
const tagSearch = document.getElementById("tag-search");
const tagCount = document.getElementById("selected-tags-count");
if (!form || !modeSelect) return;
const OPENMOJI_CATALOG_URL = "/static/assets/openmoji-catalog.json";
const OPENMOJI_REMOTE_URL = "https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/data/openmoji.json";
let OPENMOJI_CATALOG = [];
let showAllEmojis = false;
let activeEmojiCategory = "all";

// Un modificateur de teint ou de genre change le rendu de l'emoji, pas le mot
// qu'on tape pour le chercher : il ne doit pas non plus créer un doublon
// visuel côte à côte dans la grille (cf. scripts/download_openmoji_catalog.py,
// qui applique la même normalisation côté recherche française).
const EMOJI_SKIN_TONES = ["1F3FB", "1F3FC", "1F3FD", "1F3FE", "1F3FF"];

function normalizeEmojiCode(code) {
    return code.split("-").filter(function (part) {
        return part !== "FE0F" && EMOJI_SKIN_TONES.indexOf(part) === -1;
    }).join("-");
}

// Regroupement calqué sur les onglets d'un clavier de smartphone. « component »
// (teintes de peau et couleurs de cheveux isolées) n'a pas sa place ici : seul
// dans une question, un carré de couleur ne veut rien dire.
const EMOJI_CATEGORY_LABELS = {
    "smileys-emotion": "Émotions",
    "people-body": "Personnes",
    "animals-nature": "Animaux",
    "food-drink": "Nourriture",
    "travel-places": "Voyages",
    "activities": "Activités",
    "objects": "Objets",
    "symbols": "Symboles",
    "flags": "Drapeaux",
    "extras": "Autres",
};
const EMOJI_EXCLUDED_GROUPS = ["component"];
const EMOJI_GROUP_ALIASES = { "extras-openmoji": "extras", "extras-unicode": "extras" };

function updateTagCount() {
    const count = document.querySelectorAll(".tag-checkbox:checked").length;
    tagCount.textContent = `${count} sélectionné${count > 1 ? "s" : ""}`;
}

document.querySelectorAll(".tag-checkbox").forEach(function (checkbox) {
    checkbox.addEventListener("change", updateTagCount);
});

if (tagSearch) {
    tagSearch.addEventListener("input", function () {
        const query = tagSearch.value.trim().toLowerCase();
        document.querySelectorAll(".tag-option").forEach(function (option) {
            const visible = !query || option.dataset.tagName.includes(query);
            option.classList.toggle("hidden", !visible);
        });
        document.querySelectorAll(".tag-group").forEach(function (group) {
            const hasVisibleOption = group.querySelector(".tag-option:not(.hidden)");
            if (query && hasVisibleOption) {
                group.open = true;
            }
            group.classList.toggle("hidden", !hasVisibleOption);
        });
    });
}

updateTagCount();

const emojiCodesField = document.querySelector(".emoji-visual-codes");
const emojiPicker = document.querySelector(".emoji-picker");
const emojiPickerSearch = document.querySelector(".emoji-picker-search");
const emojiPickerToggle = document.getElementById("emoji-picker-toggle");
const emojiPickerCategories = document.getElementById("emoji-picker-categories");

function renderEmojiCategoryTabs() {
    if (!emojiPickerCategories) return;
    const presentGroups = new Set(OPENMOJI_CATALOG.map(function (item) { return item.group; }));
    const orderedGroups = Object.keys(EMOJI_CATEGORY_LABELS).filter(function (group) {
        return presentGroups.has(group);
    });

    emojiPickerCategories.innerHTML = "";
    [["all", "Tous"]].concat(orderedGroups.map(function (group) {
        return [group, EMOJI_CATEGORY_LABELS[group]];
    })).forEach(function (entry) {
        const [group, label] = entry;
        const tab = document.createElement("button");
        tab.type = "button";
        tab.textContent = label;
        tab.dataset.emojiCategory = group;
        tab.className = "rounded-full border px-3 py-1 text-xs font-bold transition " + (
            group === activeEmojiCategory
                ? "border-cyan-400 bg-cyan-400/10 text-cyan-300"
                : "border-slate-700 text-slate-400 hover:border-cyan-400/50 hover:text-slate-200"
        );
        tab.addEventListener("click", function () {
            activeEmojiCategory = group;
            renderEmojiCategoryTabs();
            renderEmojiPicker();
        });
        emojiPickerCategories.appendChild(tab);
    });
}

function renderEmojiPicker() {
    if (!emojiPicker) return;
    const query = (emojiPickerSearch ? emojiPickerSearch.value : "").trim().toLowerCase();
    emojiPicker.innerHTML = "";
    const matchingItems = OPENMOJI_CATALOG.filter(function (item) {
        const matchesCategory = activeEmojiCategory === "all" || item.group === activeEmojiCategory;
        const matchesQuery = !query || item.searchText.includes(query) || item.code.toLowerCase().includes(query);
        return matchesCategory && matchesQuery;
    });
    const items = query || showAllEmojis ? matchingItems : matchingItems.slice(0, 48);
    items.forEach(function (item) {
        const button = document.createElement("button");
        button.type = "button";
        button.title = item.name;
        button.dataset.code = item.code;
        button.className = "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-slate-700 bg-slate-900 p-1 transition hover:border-cyan-400 hover:bg-slate-800";
        // Le paquet npm @svgmoji/openmoji est figé à une ancienne version du jeu
        // d'icônes OpenMoji : les emojis ajoutés depuis y renvoient un 404 (ex.
        // 1FAE0, « visage qui fond »). Le dépôt GitHub d'origine, à la branche
        // master, est la même source que le catalogue de métadonnées : toujours
        // synchronisé, vérifié à 0 échec sur les 4565 entrées du catalogue.
        button.innerHTML = `<img src="https://cdn.jsdelivr.net/gh/hfg-gmuend/openmoji@master/color/svg/${item.code}.svg" alt="${item.name}" class="h-7 w-7 object-contain">`;
        button.addEventListener("click", function () {
            const codes = linesToArray(emojiCodesField.value);
            if (!codes.includes(item.code)) codes.push(item.code);
            emojiCodesField.value = codes.join("\\n");
            emojiCodesField.dispatchEvent(new Event("input"));
        });
        emojiPicker.appendChild(button);
    });
}

if (emojiPickerSearch) emojiPickerSearch.addEventListener("input", renderEmojiPicker);
if (emojiPickerToggle) {
    emojiPickerToggle.addEventListener("click", function () {
        showAllEmojis = !showAllEmojis;
        emojiPickerToggle.textContent = showAllEmojis ? "Afficher moins" : "Afficher tous les emojis";
        emojiPicker.classList.toggle("max-h-40", !showAllEmojis);
        emojiPicker.classList.toggle("max-h-96", showAllEmojis);
        renderEmojiPicker();
    });
}

fetch(OPENMOJI_CATALOG_URL)
    .catch(function () { return fetch(OPENMOJI_REMOTE_URL); })
    .then(function (response) {
        if (!response.ok) throw new Error("Catalogue HTTP " + response.status);
        return response.json();
    })
    .then(function (items) {
        const seenNormalizedCodes = new Set();
        OPENMOJI_CATALOG = items
            .filter(function (item) {
                return item.hexcode && item.annotation && EMOJI_EXCLUDED_GROUPS.indexOf(item.group) === -1;
            })
            .map(function (item) {
                // fr_name / fr_tags viennent des annotations françaises du CLDR,
                // ajoutées par scripts/download_openmoji_catalog.py : environ
                // deux tiers du catalogue en profite, le reste reste cherchable
                // en anglais (openmoji.json ne fournit que l'anglais nativement).
                const frenchTags = Array.isArray(item.fr_tags) ? item.fr_tags.join(" ") : "";
                return {
                    code: item.hexcode.toUpperCase(),
                    normalizedCode: normalizeEmojiCode(item.hexcode.toUpperCase()),
                    group: EMOJI_GROUP_ALIASES[item.group] || item.group,
                    name: item.fr_name || item.annotation,
                    // openmoji.json donne tags sous forme de chaîne « a, b, c », pas d'un
                    // tableau : un .join() dessus lève une exception et fait retomber tout
                    // le chargement sur la liste de secours à 32 emojis.
                    searchText: `${item.annotation} ${item.tags || ""} ${item.fr_name || ""} ${frenchTags}`.toLowerCase(),
                };
            })
            // Un même geste décliné en 5 teints de peau reste le même indice visuel :
            // un seul suffit dans la grille (cf. EMOJI_SKIN_TONES ci-dessus).
            .filter(function (item) {
                if (seenNormalizedCodes.has(item.normalizedCode)) return false;
                seenNormalizedCodes.add(item.normalizedCode);
                return true;
            });
        renderEmojiCategoryTabs();
        renderEmojiPicker();
    })
    .catch(function () {
        OPENMOJI_CATALOG = [
            ["1F9EA", "🧪", "science chimie"], ["1F4B0", "💰", "argent"],
            ["1F3F0", "🏰", "château royaume"], ["1F451", "👑", "roi reine couronne"],
            ["1F409", "🐉", "dragon"], ["2694", "⚔️", "épée combat"],
            ["1F47B", "👻", "fantôme"], ["1F608", "😈", "diable"],
            ["1F47D", "👽", "alien"], ["1F916", "🤖", "robot"],
            ["1F52A", "🔪", "couteau"], ["1F3AD", "🎭", "masque théâtre"],
            ["1F697", "🚗", "voiture"], ["1F680", "🚀", "fusée"],
            ["1F6A2", "🚢", "bateau"], ["1F3E0", "🏠", "maison"],
            ["1F3AC", "🎬", "cinéma film"], ["1F3B8", "🎸", "musique"],
            ["1F525", "🔥", "feu flamme"], ["1F30A", "🌊", "océan"],
            ["1F9DF", "🧟", "zombie"], ["1F47E", "👾", "monstre"],
            ["1F3B2", "🎲", "jeu dés"], ["1F6B2", "🚲", "vélo"],
            ["1F602", "😂", "rire comédie"], ["1F622", "😭", "tristesse"],
            ["0037-20E3", "7️⃣", "sept"], ["1F1EB-1F1F7", "🇫🇷", "France"],
            ["1F1FA-1F1F8", "🇺🇸", "États-Unis"], ["1F1EC-1F1E7", "🇬🇧", "Royaume-Uni"],
            ["1F1EA-1F1F8", "🇪🇸", "Espagne"], ["1F1E9-1F1EA", "🇩🇪", "Allemagne"]
        ].map(function (item) {
            return { code: item[0], name: item[2], searchText: item[2].toLowerCase() };
        });
        renderEmojiPicker();
    });

if (emojiCodesField) {
    emojiCodesField.addEventListener("input", function () {
        const preview = document.querySelector(".emoji-admin-preview");
        preview.innerHTML = "";
        linesToArray(emojiCodesField.value).forEach(function (code) {
            const image = document.createElement("img");
            image.src = `https://cdn.jsdelivr.net/gh/hfg-gmuend/openmoji@master/color/svg/${code.toUpperCase()}.svg`;
            image.referrerPolicy = "no-referrer";
            image.alt = "";
            image.className = "h-8 w-8 object-contain";
            preview.appendChild(image);
        });
    });
}

function renderSavedAudioOptions(fieldsGroup) {
    const optionsField = fieldsGroup.querySelector(".audio-options-json");
    const preview = fieldsGroup.querySelector("#audio-preview");
    if (!optionsField || !preview || !optionsField.value) return;
    let options;
    try { options = JSON.parse(optionsField.value); } catch (error) { return; }
    if (!Array.isArray(options) || !options.length) return;
    preview.innerHTML = options.map(function (option, index) {
        return `<label class="flex items-center gap-3 rounded-lg border border-slate-700 bg-slate-950/60 p-2 hover:border-cyan-400/60">
            <input type="radio" name="audio-choice" value="${index}" ${option.audio_url === fieldsGroup.querySelector(".audio-url").value ? "checked" : ""}>
            <span class="min-w-0 flex-1"><span class="block truncate text-sm text-slate-100">${option.label || "Extrait audio"}</span><span class="block truncate text-xs text-slate-500">${option.artist || option.album || "Source enregistrée"}</span></span>
            <audio controls preload="none" src="${option.audio_url}" class="h-8 max-w-[15rem]"></audio>
        </label>`;
    }).join("");
    preview.querySelectorAll('input[name="audio-choice"]').forEach(function (radio) {
        radio.addEventListener("change", function () {
            fieldsGroup.querySelector(".audio-url").value = options[parseInt(radio.value)].audio_url;
        });
    });
}

function showFieldsForMode(mode) {
    if (mode === "emoji" && emojiPicker) {
        emojiPicker.classList.remove("hidden");
    }
    allModeFieldGroups.forEach(function (group) {
        if (group.dataset.mode === mode) {
            group.classList.remove("hidden");
        } else {
            group.classList.add("hidden");
        }
    });
}

modeSelect.addEventListener("change", function () {
    showFieldsForMode(modeSelect.value);
    if (modeSelect.value === "blindtest") {
        renderSavedAudioOptions(document.querySelector('.mode-fields[data-mode="blindtest"]'));
    }
});

if (modeSelect.value) {
    showFieldsForMode(modeSelect.value);
    if (modeSelect.value === "blindtest") {
        renderSavedAudioOptions(document.querySelector('.mode-fields[data-mode="blindtest"]'));
    }
}

function shuffleArray(items) {
    const shuffled = [...items];
    for (let i = shuffled.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    return shuffled;
}

function linesToArray(textareaValue) {
    return textareaValue
        .split("\n")
        .map(function (line) {
            return line.trim();
        })
        .filter(function (line) {
            return line.length > 0;
        });
}

function buildPayloadAndAnswer(mode) {
    const activeGroup = document.querySelector(`.mode-fields[data-mode="${mode}"]`);

    if (mode === "qcm") {
        const options = Array.from(activeGroup.querySelectorAll(".qcm-option")).map(
            function (input) {
                return input.value;
            }
        );
        const selectedRadio = activeGroup.querySelector(".qcm-radio:checked");
        const correctIndex = selectedRadio ? parseInt(selectedRadio.value) : 0;
        return {
            payload: { options: options },
            correct_answer: { index: correctIndex },
        };
    }

    if (mode === "vrai_faux") {
        const selectedRadio = activeGroup.querySelector('input[name="vf_correct"]:checked');
        const value = selectedRadio ? selectedRadio.value === "true" : true;
        return {
            payload: {},
            correct_answer: { value: value },
        };
    }

    if (mode === "citation") {
        const film = activeGroup.querySelector(".film-answer").value;
        return { payload: {}, correct_answer: { film: film } };
    }

    if (mode === "emoji") {
        const film = activeGroup.querySelector(".film-answer").value;
        const codes = linesToArray(activeGroup.querySelector(".emoji-visual-codes").value)
            .map(function (value) { return value.toUpperCase(); });
        return {
            payload: { visuals: codes.map(function (value) {
                return { type: "openmoji", value: value };
            }) },
            correct_answer: { film: film },
        };
    }

    if (mode === "film_melange") {
        const title = activeGroup.querySelector(".film-melange-title").value;
        return {
            payload: {},
            correct_answer: { title: title },
        };
    }

    if (mode === "devinette") {
        const film = activeGroup.querySelector(".film-answer").value;
        const hints = linesToArray(activeGroup.querySelector(".riddle-hints").value);
        return {
            payload: { hints: hints },
            correct_answer: { film: film },
        };
    }

    if (mode === "devinette_affiche") {
        const film = activeGroup.querySelector(".film-answer").value;
        const posterUrl = activeGroup.querySelector(".poster-url").value;
        return {
            payload: { poster_url: posterUrl },
            correct_answer: { film: film },
        };
    }

    if (mode === "casting") {
        const film = activeGroup.querySelector(".film-answer").value;
        const hiddenField = activeGroup.querySelector(".actor-photos-hidden").value;
        const actorPhotos = hiddenField ? JSON.parse(hiddenField) : [];
        return {
            payload: { actor_photos: actorPhotos },
            correct_answer: { film: film },
        };
    }

    if (mode === "blindtest") {
        const film = activeGroup.querySelector(".film-answer").value;
        const audioUrl = activeGroup.querySelector(".audio-url").value;
        const optionsField = activeGroup.querySelector(".audio-options-json");
        const audioOptions = optionsField && optionsField.value ? JSON.parse(optionsField.value) : [];
        return {
            payload: { audio_url: audioUrl, audio_options: audioOptions },
            correct_answer: { film: film },
        };
    }

    if (mode === "chronologie") {
        const correctOrder = linesToArray(activeGroup.querySelector(".chronology-order").value);
        const shuffledFilms = shuffleArray(correctOrder);
        return {
            payload: { films: shuffledFilms },
            correct_answer: { order: correctOrder },
        };
    }

    return { payload: {}, correct_answer: {} };
}

form.addEventListener("submit", function (event) {
    const mode = modeSelect.value;

    if (!mode) {
        event.preventDefault();
        alert("Merci de choisir un mode de jeu.");
        return;
    }

    const result = buildPayloadAndAnswer(mode);

    document.getElementById("payload-input").value = JSON.stringify(result.payload);
    document.getElementById("visuals-input").value = JSON.stringify(result.payload.visuals || []);
    document.getElementById("correct-answer-input").value = JSON.stringify(result.correct_answer);
});

// ---- Autocomplétion de recherche de films (TMDB) ----

let searchDebounceTimer = null;

document.querySelectorAll(".movie-search-input").forEach(function (searchInput) {
    const resultsBox = searchInput.parentElement.querySelector(".movie-search-results");
    const target = searchInput.dataset.target;
    const fieldsGroup = searchInput.closest(".mode-fields");

    searchInput.addEventListener("input", function () {
        const query = searchInput.value.trim();

        clearTimeout(searchDebounceTimer);

        if (query.length < 2) {
            resultsBox.classList.add("hidden");
            resultsBox.innerHTML = "";
            return;
        }

        searchDebounceTimer = setTimeout(async function () {
            const response = await fetch(
                `/admin/api/recherche-film?query=${encodeURIComponent(query)}`
            );
            const data = await response.json();

            displaySearchResults(data.results, resultsBox, searchInput, target, fieldsGroup);
        }, 350);
    });

    document.addEventListener("click", function (event) {
        if (!searchInput.contains(event.target) && !resultsBox.contains(event.target)) {
            resultsBox.classList.add("hidden");
        }
    });
});

function displaySearchResults(movies, resultsBox, searchInput, target, fieldsGroup) {
    if (movies.length === 0) {
        resultsBox.innerHTML =
            '<p class="text-sm text-slate-500 px-3 py-2">Aucun résultat.</p>';
        resultsBox.classList.remove("hidden");
        return;
    }

    resultsBox.innerHTML = "";

    movies.forEach(function (movie) {
        const item = document.createElement("button");
        item.type = "button";
        item.className =
            "w-full flex items-center gap-3 px-3 py-2 hover:bg-slate-800 transition text-left";

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

        item.addEventListener("click", function () {
            // Le type d'œuvre sélectionné pilote les champs cachés et les
            // routes affiche/casting (film ou série sur TMDB).
            syncQuestionContentType(fieldsGroup, isSerie ? "serie" : "film");
            selectMovie(movie, target, fieldsGroup);
            resultsBox.classList.add("hidden");
        });

        resultsBox.appendChild(item);
    });

    resultsBox.classList.remove("hidden");
}

// Chaque bloc de mode porte son propre type d'œuvre (attribut data + champ
// caché) : la sélection d'un résultat le met à jour, et le type global du
// formulaire suit le dernier choix.
function syncQuestionContentType(fieldsGroup, contentType) {
    if (fieldsGroup) {
        fieldsGroup.dataset.contentType = contentType;
        const hidden = fieldsGroup.querySelector(".content-type-hidden");
        if (hidden) {
            hidden.value = contentType;
        }
    }
    document.querySelectorAll(".content-type-hidden").forEach(function (input) {
        input.value = contentType;
    });
    const select = document.getElementById("content-type-select");
    if (select) {
        select.value = contentType;
    }
}

// Pré-remplissage : à l'ouverture du formulaire (édition), le type sauvegardé
// de la question est réappliqué partout.
const savedContentType = document.getElementById("content-type-select");
if (savedContentType && savedContentType.value) {
    document.querySelectorAll(".mode-fields").forEach(function (group) {
        group.dataset.contentType = savedContentType.value;
    });
}

async function selectMovie(movie, target, fieldsGroup) {
    const filmAnswerField = fieldsGroup.querySelector(".film-answer");
    filmAnswerField.value = movie.title;

    if (target === "poster") {
        const contentType = (fieldsGroup && fieldsGroup.dataset.contentType) || "film";
        const response = await fetch(`/admin/api/recherche-affiche?movie_id=${movie.id}&content_type=${contentType}`);
        const data = await response.json();

        if (data.success) {
            fieldsGroup.querySelector(".poster-url").value = data.poster_url;
            const preview = document.getElementById("poster-preview");
            preview.innerHTML = `<img src="${data.poster_url}" class="w-full max-w-xs rounded-lg border border-cyan-400/30">`;
        } else {
            alert(data.error);
        }
    }

    if (target === "casting") {
        const contentType = (fieldsGroup && fieldsGroup.dataset.contentType) || "film";
        const response = await fetch(`/admin/api/recherche-casting?movie_id=${movie.id}&content_type=${contentType}`);
        const data = await response.json();

        if (data.success) {
            fieldsGroup.querySelector(".actor-photos-hidden").value = JSON.stringify(
                data.actor_photos
            );
            const preview = document.getElementById("cast-preview");
            preview.innerHTML = data.actor_photos
                .map(function (url) {
                    return `<img src="${url}" class="w-16 h-24 object-cover rounded-lg border border-cyan-400/30">`;
                })
                .join("");
        } else {
            alert(data.error);
        }
    }

    if (target === "audio") {
        const searchTermField = fieldsGroup.querySelector(".audio-search-term");
        const searchTerm = searchTermField ? searchTermField.value : "";

        const params = new URLSearchParams({ title: movie.title });
        if (searchTerm) {
            params.set("search_term", searchTerm);
        }

        const response = await fetch(`/admin/api/recherche-audio?${params.toString()}`);
        const data = await response.json();

        if (data.success) {
            fieldsGroup.querySelector(".audio-url").value = data.audio_url;
            fieldsGroup.querySelector(".audio-options-json").value = JSON.stringify(data.audio_options || []);
            const preview = fieldsGroup.querySelector("#audio-preview");
            preview.innerHTML = (data.audio_options || []).map(function (option, index) {
                return `<label class="flex items-center gap-3 rounded-lg border border-slate-700 bg-slate-950/60 p-2 hover:border-cyan-400/60">
                    <input type="radio" name="audio-choice" value="${index}" ${index === 0 ? "checked" : ""}>
                    <span class="min-w-0 flex-1"><span class="block truncate text-sm text-slate-100">${option.label}</span><span class="block truncate text-xs text-slate-500">${option.artist || option.album || "Source iTunes"}</span></span>
                    <audio controls preload="none" src="${option.audio_url}" class="h-8 max-w-[15rem]"></audio>
                </label>`;
            }).join("");
            preview.querySelectorAll('input[name="audio-choice"]').forEach(function (radio) {
                radio.addEventListener("change", function () {
                    const selected = data.audio_options[parseInt(radio.value)];
                    fieldsGroup.querySelector(".audio-url").value = selected.audio_url;
                });
            });
        } else {
            alert(data.error);
        }
    }
}
})();