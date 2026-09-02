const timeBar = document.getElementById("time-bar");
const timeRing = document.getElementById("time-ring");

// Durée calculée par le serveur d'après le niveau choisi par le joueur
// (et forcée à 30 s pour le blindtest) : voir src/levels.py.
const TOTAL_DURATION = parseInt(timeBar.dataset.duration, 10);
let remainingTime = TOTAL_DURATION;
let alreadyAnswered = false;

// Anneau et barre linéaire partagent le même pourcentage : deux habillages,
// une seule source de vérité pour ne pas les faire diverger.
function setTimerPercentage(percentage) {
    timeBar.style.width = percentage + "%";
    if (timeRing) {
        timeRing.style.setProperty("--time-pct", Math.max(0, percentage));
    }
}

function showBadgeNotification(badge) {
    const notification = document.createElement("div");
    notification.className =
        "fixed top-4 left-1/2 -translate-x-1/2 bg-slate-900 border border-cyan-400 rounded-lg px-4 py-3 shadow-lg z-50 flex items-center gap-3 transition-opacity duration-500";
    notification.innerHTML = `
        <span class="text-2xl">${badge.icon}</span>
        <div>
            <p class="text-cyan-400 font-bold text-sm">Badge débloqué !</p>
            <p class="text-slate-300 text-xs">${badge.name}</p>
        </div>
    `;

    document.body.appendChild(notification);

    setTimeout(function () {
        notification.style.opacity = "0";
        setTimeout(function () {
            notification.remove();
        }, 500);
    }, 3000);
}

const FRAGMENT_RARITY_LABELS = {
    commun: "Commun",
    rare: "Rare",
    epique: "Épique",
    legendaire: "Légendaire",
    mythique: "Mythique",
};

