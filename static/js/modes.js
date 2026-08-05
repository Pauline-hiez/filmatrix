document.querySelectorAll(".lien-mode").forEach(function (lien) {
    lien.addEventListener("click", function (evenement) {
        evenement.preventDefault();
        const mode = lien.dataset.mode;
        const categorie = document.getElementById("categorie").value;
        let url = `/quiz/${mode}/1`;
        if (categorie) {
            url += `?category=${categorie}`;
        }
        window.location.href = url;
    });
});