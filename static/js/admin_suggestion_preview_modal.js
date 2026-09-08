(() => {
    // Modale d'aperçu en lecture seule d'une suggestion : contrairement à
    // admin_question_modal.js / admin_suggestion_review_modal.js, il n'y a
    // ici ni formulaire ni script à réinjecter, juste du contenu à afficher.
    const modal = document.getElementById("suggestion-preview-modal");
    const content = document.getElementById("suggestion-preview-content");
    const closeButton = document.getElementById("suggestion-preview-close");
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
        try {
            const response = await fetch(button.dataset.previewUrl, { headers: { "X-Requested-With": "XMLHttpRequest" } });
            if (!response.ok) throw new Error("Impossible de charger l'aperçu");
            content.innerHTML = await response.text();
        } catch (error) {
            content.innerHTML = '<p class="py-12 text-center text-red-400">L’aperçu n’a pas pu être chargé.</p>';
        }
    }

    document.querySelectorAll(".suggestion-preview-button").forEach((button) => {
        button.addEventListener("click", () => openModal(button));
    });
    closeButton?.addEventListener("click", closeModal);
    modal.addEventListener("click", (event) => { if (event.target === modal) closeModal(); });
    document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !modal.classList.contains("hidden")) closeModal(); });
})();
