const startButton = document.getElementById("start-game");
const availabilityText = document.getElementById("availability-text");
const contentTypeSelect = document.getElementById("content-type");
const tagFilterSelects = document.querySelectorAll("[data-tag-filter]");
const levelButtons = document.querySelectorAll("#level-choices [data-level]");
const lengthButtons = document.querySelectorAll("#run-length-choices [data-length]");
const rewardXp = document.getElementById("reward-xp");
const rewardCoins = document.getElementById("reward-coins");
const timeEstimate = document.getElementById("setup-time-estimate");

function currentFilterParams() {
    const params = new URLSearchParams();

    Array.from(tagFilterSelects)
        .map(function (select) { return select.value; })
        .filter(Boolean)
        .forEach(function (tagId) { params.append("tag_id", tagId); });

    if (contentTypeSelect.value) {
        params.set("content_type", contentTypeSelect.value);
    }

    return params;
}

function activeLevelButton() {
    return document.querySelector("#level-choices [data-level].is-active") || levelButtons[0];
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
// est déjà connu du navigateur (xp/pièces/durée posés en data-* par le
// template, longueur choisie juste à côté), donc calculé sur place.
function updateRewardsAndEstimate() {
    const level = activeLevelButton();
    const length = activeLengthButton();
    if (!level || !length) {
        return;
    }

    const runLength = parseInt(length.dataset.length, 10);
    const xpPerAnswer = parseInt(level.dataset.xp, 10);
    const coinsPerAnswer = parseInt(level.dataset.coins, 10);
    const durationPerQuestion = parseInt(level.dataset.duration, 10);

    if (rewardXp) {
        rewardXp.textContent = `Jusqu'à ${runLength * xpPerAnswer} XP`;
    }
    if (rewardCoins) {
        rewardCoins.textContent = `Jusqu'à ${runLength * coinsPerAnswer} pièces`;
    }
    if (timeEstimate) {
        const minutes = Math.max(1, Math.round((runLength * durationPerQuestion) / 60));
        timeEstimate.textContent = `Environ ${minutes} min`;
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
tagFilterSelects.forEach(function (select) {
    select.addEventListener("change", refreshAvailability);
});

levelButtons.forEach(function (button) {
    button.addEventListener("click", function () {
        setActive(levelButtons, button);
        updateRewardsAndEstimate();
    });
});

lengthButtons.forEach(function (button) {
    button.addEventListener("click", function () {
        setActive(lengthButtons, button);
        updateRewardsAndEstimate();
        refreshAvailability();
    });
});

refreshAvailability();
updateRewardsAndEstimate();

// Les univers peu fournis restent dans le <select>, simplement masqués (cf.
// preparation.html) : ce bouton les révèle sans recharger la page.
const showAllUniversButton = document.getElementById("show-all-univers");
const universSelect = document.getElementById("tag-univers");

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
    const level = activeLevelButton();
    const length = activeLengthButton();
    const params = currentFilterParams();

    // Niveau et longueur suivent ensuite le joueur d'une question à l'autre,
    // puisque quiz.js conserve la query string en changeant de position.
    params.set("level", level.dataset.level);
    params.set("questions", length.dataset.length);

    window.location.href = `/quiz/${mode}/1?${params.toString()}`;
});
