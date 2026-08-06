/**
 * frontend/js/register.js — Patient Portal Registration
 */
const API_BASE_URL = (window.location.port === "8000") ? window.location.origin : "http://127.0.0.1:8000";

const form = document.getElementById("register-form");
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

form.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideStatus();

    const name = document.getElementById("name").value.trim();
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;
    const confirm_password = document.getElementById("confirm_password").value;

    if (password !== confirm_password) {
        showStatus("Passwords do not match. Please check and try again.");
        return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = "Creating Account…";

    try {
        const response = await fetch(`${API_BASE_URL}/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, email, password, confirm_password }),
        });

        if (response.ok) {
            showStatus("Account created successfully! Redirecting to login…", false);
            setTimeout(() => {
                window.location.href = "login.html";
            }, 1200);
        } else if (response.status === 409) {
            showStatus("This email is already registered. Please log in.");
        } else if (response.status === 422) {
            const errData = await response.json();
            const msg = errData?.detail?.[0]?.msg || "Invalid input. Password must be at least 8 characters.";
            showStatus(msg);
        } else {
            let errorMsg = "Registration failed. Please try again.";
            try {
                const errData = await response.json();
                if (errData.detail) errorMsg = typeof errData.detail === 'string' ? errData.detail : JSON.stringify(errData.detail);
            } catch (e) { }
            showStatus(errorMsg);
        }
    } catch (err) {
        console.error("Register error:", err);
        showStatus("Unable to connect to server. Please ensure the API is running at " + API_BASE_URL);
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Create Account";
    }
});