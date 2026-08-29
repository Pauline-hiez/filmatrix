const startButton = document.getElementById("start-game");
const availabilityText = document.getElementById("availability-text");
const contentTypeSelect = document.getElementById("content-type");
const tagFilterSelects = document.querySelectorAll("[data-tag-filter]");

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

    fetch(`/quiz/${mode}/disponibilite?${currentFilterParams().toString()}`)
        .then(function (response) { return response.json(); })
        .then(function (data) {
            if (data.available === 0) {
                availabilityText.textContent = "Aucune question disponible";
                startButton.textContent = "Aucune question disponible";
                startButton.disabled = true;
            } else {
                availabilityText.innerHTML =
                    `Partie de ${data.run_length} question${data.run_length > 1 ? "s" : ""}` +
                    `<span class="opacity-50"> · </span>` +
                    `${data.available} disponible${data.available > 1 ? "s" : ""}`;
                startButton.textContent = "Commencer";
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
refreshAvailability();

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
    const level = document.getElementById("level").value;
    const params = currentFilterParams();

    // Le niveau est toujours transmis : il suit ensuite le joueur d'une question
    // à l'autre, puisque quiz.js conserve la query string en changeant de position.
    params.set("level", level);

    window.location.href = `/quiz/${mode}/1?${params.toString()}`;
});
