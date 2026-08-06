const TOTAL_DURATION = 10;
let remainingTime = TOTAL_DURATION;
let alreadyAnswered = false;

const timeBar = document.getElementById("time-bar");

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

            const freeTextField = document.getElementById("free-text-answer");
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

            goToNextQuestion();
        }
    });
});

let timerInterval;

if (document.getElementById("riddle-submit")) {
    timerInterval = setInterval(function () {
        remainingTime -= 1;
        const percentage = (remainingTime / TOTAL_DURATION) * 100;
        timeBar.style.width = percentage + "%";

        if (remainingTime <= 0) {
            document.getElementById("riddle-submit").click();
        }
    }, 1000);
} else {
    timerInterval = setInterval(async function () {
        remainingTime -= 1;
        const percentage = (remainingTime / TOTAL_DURATION) * 100;
        timeBar.style.width = percentage + "%";

        if (remainingTime <= 0) {
            const result = await sendAnswer("timeout=true");
            if (result && result.new_badges) {
                result.new_badges.forEach(function (badge) {
                    showBadgeNotification(badge);
                });
            }
            goToNextQuestion();
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
            freeTextField.value = "";
            freeTextField.classList.remove("border-emerald-400", "border-red-400");
            freeTextField.classList.add("border-red-400");

            remainingTime = TOTAL_DURATION;
            timeBar.style.width = "100%";
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

        if (result.new_badges) {
            result.new_badges.forEach(function (badge) {
                showBadgeNotification(badge);
            });
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
