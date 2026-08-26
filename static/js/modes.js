document.querySelectorAll(".mode-link").forEach(function (link) {
    link.addEventListener("click", function (event) {
        event.preventDefault();
        const mode = link.dataset.mode;
        const category = document.getElementById("category").value;
        const tag = document.getElementById("tag").value;

        let url = `/quiz/${mode}/1`;
        const params = new URLSearchParams();

        if (category) {
            params.set("category", category);
        }
        if (tag) {
            params.set("tag_id", tag);
        }

        const queryString = params.toString();
        if (queryString) {
            url += `?${queryString}`;
        }

        window.location.href = url;
    });
});