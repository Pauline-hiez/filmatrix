const boutonMenu = document.getElementById("bouton-menu");
const menuMobile = document.getElementById("menu-mobile");

boutonMenu.addEventListener("click", function () {
    menuMobile.classList.toggle("hidden");
    menuMobile.classList.toggle("flex");
});