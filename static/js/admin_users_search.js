let currentPage = 1;
let ROWS_PER_PAGE = 10;

const searchInput = document.getElementById("user-search");
const rowsPerPageSelect = document.getElementById("user-rows-per-page-select");
const allRows = document.querySelectorAll(".user-row");

const prevButton = document.getElementById("user-pagination-prev");
const nextButton = document.getElementById("user-pagination-next");
const info = document.getElementById("user-pagination-info");

function applyFilterAndPagination() {
    const searchTerm = searchInput.value.toLowerCase().trim();

    const matchingRows = Array.from(allRows).filter(function (row) {
        return row.dataset.searchText.toLowerCase().includes(searchTerm);
    });

    allRows.forEach(function (row) {
        row.classList.add("hidden");
    });

    const startIndex = (currentPage - 1) * ROWS_PER_PAGE;
    const rowsForThisPage = matchingRows.slice(startIndex, startIndex + ROWS_PER_PAGE);

    rowsForThisPage.forEach(function (row) {
        row.classList.remove("hidden");
    });

    const totalPages = Math.max(1, Math.ceil(matchingRows.length / ROWS_PER_PAGE));

    prevButton.disabled = currentPage <= 1;
    nextButton.disabled = currentPage >= totalPages;
    info.textContent = `Page ${currentPage} / ${totalPages} (${matchingRows.length} utilisateur${matchingRows.length > 1 ? "s" : ""})`;
}

searchInput.addEventListener("input", function () {
    currentPage = 1;
    applyFilterAndPagination();
});

rowsPerPageSelect.addEventListener("change", function () {
    ROWS_PER_PAGE = parseInt(rowsPerPageSelect.value);
    currentPage = 1;
    applyFilterAndPagination();
});

prevButton.addEventListener("click", function () {
    currentPage -= 1;
    applyFilterAndPagination();
});

nextButton.addEventListener("click", function () {
    currentPage += 1;
    applyFilterAndPagination();
});

applyFilterAndPagination();