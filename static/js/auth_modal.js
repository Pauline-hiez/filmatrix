// Modale d'authentification (connexion / inscription) pour tout le site.
//
// Les liens de la navbar portent data-auth-open="login|register" : au clic, on
// intercepte et on charge en AJAX le fragment de formulaire correspondant
// (auth/_connexion_form.html ou auth/_inscription_form.html), déjà servi par
// routes/auth.py pour les requêtes XHR. Sans JS, les liens restent de vraies
// navigations vers les pages complètes (amélioration progressive).
//
// Le conteneur de modale vit dans base.html ; ce script ne fait que le remplir,
// l'afficher et gérer son cycle de vie (fermeture, Escape, clic dehors, bascule
// login <-> register via data-auth-switch présent dans les deux fragments).
(function () {
    "use strict";

    const overlay = document.getElementById("auth-modal-overlay");
    if (!overlay) return;

    const panel = overlay.querySelector("[data-auth-panel]");
    const content = document.getElementById("auth-modal-content");
    const closeButtons = overlay.querySelectorAll("[data-auth-dismiss]");
    let lastFocused = null;

    // Repos : la modale n'est jamais dans le flux ni visible (hidden + opacity).
    // L'opacité est gérée avec les utilitaires Tailwind (opacity-0 <->
    // opacity-100) : une classe maison perdrait contre opacity-0, utilities
    // venant après components dans l'ordre des couches CSS.
    function openModal() {
        lastFocused = document.activeElement;
        overlay.classList.remove("hidden");
        // Double frame d'animation : laisser le navigateur peindre l'état
        // initial (opacity 0) avant d'ajouter la classe visible, sinon la
        // transition est ignorée et le fondu d'apparition ne joue pas.
        requestAnimationFrame(function () {
            requestAnimationFrame(function () {
                overlay.classList.remove("opacity-0");
                overlay.classList.add("opacity-100");
            });
        });
        document.body.style.overflow = "hidden";
        overlay.addEventListener("transitionend", focusFirstField, { once: true });
        // Filet si transitionend ne part pas (prefers-reduced-motion, etc.)
        setTimeout(focusFirstField, 350);
    }

    function focusFirstField() {
        const field = content.querySelector("input:not([type=hidden])");
        if (field && window.innerWidth > 640) field.focus();
    }

    function closeModal() {
        overlay.classList.remove("opacity-100");
        overlay.classList.add("opacity-0");
        document.body.style.overflow = "";
        const hide = function () {
            overlay.classList.add("hidden");
            content.innerHTML = "";
        };
        // Attendre la fin du fondu de sortie avant de retirer du DOM.
        overlay.addEventListener("transitionend", hide, { once: true });
        setTimeout(hide, 250);
        if (lastFocused && typeof lastFocused.focus === "function") lastFocused.focus();
    }

    closeButtons.forEach(function (button) {
        button.addEventListener("click", closeModal);
    });

    // Clic sur le fond sombre (pas sur la carte) : ferme, comme l'attendent
    // les usages modaux standard.
    overlay.addEventListener("mousedown", function (event) {
        if (event.target === overlay) closeModal();
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && !overlay.classList.contains("hidden")) closeModal();
    });

    function injectFragment(html) {
        content.innerHTML = html;
        // Les fragments incluent <script src=auth_form.js> : via innerHTML, un
        // <script> externe inséré ne s'exécute pas tout seul (comportement HTML
        // standard). On recrée donc chaque script à la main pour brancher l'œil
        // mot de passe et la vérification de confirmation.
        content.querySelectorAll("script").forEach(function (oldScript) {
            const script = document.createElement("script");
            // Paramètre anti-cache : le fichier peut avoir été déjà chargé sur
            // cette page, on veut garantir une ré-exécution propre (le fichier
            // est une IIFE, sans risque de collision d'identifiants).
            script.src = oldScript.getAttribute("src") + "?v=" + Date.now();
            document.body.appendChild(script);
            oldScript.remove();
        });
        openModal();
    }

    function loadFragment(kind) {
        const url = (kind === "register" ? "/inscription" : "/connexion") + "?modal=1";
        fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } })
            .then(function (response) {
                if (!response.ok) throw new Error("HTTP " + response.status);
                return response.text();
            })
            .then(injectFragment)
            .catch(function () {
                // Secours : navigation classique vers la page complète.
                window.location.href = kind === "register" ? "/inscription" : "/connexion";
            });
    }

    // Un seul listener délégué pour tout le site : liens d'ouverture navbar,
    // liens de bascule dans les fragments, croix et boutons de fermeture.
    // La délégation survit au remplacement du contenu (innerHTML), contrairement
    // à des listeners posés élément par élément.
    document.addEventListener("click", function (event) {
        const opener = event.target.closest("[data-auth-open]");
        if (opener) {
            event.preventDefault();
            loadFragment(opener.dataset.authOpen === "register" ? "register" : "login");
            return;
        }
        const switcher = event.target.closest("[data-auth-switch]");
        if (switcher && !overlay.classList.contains("hidden")) {
            event.preventDefault();
            loadFragment(switcher.dataset.authSwitch === "register" ? "register" : "login");
            return;
        }
        if (event.target.closest("[data-modal-close]") && !overlay.classList.contains("hidden")) {
            event.preventDefault();
            closeModal();
        }
    });

    // Les formulaires des fragments POSTent normalement ; en modale on veut
    // rester dedans : soumission AJAX, réponse JSON du serveur soit erreur
    // (on réinjecte le fragment rendu), soit succès (redirection navigateur).
    content.addEventListener("submit", function (event) {
        const form = event.target.closest("form");
        if (!form || !overlay.contains(form)) return;
        event.preventDefault();

        const submitButton = form.querySelector("button[type=submit]");
        if (submitButton) submitButton.disabled = true;

        fetch(form.action, {
            method: "POST",
            body: new FormData(form),
            headers: { "X-Requested-With": "XMLHttpRequest" },
        })
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.success && data.redirect) {
                    window.location.href = data.redirect;
                    return;
                }
                if (data.html) injectFragment(data.html);
            })
            .catch(function () { form.submit(); }) // secours : POST classique
            .finally(function () {
                if (submitButton) submitButton.disabled = false;
            });
    });

    // Pseudo suggéré (fragment inscription) : un <script> inline ne s'exécute
    // pas après innerHTML, donc délégation ici aussi.
    content.addEventListener("click", function (event) {
        const suggestion = event.target.closest("#use-username-suggestion");
        if (!suggestion) return;
        const field = content.querySelector("#register-username");
        if (field) {
            field.value = suggestion.dataset.suggestion;
            field.focus();
        }
    });
})();
