// Déroulé d'une partie de Scène Mystère (templates/special_games/scene_mystere_jouer.html).
// Une image, une dizaine de références : le minuteur et le compteur de
// références trouvées vivent ici, comme pour Cache-Ciné (static/js/cache_cine.js).
// La différence, et l'inverse de Cache-Ciné : pas de liste de titres à
// chercher ni aucun indice fourni, le joueur clique sur ce qu'il repère
// lui-même dans l'image puis tape le nom de l'œuvre (pas de QCM).

(function () {
    const configEl = document.getElementById("scene-mystere-config");
    const stage = document.getElementById("sm-stage");
    const finishForm = document.getElementById("sm-finish-form");

    if (!configEl || !stage || !finishForm) {
        return;
    }

    const config = JSON.parse(configEl.textContent || "{}");

    let timeLeft = config.timeLimitSeconds || 0;
    let foundCount = config.foundCount || 0;
    const total = config.total || 0;
    let finished = false;
    let awaitingAnswer = false;

    const timerEl = document.getElementById("sm-timer");
    const foundEl = document.getElementById("sm-found-count");
    const toastEl = document.getElementById("sm-toast");
    const idlePanel = document.getElementById("sm-idle-panel");
    const answerPanel = document.getElementById("sm-answer-panel");
    const answerInput = document.getElementById("sm-answer-input");
    const answerSubmitButton = document.getElementById("sm-answer-submit");
    const sidebar = document.querySelector(".sm-sidebar");
    const image = document.getElementById("sm-image");
    const foundTitlesPanel = document.getElementById("sm-found-titles-panel");
    const foundTitlesList = document.getElementById("sm-found-titles-list");

    // Doublons volontairement gardés (pas de déduplication) : une même
    // œuvre peut se cacher plusieurs fois dans la scène, la revoir dans
    // cette liste est justement ce qui doit rassurer le joueur.
    function addFoundTitle(title) {
        if (!title || !foundTitlesList) return;
        const item = document.createElement("li");
        item.textContent = "🎬 " + title;
        foundTitlesList.appendChild(item);
        if (foundTitlesPanel) {
            foundTitlesPanel.classList.remove("sm-hidden");
        }
    }

    // Sous 768px, l'image doit remplir tout l'espace libre entre le
    // minuteur et la feuille idle/réponse (voir scene_mystere_jouer.html)
    // plutôt que de se contenter d'un plafond fixe (min(60vh,560px)) qui
    // laissait un vide quand l'image réelle était plus petite que ce
    // plafond. La feuille change de hauteur selon qu'elle affiche le
    // message d'attente ou le champ de réponse : on recalcule donc à chaque
    // bascule, pas seulement au chargement. .sm-stage reste dimensionnée exactement
    // sur l'image rendue (fit-content) : les zones, positionnées en % de
    // .sm-stage, doivent toujours correspondre pixel pour pixel à l'image,
    // donc c'est l'image qu'on redimensionne (via max-height en px), jamais
    // la scène elle-même.
    function fitStageHeight() {
        if (!image || window.innerWidth >= 768) {
            if (image) image.style.maxHeight = "";
            return;
        }
        const stageTop = stage.getBoundingClientRect().top;
        const sidebarHeight = sidebar ? sidebar.getBoundingClientRect().height : 0;
        const available = window.innerHeight - stageTop - sidebarHeight - 16;
        image.style.maxHeight = Math.max(available, 160) + "px";
    }
    window.addEventListener("resize", fitStageHeight);
    window.addEventListener("orientationchange", fitStageHeight);
    fitStageHeight();

    function formatTime(seconds) {
        const clamped = Math.max(seconds, 0);
        const minutes = Math.floor(clamped / 60);
        const secs = clamped % 60;
        return String(minutes).padStart(2, "0") + ":" + String(secs).padStart(2, "0");
    }

    function renderTimer() {
        timerEl.textContent = "⏱️ " + formatTime(timeLeft);
        timerEl.classList.toggle("sm-timer--low", timeLeft <= 10 && timeLeft > 0);
    }

    function renderFoundCount() {
        foundEl.textContent = "🎯 " + foundCount + "/" + total;
    }

    let toastTimer = null;
    function showToast(text, kind) {
        clearTimeout(toastTimer);
        toastEl.textContent = text;
        toastEl.className = "sm-toast sm-toast--" + kind + " is-visible";
        toastTimer = setTimeout(function () {
            toastEl.classList.remove("is-visible");
        }, 1600);
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

    function showAnswerInput() {
        awaitingAnswer = true;
        answerInput.value = "";
        if (answerSubmitButton) {
            answerSubmitButton.disabled = true;
        }
        idlePanel.classList.add("sm-hidden");
        answerPanel.classList.remove("sm-hidden");
        fitStageHeight();
        answerInput.focus();
    }

    function showIdle() {
        awaitingAnswer = false;
        answerPanel.classList.add("sm-hidden");
        idlePanel.classList.remove("sm-hidden");
        fitStageHeight();
    }

    stage.addEventListener("click", function (event) {
        if (finished || awaitingAnswer) return;

        const zoneEl = event.target.closest(".sm-zone");
        if (!zoneEl || zoneEl.classList.contains("sm-zone--found")) {
            return;
        }

        fetch(config.clickUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ zone_id: zoneEl.dataset.zoneId }),
        })
            .then(function (response) {
                return response.json();
            })
            .then(function (data) {
                if (finished) return;

                if (data.correct) {
                    zoneEl.classList.add("sm-zone--found", "sm-zone--just-found");
                    setTimeout(function () {
                        zoneEl.classList.remove("sm-zone--just-found");
                    }, 700);
                    showAnswerInput();
                } else {
                    const penalty = data.penalty_seconds || 0;
                    timeLeft = Math.max(timeLeft - penalty, 0);
                    renderTimer();
                    showToast("✗ Raté ! -" + penalty + "s", "miss");
                    stage.classList.add("sm-miss-flash");
                    setTimeout(function () {
                        stage.classList.remove("sm-miss-flash");
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

    answerInput.addEventListener("input", function () {
        if (answerSubmitButton) {
            answerSubmitButton.disabled = answerInput.value.trim() === "";
        }
    });

    function submitAnswer() {
        if (finished) return;

        const guess = answerInput.value.trim();
        if (!guess) return;

        if (answerSubmitButton) {
            answerSubmitButton.disabled = true;
        }

        fetch(config.answerUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ guess: guess }),
        })
            .then(function (response) {
                return response.json();
            })
            .then(function (data) {
                if (answerSubmitButton) {
                    answerSubmitButton.disabled = false;
                }
                if (finished) return;

                foundCount = data.found_count;
                renderFoundCount();

                if (data.correct) {
                    showToast("✓ Trouvé !", "found");
                    addFoundTitle(data.correct_label);
                } else {
                    showToast("✗ C'était : " + (data.correct_label || "?"), "miss");
                }

                if (data.done) {
                    setTimeout(finishGame, 900);
                } else {
                    showIdle();
                }
            })
            .catch(function () {
                if (answerSubmitButton) {
                    answerSubmitButton.disabled = false;
                }
            });
    }

    answerInput.addEventListener("keydown", function (event) {
        if (event.key === "Enter" && !answerSubmitButton.disabled) {
            event.preventDefault();
            submitAnswer();
        }
    });

    if (answerSubmitButton) {
        answerSubmitButton.addEventListener("click", submitAnswer);
    }
})();
