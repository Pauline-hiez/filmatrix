// Révélation des récompenses d'une partie terminée : badges, mini-missions,
// série de connexion et passage de niveau. Rien de tout ça n'est plus
// annoncé en cours de partie (tout peut être perdu si le joueur quitte avant
// la fin, voir filmatrix/services/run_rewards.py) - ces fonctions vivaient
// dans static/js/quiz.js, déplacées ici pour ne se déclencher qu'une fois,
// au chargement de l'écran de fin (templates/quiz/termine.html).

function showBadgeNotification(badge) {
    const notification = document.createElement("div");
    notification.className =
        "fixed top-4 left-1/2 -translate-x-1/2 bg-slate-900 border border-cyan-400 rounded-lg px-4 py-3 shadow-lg z-50 flex items-center gap-3 transition-opacity duration-500";
    notification.innerHTML = `
        <span class="text-2xl">${badge.icon}</span>
        <div>
            <p class="text-cyan-400 font-bold text-sm">Badge débloqué !</p>
            <p class="text-slate-300 text-xs">${badge.name}</p>
        </div>
    `;

    document.body.appendChild(notification);

    setTimeout(function () {
        notification.style.opacity = "0";
        setTimeout(function () {
            notification.remove();
        }, 500);
    }, 3000);
}

// Cliquer renvoie vers le profil, où les mini-missions du jour sont affichées.
function showMissionCompletedNotification(mission) {
    const notification = document.createElement("div");
    notification.className =
        "fixed top-4 left-1/2 -translate-x-1/2 cursor-pointer bg-slate-900 border border-violet-400 rounded-lg px-4 py-3 shadow-lg z-50 flex items-center gap-3 transition-opacity duration-500 max-w-sm";
    notification.innerHTML = `
        <span class="text-2xl">🎯</span>
        <div class="min-w-0">
            <p class="text-violet-400 font-bold text-sm">Mini-mission relevée !</p>
            <p class="truncate text-slate-300 text-xs">${mission.description}</p>
            <p class="text-amber-400 text-xs font-bold">+${mission.coin_reward} pièces</p>
        </div>
    `;
    notification.addEventListener("click", function () {
        window.location.href = "/profil";
    });

    document.body.appendChild(notification);

    setTimeout(function () {
        notification.style.opacity = "0";
        setTimeout(function () {
            notification.remove();
        }, 500);
    }, 3500);
}

// Les trois mini-missions du jour sont toutes faites : le vrai palier de la
// journée (fragment garanti), distinct de chaque mini-mission prise seule.
function showDayCompletedNotification() {
    const notification = document.createElement("div");
    notification.className =
        "fixed top-4 left-1/2 -translate-x-1/2 cursor-pointer bg-slate-900 border border-cyan-400 rounded-lg px-4 py-3 shadow-lg z-50 flex items-center gap-3 transition-opacity duration-500 max-w-sm";
    notification.innerHTML = `
        <span class="text-2xl">🏆</span>
        <div class="min-w-0">
            <p class="text-cyan-400 font-bold text-sm">Mini-missions du jour terminées !</p>
            <p class="text-slate-300 text-xs">🧩 Un fragment t'attend juste en dessous</p>
        </div>
    `;
    notification.addEventListener("click", function () {
        window.location.href = "/profil";
    });

    document.body.appendChild(notification);

    setTimeout(function () {
        notification.style.opacity = "0";
        setTimeout(function () {
            notification.remove();
        }, 500);
    }, 3500);
}

// Palier de série (7 jours de missions terminées consécutifs) : distinct de
// la journée elle-même, les deux peuvent s'afficher ensemble.
function showStreakBonusNotification(streakBonus) {
    const notification = document.createElement("div");
    notification.className =
        "fixed top-4 left-1/2 -translate-x-1/2 bg-slate-900 border border-amber-400 rounded-lg px-4 py-3 shadow-lg z-50 flex items-center gap-3 transition-opacity duration-500";
    notification.innerHTML = `
        <span class="text-2xl">🔥</span>
        <div>
            <p class="text-amber-400 font-bold text-sm">Série de ${streakBonus.streak} jours !</p>
            <p class="text-slate-300 text-xs">Un fragment bonus t'attend juste en dessous</p>
        </div>
    `;

    document.body.appendChild(notification);

    setTimeout(function () {
        notification.style.opacity = "0";
        setTimeout(function () {
            notification.remove();
        }, 500);
    }, 3500);
}

