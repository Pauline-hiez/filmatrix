// Éditeur visuel des zones cachées d'une scène Cache-Ciné
// (templates/admin/cache_cine_form.html). L'admin dessine un rectangle par
// clique-glisse directement sur l'image, saisit le titre de l'œuvre dans la
// liste en dessous ; le tout est sérialisé dans un unique champ caché JSON
// (#cc-references-json), soumis avec le reste du formulaire — même stratégie
// que les champs cachés image_x/image_y du formulaire personnage
// (static/js/admin_character_form.js), mais pour un rectangle plutôt qu'un
// point.

(function () {
    const editor = document.getElementById("cc-zone-editor");
    const image = document.getElementById("cc-editor-image");
    const zoneList = document.getElementById("cc-zone-list");
    const hiddenInput = document.getElementById("cc-references-json");
    const existingEl = document.getElementById("cc-existing-references");

    if (!editor || !image || !zoneList || !hiddenInput) {
        return;
    }

    let existing = [];
    try {
        existing = JSON.parse(existingEl.textContent || "[]");
    } catch (error) {
        existing = [];
    }

    let zones = existing.map(function (reference, index) {
        return {
            localId: "z" + index,
            title: reference.title || "",
            pos_x: reference.pos_x,
            pos_y: reference.pos_y,
            width: reference.width,
            height: reference.height,
        };
    });
    let nextLocalId = zones.length;

    const MIN_SIZE_PERCENT = 1.5;

    function clamp(value, min, max) {
        return Math.min(Math.max(value, min), max);
    }

    function syncHiddenInput() {
        const payload = zones.map(function (zone) {
            return {
                title: zone.title,
                pos_x: zone.pos_x,
                pos_y: zone.pos_y,
                width: zone.width,
                height: zone.height,
            };
        });
        hiddenInput.value = JSON.stringify(payload);
    }

    function render() {
        editor.querySelectorAll(".cc-editor-rect").forEach(function (el) {
            el.remove();
        });
        zoneList.innerHTML = "";

        zones.forEach(function (zone, index) {
            const rect = document.createElement("div");
            rect.className = "cc-editor-rect";
            rect.style.cssText =
                "position:absolute;left:" + zone.pos_x + "%;top:" + zone.pos_y + "%;" +
                "width:" + zone.width + "%;height:" + zone.height + "%;" +
                "border:2px solid #22d3ee;background:rgba(34,211,238,0.15);border-radius:4px;pointer-events:none;";

            const badge = document.createElement("span");
            badge.textContent = index + 1;
            badge.style.cssText =
                "position:absolute;top:-10px;left:-10px;width:20px;height:20px;border-radius:9999px;" +
                "background:#22d3ee;color:#020617;font-size:11px;font-weight:900;display:flex;" +
                "align-items:center;justify-content:center;";
            rect.appendChild(badge);
            editor.appendChild(rect);

            const row = document.createElement("li");
            row.className = "flex items-center gap-2 rounded-lg border border-cyan-400/20 bg-slate-950/60 px-2 py-1.5";

            const rowBadge = document.createElement("span");
            rowBadge.textContent = index + 1;
            rowBadge.className = "flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-cyan-400 text-[11px] font-black text-slate-950";
            row.appendChild(rowBadge);

            const input = document.createElement("input");
            input.type = "text";
            input.placeholder = "Titre de l'œuvre (ex. Matrix)";
            input.value = zone.title;
            input.className = "flex-1 bg-slate-900 border border-cyan-400/30 rounded px-2 py-1 text-sm text-slate-100";
            input.addEventListener("input", function () {
                zone.title = input.value;
                syncHiddenInput();
            });
            row.appendChild(input);

            const deleteButton = document.createElement("button");
            deleteButton.type = "button";
            deleteButton.textContent = "✕";
            deleteButton.className = "text-red-400 hover:text-red-300 transition px-1";
            deleteButton.addEventListener("click", function () {
                zones = zones.filter(function (item) {
                    return item.localId !== zone.localId;
                });
                render();
            });
            row.appendChild(deleteButton);

            zoneList.appendChild(row);
        });

        syncHiddenInput();
    }

    function imageRelativePercent(event) {
        const rect = image.getBoundingClientRect();
        const x = clamp(((event.clientX - rect.left) / rect.width) * 100, 0, 100);
        const y = clamp(((event.clientY - rect.top) / rect.height) * 100, 0, 100);
        return { x: x, y: y };
    }

    let drawing = null;
    let previewRect = null;

    editor.addEventListener("mousedown", function (event) {
        if (event.target.closest(".cc-editor-rect")) {
            return;
        }
        event.preventDefault();
        const start = imageRelativePercent(event);
        drawing = { startX: start.x, startY: start.y };

        previewRect = document.createElement("div");
        previewRect.style.cssText =
            "position:absolute;border:2px dashed #fbbf24;background:rgba(251,191,36,0.15);pointer-events:none;";
        editor.appendChild(previewRect);
    });

    editor.addEventListener("mousemove", function (event) {
        if (!drawing || !previewRect) return;

        const current = imageRelativePercent(event);
        const left = Math.min(drawing.startX, current.x);
        const top = Math.min(drawing.startY, current.y);
        const width = Math.abs(current.x - drawing.startX);
        const height = Math.abs(current.y - drawing.startY);

        previewRect.style.left = left + "%";
        previewRect.style.top = top + "%";
        previewRect.style.width = width + "%";
        previewRect.style.height = height + "%";
    });

    function finishDrawing(event) {
        if (!drawing) return;

        const current = imageRelativePercent(event);
        const pos_x = Math.min(drawing.startX, current.x);
        const pos_y = Math.min(drawing.startY, current.y);
        const width = Math.abs(current.x - drawing.startX);
        const height = Math.abs(current.y - drawing.startY);

        drawing = null;
        if (previewRect) {
            previewRect.remove();
            previewRect = null;
        }

        if (width < MIN_SIZE_PERCENT || height < MIN_SIZE_PERCENT) {
            return;
        }

        zones.push({
            localId: "z" + nextLocalId++,
            title: "",
            pos_x: pos_x,
            pos_y: pos_y,
            width: Math.min(width, 100 - pos_x),
            height: Math.min(height, 100 - pos_y),
        });
        render();
    }

    editor.addEventListener("mouseup", finishDrawing);
    editor.addEventListener("mouseleave", function () {
        drawing = null;
        if (previewRect) {
            previewRect.remove();
            previewRect = null;
        }
    });

    render();
})();
