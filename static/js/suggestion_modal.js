(() => {
    // Copie de admin_question_modal.js adaptée à la création d'une suggestion
    // de question par un joueur : au succès, on redirige vers l'historique
    // plutôt que de patcher une ligne de tableau (il n'y en a pas encore).
    const modal = document.getElementById("suggestion-modal");
    const content = document.getElementById("suggestion-modal-content");
    const closeButton = document.getElementById("suggestion-modal-close");
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
        modal.querySelector(".suggestion-modal-dialog")?.classList.remove("hidden");
        try {
            const response = await fetch(button.dataset.editUrl, { headers: { "X-Requested-With": "XMLHttpRequest" } });
            if (!response.ok) throw new Error("Impossible de charger le formulaire");
            const html = await response.text();
            const documentFragment = new DOMParser().parseFromString(html, "text/html");
            const form = documentFragment.querySelector("#question-form");
            if (!form) throw new Error("Formulaire introuvable");
            content.innerHTML = "";
            content.appendChild(form);
            // Rechargé à chaque ouverture (paramètre anti-cache + IIFE côté script,
            // cf. admin_question_form.js) : un <script src> déjà exécuté une fois
            // ne se relance pas tout seul à la deuxième ouverture de la modale.
            const script = document.createElement("script");
            script.src = `/static/js/admin_question_form.js?t=${Date.now()}`;
            content.appendChild(script);
        } catch (error) {
            content.innerHTML = '<p class="py-12 text-center text-red-400">Le formulaire n’a pas pu être chargé.</p>';
        }
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
                alert(data.error || "La suggestion n'a pas pu être envoyée.");
                return;
            }
            // Contrairement à l'édition d'une question, il n'y a pas de ligne à
            // patcher : la suggestion vient d'être créée, direction l'historique.
            window.location.href = data.redirect;
        } catch (error) {
            alert("La suggestion n'a pas pu être envoyée.");
        } finally {
            if (submitButton) submitButton.disabled = false;
        }
    }

    document.querySelectorAll(".suggestion-new-button").forEach((button) => {
        button.addEventListener("click", () => openModal(button));
    });
    closeButton?.addEventListener("click", closeModal);
    content.addEventListener("click", (event) => { if (event.target.closest("[data-modal-cancel]")) closeModal(); });
    content.addEventListener("submit", (event) => {
        if (event.target.id !== "question-form") return;
        event.preventDefault();
        submitForm(event.target);
    });
    modal.addEventListener("click", (event) => { if (event.target === modal) closeModal(); });
    document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !modal.classList.contains("hidden")) closeModal(); });
})();
