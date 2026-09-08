const startButton = document.getElementById("start-game");
const availabilityText = document.getElementById("availability-text");
const contentTypeSelect = document.getElementById("content-type");
const difficultySelect = document.getElementById("difficulty-filter");
const tagFilterSelects = document.querySelectorAll("[data-tag-filter]");
const lengthButtons = document.querySelectorAll("#run-length-choices [data-length]");
const rewardXp = document.getElementById("reward-xp");
const rewardCoins = document.getElementById("reward-coins");
const timeEstimate = document.getElementById("setup-time-estimate");
const universSelect = document.getElementById("tag-univers");
const incompatibleUniverseModes = new Set([
    "devinette_affiche",
    "casting",
    "emoji",
    "blindtest",
    "film_melange",
]);

function currentFilterParams() {
    const params = new URLSearchParams();

    Array.from(tagFilterSelects)
        .map(function (select) { return select.value; })
        .filter(Boolean)
        .forEach(function (tagId) { params.append("tag_id", tagId); });

    if (contentTypeSelect.value) {
        params.set("content_type", contentTypeSelect.value);
    }

    if (difficultySelect.value) {
        params.set("difficulty", difficultySelect.value);
    }

    return params;
}

function activeLengthButton() {
    return document.querySelector("#run-length-choices [data-length].is-active") || lengthButtons[0];
}

// Un choix cliqué devient le seul actif de son groupe (comportement de
// boutons-radio), sans le champ <select> ou <input type="radio"> que ça
// demanderait autrement.
function setActive(buttons, clicked) {
    buttons.forEach(function (button) {
        button.classList.toggle("is-active", button === clicked);
    });
}

// Récompense et durée annoncées ne viennent d'aucune requête serveur : tout
// est déjà connu du navigateur (xp/pièces posés en data-* sur les options du
// filtre de difficulté, durée fixe du mode posée sur le select lui-même,
// longueur choisie juste à côté). Le chrono ne dépend plus de la difficulté
// (services/levels.py) : son estimation est donc la même quel que soit le
// filtre de difficulté choisi. Sans difficulté précise (Mixte), les gains
// varient en revanche question par question : on annonce une fourchette.
function updateRewardsAndEstimate() {
    const length = activeLengthButton();
    if (!length) {
        return;
    }

    const runLength = parseInt(length.dataset.length, 10);
    const modeDuration = parseInt(difficultySelect.dataset.modeDuration, 10);

    if (timeEstimate) {
        const minutes = Math.max(1, Math.round((runLength * modeDuration) / 60));
        timeEstimate.textContent = `Environ ${minutes} min`;
    }

    const selectedOption = difficultySelect.options[difficultySelect.selectedIndex];

    if (difficultySelect.value && selectedOption) {
        const xpPerAnswer = parseInt(selectedOption.dataset.xp, 10);
        const coinsPerAnswer = parseInt(selectedOption.dataset.coins, 10);

        if (rewardXp) {
            rewardXp.textContent = `Jusqu'à ${runLength * xpPerAnswer} XP`;
        }
        if (rewardCoins) {
            rewardCoins.textContent = `Jusqu'à ${runLength * coinsPerAnswer} pièces`;
        }
        return;
    }

    const difficultyOptions = Array.from(difficultySelect.options).filter(function (option) {
        return option.value;
    });
    const xpValues = difficultyOptions.map(function (option) { return parseInt(option.dataset.xp, 10); });
    const coinsValues = difficultyOptions.map(function (option) { return parseInt(option.dataset.coins, 10); });

    if (rewardXp) {
        rewardXp.textContent = `${runLength * Math.min(...xpValues)} - ${runLength * Math.max(...xpValues)} XP`;
    }
    if (rewardCoins) {
        rewardCoins.textContent = `${runLength * Math.min(...coinsValues)} - ${runLength * Math.max(...coinsValues)} pièces`;
    }
}

// Ne désactive jamais le choix « Tous les X » (on doit toujours pouvoir
// annuler un filtre), ni la valeur actuellement retenue par le sélecteur :
// sans quoi ce sélecteur perdrait son propre choix dès qu'il devient, seul,
// incompatible avec un autre filtre déjà posé ailleurs.
function disableUnreachableOptions(select, reachableIds) {
    Array.from(select.options).forEach(function (option) {
        if (option.value === "" || option.value === select.value) {
            option.disabled = false;
            return;
        }
        option.disabled = !reachableIds.includes(option.value);
    });
}

