(() => {
    // Copie de admin_question_modal.js adaptée à la revue d'une suggestion de
    // question : la soumission de ce formulaire approuve la suggestion avec
    // le contenu (éventuellement modifié) qu'il contient, ce n'est pas une
    // simple édition.
    const modal = document.getElementById("suggestion-review-modal");
    const content = document.getElementById("suggestion-review-content");
    const closeButton = document.getElementById("suggestion-review-close");
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
            const response = await fetch(button.dataset.editUrl, { headers: { "X-Requested-With": "XMLHttpRequest" } });
            if (!response.ok) throw new Error("Impossible de charger la suggestion");
            const html = await response.text();
            const documentFragment = new DOMParser().parseFromString(html, "text/html");
            const form = documentFragment.querySelector("#question-form");
            if (!form) throw new Error("Formulaire introuvable");
            content.innerHTML = "";
            content.appendChild(form);
            const script = document.createElement("script");
            script.src = `/static/js/admin_question_form.js?t=${Date.now()}`;
            content.appendChild(script);
        } catch (error) {
            content.innerHTML = '<p class="py-12 text-center text-red-400">La suggestion n’a pas pu être chargée.</p>';
        }
    }

    // Comme admin_question_modal.js : raccroche la ligne à jour à la place de
    // l'ancienne plutôt que de renaviguer, pour garder la position dans une
    // longue file de suggestions à traiter.
    async function refreshRow(submissionId) {
        const response = await fetch(window.location.pathname + window.location.search);
        const html = await response.text();
        const freshDocument = new DOMParser().parseFromString(html, "text/html");
        const freshRow = freshDocument.getElementById(`suggestion-row-${submissionId}`);
        const currentRow = document.getElementById(`suggestion-row-${submissionId}`);
        if (!freshRow || !currentRow) return;
        currentRow.innerHTML = freshRow.innerHTML;
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
                alert(data.error || "La suggestion n'a pas pu être approuvée.");
                return;
            }
            const match = form.action.match(/\/admin\/suggestions\/(\d+)\/modifier/);
            if (match) await refreshRow(match[1]);
            closeModal();
        } catch (error) {
            alert("La suggestion n'a pas pu être approuvée.");
        } finally {
            if (submitButton) submitButton.disabled = false;
        }
    }

    document.querySelectorAll(".suggestion-review-button").forEach((button) => {
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
