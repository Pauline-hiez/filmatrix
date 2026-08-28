const startButton = document.getElementById("start-game");

startButton.addEventListener("click", function () {
    const mode = startButton.dataset.mode;
    const tagIds = Array.from(document.querySelectorAll("[data-tag-filter]"))
        .map(function (select) { return select.value; })
        .filter(Boolean);
    const level = document.getElementById("level").value;
    const contentType = document.getElementById("content-type").value;

    const params = new URLSearchParams();

    tagIds.forEach(function (tagId) {
        params.append("tag_id", tagId);
    });
    if (contentType) {
        params.set("content_type", contentType);
    }
    // Le niveau est toujours transmis : il suit ensuite le joueur d'une question
    // à l'autre, puisque quiz.js conserve la query string en changeant de position.
    params.set("level", level);

    window.location.href = `/quiz/${mode}/1?${params.toString()}`;
});
