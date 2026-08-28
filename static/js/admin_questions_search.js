const currentPageByMode = {};

const searchInput = document.getElementById("question-search");
const suggestionsBox = document.getElementById("search-suggestions");
const rowsPerPageSelect = document.getElementById("rows-per-page-select");
const allRows = document.querySelectorAll(".question-row");
const allPanels = document.querySelectorAll(".question-mode-panel");

let ROWS_PER_PAGE = parseInt(rowsPerPageSelect.value);

// ---- Nombre de lignes par page ----

rowsPerPageSelect.addEventListener("change", function () {
    ROWS_PER_PAGE = parseInt(rowsPerPageSelect.value);

    allPanels.forEach(function (panel) {
        const mode = panel.dataset.mode;
        currentPageByMode[mode] = 1;
        applySearchToPanel(panel, searchInput.value.toLowerCase().trim());
    });
});

// ---- Onglets ----

document.querySelectorAll(".mode-tab-button").forEach(function (tabButton) {
    tabButton.addEventListener("click", function () {
        activateTab(tabButton.dataset.mode);
    });
});

function activateTab(selectedMode) {
    document.querySelectorAll(".mode-tab-button").forEach(function (button) {
        const isActive = button.dataset.mode === selectedMode;
        button.classList.toggle("bg-cyan-400", isActive);
        button.classList.toggle("text-slate-950", isActive);
        button.classList.toggle("font-bold", isActive);
        button.classList.toggle("bg-slate-900", !isActive);
        button.classList.toggle("border", !isActive);
        button.classList.toggle("border-cyan-400/30", !isActive);
        button.classList.toggle("text-slate-300", !isActive);
    });

    allPanels.forEach(function (panel) {
        panel.classList.toggle("hidden", panel.dataset.mode !== selectedMode);
    });
}

// ---- Recherche et suggestions ----

searchInput.addEventListener("input", function () {
    const searchTerm = searchInput.value.toLowerCase().trim();

    allPanels.forEach(function (panel) {
        const mode = panel.dataset.mode;
        currentPageByMode[mode] = 1;
        applySearchToPanel(panel, searchTerm);
    });

    showSuggestions(searchTerm);
});

function applySearchToPanel(panel, searchTerm) {
    const mode = panel.dataset.mode;
    const rows = Array.from(panel.querySelectorAll(".question-row"));

    const matchingRows = rows.filter(function (row) {
        return row.dataset.searchText.toLowerCase().includes(searchTerm);
    });

    rows.forEach(function (row) {
        row.classList.add("hidden");
    });

    const page = currentPageByMode[mode] || 1;
    const startIndex = (page - 1) * ROWS_PER_PAGE;
    const rowsForThisPage = matchingRows.slice(startIndex, startIndex + ROWS_PER_PAGE);

    rowsForThisPage.forEach(function (row) {
        row.classList.remove("hidden");
    });

    updatePaginationControls(panel, matchingRows.length, page);
}

function updatePaginationControls(panel, totalMatching, currentPage) {
    const mode = panel.dataset.mode;
    const controls = document.querySelector(`.pagination-controls[data-mode="${mode}"]`);
    const totalPages = Math.max(1, Math.ceil(totalMatching / ROWS_PER_PAGE));

    const prevButton = controls.querySelector(".pagination-prev");
    const nextButton = controls.querySelector(".pagination-next");
    const info = controls.querySelector(".pagination-info");

    prevButton.disabled = currentPage <= 1;
    nextButton.disabled = currentPage >= totalPages;
    info.textContent = `Page ${currentPage} / ${totalPages} (${totalMatching} question${totalMatching > 1 ? "s" : ""})`;

    prevButton.onclick = function () {
        currentPageByMode[mode] = currentPage - 1;
        applySearchToPanel(panel, searchInput.value.toLowerCase().trim());
    };

    nextButton.onclick = function () {
        currentPageByMode[mode] = currentPage + 1;
        applySearchToPanel(panel, searchInput.value.toLowerCase().trim());
    };
}

function showSuggestions(searchTerm) {
    if (!searchTerm) {
        suggestionsBox.classList.add("hidden");
        suggestionsBox.innerHTML = "";
        return;
    }

    const matchingRows = Array.from(allRows)
        .filter(function (row) {
            return row.dataset.searchText.toLowerCase().includes(searchTerm);
        })
        .slice(0, 8);

    if (matchingRows.length === 0) {
        suggestionsBox.innerHTML =
            '<p class="text-sm text-slate-500 px-3 py-2">Aucune question trouvée.</p>';
        suggestionsBox.classList.remove("hidden");
        return;
    }

    suggestionsBox.innerHTML = "";

    matchingRows.forEach(function (row) {
        const suggestion = document.createElement("button");
        suggestion.type = "button";
        suggestion.className =
            "w-full text-left px-3 py-2 hover:bg-slate-800 transition flex items-center gap-2";
        suggestion.innerHTML = `
            <span class="text-xs text-cyan-400 uppercase shrink-0">${row.dataset.mode.replaceAll("_", " ")}</span>
            <span class="text-sm text-slate-200 truncate">${row.dataset.displayText}</span>
        `;

        suggestion.addEventListener("click", function () {
            jumpToRow(row);
        });

        suggestionsBox.appendChild(suggestion);
    });

    suggestionsBox.classList.remove("hidden");
}

function jumpToRow(row) {
    activateTab(row.dataset.mode);

    suggestionsBox.classList.add("hidden");
    searchInput.value = "";

    const panel = row.closest(".question-mode-panel");
    const mode = panel.dataset.mode;
    const rows = Array.from(panel.querySelectorAll(".question-row"));
    const rowIndex = rows.indexOf(row);
    currentPageByMode[mode] = Math.floor(rowIndex / ROWS_PER_PAGE) + 1;

    applySearchToPanel(panel, "");

    row.scrollIntoView({ behavior: "smooth", block: "center" });
    row.classList.add("bg-cyan-400/20");
    setTimeout(function () {
        row.classList.remove("bg-cyan-400/20");
    }, 2000);
}

document.addEventListener("click", function (event) {
    if (!searchInput.contains(event.target) && !suggestionsBox.contains(event.target)) {
        suggestionsBox.classList.add("hidden");
    }
});

// ---- Initialisation : pagine chaque panneau des le chargement ----

allPanels.forEach(function (panel) {
    const mode = panel.dataset.mode;
    currentPageByMode[mode] = 1;
    applySearchToPanel(panel, "");
});