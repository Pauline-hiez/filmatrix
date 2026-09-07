// Éditeur visuel des références d'un cas Scène Mystère
// (templates/admin/scene_mystere_form.html). Même principe que
// static/js/admin_cache_cine_zones.js (clique-glisse pour dessiner un
// rectangle, sérialisation dans un champ caché JSON), mais chaque zone
// porte ici son propre indice et son propre QCM à 4 options (une question
// indépendante par référence, plutôt qu'un simple titre ou un radio
// "correcte" partagé par tout le cas).

(function () {
    const editor = document.getElementById("sm-zone-editor");
    const image = document.getElementById("sm-editor-image");
    const zoneList = document.getElementById("sm-zone-list");
    const hiddenInput = document.getElementById("sm-zones-json");
    const existingEl = document.getElementById("sm-existing-zones");

    if (!editor || !image || !zoneList || !hiddenInput) {
        return;
    }

    let existing = [];
    try {
        existing = JSON.parse(existingEl.textContent || "[]");
    } catch (error) {
        existing = [];
    }

    function emptyOptions() {
        return [
            { label: "", is_correct: true },
            { label: "", is_correct: false },
            { label: "", is_correct: false },
            { label: "", is_correct: false },
        ];
    }

    let zones = existing.map(function (zone, index) {
        const options = (zone.options && zone.options.length ? zone.options : emptyOptions()).slice(0, 4);
        while (options.length < 4) {
            options.push({ label: "", is_correct: false });
        }
        return {
            localId: "z" + index,
            pos_x: zone.pos_x,
            pos_y: zone.pos_y,
            width: zone.width,
            height: zone.height,
            clue_text: zone.clue_text || "",
            options: options,
        };
    });
    let nextLocalId = zones.length;

    const MIN_SIZE_PERCENT = 1.5;
    const OPTION_LETTERS = ["A", "B", "C", "D"];

    function clamp(value, min, max) {
        return Math.min(Math.max(value, min), max);
    }

    function syncHiddenInput() {
        const payload = zones.map(function (zone) {
            return {
                pos_x: zone.pos_x,
                pos_y: zone.pos_y,
                width: zone.width,
                height: zone.height,
                clue_text: zone.clue_text,
                options: zone.options,
            };
        });
        hiddenInput.value = JSON.stringify(payload);
    }

    function render() {
        editor.querySelectorAll(".sm-editor-rect").forEach(function (el) {
            el.remove();
        });
        zoneList.innerHTML = "";

        zones.forEach(function (zone, index) {
            const rect = document.createElement("div");
            rect.className = "sm-editor-rect";
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

            const card = document.createElement("div");
            card.className = "flex flex-col gap-2 rounded-lg border border-cyan-400/20 bg-slate-950/60 p-3";

            const header = document.createElement("div");
            header.className = "flex items-center justify-between gap-2";
            const headerLabel = document.createElement("span");
            headerLabel.className = "flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-cyan-400 text-[11px] font-black text-slate-950";
            headerLabel.textContent = index + 1;
            const deleteButton = document.createElement("button");
            deleteButton.type = "button";
            deleteButton.textContent = "Supprimer cette référence ✕";
            deleteButton.className = "text-xs text-red-400 hover:text-red-300 transition";
            deleteButton.addEventListener("click", function () {
                zones = zones.filter(function (item) {
                    return item.localId !== zone.localId;
                });
                render();
            });
            header.appendChild(headerLabel);
            header.appendChild(deleteButton);
            card.appendChild(header);

            const clueInput = document.createElement("input");
            clueInput.type = "text";
            clueInput.placeholder = "Indice (ex : Trouvez la référence à un film sur des dinosaures)";
            clueInput.value = zone.clue_text;
            clueInput.className = "bg-slate-900 border border-cyan-400/30 rounded px-2 py-1.5 text-sm text-slate-100";
            clueInput.addEventListener("input", function () {
                zone.clue_text = clueInput.value;
                syncHiddenInput();
            });
            card.appendChild(clueInput);

            const optionsWrap = document.createElement("div");
            optionsWrap.className = "flex flex-col gap-1.5";
            zone.options.forEach(function (option, optionIndex) {
                const row = document.createElement("label");
                row.className = "sm-option-row flex items-center gap-2 cursor-pointer";

                const radio = document.createElement("input");
                radio.type = "radio";
                radio.name = "sm-correct-option-" + zone.localId;
                radio.className = "accent-emerald-400";
                radio.checked = option.is_correct;
                radio.addEventListener("change", function () {
                    zone.options.forEach(function (item, i) {
                        item.is_correct = i === optionIndex;
                    });
                    syncHiddenInput();
                });

                const letter = document.createElement("span");
                letter.className = "w-4 shrink-0 text-xs font-bold text-slate-500";
                letter.textContent = OPTION_LETTERS[optionIndex];

                const input = document.createElement("input");
                input.type = "text";
                input.placeholder = "Option " + OPTION_LETTERS[optionIndex];
                input.value = option.label;
                input.className = "flex-1 bg-slate-900 border border-cyan-400/30 rounded px-2 py-1 text-sm text-slate-100";
                input.addEventListener("input", function () {
                    option.label = input.value;
                    syncHiddenInput();
                });

                row.appendChild(radio);
                row.appendChild(letter);
                row.appendChild(input);
                optionsWrap.appendChild(row);
            });
            card.appendChild(optionsWrap);

            zoneList.appendChild(card);
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
        if (event.target.closest(".sm-editor-rect")) {
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
            pos_x: pos_x,
            pos_y: pos_y,
            width: Math.min(width, 100 - pos_x),
            height: Math.min(height, 100 - pos_y),
            clue_text: "",
            options: emptyOptions(),
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
