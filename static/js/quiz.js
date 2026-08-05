document.querySelectorAll(".bouton-reponse").forEach(function (bouton) {
    bouton.addEventListener("click", async function (evenement) {
        evenement.preventDefault();

        document.querySelectorAll(".bouton-reponse").forEach(function (b) {
            b.disabled = true;
        });

        const reponse = bouton.dataset.reponse;
        const url = window.location.pathname + window.location.search;

        const reponseServeur = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: `reponse=${encodeURIComponent(reponse)}`,
        });

        const resultat = await reponseServeur.json();

        if (resultat.est_correct) {
            bouton.classList.add("bg-emerald-500/30", "border-emerald-400");
        } else {
            bouton.classList.add("bg-red-500/30", "border-red-400");
        }

        setTimeout(function () {
            window.location.href = window.location.href.replace(
                /\/(\d+)(\?|$)/,
                function (correspondance, position, fin) {
                    return "/" + (parseInt(position) + 1) + fin;
                }
            );
        }, 1500);
    });
});