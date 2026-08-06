/**
 * frontend/js/login.js — Patient Portal Login Handler
 */
const API_BASE_URL = (window.location.port === "8000") ? window.location.origin : "http://127.0.0.1:8000";
const SEHATAI_TOKEN_KEY = "sehatai_token";

const form = document.getElementById("login-form");
const statusBox = document.getElementById("form-status");
const submitBtn = document.getElementById("submit-btn");

function showStatus(message, isError = true) {
    statusBox.textContent = message;
    statusBox.hidden = false;
    statusBox.className = `form-status ${isError ? "form-status--error" : "form-status--success"}`;
}

function hideStatus() {
    statusBox.hidden = true;
    statusBox.textContent = "";
}

// Auto-check stored session
(async function checkExistingToken() {
    const token = localStorage.getItem(SEHATAI_TOKEN_KEY);
    if (!token) return;

    try {
        const resp = await fetch(`${API_BASE_URL}/profile/status`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (resp.ok) {
            const data = await resp.json();
            if (data.profile_completed) {
                window.location.href = "dashboard.html";
            } else {
                window.location.href = "wizard.html";
            }
        }
    } catch (e) {
        // Token invalid or network issue, remain on login page
    }
})();

form.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideStatus();

    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;

    submitBtn.disabled = true;
    submitBtn.textContent = "Logging In…";

    try {
        const response = await fetch(`${API_BASE_URL}/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password }),
        });

        if (response.ok) {
            const data = await response.json();
            localStorage.setItem(SEHATAI_TOKEN_KEY, data.access_token);

            if (data.profile_completed) {
                window.location.href = "dashboard.html";
            } else {
                window.location.href = "wizard.html";
            }
        } else if (response.status === 401) {
            showStatus("Incorrect email or password.");
        } else {
            showStatus("Login failed. Please check your credentials.");
        }
    } catch (err) {
        console.error("Login error:", err);
        showStatus("Unable to connect to server. Please check your network or API status.");
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Log In";
    }
});