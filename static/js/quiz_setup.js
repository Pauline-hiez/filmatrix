const startButton = document.getElementById("start-game");

startButton.addEventListener("click", function () {
    const mode = startButton.dataset.mode;
    const category = document.getElementById("category").value;
    const tag = document.getElementById("tag").value;
    const level = document.getElementById("level").value;

    const params = new URLSearchParams();

    if (category) {
        params.set("category", category);
    }
    if (tag) {
        params.set("tag_id", tag);
    }
    // Le niveau est toujours transmis : il suit ensuite le joueur d'une question
    // à l'autre, puisque quiz.js conserve la query string en changeant de position.
    params.set("level", level);

    window.location.href = `/quiz/${mode}/1?${params.toString()}`;
});
