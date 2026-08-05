/**
 * frontend/js/profile.js — Phase 20: Expanded Patient Health Profile
 *
 * Auth guard identical to chat.js: no token -> straight to login.html.
 *
 * On load: GET /profile, pre-fill every field with whatever's already on
 * file (a first-time visitor gets an all-empty-but-freshly-created row —
 * see backend/routes/profile_routes.py's _get_or_create_profile).
 *
 * On save: PUT /profile with every field's current value. Unlike
 * register.js's "send null if nothing filled in" for a brand-new patient,
 * this always sends the full field set, INCLUDING blanks — a field a
 * patient clears here should actually clear on the server, not be
 * silently skipped.
 *
 * Same CORS note as the other frontend pages: serve this folder from a
 * local static server, don't open profile.html as a file:// URL.
 */

const API_BASE_URL = "http://127.0.0.1:8000";
const SEHATAI_TOKEN_KEY = "sehatai_token"; // must match login.js/chat.js

const token = localStorage.getItem(SEHATAI_TOKEN_KEY);
if (!token) {
    window.location.href = "login.html";
}

const form = document.getElementById("profile-form");
const statusBox = document.getElementById("form-status");
const loadingNote = document.getElementById("loading-note");
const fieldsWrapper = document.getElementById("profile-fields");
const submitBtn = document.getElementById("submit-btn");

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

/** Same 401-aware fetch wrapper as chat.js. */
async function authedFetch(path, options = {}) {
    const response = await fetch(`${API_BASE_URL}${path}`, {
        ...options,
        headers: {
            ...(options.headers || {}),
            Authorization: `Bearer ${token}`,
        },
    });

    if (response.status === 401) {
        localStorage.removeItem(SEHATAI_TOKEN_KEY);
        window.location.href = "login.html";
        throw new Error("Session expired");
    }

    return response;
}

/** Field IDs shared between the DOM and the API's field names — every
 * one of these is both a getElementById target and a JSON key. */
const FIELD_IDS = [
    "age", "gender", "blood-group", "height", "weight", "pregnancy",
    "smoking", "emergency-name", "emergency-phone",
    "allergies", "medications", "surgeries", "history",
];
const API_FIELD_NAMES = {
    age: "age", gender: "gender", "blood-group": "blood_group",
    height: "height_cm", weight: "weight_kg", pregnancy: "pregnancy_status",
    smoking: "smoking_status", "emergency-name": "emergency_contact_name",
    "emergency-phone": "emergency_contact_phone", allergies: "allergies",
    medications: "medications", surgeries: "surgeries", history: "medical_history",
};

function fillFormFromProfile(profile) {
    for (const fieldId of FIELD_IDS) {
        const el = document.getElementById(`profile-${fieldId}`);
        const value = profile[API_FIELD_NAMES[fieldId]];
        el.value = value === null || value === undefined ? "" : value;
    }
}

function collectFormAsProfile() {
    const payload = {};
    for (const fieldId of FIELD_IDS) {
        const el = document.getElementById(`profile-${fieldId}`);
        const raw = el.value.trim();
        const apiName = API_FIELD_NAMES[fieldId];
        if (el.type === "number") {
            payload[apiName] = raw === "" ? null : Number(raw);
        } else {
            payload[apiName] = raw === "" ? null : raw;
        }
    }
    return payload;
}

async function loadProfile() {
    try {
        const response = await authedFetch("/profile");
        if (!response.ok) {
            throw new Error(`Server responded with ${response.status}`);
        }
        const profile = await response.json();
        fillFormFromProfile(profile);
        loadingNote.hidden = true;
        fieldsWrapper.hidden = false;
    } catch (err) {
        loadingNote.textContent =
            "Couldn't load your profile right now. Please refresh to try again.";
        console.error("Failed to load /profile:", err);
    }
}

form.addEventListener("submit", async (event) => {
    event.preventDefault();
    hideStatus();

    submitBtn.disabled = true;
    submitBtn.textContent = "Saving…";

    try {
        const response = await authedFetch("/profile", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(collectFormAsProfile()),
        });

        if (response.ok) {
            showStatus("Profile saved.", "success");
        } else if (response.status === 422) {
            const errorBody = await response.json();
            const firstMessage =
                errorBody?.detail?.[0]?.msg || "Please check the form and try again.";
            showStatus(firstMessage, "error");
        } else {
            showStatus("Something went wrong. Please try again.", "error");
        }
    } catch (err) {
        showStatus("Couldn't reach the server. Is the API running?", "error");
        console.error("Profile save failed:", err);
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Save profile";
    }
});

loadProfile();