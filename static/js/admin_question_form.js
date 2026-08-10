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
        const hints = linesToArray(activeGroup.querySelector(".poster-hints").value);
        return {
            payload: { poster_url: posterUrl, hints: hints },
            correct_answer: { film: film },
        };
    }

    if (mode === "casting") {
        const film = activeGroup.querySelector(".film-answer").value;
        const actorPhotos = linesToArray(activeGroup.querySelector(".actor-photos").value);
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