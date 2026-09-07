// Découpe des grilles de fragments en vraies pièces de puzzle qui
// s'emboîtent (clipPath SVG en courbes de Bézier), partagée entre la page
// collection (templates/partials/puzzle_grid.html) et l'animation de fin de
// partie (fragment_reveal.js) : une pièce doit avoir exactement la même
// forme aux deux endroits, d'où ce module commun plutôt que deux générateurs
// séparés. Remplace l'ancien système de classes .puzzle-piece--v0..v5
// (simples coins coupés en polygon CSS).
//
// Point important : une languette qui doit déborder chez la case voisine a
// besoin d'une vraie boîte DOM plus grande que la case pour avoir quelque
// chose à peindre au-delà de son propre bord (un clip-path ne peut que
// retirer de la matière à un élément, jamais lui en ajouter hors de sa
// boîte). applyToGrid() positionne donc chaque pièce en absolute, dans une
// boîte agrandie d'une marge (padFractionFor), et les coordonnées du tracé
// sont reprojetées dans cette boîte via toBox (voir buildJigsawClipPaths) —
// sans ça, les languettes ne s'affichent tout simplement pas (silhouette
// visuellement erronée, corrigé après un premier essai en CSS Grid pur).

window.FilmatrixPuzzle = (function () {
    "use strict";

    // RNG déterministe (mulberry32), seedé par une chaîne (id du personnage) :
    // même seed -> toujours la même découpe, pour qu'une pièce déjà révélée
    // ne change jamais de forme d'un affichage à l'autre.
    function hashSeed(str) {
        let h = 2166136261;
        for (let i = 0; i < str.length; i++) {
            h ^= str.charCodeAt(i);
            h = Math.imul(h, 16777619);
        }
        return h >>> 0;
    }

    function mulberry32(seed) {
        return function () {
            seed |= 0;
            seed = (seed + 0x6d2b79f5) | 0;
            let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
            t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
            return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
        };
    }

    // Un bord de pièce : droit (dir=0, bordure de la grille), languette
    // (dir=+1, cette pièce "possède" la bosse) ou creux (dir=-1, la bosse
    // appartient à la voisine). Coordonnées locales : le bord va de (0,0) à
    // (1,0), la bosse déborde vers -n (extérieur de la case).
    function edgeCommands(dir, amplitude) {
        if (dir === 0) return ["L 1,0"];
        const n = amplitude * dir;
        return [
            "L 0.35,0",
            "C 0.35," + n * 1.0 + " 0.26," + n * 1.6 + " 0.5," + n * 1.6,
            "C 0.74," + n * 1.6 + " 0.65," + n * 1.0 + " 0.65,0",
            "L 1,0",
        ];
    }

    // Remappe une commande locale (t,n) vers les coordonnées réelles du bord
    // concerné, en tournant autour du carré unité dans le sens horaire :
    // haut (gauche→droite), droite (haut→bas), bas (droite→gauche),
    // gauche (bas→haut). toBox reprojette ensuite ces coordonnées "en unité
    // de case" vers la boîte réellement dessinée à l'écran (voir toBoxScale
    // ci-dessous : la boîte est plus grande que la case pour laisser de la
    // place aux languettes qui débordent chez la voisine).
    function transformCommand(side, cmd, toBox) {
        const type = cmd[0];
        const pairs = cmd
            .slice(1)
            .trim()
            .split(/\s+/)
            .map(function (pair) {
                return pair.split(",").map(Number);
            });
        function map(t, n) {
            switch (side) {
                case "top":
                    return [t, -n];
                case "right":
                    return [1 + n, t];
                case "bottom":
                    return [1 - t, 1 + n];
                case "left":
                    return [-n, 1 - t];
            }
        }
        const mapped = pairs.map(function (p) {
            const local = map(p[0], p[1]);
            return [toBox(local[0]), toBox(local[1])];
        });
        return (
            type +
            " " +
            mapped
                .map(function (p) {
                    return p[0].toFixed(4) + "," + p[1].toFixed(4);
                })
                .join(" ")
        );
    }

    function sidePath(side, dir, amplitude, toBox) {
        return edgeCommands(dir, amplitude).map(function (cmd) {
            return transformCommand(side, cmd, toBox);
        });
    }

    function cellPathD(dirs, amplitude, toBox) {
        const commands = ["M " + toBox(0) + "," + toBox(0)];
        ["top", "right", "bottom", "left"].forEach(function (side) {
            sidePath(side, dirs[side], amplitude, toBox).forEach(function (c) {
                commands.push(c);
            });
        });
        commands.push("Z");
        return commands.join(" ");
    }

    // Une pièce dessinée exactement à la taille de sa case ne peut pas
    // montrer de languette qui déborde : il n'y a tout simplement rien à
    // peindre au-delà de sa propre boîte, quelle que soit la forme du
    // clip-path (le clip ne peut que retirer de la matière, jamais en
    // ajouter hors de l'élément). padFraction agrandit donc la boîte de
    // chaque pièce d'une marge (fraction d'une case) tout autour, et toBox
    // reprojette les coordonnées "en case" (0..1 = la case) vers cette boîte
    // agrandie (0..1 = la boîte) : n=0 (bord plat) retombe pile sur le bord
    // réel de la case, n=+amplitude (languette) déborde dans la marge, qui
    // existe désormais pour de vrai côté DOM (voir applyToGrid).
    function padFractionFor(amplitude) {
        return amplitude * 1.6 + 0.08;
    }

    // totalCells : nombre réel de pièces — peut ne pas remplir tout le
    // rectangle rows×cols (dernière ligne incomplète, ex. 3 cases sur 2
    // colonnes). Un bord donnant sur une case absente reste droit (dir=0),
    // jamais d'emboîtement dans le vide.
    function buildJigsawClipPaths(totalCells, cols, seedStr, amplitude) {
        amplitude = amplitude || 0.2;
        cols = Math.max(1, cols || 1);
        const rows = Math.ceil(totalCells / cols);
        const exists = function (r, c) {
            return r >= 0 && r < rows && c >= 0 && c < cols && r * cols + c < totalCells;
        };
        const rng = mulberry32(hashSeed(seedStr));

        // pad : la case (0..1) est recentrée dans une boîte plus grande
        // (0..1 de la boîte = pad..1-pad de la case), voir padFractionFor.
        const pad = padFractionFor(amplitude);
        const boxScale = 1 + 2 * pad;
        const coreStart = pad / boxScale;
        const coreSpan = 1 / boxScale;
        const toBox = function (v) {
            return coreStart + v * coreSpan;
        };

        // hBump[r][c] : true = la case du haut (r,c) possède la languette,
        // qui pousse vers le bas.
        const hBump = [];
        for (let r = 0; r < rows - 1; r++) {
            hBump.push([]);
            for (let c = 0; c < cols; c++) hBump[r].push(rng() < 0.5);
        }
        // vBump[r][c] : true = la case de gauche (r,c) possède la languette,
        // qui pousse vers la droite.
        const vBump = [];
        for (let r = 0; r < rows; r++) {
            vBump.push([]);
            for (let c = 0; c < cols - 1; c++) vBump[r].push(rng() < 0.5);
        }

        const cells = [];
        for (let index = 0; index < totalCells; index++) {
            const r = Math.floor(index / cols);
            const c = index % cols;
            const dirs = {
                top: exists(r - 1, c) ? (hBump[r - 1][c] ? -1 : 1) : 0,
                bottom: exists(r + 1, c) ? (hBump[r][c] ? 1 : -1) : 0,
                left: exists(r, c - 1) ? (vBump[r][c - 1] ? -1 : 1) : 0,
                right: exists(r, c + 1) ? (vBump[r][c] ? 1 : -1) : 0,
            };
            cells.push({ index: index, row: r, col: c, d: cellPathD(dirs, amplitude, toBox) });
        }
        cells.pad = pad;
        return cells;
    }

    // Applique les découpes à une grille déjà présente dans le DOM :
    // container doit contenir des éléments correspondant à pieceSelector
    // (.puzzle-piece par défaut), dans l'ordre des cases (index = ordre DOM).
    function applyToGrid(container, options) {
        options = options || {};
        const cols = options.cols || 1;
        const seed = String(options.seed != null ? options.seed : "puzzle");
        const amplitude = options.amplitude || 0.2;
        const pieceSelector = options.pieceSelector || ".puzzle-piece";

        const pieces = container.querySelectorAll(pieceSelector);
        if (!pieces.length) return;

        const shapes = buildJigsawClipPaths(pieces.length, cols, seed, amplitude);
        const rows = Math.ceil(pieces.length / cols);
        const pad = shapes.pad;
        const cellW = 100 / cols;
        const cellH = 100 / rows;

        const svgNS = "http://www.w3.org/2000/svg";
        const svg = document.createElementNS(svgNS, "svg");
        svg.setAttribute("width", "0");
        svg.setAttribute("height", "0");
        svg.style.position = "absolute";
        const defs = document.createElementNS(svgNS, "defs");
        svg.appendChild(defs);
        container.appendChild(svg);

        // Identifiant unique par appel : plusieurs grilles peuvent coexister
        // sur une même page (ex. la page collection liste des dizaines de
        // personnages), leurs ids de clipPath ne doivent jamais entrer en
        // collision.
        const uid = "pz" + Math.random().toString(36).slice(2, 9);

        pieces.forEach(function (piece, index) {
            const shape = shapes[index];
            const clipId = uid + "-" + shape.index;
            const clipPath = document.createElementNS(svgNS, "clipPath");
            clipPath.setAttribute("id", clipId);
            clipPath.setAttribute("clipPathUnits", "objectBoundingBox");
            const path = document.createElementNS(svgNS, "path");
            path.setAttribute("d", shape.d);
            clipPath.appendChild(path);
            defs.appendChild(clipPath);

            // La boîte de la pièce déborde de sa case (voir padFractionFor) :
            // sans ça, une languette qui pousse vers la voisine n'aurait
            // littéralement rien à peindre au-delà de la case, quel que soit
            // le clip-path. Position absolue plutôt que grid : les pièces
            // voisines doivent pouvoir se chevaucher légèrement.
            piece.style.position = "absolute";
            piece.style.left = (shape.col - pad) * cellW + "%";
            piece.style.top = (shape.row - pad) * cellH + "%";
            piece.style.width = cellW * (1 + 2 * pad) + "%";
            piece.style.height = cellH * (1 + 2 * pad) + "%";

            piece.style.clipPath = "url(#" + clipId + ")";
        });
    }

    // Auto-initialisation pour la page collection : toute grille déjà dans
    // le DOM au chargement, marquée data-puzzle-grid, est découpée
    // automatiquement. L'animation de fin de partie (fragment_reveal.js),
    // qui insère ses grilles dynamiquement après ce moment, appelle
    // applyToGrid() elle-même.
    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("[data-puzzle-grid]").forEach(function (container) {
            applyToGrid(container, {
                cols: parseInt(container.dataset.puzzleCols, 10) || 1,
                seed: container.dataset.puzzleSeed || "puzzle",
            });
        });
    });

    return { buildJigsawClipPaths: buildJigsawClipPaths, applyToGrid: applyToGrid };
})();
