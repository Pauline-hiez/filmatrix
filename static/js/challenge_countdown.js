// Compte à rebours jusqu'au renouvellement du défi du jour (minuit local).
// Cible tout élément portant data-challenge-countdown, sur l'accueil et le
// profil : un seul minuteur pour les deux affichages de la même donnée.

(function () {
    const elements = document.querySelectorAll("[data-challenge-countdown]");
    if (!elements.length) {
        return;
    }

    function pad(value) {
        return String(value).padStart(2, "0");
    }

    function tick() {
        const now = new Date();
        const nextMidnight = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
        const remaining = Math.max(0, nextMidnight - now);

        const hours = Math.floor(remaining / 3600000);
        const minutes = Math.floor((remaining % 3600000) / 60000);
        const seconds = Math.floor((remaining % 60000) / 1000);
        const label = `${hours}h ${pad(minutes)}m ${pad(seconds)}s`;

        elements.forEach(function (element) {
            element.textContent = label;
        });
    }

    tick();
    setInterval(tick, 1000);
})();
