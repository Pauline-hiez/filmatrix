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
    const selectedCodes = linesToArray(emojiCodesField ? emojiCodesField.value : "");
    items.forEach(function (item) {
        const isSelected = selectedCodes.includes(item.code);
        const button = document.createElement("button");
        button.type = "button";
        button.title = isSelected ? `${item.name} (cliquer pour retirer)` : item.name;
        button.dataset.code = item.code;
        button.className = "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border p-1 transition hover:border-cyan-400 hover:bg-slate-800 " + (
            isSelected ? "border-cyan-400 bg-cyan-400/10 ring-1 ring-cyan-400/60" : "border-slate-700 bg-slate-900"
        );
        // Le paquet npm @svgmoji/openmoji est figé à une ancienne version du jeu
        // d'icônes OpenMoji : les emojis ajoutés depuis y renvoient un 404 (ex.
        // 1FAE0, « visage qui fond »). Le dépôt GitHub d'origine, à la branche
        // master, est la même source que le catalogue de métadonnées : toujours
        // synchronisé, vérifié à 0 échec sur les 4565 entrées du catalogue.
        // jsDelivr (CDN devant ce dépôt) reste malgré tout un service tiers : une
        // grille en affiche jusqu'à ~48 d'un coup, et une requête isolée qui
        // échoue (limite de débit, aléa réseau) ne doit pas laisser une icône
        // cassée - un second essai direct sur GitHub avant d'abandonner.
        const image = document.createElement("img");
        image.src = `https://cdn.jsdelivr.net/gh/hfg-gmuend/openmoji@master/color/svg/${item.code}.svg`;
        image.alt = item.name;
        image.className = "h-7 w-7 object-contain";
        image.addEventListener("error", function retryOnGitHub() {
            image.removeEventListener("error", retryOnGitHub);
            image.src = `https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/color/svg/${item.code}.svg`;
        }, { once: true });
        button.appendChild(image);
        button.addEventListener("click", function () {
            const codes = linesToArray(emojiCodesField.value);
            const existingIndex = codes.indexOf(item.code);
            if (existingIndex === -1) {
                codes.push(item.code);
            } else {
                codes.splice(existingIndex, 1);
            }
            emojiCodesField.value = codes.join("\n");
            emojiCodesField.dispatchEvent(new Event("input"));
            renderEmojiPicker();
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
            const button = document.createElement("button");
            button.type = "button";
            button.title = "Cliquer pour retirer";
            button.className = "group relative flex h-8 w-8 items-center justify-center";
            const image = document.createElement("img");
            image.src = `https://cdn.jsdelivr.net/gh/hfg-gmuend/openmoji@master/color/svg/${code.toUpperCase()}.svg`;
            image.referrerPolicy = "no-referrer";
            image.alt = "";
            image.className = "h-8 w-8 object-contain transition group-hover:opacity-30";
            // Même filet que dans la grille du sélecteur (renderEmojiPicker) : un
            // second essai sur GitHub directement avant d'abandonner.
            image.addEventListener("error", function retryOnGitHub() {
                image.removeEventListener("error", retryOnGitHub);
                image.src = `https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/color/svg/${code.toUpperCase()}.svg`;
            }, { once: true });
            const removeHint = document.createElement("span");
            removeHint.className = "pointer-events-none absolute inset-0 hidden items-center justify-center text-sm font-bold text-red-400 group-hover:flex";
            removeHint.textContent = "×";
            button.append(image, removeHint);
            button.addEventListener("click", function () {
                const codes = linesToArray(emojiCodesField.value);
                codes.splice(codes.indexOf(code), 1);
                emojiCodesField.value = codes.join("\n");
                emojiCodesField.dispatchEvent(new Event("input"));
                renderEmojiPicker();
            });
            preview.appendChild(button);
        });
    });
    // Remplace tout de suite l'aperçu Jinja statique (juste des <img>, sans
    // interaction) par la version JS cliquable ci-dessus, sans attendre une
    // première modification côté admin.
    emojiCodesField.dispatchEvent(new Event("input"));
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

