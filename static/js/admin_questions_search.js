document.querySelectorAll(".mode-tab-button").forEach(function (tabButton) {
    tabButton.addEventListener("click", function () {
        const selectedMode = tabButton.dataset.mode;

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

        document.querySelectorAll(".question-mode-panel").forEach(function (panel) {
            panel.classList.toggle("hidden", panel.dataset.mode !== selectedMode);
        });
    });
});

const searchInput = document.getElementById("question-search");
const suggestionsBox = document.getElementById("search-suggestions");
const allRows = document.querySelectorAll(".question-row");
const allSections = document.querySelectorAll(".question-mode-section");

searchInput.addEventListener("input", function () {
    const searchTerm = searchInput.value.toLowerCase().trim();

    filterTableRows(searchTerm);
    showSuggestions(searchTerm);
});

function filterTableRows(searchTerm) {
    allSections.forEach(function (section) {
        let visibleRowsInSection = 0;

        section.querySelectorAll(".question-row").forEach(function (row) {
            const rowText = row.dataset.searchText.toLowerCase();
            const matches = rowText.includes(searchTerm);

            row.classList.toggle("hidden", !matches);
            if (matches) {
                visibleRowsInSection += 1;
            }
        });

        if (searchTerm) {
            section.open = visibleRowsInSection > 0;
        }
    });
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
            <span class="text-xs text-cyan-400 uppercase shrink-0">${row.dataset.mode}</span>
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
    const targetButton = document.querySelector(`.mode-tab-button[data-mode="${row.dataset.mode}"]`);
    targetButton.click();

    suggestionsBox.classList.add("hidden");
    searchInput.value = "";
    filterTableRows("");

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