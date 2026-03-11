document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("loginForm");
    const emailInput = document.getElementById("loginEmail");
    const passwordInput = document.getElementById("loginPassword");

    const emailError = document.getElementById("loginEmailError");
    const passwordError = document.getElementById("loginPasswordError");
    const status = document.getElementById("loginStatus");

    form.addEventListener("submit", function (event) {
        let valid = true;

        emailError.textContent = "";
        passwordError.textContent = "";
        status.textContent = "";

        if (emailInput.value.trim() === "") {
            emailError.textContent = "Username or Email is required.";
            valid = false;
        }

        if (passwordInput.value.trim() === "") {
            passwordError.textContent = "Password is required.";
            valid = false;
        }

        if (!valid) {
            event.preventDefault();
        } else {
            event.preventDefault();
            status.textContent = "Validation passed. This page is ready to connect to Django authentication.";
        }
    });
});