function assetUrl(url) {
    if (!url) return "";
    if (/^https?:\/\//i.test(url)) return url;
    return "/static/" + url;
}

// Animation de la case qui vient d'être révélée dans le toast.
function ensureFragmentRevealStyle() {
    if (document.getElementById("fragment-reveal-style")) {
        return;
    }
    const style = document.createElement("style");
    style.id = "fragment-reveal-style";
    style.textContent = `
        @keyframes fragmentCellReveal {
            0% { opacity: 0; transform: scale(0.3); filter: brightness(2.2); }
            55% { opacity: 1; transform: scale(1.18); }
            100% { opacity: 1; transform: scale(1); filter: brightness(1); }
        }
        .fragment-cell-reveal { animation: fragmentCellReveal 0.65s ease-out; }
        @keyframes fragmentGlow {
            0%, 100% { box-shadow: 0 0 0 0 rgba(34, 211, 238, 0); }
            40% { box-shadow: 0 0 10px 2px rgba(34, 211, 238, 0.7); }
        }
        .fragment-new-cell { animation: fragmentCellReveal 0.65s ease-out, fragmentGlow 0.9s ease-out; }
    `;
    document.head.appendChild(style);
}

function buildPuzzleCells(fragmentResult, imageUrl) {
    const grid = fragmentResult.puzzle_grid || [];
    const newCells = fragmentResult.puzzle_new_cells || [];
    let html = "";
    for (let index = 0; index < 9; index += 1) {
        const revealed = Boolean(grid[index]);
        const isNew = newCells.indexOf(index) !== -1;
        const background = revealed && imageUrl
            ? `background-image:url('${imageUrl}');background-size:cover;background-position:center;`
            : "";
        const cellClass = isNew
            ? "fragment-new-cell"
            : (revealed ? "" : "opacity-90");
        html += `
            <div class="relative overflow-hidden bg-slate-900 ${cellClass}" style="${background}">
                ${revealed ? "" : `<span class="absolute inset-0 flex items-center justify-center text-[0.6rem] text-slate-600">?</span>`}
            </div>
        `;
    }
    return html;
}

function showFragmentNotification(fragmentResult) {
    const title = fragmentResult.just_unlocked ? "Personnage débloqué !" : "Fragment obtenu";
    const icon = fragmentResult.just_unlocked ? "🎉" : "🧩";
    const rarity = FRAGMENT_RARITY_LABELS[fragmentResult.rarity] || fragmentResult.rarity || "";

    const imageUrl = assetUrl(fragmentResult.image_url);
    const progress = fragmentResult.progress_percent || 0;
    const sagaName = fragmentResult.saga_name || "";
    ensureFragmentRevealStyle();

    const puzzleCells = buildPuzzleCells(fragmentResult, imageUrl);

    const notification = document.createElement("div");
    notification.className =
        "fixed top-4 left-1/2 -translate-x-1/2 z-50 flex cursor-pointer items-center gap-3 rounded-xl border border-cyan-400 bg-slate-900 px-4 py-3 shadow-2xl transition-opacity duration-500 max-w-sm";
    notification.setAttribute("role", "status");
    notification.addEventListener("click", function () {
        window.location.href = "/collection";
    });
    notification.innerHTML = `
        <div class="grid h-16 w-16 shrink-0 grid-cols-3 grid-rows-3 gap-px overflow-hidden rounded-lg border border-slate-700 bg-slate-950">
            ${puzzleCells}
        </div>
        <div class="min-w-0 flex-1">
            <p class="text-sm font-bold text-cyan-400">${icon} ${title}</p>
            <p class="truncate text-sm font-semibold text-slate-100">${fragmentResult.character_name}</p>
            <p class="truncate text-xs text-slate-500">${sagaName}${sagaName && rarity ? " · " : ""}${rarity}</p>
            <div class="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
                <div class="h-1.5 rounded-full bg-gradient-to-r from-cyan-400 to-violet-500" style="width:${progress}%"></div>
            </div>
            <p class="mt-0.5 text-[0.65rem] text-slate-500">${fragmentResult.fragments}/${fragmentResult.fragments_required} fragments</p>
        </div>
    `;

    document.body.appendChild(notification);

    setTimeout(function () {
        notification.style.opacity = "0";
        setTimeout(function () {
            notification.remove();
        }, 500);
    }, 3500);
}

function showAnswerFeedback(isCorrect, correctAnswer) {
    const feedback = document.getElementById("answer-feedback");
    const label = document.getElementById("answer-feedback-label");
    const text = document.getElementById("answer-feedback-text");

    if (isCorrect) {
        // Vert, et l'intitulé "Bonne réponse" n'a plus lieu d'être : rien à révéler.
        feedback.classList.add("border-emerald-400", "bg-emerald-500/10");
        text.classList.add("text-emerald-400");
        label.classList.add("hidden");
        text.textContent = "✓ Bonne réponse !";
    } else if (correctAnswer) {
        // Rouge pour marquer l'échec, mais la solution reste en blanc : elle est
        // une information, pas l'erreur du joueur.
        feedback.classList.add("border-red-400", "bg-red-500/10");
        label.classList.add("text-red-300");
        text.classList.add("text-slate-100");
        text.textContent = correctAnswer;
    } else {
        return;
    }

    feedback.classList.remove("hidden");
}

function goToNextQuestion() {
    setTimeout(function () {
        window.location.href = window.location.href.replace(
            /\/(\d+)(\?|$)/,
            function (match, position, end) {
                return "/" + (parseInt(position) + 1) + end;
            }
        );
    }, 1500);
}

async function sendAnswer(body) {
    if (alreadyAnswered) {
        return;
    }
    alreadyAnswered = true;
    clearInterval(timerInterval);

    document.querySelectorAll(".answer-button").forEach(function (b) {
        b.disabled = true;
    });

    const url = window.location.pathname + window.location.search;
    const serverResponse = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: body,
    });

    const result = await serverResponse.json();
    return result;
}

