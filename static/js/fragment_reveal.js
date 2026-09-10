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
        // une vraie silhouette de puzzle (languettes/creux qui s'emboîtent),
        // appliquée après coup par applyPuzzleClipPaths() une fois ce HTML
        // inséré dans le DOM — un clip-path ne peut pas être posé sur une
        // chaîne de caractères, seulement sur un élément réel.
        //
        // La pièce tout juste gagnée (puzzle_new_cells) est déjà marquée
        // "revealed" côté serveur, mais on la couvre volontairement ici avec
        // .puzzle-piece--pending : c'est le joueur qui doit cliquer dessus
        // pour la retirer et découvrir l'image (voir playStage ci-dessous).
        const grid = result.puzzle_grid || [];
        const newCells = result.puzzle_new_cells || [];

        const imageBackdrop = imageUrl
            ? `<div class="absolute inset-0 bg-cover bg-center" style="background-image:url('${imageUrl}');background-repeat:no-repeat;"></div>`
            : "";

        if (!grid.length) {
            return imageBackdrop;
        }

        const cellsHtml = grid.map(function (revealed, index) {
            const isNew = newCells.indexOf(index) !== -1;
            if (revealed && !isNew) {
                return `<div class="puzzle-piece puzzle-piece--revealed"></div>`;
            }
            const pendingClass = isNew ? " puzzle-piece--pending" : "";
            return `<div class="puzzle-piece puzzle-piece--hidden${pendingClass}">
                <span class="puzzle-piece-glyph text-sm">?</span>
            </div>`;
        }).join("");

        // Autant de cases que de fragments requis (voir puzzle.py côté
        // serveur, grid_size_for) : commun = 3 cases, légendaire = 8, etc.
        // On retombe sur une grille carrée si le serveur n'a pas fourni le
        // nombre de colonnes (anciens payloads en cache). gap:0 volontaire :
        // les languettes des pièces doivent chevaucher la case voisine.
        const columns = result.puzzle_columns || Math.ceil(Math.sqrt(grid.length));

        return `${imageBackdrop}<div class="fragment-puzzle-grid absolute inset-0 grid" style="z-index:1;gap:0;grid-template-columns:repeat(${columns},1fr);grid-auto-rows:1fr;">${cellsHtml}</div>`;
    }

    // Découpe les pièces tout juste insérées dans le DOM (voir buildPuzzleCells
    // ci-dessus) en vraies silhouettes de puzzle, avec le même seed (id du
    // personnage) que la grille utilisée sur la page collection — la pièce a
    // ainsi exactement la même forme aux deux endroits.
    function applyPuzzleClipPaths(result) {
        if (!window.FilmatrixPuzzle || !result.puzzle_grid || !result.puzzle_grid.length) {
            return;
        }
        window.FilmatrixPuzzle.applyToGrid(stage, {
            cols: result.puzzle_columns || Math.ceil(Math.sqrt(result.puzzle_grid.length)),
            seed: result.character_id,
        });
    }

    // Petit éclat de particules positionné exactement sur la pièce qui vient
    // d'apparaître (contrairement à renderParticles ci-dessous, qui remplit
    // toute la carte et ne joue qu'au déblocage complet du personnage) : un
    // retour visuel immédiat à CHAQUE fragment gagné, même les intermédiaires.
    function buildCellSparkles(result, color) {
        const grid = result.puzzle_grid || [];
        const newCells = result.puzzle_new_cells || [];
        if (!grid.length || !newCells.length) {
            return "";
        }
        const columns = result.puzzle_columns || Math.ceil(Math.sqrt(grid.length));
        const rows = Math.ceil(grid.length / columns);
        const cellIndex = newCells[0];
        const row = Math.floor(cellIndex / columns);
        const col = cellIndex % columns;
        const centerLeft = ((col + 0.5) / columns) * 100;
        const centerTop = ((row + 0.5) / rows) * 100;

        let sparkles = "";
        const count = 7;
        for (let i = 0; i < count; i++) {
            const angle = (Math.PI * 2 * i) / count + Math.random() * 0.5;
            const distance = 22 + Math.random() * 14;
            const sx = Math.round(Math.cos(angle) * distance);
            const sy = Math.round(Math.sin(angle) * distance);
            const size = 3 + Math.round(Math.random() * 3);
            const delay = (Math.random() * 0.15).toFixed(2);
            sparkles += `<span class="fragment-cell-sparkle" style="left:${centerLeft}%; top:${centerTop}%; --sx:${sx}px; --sy:${sy}px; width:${size}px; height:${size}px; color:${color}; background:${color}; animation-delay:${0.45 + Number(delay)}s;"></span>`;
        }
        return `<div class="fragment-cell-sparkles">${sparkles}</div>`;
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

    // Contrairement à wait(), aucun minuteur ne fait avancer le paquet cadeau
    // tout seul : il reste en boucle (rebond + halo, voir base.html) jusqu'à
    // ce que le joueur clique dessus.
    function waitForClick() {
        return new Promise(function (resolve) {
            skipCurrentStage = function () {
                skipCurrentStage = null;
                resolve();
            };
        });
    }

    async function playGiftBox(result) {
        const rarityKey = result.rarity;
        const rarityLabel = FRAGMENT_RARITY_LABELS[rarityKey] || rarityKey || "";
        const colors = FRAGMENT_RARITY_COLORS[rarityKey] || FRAGMENT_RARITY_COLORS.commun;

        overlay.style.setProperty("--frag-glow", colors.glow);

        stage.innerHTML = `
            <div class="fragment-giftbox" style="--frag-glow:${colors.glow}">
                <div class="fragment-giftbox-glow"></div>
                <img class="fragment-giftbox-img" src="/static/images/habillage/cadeau1.png" alt="" />
                <div class="fragment-giftbox-flash"></div>
            </div>
            <p class="fragment-stage-title" style="color:${colors.text}">🎁 Un fragment t'attend</p>
            <p class="fragment-stage-sub">${rarityLabel}</p>
        `;

        await waitForClick();

        // Couvercle qui s'envole + corps qui se rétracte (base.html,
        // .fragment-giftbox.is-opening) avant de laisser la place à la carte
        // de fragment habituelle, qui prend le relais pour l'effet "le
        // fragment sort du paquet" (flash, pellicule, pièce qui s'emboîte).
        const box = stage.querySelector(".fragment-giftbox");
        if (box) {
            box.classList.add("is-opening");
        }
        await wait(380);
    }

    // Attend un clic précisément sur la pièce en attente (et pas ailleurs
    // sur la scène) : stopPropagation empêche ce clic de remonter jusqu'au
    // gestionnaire global de l'overlay (qui gère lui le "cliquer pour passer
    // à la suite" des autres étapes), donc rien ne se produit tant que le
    // joueur n'a pas visé la bonne pièce.
    function waitForPieceClick(piece) {
        return new Promise(function (resolve) {
            piece.addEventListener("click", function onPieceClick(event) {
                event.stopPropagation();
                piece.removeEventListener("click", onPieceClick);
                resolve();
            });
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

        // Tant que la pièce n'a pas été retirée, on ne sait pas encore si
        // c'est LE fragment qui complète le personnage : le titre reste
        // neutre, tout comme le compteur qui affiche encore l'ancien total.
        stage.innerHTML = `
            <div class="fragment-card" style="--frag-border:${colors.border}">
                <div class="fragment-burst"></div>
                ${puzzleCells}
            </div>
            <p class="fragment-stage-title" style="color:${colors.text}">🧩 Trouve la pièce qui brille</p>
            <p class="fragment-stage-name">???</p>
            <p class="fragment-stage-sub">${result.saga_name ? result.saga_name + " · " : ""}${rarityLabel}</p>
            <div class="fragment-stage-bar-track">
                <div class="fragment-bar-fill" style="width:${progressBefore}%"></div>
            </div>
            <p class="fragment-stage-count">${fragmentsBefore}/${result.fragments_required} fragments</p>
        `;

        applyPuzzleClipPaths(result);

        const card = stage.querySelector(".fragment-card");
        const pendingPiece = stage.querySelector(".puzzle-piece--pending");
        const titleEl = stage.querySelector(".fragment-stage-title");
        const nameEl = stage.querySelector(".fragment-stage-name");
        const barTrack = stage.querySelector(".fragment-stage-bar-track");
        const bar = stage.querySelector(".fragment-bar-fill");
        const countEl = stage.querySelector(".fragment-stage-count");
        const hint = overlay.querySelector(".fragment-overlay-hint");

        function revealFragment() {
            if (titleEl) {
                titleEl.textContent = justUnlocked ? "🎬 Personnage débloqué !" : "🧩 Fragment obtenu";
            }
            // Le nom ne se dévoile que lorsque le personnage est
            // complètement révélé (tous ses fragments réunis) - un fragment
            // isolé ne doit pas spoiler qui se cache derrière le puzzle.
            if (nameEl) {
                nameEl.textContent = justUnlocked ? result.character_name : "???";
            }
            if (countEl) {
                countEl.textContent = result.fragments + "/" + result.fragments_required + " fragments";
                countEl.classList.add("fragment-count-pop");
            }
            if (barTrack) {
                barTrack.classList.add("fragment-bar-pulse");
            }
            // Décalé d'une frame : il faut que le navigateur peigne d'abord
            // la largeur de départ avant de basculer sur la largeur finale,
            // sinon la transition CSS de .fragment-bar-fill ne se déclenche
            // pas.
            requestAnimationFrame(function () {
                if (bar) {
                    bar.style.width = progress + "%";
                }
            });
        }

        if (pendingPiece) {
            const originalHint = hint ? hint.textContent : "";
            if (hint) {
                hint.textContent = "Touche la pièce qui brille pour la révéler";
            }

            await waitForPieceClick(pendingPiece);

            if (hint) {
                hint.textContent = originalHint;
            }

            // La pièce "s'enlève" : on bascule son habillage de couverte à
            // transparente, ce qui laisse apparaître l'image posée en
            // arrière-plan de la grille — puis on rejoue par-dessus les
            // mêmes effets qu'avant (pellicule, flash, reflet, étincelles)
            // pour que le retrait ait le même impact visuel qu'un déblocage
            // automatique.
            pendingPiece.classList.remove("puzzle-piece--pending", "puzzle-piece--hidden");
            pendingPiece.classList.add("puzzle-piece--revealed", "fragment-new-cell");
            pendingPiece.innerHTML = "";

            if (justUnlocked && card) {
                card.classList.add("fragment-stage-tremble");
            }
            if (card) {
                card.insertAdjacentHTML(
                    "beforeend",
                    `<div class="fragment-filmstrip"></div>
                     <div class="fragment-clap-flash"></div>
                     ${buildCellSparkles(result, colors.text)}
                     ${justUnlocked ? `<div class="fragment-particles">${renderParticles(colors.particles, colors.glow)}</div>` : ""}`
                );
            }

            revealFragment();
        } else {
            // Pas de pièce en attente (grille absente du payload, ancien
            // cache navigateur, etc.) : on retombe sur l'affichage
            // entièrement automatique d'avant.
            revealFragment();
        }

        await wait(justUnlocked ? 3400 : 2000);
    }

    async function run() {
        overlay.classList.add("is-visible");
        for (let i = 0; i < results.length; i++) {
            await playGiftBox(results[i]);
            await playStage(results[i]);
        }
        overlay.classList.remove("is-visible");
    }

    run();
})();
