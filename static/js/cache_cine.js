// Déroulé d'une partie de Cache-Ciné (templates/special_games/cache_cine_jouer.html).
// Le minuteur et le compteur de références trouvées vivent entièrement ici :
// le serveur (filmatrix/routes/special_games.py) ne fait que valider chaque
// clic et calculer la récompense finale, jamais de va-et-vient par rechargement
// de page pendant la partie.

(function () {
    const configEl = document.getElementById("cache-cine-config");
    const stage = document.getElementById("cc-stage");
    const finishForm = document.getElementById("cc-finish-form");

    if (!configEl || !stage || !finishForm) {
        return;
    }

    const config = JSON.parse(configEl.textContent || "{}");

    let timeLeft = config.timeLimitSeconds || 0;
    let foundCount = config.foundCount || 0;
    const total = config.totalReferences || 0;
    let finished = false;

    const timerEl = document.getElementById("cc-timer");
    const foundEl = document.getElementById("cc-found-count");
    const toastEl = document.getElementById("cc-toast");
    const checklist = document.getElementById("cc-checklist");

    function formatTime(seconds) {
        const clamped = Math.max(seconds, 0);
        const minutes = Math.floor(clamped / 60);
        const secs = clamped % 60;
        return String(minutes).padStart(2, "0") + ":" + String(secs).padStart(2, "0");
    }

    function renderTimer() {
        timerEl.textContent = "⏱️ " + formatTime(timeLeft);
        timerEl.classList.toggle("cc-timer--low", timeLeft <= 10 && timeLeft > 0);
    }

    function renderFoundCount() {
        foundEl.textContent = "🎯 " + foundCount + "/" + total;
    }

    let toastTimer = null;
    function showToast(text, kind) {
        clearTimeout(toastTimer);
        toastEl.textContent = text;
        toastEl.className = "cc-toast cc-toast--" + kind + " is-visible";
        toastTimer = setTimeout(function () {
            toastEl.classList.remove("is-visible");
        }, 1400);
    }

    function finishGame() {
        if (finished) return;
        finished = true;
        clearInterval(timerInterval);
        finishForm.submit();
    }

    const timerInterval = setInterval(function () {
        if (finished) return;
        timeLeft -= 1;
        renderTimer();
        if (timeLeft <= 0) {
            finishGame();
        }
    }, 1000);

    renderTimer();
    renderFoundCount();

    stage.addEventListener("click", function (event) {
        if (finished) return;

        const zoneEl = event.target.closest(".cc-zone");
        const alreadyFound = zoneEl && zoneEl.classList.contains("cc-zone--found");
        const referenceId = zoneEl && !alreadyFound ? zoneEl.dataset.referenceId : null;

        if (alreadyFound) {
            return;
        }

        fetch(config.clickUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ reference_id: referenceId }),
        })
            .then(function (response) {
                return response.json();
            })
            .then(function (data) {
                if (finished) return;

                if (data.correct) {
                    foundCount = data.found_count;
                    renderFoundCount();
                    showToast("✓ " + data.title + " — Référence trouvée !", "found");

                    if (zoneEl) {
                        zoneEl.classList.add("cc-zone--found", "cc-zone--just-found");
                        setTimeout(function () {
                            zoneEl.classList.remove("cc-zone--just-found");
                        }, 700);
                    }

                    const item = checklist.querySelector('[data-reference-id="' + data.reference_id + '"]');
                    if (item) {
                        item.classList.add("is-found");
                        const check = item.querySelector(".cc-check");
                        if (check) check.textContent = "✓";
                    }

                    if (foundCount >= total) {
                        setTimeout(finishGame, 500);
                    }
                } else {
                    const penalty = data.penalty_seconds || 0;
                    timeLeft = Math.max(timeLeft - penalty, 0);
                    renderTimer();
                    showToast("✗ Raté ! -" + penalty + "s", "miss");
                    stage.classList.add("cc-miss-flash");
                    setTimeout(function () {
                        stage.classList.remove("cc-miss-flash");
                    }, 300);
                    if (timeLeft <= 0) {
                        finishGame();
                    }
                }
            })
            .catch(function () {
                // Le clic n'a pas pu être validé (réseau) : le joueur peut
                // simplement recliquer, aucun état local n'a changé.
            });
    });
})();