// Repère interne (jamais montré aux joueurs, voir templates/partials/
// admin_reference_image.html) : ce hidden ne fait que le faire voyager tel
// quel jusqu'ici, il ne se modifie pas depuis ce formulaire. Sans ça, il
// disparaîtrait au prochain enregistrement comme question_image_url l'était
// avant pour qcm/vrai_faux (payload reconstruit de zéro à chaque envoi).
function adminReferencePayload(activeGroup) {
    const field = activeGroup.querySelector(".admin-reference-image");
    const value = field ? field.value : "";
    return value ? { admin_reference_image: value } : {};
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
        // L'affiche de contexte et les images par option ne se modifient pas
        // depuis ce formulaire (posées par l'enrichissement TMDB) : ces deux
        // hidden ne font que les faire voyager telles quelles jusqu'ici,
        // sans quoi elles disparaîtraient à chaque enregistrement.
        const payload = { options: options };
        const questionImageUrl = activeGroup.querySelector(".question-image-url").value;
        if (questionImageUrl) {
            payload.question_image_url = questionImageUrl;
        }
        const optionImages = Array.from(activeGroup.querySelectorAll(".qcm-option-image")).map(
            function (input) {
                return input.value || null;
            }
        );
        if (optionImages.some(function (url) { return url; })) {
            payload.option_images = optionImages;
        }
        return {
            payload: payload,
            correct_answer: { index: correctIndex },
        };
    }

    if (mode === "vrai_faux") {
        const selectedRadio = activeGroup.querySelector('input[name="vf_correct"]:checked');
        const value = selectedRadio ? selectedRadio.value === "true" : true;
        const payload = {};
        const questionImageUrl = activeGroup.querySelector(".question-image-url").value;
        if (questionImageUrl) {
            payload.question_image_url = questionImageUrl;
        }
        return {
            payload: payload,
            correct_answer: { value: value },
        };
    }

    if (mode === "citation") {
        const film = activeGroup.querySelector(".film-answer").value;
        return { payload: adminReferencePayload(activeGroup), correct_answer: { film: film } };
    }

    if (mode === "emoji") {
        const film = activeGroup.querySelector(".film-answer").value;
        const codes = linesToArray(activeGroup.querySelector(".emoji-visual-codes").value)
            .map(function (value) { return value.toUpperCase(); });
        const payload = Object.assign(
            { visuals: codes.map(function (value) {
                return { type: "openmoji", value: value };
            }) },
            adminReferencePayload(activeGroup)
        );
        return {
            payload: payload,
            correct_answer: { film: film },
        };
    }

    if (mode === "film_melange") {
        const title = activeGroup.querySelector(".film-melange-title").value;
        return {
            payload: adminReferencePayload(activeGroup),
            correct_answer: { title: title },
        };
    }

    if (mode === "devinette") {
        const film = activeGroup.querySelector(".film-answer").value;
        const hints = linesToArray(activeGroup.querySelector(".riddle-hints").value);
        return {
            payload: Object.assign({ hints: hints }, adminReferencePayload(activeGroup)),
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
            payload: Object.assign(
                { audio_url: audioUrl, audio_options: audioOptions },
                adminReferencePayload(activeGroup)
            ),
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

async function autoTagGenres(movieId, contentType) {
    const response = await fetch(`/admin/api/genres-tmdb?movie_id=${movieId}&content_type=${contentType}`);
    const data = await response.json();
    const genres = (data.genres || []);

    document.querySelectorAll('[data-group-label="genres"] .tag-option').forEach(function (option) {
        const checkbox = option.querySelector(".tag-checkbox");
        if (checkbox && !checkbox.checked && genres.indexOf(option.dataset.tagName) !== -1) {
            checkbox.checked = true;
            checkbox.dispatchEvent(new Event("change", { bubbles: true }));
        }
    });
}

async function selectMovie(movie, target, fieldsGroup) {
    const filmAnswerField = fieldsGroup.querySelector(".film-answer");
    filmAnswerField.value = movie.title;

    // Les 3 seuls modes reliés à une œuvre TMDB précise (poster/casting/audio)
    // peuvent en déduire le genre de façon fiable : les autres modes n'ont
    // qu'un titre en texte libre, pas assez sûr pour cocher automatiquement.
    autoTagGenres(movie.id, (fieldsGroup && fieldsGroup.dataset.contentType) || "film");

    if (target === "poster") {
        const contentType = (fieldsGroup && fieldsGroup.dataset.contentType) || "film";
        const response = await fetch(`/admin/api/recherche-affiche?movie_id=${movie.id}&content_type=${contentType}`);
        const data = await response.json();

        if (data.success) {
            fieldsGroup.querySelector(".poster-url").value = data.poster_url;
            const preview = document.getElementById("poster-preview");
            preview.innerHTML = `<img src="${data.poster_url}" class="w-40 rounded-lg border border-cyan-400/30">`;
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

        // Blindtest n'a pas de recherche séparée pour son repère interne (voir
        // question_form_fields.html, show_search=false) : la même recherche,
        // faite pour l'extrait audio, l'attache directement au passage.
        applyPosterField(movie, fieldsGroup, ".admin-reference-image", ".admin-reference-preview", "border-amber-400/30");
    }

    if (target === "question-image") {
        await applyPosterField(movie, fieldsGroup, ".question-image-url", ".question-image-preview", "border-cyan-400/30");
    }

    if (target === "admin-reference") {
        await applyPosterField(movie, fieldsGroup, ".admin-reference-image", ".admin-reference-preview", "border-amber-400/30");
    }
}

// Affiche officielle (jaquette, avec le titre) TMDB, posée sur un champ
// caché + son aperçu — mutualisé entre l'image de contexte (qcm/vrai_faux)
// et le repère interne (citation/devinette/film_melange/blindtest). Ignoré
// silencieusement en cas d'échec quand appelé en tâche de fond (blindtest) :
// l'audio, lui, a déjà été traité avec son propre message d'erreur.
async function applyPosterField(movie, fieldsGroup, fieldSelector, previewSelector, borderClass) {
    const field = fieldsGroup.querySelector(fieldSelector);
    if (!field) return;

    const contentType = (fieldsGroup && fieldsGroup.dataset.contentType) || "film";
    const response = await fetch(`/admin/api/recherche-jaquette?movie_id=${movie.id}&content_type=${contentType}`);
    const data = await response.json();

    if (!data.success) return;

    field.value = data.poster_url;
    const preview = fieldsGroup.querySelector(previewSelector);
    if (preview) {
        preview.innerHTML = `<img src="${data.poster_url}" class="w-40 rounded-lg border ${borderClass}">`;
    }
}

// ---- Sélecteur cherchable pour les tags univers ----
// Les cases à cocher réelles (.tag-checkbox, name="tags") restent dans le DOM,
// juste masquées : le serveur continue de les lire via request.form.getlist,
// aucun changement côté backend. Cette UI ne fait que les cocher/décocher.

function normalizeSearchText(text) {
    return text.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").trim();
}

document.querySelectorAll("[data-tag-picker]").forEach(function (container) {
    const optionsSource = container.querySelector(".tag-picker-options");
    const chipsBox = container.querySelector(".tag-picker-chips");
    const input = container.querySelector(".tag-picker-input");
    const dropdown = container.querySelector(".tag-picker-dropdown");
    if (!optionsSource || !chipsBox || !input || !dropdown) return;

    const entries = Array.from(optionsSource.querySelectorAll("label")).map(function (label) {
        return { checkbox: label.querySelector(".tag-checkbox"), name: label.querySelector("span").textContent };
    });

    function matchesQuery(entry, query) {
        const haystack = normalizeSearchText(entry.name);
        return query.split(/\s+/).filter(Boolean).every(function (word) {
            return haystack.indexOf(normalizeSearchText(word)) !== -1;
        });
    }

    function renderChips() {
        chipsBox.innerHTML = "";
        entries.filter(function (entry) { return entry.checkbox.checked; }).forEach(function (entry) {
            const chip = document.createElement("span");
            chip.className = "flex items-center gap-1.5 rounded-full border border-cyan-400/40 bg-cyan-400/10 px-2.5 py-1 text-xs text-cyan-200";
            chip.textContent = entry.name;

            const remove = document.createElement("button");
            remove.type = "button";
            remove.className = "text-cyan-300 hover:text-white";
            remove.textContent = "×";
            remove.addEventListener("click", function () {
                entry.checkbox.checked = false;
                entry.checkbox.dispatchEvent(new Event("change", { bubbles: true }));
                renderChips();
                renderDropdown();
            });

            chip.appendChild(remove);
            chipsBox.appendChild(chip);
        });
    }

    function renderDropdown() {
        const query = input.value.trim();
        dropdown.innerHTML = "";
        const available = entries.filter(function (entry) { return !entry.checkbox.checked; });
        const filtered = query ? available.filter(function (entry) { return matchesQuery(entry, query); }) : available;

        if (!filtered.length) {
            dropdown.innerHTML = '<p class="px-3 py-2 text-sm text-slate-500">Aucun univers trouvé.</p>';
            return;
        }

        filtered.slice(0, 30).forEach(function (entry) {
            const item = document.createElement("button");
            item.type = "button";
            item.className = "block w-full px-3 py-2 text-left text-sm text-slate-100 hover:bg-slate-800 transition";
            item.textContent = entry.name;
            item.addEventListener("click", function () {
                entry.checkbox.checked = true;
                entry.checkbox.dispatchEvent(new Event("change", { bubbles: true }));
                input.value = "";
                renderChips();
                renderDropdown();
                input.focus();
            });
            dropdown.appendChild(item);
        });
    }

    input.addEventListener("focus", function () {
        renderDropdown();
        dropdown.classList.remove("hidden");
    });
    input.addEventListener("input", function () {
        renderDropdown();
        dropdown.classList.remove("hidden");
    });
    input.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            dropdown.classList.add("hidden");
        }
    });
    document.addEventListener("click", function (event) {
        if (!container.contains(event.target)) {
            dropdown.classList.add("hidden");
        }
    });

    renderChips();
});
})();