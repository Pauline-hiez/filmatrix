const avatarButtons = document.querySelectorAll(".avatar-choice");
const selectedAvatarInput = document.getElementById("selected-avatar");

avatarButtons.forEach(function (button) {
    button.addEventListener("click", function () {
        avatarButtons.forEach(function (b) {
            b.classList.remove("border-cyan-400", "bg-slate-900");
            b.classList.add("border-transparent");
        });

        button.classList.remove("border-transparent");
        button.classList.add("border-cyan-400", "bg-slate-900");

        selectedAvatarInput.value = button.dataset.avatar;
    });
});