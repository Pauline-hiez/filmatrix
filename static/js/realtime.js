// Le garde-fou doit interrompre le script : se contenter de journaliser laissait
// io() lever une ReferenceError, et « socket » n'était jamais défini — ce que
// multiplayer_game.js interprète silencieusement comme « pas de temps réel ».
let socket;

if (typeof io === "undefined") {
    console.error(
        "Socket.IO n'a pas pu être chargé : les notifications en temps réel sont désactivées."
    );
} else {
    socket = io();

    socket.on("new_notification", function (data) {
        updateBadge();
        showToast(data);
        insertIntoOpenDropdown(data);
    });

    // Une déconnexion passait totalement inaperçue : la page semblait vivante
    // alors que plus rien n'arrivait. Socket.IO se reconnecte seul, et le
    // serveur réinscrit alors le joueur dans son salon.
    socket.on("connect_error", function (error) {
        console.warn("Notifications en direct : connexion impossible —", error.message);
    });
}

/** Crée le badge de la cloche, ou incrémente celui déjà présent. */
function updateBadge() {
    const notificationBadge = document.getElementById("notification-badge");
    const notificationBell = document.getElementById("notification-bell");

    if (notificationBell && !notificationBadge) {
        const badge = document.createElement("span");
        badge.id = "notification-badge";
        // Mêmes classes que le badge rendu par base.html : sans cela un badge
        // apparu en direct ne se place pas au même endroit qu'après un
        // rechargement de page.
        badge.className =
            "absolute right-0 top-0 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white";
        badge.textContent = "1";
        notificationBell.appendChild(badge);
    } else if (notificationBadge) {
        const currentCount = parseInt(notificationBadge.textContent) || 0;
        notificationBadge.textContent = currentCount < 9 ? currentCount + 1 : "9+";
    }
}

/** Affiche l'alerte en bas à droite pendant quelques secondes. */
function showToast(data) {
    let container = document.getElementById("toast-container");

    if (!container) {
        container = document.createElement("div");
        container.id = "toast-container";
        container.className = "fixed bottom-4 right-4 z-50 flex flex-col gap-2";
        document.body.appendChild(container);
    }

    const toast = document.createElement(data.link ? "a" : "div");
    if (data.link) {
        toast.href = data.link;
    }
    toast.className =
        "block max-w-xs bg-slate-900 border border-cyan-400/50 text-slate-100 text-sm rounded-lg shadow-lg px-4 py-3 hover:border-cyan-400 transition";
    toast.textContent = data.message;

    container.appendChild(toast);

    setTimeout(function () {
        toast.remove();
    }, 6000);
}

/** Ajoute la notification en haut du menu déroulant si celui-ci est déjà ouvert. */
function insertIntoOpenDropdown(data) {
    const dropdown = document.getElementById("notification-dropdown");

    if (!dropdown || dropdown.classList.contains("hidden")) {
        return;
    }

    const item = document.createElement(data.link ? "a" : "div");
    if (data.link) {
        item.href = data.link;
    }
    item.className =
        "block px-4 py-3 text-sm text-slate-200 hover:bg-slate-800 transition border-b border-slate-800 last:border-0";
    item.textContent = data.message;

    dropdown.prepend(item);
}
