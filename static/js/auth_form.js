// Enveloppé dans une IIFE : ce script est réinjecté à chaque ouverture de la
// modale (static/js/auth_modal.js), avec un paramètre anti-cache qui force le
// navigateur à le réexécuter. Sans cette IIFE, les "const" du haut de fichier
// entreraient en collision avec ceux de l'exécution précédente ("Identifier
// ... has already been declared") dès la deuxième ouverture - même pattern
// que static/js/admin_question_form.js.
(function () {
    // Bouton œil : bascule type="password" <-> "text" sur le champ visé par
    // data-toggle-password. Partagé par connexion et inscription (chacun n'a
    // que les boutons correspondant à ses propres champs mot de passe).
    document.querySelectorAll("[data-toggle-password]").forEach(function (button) {
        const field = document.getElementById(button.dataset.togglePassword);
        if (!field) return;

        button.addEventListener("click", function () {
            const showing = field.type === "text";
            field.type = showing ? "password" : "text";
            button.setAttribute("aria-label", showing ? "Afficher le mot de passe" : "Masquer le mot de passe");
            button.classList.toggle("text-cyan-400", !showing);
        });
    });

    // Inscription uniquement : prévient la faute de frappe avant l'envoi
    // plutôt que de laisser le serveur la révéler après coup - la
    // confirmation reste aussi vérifiée côté serveur (routes/auth.py), ceci
    // n'est qu'un confort.
    const passwordField = document.getElementById("register-password");
    const confirmField = document.getElementById("register-password-confirm");
    if (passwordField && confirmField) {
        function checkMatch() {
            const mismatch = confirmField.value.length > 0 && confirmField.value !== passwordField.value;
            confirmField.classList.toggle("border-red-400", mismatch);
            confirmField.classList.toggle("border-cyan-400/30", !mismatch);
        }
        passwordField.addEventListener("input", checkMatch);
        confirmField.addEventListener("input", checkMatch);
    }
})();
