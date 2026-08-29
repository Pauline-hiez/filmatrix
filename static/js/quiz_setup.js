const startButton = document.getElementById("start-game");
const availabilityText = document.getElementById("availability-text");

function currentFilterParams() {
    const params = new URLSearchParams();

    Array.from(document.querySelectorAll("[data-tag-filter]"))
        .map(function (select) { return select.value; })
        .filter(Boolean)
        .forEach(function (tagId) { params.append("tag_id", tagId); });

    const contentType = document.getElementById("content-type").value;
    if (contentType) {
        params.set("content_type", contentType);
    }

    return params;
}

// Le compteur n'est à jour qu'au chargement de la page : changer un filtre
// doit le rafraîchir sans recharger l'écran, sans quoi le joueur ne
// découvre le vrai nombre de questions qu'une fois la partie lancée.
function refreshAvailability() {
    const mode = startButton.dataset.mode;

    fetch(`/quiz/${mode}/disponibilite?${currentFilterParams().toString()}`)
        .then(function (response) { return response.json(); })
        .then(function (data) {
            if (data.available === 0) {
                availabilityText.textContent = "Aucune question disponible";
                startButton.textContent = "Aucune question disponible";
                startButton.disabled = true;
                return;
            }

            availabilityText.innerHTML =
                `Partie de ${data.run_length} question${data.run_length > 1 ? "s" : ""}` +
                `<span class="opacity-50"> · </span>` +
                `${data.available} disponible${data.available > 1 ? "s" : ""}`;
            startButton.textContent = "Commencer";
            startButton.disabled = false;
        });
}

document.getElementById("content-type").addEventListener("change", refreshAvailability);
document.querySelectorAll("[data-tag-filter]").forEach(function (select) {
    select.addEventListener("change", refreshAvailability);
});

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