// Fait tomber des confettis colorés sur tout l'écran, à l'intérieur du
// conteneur donné (voir .level-up-confetti-piece dans templates/base.html).
function spawnConfetti(container) {
    const confettiColors = ["#22d3ee", "#a78bfa", "#fbbf24", "#34d399", "#f472b6"];
    for (let i = 0; i < 48; i++) {
        const piece = document.createElement("span");
        piece.className = "level-up-confetti-piece";
        const size = 6 + Math.random() * 7;
        piece.style.setProperty("--x", `${Math.random() * 100}%`);
        piece.style.setProperty("--size", `${size}px`);
        piece.style.setProperty("--color", confettiColors[i % confettiColors.length]);
        piece.style.setProperty("--dx", `${(Math.random() - 0.5) * 220}px`);
        piece.style.setProperty("--spin", `${360 + Math.random() * 540}deg`);
        piece.style.setProperty("--duration", `${2.1 + Math.random() * 1.1}s`);
        piece.style.setProperty("--delay", `${Math.random() * 0.4}s`);
        container.appendChild(piece);
    }
}

// Anime --level-pct de 0 à 100 sur l'anneau (un tour complet), en résolvant
// la promesse une fois le tour terminé - c'est ce moment précis qui déclenche
// la suite (chiffre qui bascule + confettis), pas une simple temporisation.
function animateRingFill(ringEl, durationMs) {
    return new Promise(function (resolve) {
        const start = performance.now();
        function step(now) {
            const pct = Math.min(100, ((now - start) / durationMs) * 100);
            ringEl.style.setProperty("--level-pct", pct);
            if (pct < 100) {
                requestAnimationFrame(step);
            } else {
                resolve();
            }
        }
        requestAnimationFrame(step);
    });
}

function wait(ms) {
    return new Promise(function (resolve) { setTimeout(resolve, ms); });
}

// Passage de niveau : voile plein écran + carte centrale avec un anneau qui
// fait un tour complet (comme le chrono en jeu, .game-timer-ring) - le
// chiffre ne bascule, et les confettis ne se déclenchent, qu'une fois ce
// tour terminé, pas dès l'ouverture de la carte.
async function showLevelUpAnimation(levelUp) {
    const overlay = document.createElement("div");
    overlay.className = "level-up-overlay";
    overlay.innerHTML = `
        <div class="level-up-card">
            <p class="level-up-card-label">Niveau supérieur !</p>
            <div class="level-up-ring" style="--level-pct: 0">
                <strong class="level-up-ring-number">${levelUp.previous}</strong>
            </div>
            <p class="level-up-card-sub">Continue comme ça !</p>
        </div>
    `;
    document.body.appendChild(overlay);

    const ring = overlay.querySelector(".level-up-ring");
    const numberEl = overlay.querySelector(".level-up-ring-number");
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (prefersReducedMotion) {
        ring.style.setProperty("--level-pct", 100);
    } else {
        // Laisse la carte finir son entrée avant de lancer le remplissage.
        await wait(400);
        await animateRingFill(ring, 1300);
    }

    // Le tour de l'anneau est terminé : le chiffre bascule et les confettis
    // se déclenchent à cet instant précis, pas avant.
    numberEl.textContent = levelUp.new;
    numberEl.classList.add("is-swapping");
    if (!prefersReducedMotion) {
        spawnConfetti(overlay);
    }

    await wait(2600);
    overlay.classList.add("is-leaving");
    await wait(500);
    overlay.remove();
}

function run() {
    const dataScript = document.getElementById("run-reveal-data");
    if (!dataScript) {
        return;
    }

    let reveal;
    try {
        reveal = JSON.parse(dataScript.textContent);
    } catch (error) {
        return;
    }
    if (!reveal) {
        return;
    }

    if (reveal.level_up) {
        showLevelUpAnimation(reveal.level_up);
    }
    if (reveal.new_badges) {
        reveal.new_badges.forEach(function (badge) {
            showBadgeNotification(badge);
        });
    }
    if (reveal.completed_missions) {
        reveal.completed_missions.forEach(function (mission) {
            showMissionCompletedNotification(mission);
        });
    }
    if (reveal.day_completed) {
        showDayCompletedNotification();
    }
    if (reveal.streak_bonus) {
        showStreakBonusNotification(reveal.streak_bonus);
    }
}

run();
