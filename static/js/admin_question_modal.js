(() => {
    const modal = document.getElementById("question-edit-modal");
    const content = document.getElementById("question-edit-content");
    const closeButton = document.getElementById("question-edit-close");
    if (!modal || !content) return;

    function closeModal() {
        modal.classList.add("hidden");
        modal.classList.remove("flex");
        content.innerHTML = '<p class="py-12 text-center text-slate-400">Chargement…</p>';
        document.body.classList.remove("overflow-hidden");
    }

    async function openModal(button) {
        modal.classList.remove("hidden");
        modal.classList.add("flex");
        document.body.classList.add("overflow-hidden");
        modal.querySelector(".question-edit-dialog")?.classList.remove("hidden");
        try {
            const response = await fetch(button.dataset.editUrl, { headers: { "X-Requested-With": "XMLHttpRequest" } });
            if (!response.ok) throw new Error("Impossible de charger la question");
            const html = await response.text();
            const documentFragment = new DOMParser().parseFromString(html, "text/html");
            const form = documentFragment.querySelector("#question-form");
            if (!form) throw new Error("Formulaire introuvable");
            // Le fragment renvoyé (admin/question_form_fields.html) pré-remplit déjà
            // chaque champ côté serveur : rien à recopier depuis une autre source.
            // Il reprend les mêmes id/classes que la page complète (mode-select,
            // .mode-fields, tag-search...), donc le même script sait l'initialiser.
            content.innerHTML = "";
            content.appendChild(form);
            // Rechargé à chaque ouverture (paramètre anti-cache + IIFE côté script,
            // cf. son en-tête) : un <script src> déjà exécuté une fois ne se
            // relance pas tout seul à la deuxième ouverture de la modale.
            const script = document.createElement("script");
            script.src = `/static/js/admin_question_form.js?t=${Date.now()}`;
            content.appendChild(script);
        } catch (error) {
            content.innerHTML = '<p class="py-12 text-center text-red-400">Le formulaire n’a pas pu être chargé.</p>';
        }
    }

    // Raccroche la ligne modifiée à jour à la place de l'ancienne plutôt que
    // de renaviguer vers /admin/questions : sur cette page, avec beaucoup de
    // questions à corriger d'affilée, revenir en haut de la liste à chaque
    // sauvegarde faisait perdre le défilement et la section en cours.
    async function refreshRow(questionId) {
        const response = await fetch(window.location.pathname + window.location.search);
        const html = await response.text();
        const freshDocument = new DOMParser().parseFromString(html, "text/html");
        const freshRow = freshDocument.getElementById(`question-row-${questionId}`);
        const currentRow = document.getElementById(`question-row-${questionId}`);
        if (!freshRow || !currentRow) return;
        // Met à jour la ligne en place (contenu + attributs de recherche)
        // plutôt que de la remplacer : admin_questions_search.js capture ses
        // lignes une fois au chargement (allRows) - un nouveau nœud sortirait
        // de son suivi et échapperait ensuite à la recherche/pagination.
        currentRow.innerHTML = freshRow.innerHTML;
        currentRow.setAttribute("data-search-text", freshRow.getAttribute("data-search-text") || "");
        currentRow.setAttribute("data-display-text", freshRow.getAttribute("data-display-text") || "");
    }

    async function submitForm(form) {
        const submitButton = form.querySelector('button[type="submit"]');
        if (submitButton) submitButton.disabled = true;
        try {
            const response = await fetch(form.action, {
                method: "POST",
                body: new FormData(form),
                headers: { "X-Requested-With": "XMLHttpRequest" },
            });
            const data = await response.json();
            if (!data.success) {
                alert(data.error || "La question n'a pas pu être enregistrée.");
                return;
            }
            const match = form.action.match(/\/admin\/questions\/(\d+)\/modifier/);
            if (match) await refreshRow(match[1]);
            closeModal();
        } catch (error) {
            alert("La question n'a pas pu être enregistrée.");
        } finally {
            if (submitButton) submitButton.disabled = false;
        }
    }

    document.querySelectorAll(".question-edit-button").forEach((button) => {
        button.addEventListener("click", () => openModal(button));
    });
    closeButton?.addEventListener("click", closeModal);
    content.addEventListener("click", (event) => { if (event.target.closest("[data-modal-cancel]")) closeModal(); });
    // Écouteur délégué sur #question-edit-content plutôt que sur le <form>
    // directement : ce dernier est réinjecté à chaque ouverture, mais son
    // parent, lui, ne change jamais. Se déclenche après le script du
    // formulaire (admin_question_form.js) qui a déjà rempli les champs
    // cachés (payload, correct_answer...) au moment de la remontée (bubble)
    // de l'événement jusqu'ici.
    content.addEventListener("submit", (event) => {
        if (event.target.id !== "question-form") return;
        event.preventDefault();
        submitForm(event.target);
    });
    modal.addEventListener("click", (event) => { if (event.target === modal) closeModal(); });
    document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !modal.classList.contains("hidden")) closeModal(); });
})();
