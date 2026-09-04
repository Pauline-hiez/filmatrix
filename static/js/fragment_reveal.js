// Scène plein écran des fragments gagnés pendant la partie qui vient de se
// terminer (templates/quiz/termine.html). Les gains sont accumulés côté
// serveur pendant le jeu (filmatrix/services/score.py,
// add_run_fragment_result) et ne sont révélés qu'ici, tous ensemble, pour ne
// jamais interrompre le rythme d'une partie en cours.

(function () {
    const dataEl = document.getElementById("fragment-results-data");
    const overlay = document.getElementById("fragment-overlay");
    const stage = document.getElementById("fragment-stage");

    if (!dataEl || !overlay || !stage) {
        return;
    }

    let results = [];
    try {
        results = JSON.parse(dataEl.textContent || "[]");
    } catch (error) {
        results = [];
    }

    if (!results.length) {
        return;
    }

    const FRAGMENT_RARITY_LABELS = {
        commun: "Commun",
        rare: "Rare",
        epique: "Épique",
        legendaire: "Légendaire",
        mythique: "Mythique",
    };

    // Miroir JS des couleurs de rareté (filmatrix/catalog_rarities.py,
    // RARITIES) : le nombre de particules et l'intensité du glow montent
    // avec la rareté, pour que le déblocage d'un mythique en mette
    // nettement plus plein la vue que celui d'un commun.
    const FRAGMENT_RARITY_COLORS = {
        commun: { border: "#64748b", text: "#cbd5e1", glow: "rgba(148, 163, 184, 0.55)", particles: 0 },
        rare: { border: "#34d399", text: "#34d399", glow: "rgba(52, 211, 153, 0.65)", particles: 6 },
        epique: { border: "#60a5fa", text: "#60a5fa", glow: "rgba(96, 165, 250, 0.7)", particles: 10 },
        legendaire: { border: "#a78bfa", text: "#a78bfa", glow: "rgba(167, 139, 250, 0.75)", particles: 14 },
        mythique: { border: "#fbbf24", text: "#fbbf24", glow: "rgba(251, 191, 36, 0.8)", particles: 18 },
    };

    function assetUrl(url) {
        if (!url) return "";
        if (/^https?:\/\//i.test(url)) return url;
        return "/static/" + url;
    }

    function buildPuzzleCells(result, imageUrl) {
        // Même découpe que la grille de la page collection : l'image est
        // posée UNE fois derrière, puis des pièces par-dessus : transparentes
        // et cernées d'un liseré si révélées (.puzzle-piece--revealed), en
        // verre dépoli sombre sinon (.puzzle-piece--hidden). Chaque pièce a
        // une silhouette hexagonale irrégulière (.puzzle-piece--v0..v5, cf.
        // base.html) pour ne pas ressembler à une grille posée sur l'image.
        const grid = result.puzzle_grid || [];
        const newCells = result.puzzle_new_cells || [];

        const imageBackdrop = imageUrl
            ? `<div class="absolute inset-0 bg-cover bg-center" style="background-image:url('${imageUrl}');background-repeat:no-repeat;"></div>`
            : "";

        function cellClass(index) {
            return newCells.indexOf(index) !== -1 ? "fragment-new-cell" : "";
        }

        if (!grid.length) {
            return imageBackdrop;
        }

        const cellsHtml = grid.map(function (revealed, index) {
            const extra = cellClass(index);
            const variant = "puzzle-piece--v" + (index % 6);
            if (revealed) {
                return `<div class="puzzle-piece puzzle-piece--revealed ${variant} ${extra}"></div>`;
            }
            return `<div class="puzzle-piece puzzle-piece--hidden ${variant} ${extra}">
                <span class="puzzle-piece-glyph text-sm">?</span>
            </div>`;
        }).join("");

        // Autant de cases que de fragments requis (voir puzzle.py côté
        // serveur, grid_size_for) : commun = 3 cases, légendaire = 8, etc.
        // On retombe sur une grille carrée si le serveur n'a pas fourni le
        // nombre de colonnes (anciens payloads en cache).
        const columns = result.puzzle_columns || Math.ceil(Math.sqrt(grid.length));

        return `${imageBackdrop}<div class="absolute inset-0 grid" style="z-index:1;gap:4px;grid-template-columns:repeat(${columns},1fr);grid-auto-rows:1fr;">${cellsHtml}</div>`;
    }

    function renderParticles(count, color) {
        let html = "";
        for (let i = 0; i < count; i++) {
            const dx = Math.round((Math.random() * 2 - 1) * 90);
            const delay = (Math.random() * 0.4).toFixed(2);
            const size = 4 + Math.round(Math.random() * 4);
            const left = 20 + Math.random() * 60;
            html += `<span class="fragment-particle" style="--dx:${dx}px; --p-delay:${delay}s; width:${size}px; height:${size}px; left:${left}%; color:${color}; background:${color};"></span>`;
        }
        return html;
    }

    // Un clic (ou un appui) sur la scène passe directement à l'étape
    // suivante, sans attendre le minutage complet : le joueur garde la main.
    let skipCurrentStage = null;
    overlay.addEventListener("click", function () {
        if (skipCurrentStage) {
            const fn = skipCurrentStage;
            skipCurrentStage = null;
            fn();
        }
    });

    function wait(ms) {
        return new Promise(function (resolve) {
            let settled = false;
            const timer = setTimeout(function () {
                if (settled) return;
                settled = true;
                skipCurrentStage = null;
                resolve();
            }, ms);
            skipCurrentStage = function () {
                if (settled) return;
                settled = true;
                clearTimeout(timer);
                resolve();
            };
        });
    }

    async function playStage(result) {
        const justUnlocked = result.just_unlocked;
        const rarityKey = result.rarity;
        const rarityLabel = FRAGMENT_RARITY_LABELS[rarityKey] || rarityKey || "";
        const colors = FRAGMENT_RARITY_COLORS[rarityKey] || FRAGMENT_RARITY_COLORS.commun;
        const imageUrl = assetUrl(result.image_url);
        const progress = result.progress_percent || 0;

        // Un seul fragment est distribué à la fois (add_fragments côté
        // serveur) : la valeur d'avant sert juste à animer le remplissage de
        // la barre, du niveau précédent jusqu'au niveau actuel.
        const fragmentsBefore = Math.max((result.fragments || 0) - 1, 0);
        const progressBefore = result.fragments_required
            ? Math.round((fragmentsBefore * 100) / result.fragments_required)
            : 0;

        const puzzleCells = buildPuzzleCells(result, imageUrl);

        overlay.style.setProperty("--frag-glow", colors.glow);

        stage.innerHTML = `
            <div class="fragment-card ${justUnlocked ? "fragment-stage-tremble" : ""}" style="--frag-border:${colors.border}">
                <div class="fragment-burst"></div>
                ${puzzleCells}
                <div class="fragment-filmstrip"></div>
                <div class="fragment-clap-flash"></div>
                ${justUnlocked ? `<div class="fragment-particles">${renderParticles(colors.particles, colors.glow)}</div>` : ""}
            </div>
            <p class="fragment-stage-title" style="color:${colors.text}">
                ${justUnlocked ? "🎬 Personnage débloqué !" : "🧩 Fragment obtenu"}
            </p>
            <p class="fragment-stage-name">${result.character_name}</p>
            <p class="fragment-stage-sub">${result.saga_name ? result.saga_name + " · " : ""}${rarityLabel}</p>
            <div class="fragment-stage-bar-track">
                <div class="fragment-bar-fill" style="width:${progressBefore}%"></div>
            </div>
            <p class="fragment-stage-count">${result.fragments}/${result.fragments_required} fragments</p>
        `;

        // Décalé d'une frame : il faut que le navigateur peigne d'abord la
        // largeur de départ avant de basculer sur la largeur finale, sinon
        // la transition CSS de .fragment-bar-fill ne se déclenche pas.
        requestAnimationFrame(function () {
            const bar = stage.querySelector(".fragment-bar-fill");
            if (bar) {
                bar.style.width = progress + "%";
            }
        });

        await wait(justUnlocked ? 3400 : 2000);
    }

    async function run() {
        overlay.classList.add("is-visible");
        for (let i = 0; i < results.length; i++) {
            await playStage(results[i]);
        }
        overlay.classList.remove("is-visible");
    }

    run();
})();
