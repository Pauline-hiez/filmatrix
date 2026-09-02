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

    document.querySelectorAll(".question-edit-button").forEach((button) => {
        button.addEventListener("click", () => openModal(button));
    });
    closeButton?.addEventListener("click", closeModal);
    content.addEventListener("click", (event) => { if (event.target.closest("[data-modal-cancel]")) closeModal(); });
    modal.addEventListener("click", (event) => { if (event.target === modal) closeModal(); });
    document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !modal.classList.contains("hidden")) closeModal(); });
})();
