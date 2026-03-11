document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("expenseForm");

    const amount = document.getElementById("amount");
    const expenseDate = document.getElementById("expenseDate");
    const category = document.getElementById("category");
    const note = document.getElementById("note");

    const amountError = document.getElementById("amountError");
    const dateError = document.getElementById("dateError");
    const categoryError = document.getElementById("categoryError");
    const status = document.getElementById("expenseStatus");

    form.addEventListener("submit", function (event) {
        let valid = true;

        amountError.textContent = "";
        dateError.textContent = "";
        categoryError.textContent = "";
        status.textContent = "";

        if (amount.value.trim() === "") {
            amountError.textContent = "Amount is required.";
            valid = false;
        } else if (parseFloat(amount.value) <= 0) {
            amountError.textContent = "Amount must be greater than 0.";
            valid = false;
        }

        if (expenseDate.value.trim() === "") {
            dateError.textContent = "Date is required.";
            valid = false;
        }

        if (category.value.trim() === "") {
            categoryError.textContent = "Please select a category.";
            valid = false;
        }

        if (!valid) {
            event.preventDefault();
        } else {
            event.preventDefault();
            status.textContent = "Validation passed. This page is ready to save expense data to the Django back end.";
        }
    });
});