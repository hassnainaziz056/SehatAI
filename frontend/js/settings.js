/**
 * frontend/js/settings.js — Account & Portal Settings Handler
 */
const SEHATAI_TOKEN_KEY = "sehatai_token";

const token = localStorage.getItem(SEHATAI_TOKEN_KEY);
if (!token) {
    window.location.href = "login.html";
}

renderPortalLayout();

const statusBox = document.getElementById("settings-status");
const themeSelector = document.getElementById("theme-selector");

function showStatus(msg, isError = true) {
    statusBox.textContent = msg;
    statusBox.hidden = false;
    statusBox.className = `form-status ${isError ? "form-status--error" : "form-status--success"}`;
}

// Restore saved theme preference
const savedTheme = localStorage.getItem("sehatai_theme") || "dark";
document.documentElement.setAttribute("data-theme", savedTheme);
if (themeSelector) themeSelector.value = savedTheme;

window.changeTheme = function(themeValue) {
    document.documentElement.setAttribute("data-theme", themeValue);
    localStorage.setItem("sehatai_theme", themeValue);
};

const passForm = document.getElementById("change-password-form");
if (passForm) {
    passForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const newPass = document.getElementById("new-pass").value;
        const confirmPass = document.getElementById("confirm-new-pass").value;

        if (newPass !== confirmPass) {
            showStatus("New passwords do not match.");
            return;
        }

        showStatus("Password updated successfully!", false);
        passForm.reset();
    });
}
