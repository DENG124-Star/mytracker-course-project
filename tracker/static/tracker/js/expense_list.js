document.addEventListener("DOMContentLoaded", function () {
    const filterDate = document.getElementById("filterDate");
    const filterCategory = document.getElementById("filterCategory");
    const tableRows = document.querySelectorAll("#expenseTable tbody tr");
    const deleteButtons = document.querySelectorAll(".delete-btn");
    const editButtons = document.querySelectorAll(".edit-btn");

    function applyFilters() {
        const selectedDate = filterDate.value;
        const selectedCategory = filterCategory.value;

        tableRows.forEach(function (row) {
            const rowDate = row.dataset.date;
            const rowCategory = row.dataset.category;

            const matchDate = !selectedDate || rowDate === selectedDate;
            const matchCategory = !selectedCategory || rowCategory === selectedCategory;

            if (matchDate && matchCategory) {
                row.style.display = "";
            } else {
                row.style.display = "none";
            }
        });
    }

    filterDate.addEventListener("change", applyFilters);
    filterCategory.addEventListener("change", applyFilters);

    editButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            window.alert("Edit feature will be connected to the Django back end.");
        });
    });

    deleteButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            const confirmed = window.confirm("Are you sure you want to delete this expense?");
            if (confirmed) {
                const row = button.closest("tr");
                row.remove();
            }
        });
    });
});