document.querySelectorAll(".answer-button").forEach(function (button) {
    button.addEventListener("click", async function (event) {
        event.preventDefault();
        let answer = button.dataset.answer;
        const freeTextField = document.getElementById("free-text-answer");
        if (freeTextField) {
            answer = freeTextField.value;
        }

        const result = await sendAnswer(`answer=${encodeURIComponent(answer)}`);

        if (result) {
            button.classList.remove("bg-cyan-400", "hover:bg-cyan-300");

            if (freeTextField) {
                freeTextField.classList.remove("border-cyan-400/30");
            }

            if (result.is_correct) {
                button.classList.add("bg-emerald-500/30", "border-emerald-400");
                if (freeTextField) {
                    freeTextField.classList.add("border-emerald-400");
                }
            } else {
                button.classList.add("bg-red-500/30", "border-red-400");
                if (freeTextField) {
                    freeTextField.classList.add("border-red-400");
                }
            }

            showAnswerFeedback(result.is_correct, result.correct_answer);

            if (result.position_results) {
                const filmButtons = document.querySelectorAll(".chronology-film");
                let correctCount = 0;

                filmButtons.forEach(function (filmButton, index) {
                    filmButton.classList.remove("border-cyan-400/30");
                    if (result.position_results[index]) {
                        filmButton.classList.add("border-emerald-400", "bg-emerald-500/10");
                        correctCount += 1;
                    } else {
                        filmButton.classList.add("border-red-400", "bg-red-500/10");
                    }
                });

                const summary = document.getElementById("chronology-summary");
                summary.textContent = correctCount + " / " + filmButtons.length + " films bien placés.";
            }

            if (result.new_badges) {
                result.new_badges.forEach(function (badge) {
                    showBadgeNotification(badge);
                });
            }

            if (result.fragment_result) {
                showFragmentNotification(result.fragment_result);
            }

            goToNextQuestion();
        }
    });
});

function updateTimerDisplay(percentage) {
    const labels = [
        document.getElementById("time-remaining"),
        document.getElementById("time-remaining-inline"),
    ];

    labels.forEach(function (label) {
        if (label) {
            label.textContent = label.id === "time-remaining" ? remainingTime : remainingTime + " s";
        }
    });

    const sideBar = document.getElementById("time-bar-side");
    if (sideBar && sideBar !== timeBar) {
        sideBar.style.width = Math.max(0, percentage) + "%";
    }
}

let timerInterval;

if (document.getElementById("riddle-submit")) {
    timerInterval = setInterval(function () {
        remainingTime -= 1;
        const percentage = (remainingTime / TOTAL_DURATION) * 100;
        setTimerPercentage(percentage);
        updateTimerDisplay(percentage);

        if (remainingTime <= 0) {
            document.getElementById("riddle-submit").click();
        }
    }, 1000);
} else {
    timerInterval = setInterval(function () {
        remainingTime -= 1;
        const percentage = (remainingTime / TOTAL_DURATION) * 100;
        setTimerPercentage(percentage);
        updateTimerDisplay(percentage);

        if (remainingTime <= 0) {
            (async function () {
                const result = await sendAnswer("timeout=true");
                if (!result) {
                    return;
                }

                if (result.new_badges) {
                    result.new_badges.forEach(function (badge) {
                        showBadgeNotification(badge);
                    });
                }

                if (result.fragment_result) {
                    showFragmentNotification(result.fragment_result);
                }

                showAnswerFeedback(result.is_correct, result.correct_answer);
                goToNextQuestion();
            })();
        }
    }, 1000);
}

const chronologyFilms = document.querySelectorAll(".chronology-film");
const chosenOrder = [];

chronologyFilms.forEach(function (filmButton) {
    filmButton.addEventListener("click", function () {
        const film = filmButton.dataset.film;
        chosenOrder.push(film);

        const badge = filmButton.querySelector(".chronology-order-badge");
        badge.textContent = chosenOrder.length;

        filmButton.disabled = true;
        filmButton.classList.add("opacity-50");

        if (chosenOrder.length === chronologyFilms.length) {
            const validateButton = document.getElementById("validate-order");
            validateButton.dataset.answer = chosenOrder.join("|");
            validateButton.disabled = false;
        }
    });
});

const riddleButton = document.getElementById("riddle-submit");

