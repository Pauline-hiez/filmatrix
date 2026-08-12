const notificationBell = document.getElementById("notification-bell");
const notificationDropdown = document.getElementById("notification-dropdown");
const notificationBadge = document.getElementById("notification-badge");

if (notificationBell) {
    notificationBell.addEventListener("click", async function () {
        const isHidden = notificationDropdown.classList.contains("hidden");

        if (isHidden) {
            const response = await fetch("/notifications");
            const data = await response.json();

            displayNotifications(data.notifications);
            notificationDropdown.classList.remove("hidden");

            if (notificationBadge) {
                notificationBadge.remove();
            }
        } else {
            notificationDropdown.classList.add("hidden");
        }
    });

    document.addEventListener("click", function (event) {
        if (
            !notificationBell.contains(event.target) &&
            !notificationDropdown.contains(event.target)
        ) {
            notificationDropdown.classList.add("hidden");
        }
    });
}

function displayNotifications(notifications) {
    if (notifications.length === 0) {
        notificationDropdown.innerHTML =
            '<p class="text-sm text-slate-500 px-4 py-3">Aucune notification.</p>';
        return;
    }

    notificationDropdown.innerHTML = "";

    notifications.forEach(function (notification) {
        const item = document.createElement(notification.link ? "a" : "div");
        if (notification.link) {
            item.href = notification.link;
        }
        item.className =
            "block px-4 py-3 text-sm text-slate-200 hover:bg-slate-800 transition border-b border-slate-800 last:border-0";
        item.textContent = notification.message;

        notificationDropdown.appendChild(item);
    });
}