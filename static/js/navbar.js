const menuButton = document.getElementById("menu-button");
const mobileMenu = document.getElementById("mobile-menu");

menuButton.addEventListener("click", function () {
    const isOpen = mobileMenu.classList.toggle("flex");
    mobileMenu.classList.toggle("hidden");

    // Le bouton doit annoncer l'état du menu : sans cela un lecteur d'écran
    // le décrit comme replié même une fois ouvert.
    menuButton.setAttribute("aria-expanded", String(isOpen));
});
