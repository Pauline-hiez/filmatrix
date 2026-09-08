// Bulle de messagerie flottante (templates/partials/chat_widget.html),
// incluse une fois dans base.html donc présente sur toutes les pages —
// y compris pendant une partie multijoueur. L'historique se charge par
// fetch (filmatrix/routes/chat.py), l'envoi et la réception passent
// entièrement par Socket.IO (filmatrix/realtime/events.py), sur le même
// socket que les notifications et la présence (voir realtime.js).

(function () {
    const widget = document.getElementById("chat-widget");
    const bubble = document.getElementById("chat-bubble");
    const panel = document.getElementById("chat-panel");

    if (!widget || !bubble || !panel) {
        return;
    }

    const CURRENT_USER_ID = Number(widget.dataset.currentUserId);

    const backButton = document.getElementById("chat-back");
    const closeButton = document.getElementById("chat-close");
    const inviteButton = document.getElementById("chat-invite");
    const titleEl = document.getElementById("chat-panel-title");
    const friendListEl = document.getElementById("chat-friend-list");
    const threadEl = document.getElementById("chat-thread");
    const messagesEl = document.getElementById("chat-messages");
    const formEl = document.getElementById("chat-form");
    const inputEl = document.getElementById("chat-input");
    const emojiButton = document.getElementById("chat-emoji-button");
    const emojiPicker = document.getElementById("chat-emoji-picker");

    const EMOJIS = [
        "😀", "😂", "😍", "😎", "🤔", "😢",
        "😡", "👍", "👎", "🙏", "🎬", "🍿",
        "🔥", "💯", "🎉", "😱", "🥳", "😴",
        "🤯", "😅", "❤️", "👀", "🤝", "✨",
    ];

    let friends = [];
    let activeFriendId = null;
    let panelOpen = false;
    // true une fois déplacé dans une carte de page (voir embedIn tout en
    // bas) : le panneau reste alors ouvert en permanence, sans bulle ni
    // fermeture au clic extérieur.
    let embedded = false;

    // Compteur du badge tenu à part de la liste `friends` (plutôt que
    // recalculé par une somme dessus) : tant que la bulle n'a jamais été
    // ouverte, `friends` est vide, et un message reçu en direct aurait sinon
    // fait retomber le badge à 0 au lieu de l'incrémenter. Initialisé avec
    // le badge déjà rendu côté serveur au chargement de la page.
    const initialBadge = document.getElementById("chat-badge");
    let unreadBubbleTotal = initialBadge ? parseInt(initialBadge.textContent, 10) || 0 : 0;

    function truncate(text, max) {
        if (!text) return "";
        return text.length > max ? text.slice(0, max - 1) + "…" : text;
    }

    function setBubbleBadge(total) {
        unreadBubbleTotal = Math.max(total, 0);
        let badge = document.getElementById("chat-badge");
        if (unreadBubbleTotal <= 0) {
            if (badge) badge.remove();
            return;
        }
        if (!badge) {
            badge = document.createElement("span");
            badge.id = "chat-badge";
            badge.className = "chat-badge";
            bubble.appendChild(badge);
        }
        badge.textContent = unreadBubbleTotal < 10 ? String(unreadBubbleTotal) : "9+";
    }

    function sortFriends() {
        friends.sort(function (a, b) {
            if (a.unread_count !== b.unread_count) return b.unread_count - a.unread_count;
            const aDate = a.last_message_at || "";
            const bDate = b.last_message_at || "";
            return bDate.localeCompare(aDate);
        });
    }

    function renderFriendList() {
        if (!friends.length) {
            friendListEl.innerHTML = '<p class="chat-empty">Ajoute des amis pour pouvoir leur écrire.</p>';
            return;
        }

        friendListEl.innerHTML = "";
        friends.forEach(function (friend) {
            const item = document.createElement("button");
            item.type = "button";
            item.className = "chat-friend-item" + (friend.unread_count > 0 ? " has-unread" : "");
            item.dataset.friendId = friend.friend_id;

            const previewPrefix = friend.last_message_from_me ? "Toi : " : "";
            const preview = friend.last_message
                ? previewPrefix + truncate(friend.last_message, 40)
                : "Dis bonjour \u{1F44B}";

            item.innerHTML =
                '<span class="chat-friend-avatar">' +
                    '<img src="' + friend.avatar_url + '" alt="">' +
                    '<span class="presence-dot bg-slate-600" data-user-id="' + friend.friend_id + '"></span>' +
                '</span>' +
                '<span class="chat-friend-info">' +
                    '<span class="chat-friend-name">' + friend.username + '</span>' +
                    '<span class="chat-friend-preview"></span>' +
                '</span>';
            item.querySelector(".chat-friend-preview").textContent = preview;

            if (friend.unread_count > 0) {
                const unreadBadge = document.createElement("span");
                unreadBadge.className = "chat-friend-unread";
                unreadBadge.textContent = friend.unread_count < 10 ? String(friend.unread_count) : "9+";
                item.appendChild(unreadBadge);
            }

            item.addEventListener("click", function () {
                openThread(friend.friend_id);
            });

            friendListEl.appendChild(item);
        });

        // La présence est déjà connue de realtime.js (presence_snapshot) : on
        // ne fait que redemander l'état courant pour peindre ces nouvelles
        // pastilles fraîchement insérées dans le DOM. `socket` est la
        // variable globale déclarée par realtime.js (chargé juste avant),
        // pas window.socket : un `let` de premier niveau dans un script
        // classique n'atterrit jamais sur `window`, seul son nom nu reste
        // partagé entre scripts classiques.
        if (typeof socket !== "undefined" && socket) {
            socket.emit("request_presence");
        }
    }

    // Pas de groupe capturant : avec un groupe, String.replace() passe le
    // texte capturé en 2e argument du callback (avant l'offset), ce qui
    // décalait tout — "offset" recevait en fait l'URL elle-même.
    const URL_PATTERN = /https?:\/\/[^\s]+/g;

    // Convertit un texte en noeuds DOM (texte + <a> pour les liens), plutôt
    // que via innerHTML : le corps d'un message reste du texte simple côté
    // serveur (pas de HTML), un lien de type "invitation à jouer" (voir
    // openInviteButton) doit rester cliquable sans jamais interpréter le
    // reste du message comme du balisage.
    function linkify(text) {
        const fragment = document.createDocumentFragment();
        let lastIndex = 0;
        text.replace(URL_PATTERN, function (url, offset) {
            if (offset > lastIndex) {
                fragment.appendChild(document.createTextNode(text.slice(lastIndex, offset)));
            }
            const link = document.createElement("a");
            link.href = url;
            link.textContent = url;
            link.target = "_blank";
            link.rel = "noopener";
            fragment.appendChild(link);
            lastIndex = offset + url.length;
            return url;
        });
        if (lastIndex < text.length) {
            fragment.appendChild(document.createTextNode(text.slice(lastIndex)));
        }
        return fragment;
    }

    function renderMessage(message) {
        const bubbleEl = document.createElement("div");
        const mine = message.sender_id === CURRENT_USER_ID;
        bubbleEl.className = "chat-bubble-msg " + (mine ? "is-mine" : "is-theirs");
        bubbleEl.appendChild(linkify(message.body));
        messagesEl.appendChild(bubbleEl);
    }

    function scrollMessagesToBottom() {
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    let activeFriendUsername = null;

    function showFriendListView() {
        activeFriendId = null;
        activeFriendUsername = null;
        threadEl.classList.add("hidden");
        friendListEl.classList.remove("hidden");
        backButton.classList.add("hidden");
        inviteButton.classList.add("hidden");
        titleEl.textContent = "Messagerie";
        renderFriendList();
    }

    async function openThread(friendId) {
        activeFriendId = friendId;
        friendListEl.classList.add("hidden");
        threadEl.classList.remove("hidden");
        backButton.classList.remove("hidden");
        inviteButton.classList.remove("hidden");
        messagesEl.innerHTML = '<p class="chat-empty">Chargement…</p>';

        const response = await fetch("/messagerie/" + friendId);
        if (!response.ok) {
            messagesEl.innerHTML = '<p class="chat-empty">Impossible de charger cette conversation.</p>';
            return;
        }
        const data = await response.json();

        activeFriendUsername = data.friend.username;
        titleEl.textContent = data.friend.username;
        messagesEl.innerHTML = "";
        if (!data.messages.length) {
            messagesEl.innerHTML = '<p class="chat-empty">Aucun message pour l’instant. Dis bonjour \u{1F44B}</p>';
        } else {
            data.messages.forEach(renderMessage);
        }
        scrollMessagesToBottom();
        inputEl.focus();

        const friend = friends.find(function (f) { return f.friend_id === friendId; });
        if (friend && friend.unread_count > 0) {
            setBubbleBadge(unreadBubbleTotal - friend.unread_count);
            friend.unread_count = 0;
        }
        fetch("/messagerie/" + friendId + "/lu", { method: "POST" }).catch(function () {});
    }

    async function loadFriends() {
        friendListEl.innerHTML = '<p class="chat-empty">Chargement…</p>';
        const response = await fetch("/messagerie/amis");
        if (!response.ok) {
            friendListEl.innerHTML = '<p class="chat-empty">Impossible de charger tes amis.</p>';
            return;
        }
        const data = await response.json();
        friends = data.conversations;
        sortFriends();
        setBubbleBadge(data.unread_total);
        renderFriendList();
    }

    function openPanel() {
        panelOpen = true;
        panel.classList.remove("hidden");
        showFriendListView();
        // Toujours revérifié à l'ouverture (comme la cloche de
        // notifications) : la liste en mémoire peut dater d'avant un
        // message reçu pendant que la bulle était fermée.
        loadFriends();
    }

    function closePanel() {
        panelOpen = false;
        panel.classList.add("hidden");
        emojiPicker.classList.add("hidden");
    }

    bubble.addEventListener("click", function () {
        if (panelOpen) {
            closePanel();
        } else {
            openPanel();
        }
    });

    closeButton.addEventListener("click", closePanel);
    backButton.addEventListener("click", showFriendListView);

    // Réutilise la route d'invitation multijoueur existante
    // (filmatrix/routes/multiplayer.py, invite_to_game) — elle crée déjà la
    // GameSession et notifie l'ami ; on dépose juste, en plus, un message
    // avec le lien du salon dans le fil de discussion, pour qu'il reste
    // visible dans la conversation plutôt que seulement dans la cloche.
    inviteButton.addEventListener("click", async function () {
        if (!activeFriendId || typeof socket === "undefined" || !socket) {
            return;
        }

        inviteButton.disabled = true;
        try {
            const response = await fetch("/multijoueur/inviter/" + activeFriendId, { method: "POST" });
            const match = response.url.match(/\/multijoueur\/(\d+)/);
            if (!response.ok || !match) {
                if (typeof showToast === "function") {
                    showToast({ message: "⚠️ Impossible d'inviter " + activeFriendUsername + " pour le moment." });
                }
                return;
            }

            const inviteBody = "🎮 Je t'invite à une partie ! Rejoins-moi : " + response.url;
            socket.emit("send_chat_message", { to_user_id: activeFriendId, body: inviteBody });
            renderMessage({ sender_id: CURRENT_USER_ID, body: inviteBody });
            scrollMessagesToBottom();

            if (typeof showToast === "function") {
                showToast({ message: "Invitation envoyée à " + activeFriendUsername + " !" });
            }
        } catch (error) {
            if (typeof showToast === "function") {
                showToast({ message: "⚠️ Impossible d'inviter " + activeFriendUsername + " pour le moment." });
            }
        } finally {
            inviteButton.disabled = false;
        }
    });

    document.addEventListener("click", function (event) {
        if (!embedded && panelOpen && !widget.contains(event.target)) {
            closePanel();
        }
    });

    emojiButton.addEventListener("click", function (event) {
        event.stopPropagation();
        if (!emojiPicker.childElementCount) {
            EMOJIS.forEach(function (emoji) {
                const option = document.createElement("button");
                option.type = "button";
                option.className = "chat-emoji-option";
                option.textContent = emoji;
                option.addEventListener("click", function () {
                    inputEl.value += emoji;
                    inputEl.focus();
                    emojiPicker.classList.add("hidden");
                });
                emojiPicker.appendChild(option);
            });
        }
        emojiPicker.classList.toggle("hidden");
    });

    formEl.addEventListener("submit", function (event) {
        event.preventDefault();
        const body = inputEl.value.trim();
        if (!body || !activeFriendId) {
            return;
        }
        if (typeof socket === "undefined" || !socket) {
            return;
        }

        socket.emit("send_chat_message", { to_user_id: activeFriendId, body: body });
        renderMessage({ sender_id: CURRENT_USER_ID, body: body });
        scrollMessagesToBottom();
        inputEl.value = "";
        emojiPicker.classList.add("hidden");
    });

    if (typeof socket !== "undefined" && socket) {
        socket.on("new_chat_message", function (data) {
            // Écho de mon propre message (autre onglet/appareil) : déjà
            // affiché en optimiste sur l'onglet qui l'a envoyé, ignoré ici
            // pour ne jamais le dupliquer dans le fil actif.
            if (data.sender_id === CURRENT_USER_ID) {
                return;
            }

            const isThreadOpen = panelOpen && activeFriendId === data.sender_id;

            if (isThreadOpen) {
                renderMessage(data);
                scrollMessagesToBottom();
                fetch("/messagerie/" + data.sender_id + "/lu", { method: "POST" }).catch(function () {});
            } else if (typeof showToast === "function") {
                showToast({ message: "\u{1F4AC} " + data.sender_username + " : " + truncate(data.body, 60) });
            }

            const friend = friends.find(function (f) { return f.friend_id === data.sender_id; });
            if (friend) {
                if (!isThreadOpen) {
                    friend.unread_count += 1;
                }
                friend.last_message = data.body;
                friend.last_message_at = data.created_at;
                friend.last_message_from_me = false;
                sortFriends();
                if (panelOpen && activeFriendId === null) {
                    renderFriendList();
                }
            }
            if (!isThreadOpen) {
                setBubbleBadge(unreadBubbleTotal + 1);
            }
        });

        socket.on("chat_error", function (data) {
            if (typeof showToast === "function") {
                showToast({ message: "⚠️ " + data.error });
            }
        });
    }

    // API publique minimale : permet à une page (ex. multiplayer/partie.html,
    // pendant un duel) de déplacer la bulle globale dans une carte de sa
    // propre mise en page plutôt que de dupliquer toute cette logique.
    // Réutilise le même widget/les mêmes écouteurs — seul son emplacement et
    // son habillage (classe .chat-widget--embedded, voir chat_widget.html)
    // changent.
    window.FilmatrixChat = {
        embedIn: function (container, friendId) {
            if (!container) {
                return;
            }
            container.appendChild(widget);
            widget.classList.add("chat-widget--embedded");
            embedded = true;
            panelOpen = true;
            panel.classList.remove("hidden");

            if (friendId) {
                openThread(friendId);
            } else {
                showFriendListView();
                loadFriends();
            }
        },
    };
})();