function updateModeVisibility() {
    const universeSelected = Boolean(universSelect && universSelect.value);
    const modeLinks = document.querySelectorAll("[data-mode-slug]");

    modeLinks.forEach(function (link) {
        const shouldHide = universeSelected && incompatibleUniverseModes.has(link.dataset.modeSlug);
        link.hidden = shouldHide;
        link.setAttribute("aria-hidden", shouldHide ? "true" : "false");
    });

    // Si le joueur choisit un univers depuis un mode devenu incompatible,
    // on le replace sur le QCM en conservant ses filtres déjà sélectionnés.
    const currentMode = startButton.dataset.mode;
    if (universeSelected && incompatibleUniverseModes.has(currentMode)) {
        const params = currentFilterParams();
        window.location.href = `/quiz/qcm?${params.toString()}`;
    }
}

// Le compteur et les options des sélecteurs ne sont à jour qu'au chargement
// de la page : changer un filtre doit les rafraîchir sans recharger l'écran,
// sans quoi le joueur pourrait choisir « Horreur » puis « Années 2000 » sans
// savoir qu'aucune question ne réunit les deux.
function refreshAvailability() {
    const mode = startButton.dataset.mode;
    const params = currentFilterParams();
    const length = activeLengthButton();
    if (length) {
        params.set("questions", length.dataset.length);
    }

    fetch(`/quiz/${mode}/disponibilite?${params.toString()}`)
        .then(function (response) { return response.json(); })
        .then(function (data) {
            if (data.available === 0) {
                availabilityText.textContent = "Aucune question disponible";
                startButton.textContent = "Aucune question disponible";
                startButton.disabled = true;
            } else {
                const lengthLabel = length ? length.querySelector("strong").textContent : "";
                availabilityText.innerHTML =
                    `Partie ${lengthLabel.toLowerCase()} de ${data.run_length} question${data.run_length > 1 ? "s" : ""}` +
                    `<span class="opacity-50"> · </span>` +
                    `${data.available} disponible${data.available > 1 ? "s" : ""}`;
                startButton.textContent = "▶ Lancer la partie";
                startButton.disabled = false;
            }

            tagFilterSelects.forEach(function (select) {
                const tagType = select.id.replace(/^tag-/, "");
                const reachableIds = (
                    data.reachable_tag_ids_by_type[tagType] || data.default_reachable_tag_ids
                ).map(String);
                disableUnreachableOptions(select, reachableIds);
            });
            disableUnreachableOptions(contentTypeSelect, data.reachable_content_types);
        });
}

contentTypeSelect.addEventListener("change", refreshAvailability);

difficultySelect.addEventListener("change", function () {
    refreshAvailability();
    updateRewardsAndEstimate();
});

if (universSelect) {
    universSelect.addEventListener("change", function () {
        updateModeVisibility();
        refreshAvailability();
    });
}

tagFilterSelects.forEach(function (select) {
    select.addEventListener("change", refreshAvailability);
});

lengthButtons.forEach(function (button) {
    button.addEventListener("click", function () {
        setActive(lengthButtons, button);
        updateRewardsAndEstimate();
        refreshAvailability();
    });
});

updateModeVisibility();
refreshAvailability();
updateRewardsAndEstimate();

// Les univers peu fournis restent dans le <select>, simplement masqués (cf.
// preparation.html) : ce bouton les révèle sans recharger la page.
const showAllUniversButton = document.getElementById("show-all-univers");

function revealAllUnivers() {
    universSelect.querySelectorAll("option[hidden]").forEach(function (option) {
        option.hidden = false;
    });
    if (showAllUniversButton) {
        showAllUniversButton.classList.add("hidden");
    }
}

if (showAllUniversButton) {
    showAllUniversButton.addEventListener("click", revealAllUnivers);
}
// Un univers peu fourni peut déjà être sélectionné en arrivant sur la page
// (lien direct, retour arrière) : il doit rester visible dans la liste.
if (universSelect && universSelect.querySelector("option[hidden][selected]")) {
    revealAllUnivers();
}

startButton.addEventListener("click", function () {
    const mode = startButton.dataset.mode;
    const length = activeLengthButton();
    const params = currentFilterParams();

    // Le filtre de difficulté (dans currentFilterParams) et la longueur
    // suivent ensuite le joueur d'une question à l'autre, puisque quiz.js
    // conserve la query string en changeant de position.
    params.set("questions", length.dataset.length);

    window.location.href = `/quiz/${mode}/1?${params.toString()}`;
});
