const modeSelect = document.getElementById("mode-select");
const allModeFieldGroups = document.querySelectorAll(".mode-fields");
const form = document.getElementById("question-form");

function showFieldsForMode(mode) {
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
});

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

    if (mode === "citation" || mode === "emoji") {
        const film = activeGroup.querySelector(".film-answer").value;
        return {
            payload: {},
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
        return {
            payload: { audio_url: audioUrl },
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

            displaySearchResults(data.results, resultsBox, target, fieldsGroup);
        }, 350);
    });

    document.addEventListener("click", function (event) {
        if (!searchInput.contains(event.target) && !resultsBox.contains(event.target)) {
            resultsBox.classList.add("hidden");
        }
    });
});

function displaySearchResults(movies, resultsBox, target, fieldsGroup) {
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

        item.innerHTML = `
            ${thumbnailHtml}
            <span class="text-sm text-slate-100">${movie.title} <span class="text-slate-500">(${movie.year})</span></span>
        `;

        item.addEventListener("click", function () {
            selectMovie(movie, target, fieldsGroup);
            resultsBox.classList.add("hidden");
        });

        resultsBox.appendChild(item);
    });

    resultsBox.classList.remove("hidden");
}

async function selectMovie(movie, target, fieldsGroup) {
    const filmAnswerField = fieldsGroup.querySelector(".film-answer");
    filmAnswerField.value = movie.title;

    if (target === "poster") {
        const response = await fetch(`/admin/api/recherche-affiche?movie_id=${movie.id}`);
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
        const response = await fetch(`/admin/api/recherche-casting?movie_id=${movie.id}`);
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
            const preview = document.getElementById("audio-preview");
            preview.innerHTML = `<audio controls src="${data.audio_url}" class="w-full mt-2"></audio>`;
        } else {
            alert(data.error);
        }
    }
}