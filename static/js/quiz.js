const DUREE_TOTALE = 10;
let tempsRestant = DUREE_TOTALE;
let dejaRepondu = false;

const barreTemps = document.getElementById("barre-temps");

function allerALaQuestionSuivante() {
    setTimeout(function () {
        window.location.href = window.location.href.replace(
            /\/(\d+)(\?|$)/,
            function (correspondance, position, fin) {
                return "/" + (parseInt(position) + 1) + fin;
            }
        );
    }, 1500);
}

async function envoyerReponse(corps) {
    if (dejaRepondu) {
        return;
    }
    dejaRepondu = true;
    clearInterval(intervalleChrono);

    document.querySelectorAll(".bouton-reponse").forEach(function (b) {
        b.disabled = true;
    });

    const url = window.location.pathname + window.location.search;
    const reponseServeur = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: corps,
    });

    const resultat = await reponseServeur.json();
    return resultat;
}

document.querySelectorAll(".bouton-reponse").forEach(function (bouton) {
    bouton.addEventListener("click", async function (evenement) {
        evenement.preventDefault();
        const reponse = bouton.dataset.reponse;
        const resultat = await envoyerReponse(`reponse=${encodeURIComponent(reponse)}`);

        if (resultat) {
            if (resultat.est_correct) {
                bouton.classList.add("bg-emerald-500/30", "border-emerald-400");
            } else {
                bouton.classList.add("bg-red-500/30", "border-red-400");
            }
            allerALaQuestionSuivante();
        }
    });
});

const intervalleChrono = setInterval(async function () {
    tempsRestant -= 1;
    const pourcentage = (tempsRestant / DUREE_TOTALE) * 100;
    barreTemps.style.width = pourcentage + "%";

    if (tempsRestant <= 0) {
        await envoyerReponse("timeout=true");
        allerALaQuestionSuivante();
    }
}, 1000);