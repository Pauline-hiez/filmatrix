document.querySelectorAll(".mode-link").forEach(function (link) {
    link.addEventListener("click", function (event) {
        event.preventDefault();
        const mode = link.dataset.mode;
        const category = document.getElementById("category").value;
        let url = `/quiz/${mode}/1`;
        if (category) {
            url += `?category=${category}`;
        }
        window.location.href = url;
    });
});
