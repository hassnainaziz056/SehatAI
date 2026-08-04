/**
 * frontend/js/login.js — Phase 18: Chat UI (login half)
 *
 * On submit: POSTs email/password to POST /login. On success, stores the
 * returned JWT in localStorage under SEHATAI_TOKEN_KEY and redirects to
 * chat.html, which reads that same key to authenticate GET /chat/history
 * and POST /chat.
 *
 * Same CORS note as register.js: open this page through a local static
 * server (e.g. `python -m http.server 5500`), not as a file:// URL, or
 * the fetch() below will fail with a CORS error before it ever reaches
 * the backend's error handling.
 */

// Change this if the API is running somewhere other than local default.
const API_BASE_URL = "http://127.0.0.1:8000";

// Shared with chat.js — the localStorage key the JWT lives under.
const SEHATAI_TOKEN_KEY = "sehatai_token";

const form = document.getElementById("login-form");
const statusBox = document.getElementById("form-status");
const submitBtn = document.getElementById("submit-btn");

/** Show a status message above the form. kind is "error" or "success". */
function showStatus(message, kind) {
    statusBox.textContent = message;
    statusBox.hidden = false;
    statusBox.className = `form-status form-status--${kind}`;
}

function hideStatus() {
    statusBox.hidden = true;
    statusBox.textContent = "";
    statusBox.className = "form-status";
}

// If a token is already stored, this patient is presumably still logged
// in — skip the form and go straight to the chat page. A stale/expired
// token isn't a problem here: chat.js's own auth guard will bounce back
// to this page if GET /chat/history comes back 401.
if (localStorage.getItem(SEHATAI_TOKEN_KEY)) {
    window.location.href = "chat.html";
}

form.addEventListener("submit", async (event) => {
    event.preventDefault();
    hideStatus();

    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;

    submitBtn.disabled = true;
    submitBtn.textContent = "Logging in…";

    try {
        const response = await fetch(`${API_BASE_URL}/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password }),
        });

        if (response.ok) {
            const data = await response.json();
            localStorage.setItem(SEHATAI_TOKEN_KEY, data.access_token);
            window.location.href = "chat.html";
            return;
        } else if (response.status === 401) {
            showStatus("Incorrect email or password.", "error");
        } else if (response.status === 422) {
            const errorBody = await response.json();
            const firstMessage =
                errorBody?.detail?.[0]?.msg || "Please check the form and try again.";
            showStatus(firstMessage, "error");
        } else {
            showStatus("Something went wrong. Please try again.", "error");
        }
    } catch (err) {
        // Network-level failure — most commonly the CORS/file:// issue
        // described at the top of this file, or the API simply not running.
        showStatus(
            "Couldn't reach the server. Is the API running, and is this page " +
            "open through a local server (not opened as a file)?",
            "error"
        );
        console.error("Login request failed:", err);
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Log in";
    }
});