const startButton = document.getElementById("start-game");

startButton.addEventListener("click", function () {
    const mode = startButton.dataset.mode;
    const tag = document.getElementById("tag").value;
    const level = document.getElementById("level").value;
    const contentType = document.getElementById("content-type").value;

    const params = new URLSearchParams();

    if (tag) {
        params.set("tag_id", tag);
    }
    if (contentType) {
        params.set("content_type", contentType);
    }
    // Le niveau est toujours transmis : il suit ensuite le joueur d'une question
    // à l'autre, puisque quiz.js conserve la query string en changeant de position.
    params.set("level", level);

    window.location.href = `/quiz/${mode}/1?${params.toString()}`;
});
