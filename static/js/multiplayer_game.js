const gameContainer = document.getElementById("game-container");
const gameSessionId = parseInt(gameContainer.dataset.gameSessionId);
const questionIndex = parseInt(gameContainer.dataset.questionIndex);

let hasAnswered = false;

if (typeof socket !== "undefined") {
    socket.emit("join_game", { game_session_id: gameSessionId });

    socket.on("round_result", function (data) {
        if (data.next_question_index !== questionIndex + 1) {
            return;
        }

        const statusMessage = document.getElementById("game-status-message");

        if (data.winner_id === null) {
            statusMessage.textContent = "Personne n'a trouvé la bonne réponse !";
        } else {
            statusMessage.textContent = "Un point a été marqué !";
        }

        setTimeout(function () {
            window.location.reload();
        }, 2000);
    });
}

function submitGameAnswer(answer) {
    if (hasAnswered) {
        return;
    }
    hasAnswered = true;

    document.querySelectorAll(".game-answer-button").forEach(function (button) {
        button.disabled = true;
    });

    document.getElementById("game-status-message").textContent = "Réponse envoyée, en attente...";

    if (typeof socket !== "undefined") {
        socket.emit("submit_game_answer", {
            game_session_id: gameSessionId,
            answer: answer,
        });
    }
}

document.querySelectorAll(".game-answer-button").forEach(function (button) {
    button.addEventListener("click", function () {
        submitGameAnswer(button.dataset.answer);
    });
});

// Chronologie : le joueur numérote les films en cliquant dessus, et le bouton
// de validation ne s'active qu'une fois l'ordre complet. La réponse part comme
// une chaîne, le serveur la redécoupe (voir convert_answer dans src/engine.py).
const chronologyFilms = document.querySelectorAll(".game-chronology-film");
const chosenOrder = [];

chronologyFilms.forEach(function (filmButton) {
    filmButton.addEventListener("click", function () {
        chosenOrder.push(filmButton.dataset.film);

        filmButton.querySelector(".game-chronology-badge").textContent = chosenOrder.length;
        filmButton.disabled = true;
        filmButton.classList.add("opacity-50");

        if (chosenOrder.length === chronologyFilms.length) {
            const validateButton = document.getElementById("game-validate-order");
            validateButton.dataset.answer = chosenOrder.join("|");
            validateButton.disabled = false;
        }
    });
});