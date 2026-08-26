const countdownEl = document.getElementById("countdown");

if (countdownEl) {
    const isoDate = countdownEl.dataset.expiresAt.replace(" ", "T");
    const expiresAt = new Date(isoDate).getTime();

    const interval = setInterval(function () {
        const remainingMs = expiresAt - Date.now();

        if (remainingMs <= 0) {
            clearInterval(interval);
            window.location.reload();
            return;
        }

        const minutes = Math.floor(remainingMs / 60000);
        const seconds = Math.floor((remainingMs % 60000) / 1000);
        countdownEl.textContent = String(minutes).padStart(2, "0") + ":" + String(seconds).padStart(2, "0");
    }, 1000);
}

const waitingIndicator = document.getElementById("waiting-for-guest");

if (waitingIndicator) {
    const gameSessionId = waitingIndicator.dataset.gameSessionId;

    // Voie principale : l'invité accepte, le serveur prévient l'hôte immédiatement.
    if (typeof socket !== "undefined") {
        socket.on("game_started", function (data) {
            window.location.href = data.redirect_url;
        });
    }

    // Filet de sécurité si le websocket est indisponible ou la notification perdue.
    const statusPolling = setInterval(async function () {
        const response = await fetch(`/multijoueur/${gameSessionId}/statut`);
        const data = await response.json();

        if (data.status !== "invited") {
            clearInterval(statusPolling);
            window.location.reload();
        }
    }, 2000);
}

const gameStartingEl = document.getElementById("game-starting");

if (gameStartingEl) {
    setTimeout(function () {
        window.location.href = gameStartingEl.dataset.playUrl;
    }, 1500);
}