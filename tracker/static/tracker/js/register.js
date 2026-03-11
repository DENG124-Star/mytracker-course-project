document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("registerForm");

    const username = document.getElementById("username");
    const email = document.getElementById("registerEmail");
    const password = document.getElementById("registerPassword");
    const confirmPassword = document.getElementById("confirmPassword");

    const usernameError = document.getElementById("usernameError");
    const emailError = document.getElementById("registerEmailError");
    const passwordError = document.getElementById("registerPasswordError");
    const confirmPasswordError = document.getElementById("confirmPasswordError");
    const status = document.getElementById("registerStatus");

    function isValidEmail(value) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
    }

    form.addEventListener("submit", function (event) {
        let valid = true;

        usernameError.textContent = "";
        emailError.textContent = "";
        passwordError.textContent = "";
        confirmPasswordError.textContent = "";
        status.textContent = "";

        if (username.value.trim() === "") {
            usernameError.textContent = "Username is required.";
            valid = false;
        }

        if (email.value.trim() === "") {
            emailError.textContent = "Email is required.";
            valid = false;
        } else if (!isValidEmail(email.value.trim())) {
            emailError.textContent = "Please enter a valid email address.";
            valid = false;
        }

        if (password.value.trim() === "") {
            passwordError.textContent = "Password is required.";
            valid = false;
        } else if (password.value.trim().length < 8) {
            passwordError.textContent = "Password must be at least 8 characters.";
            valid = false;
        }

        if (confirmPassword.value.trim() === "") {
            confirmPasswordError.textContent = "Please confirm your password.";
            valid = false;
        } else if (confirmPassword.value !== password.value) {
            confirmPasswordError.textContent = "Passwords do not match.";
            valid = false;
        }

        if (!valid) {
            event.preventDefault();
        } else {
            event.preventDefault();
            status.textContent = "Validation passed. This page is ready to connect to Django registration logic.";
        }
    });
});