if (riddleButton) {
    riddleButton.addEventListener("click", async function (event) {
        event.preventDefault();

        const freeTextField = document.getElementById("free-text-answer");
        const answer = freeTextField.value;
        const hintIndex = riddleButton.dataset.hintIndex;

        const url = window.location.pathname + window.location.search;
        const serverResponse = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: `answer=${encodeURIComponent(answer)}&hint_index=${hintIndex}`,
        });

        const result = await serverResponse.json();

        if (!result.give_up) {
            const currentHint = document.getElementById("current-hint");
            currentHint.textContent = result.next_hint;
            riddleButton.dataset.hintIndex = parseInt(hintIndex) + 1;
            freeTextField.classList.remove("border-emerald-400", "border-red-400");
            freeTextField.classList.add("border-red-400");
            freeTextField.focus();

            remainingTime = TOTAL_DURATION;
            setTimerPercentage(100);
            return;
        }

        clearInterval(timerInterval);
        freeTextField.disabled = true;
        riddleButton.disabled = true;

        freeTextField.classList.remove("border-red-400", "border-emerald-400", "border-cyan-400/30");

        if (result.is_correct) {
            freeTextField.classList.add("border-emerald-400");
        } else {
            freeTextField.classList.add("border-red-400");
        }

        showAnswerFeedback(result.is_correct, result.correct_answer);

        if (result.new_badges) {
            result.new_badges.forEach(function (badge) {
                showBadgeNotification(badge);
            });
        }

        if (result.fragment_result) {
            showFragmentNotification(result.fragment_result);
        }

        setTimeout(function () {
            window.location.href = window.location.href.replace(
                /\/(\d+)(\?|$)/,
                function (match, position, end) {
                    return "/" + (parseInt(position) + 1) + end;
                }
            );
        }, 1500);
    });
}

const reportButton = document.getElementById("report-button");
const reportModal = document.getElementById("report-modal");
const reportCancelButton = document.getElementById("report-cancel");
const reportSubmitButton = document.getElementById("report-submit");
const reportFeedback = document.getElementById("report-feedback");

if (reportButton) {
    reportButton.addEventListener("click", function () {
        reportModal.classList.remove("hidden");
        reportModal.classList.add("flex");
        reportFeedback.textContent = "";
    });

    reportCancelButton.addEventListener("click", function () {
        reportModal.classList.add("hidden");
        reportModal.classList.remove("flex");
    });

    reportSubmitButton.addEventListener("click", async function () {
        const selectedReason = document.querySelector('input[name="report-reason"]:checked');

        if (!selectedReason) {
            reportFeedback.textContent = "Choisis un motif avant d'envoyer.";
            reportFeedback.className = "mb-3 text-sm text-red-400";
            return;
        }

        const currentQuestionId = document.getElementById("time-bar").dataset.questionId;

        const response = await fetch(`/signaler/${currentQuestionId}`, {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: `reason=${encodeURIComponent(selectedReason.value)}`,
        });

        const result = await response.json();

        if (result.success) {
            reportFeedback.textContent = "Signalement envoyé, merci !";
            reportFeedback.className = "mb-3 text-sm text-emerald-400";
            setTimeout(function () {
                reportModal.classList.add("hidden");
                reportModal.classList.remove("flex");
            }, 1200);
        } else {
            reportFeedback.textContent = "Une erreur est survenue.";
            reportFeedback.className = "mb-3 text-sm text-red-400";
        }
    });
}

// Le champ doit être prêt dès l'affichage de la question : chaque question est
// une nouvelle page, et sans cela il faut cliquer dedans à chaque fois alors que
// le chrono tourne déjà.
//
// preventScroll est indispensable : sur les modes à média — affiche, casting,
// blind test — le navigateur ferait défiler la page jusqu'au champ et masquerait
// l'image ou le lecteur qu'il faut justement regarder ou écouter.
const answerField = document.getElementById("free-text-answer");

if (answerField) {
    answerField.focus({ preventScroll: true });
}

document.addEventListener("keydown", function (event) {
    if (event.key !== "Enter") {
        return;
    }

    const freeTextField = document.getElementById("free-text-answer");
    if (!freeTextField || document.activeElement !== freeTextField) {
        return;
    }

    event.preventDefault();

    const riddleButton = document.getElementById("riddle-submit");
    const validateButton = riddleButton || document.querySelector(".answer-button");

    if (validateButton && !validateButton.disabled) {
        validateButton.click();
    }
});
