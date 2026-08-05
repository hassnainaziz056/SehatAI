/**
 * frontend/js/register.js — Phase 17: Registration UI
 *
 * On load: fetches the fixed condition checklist from GET /conditions/available
 * and renders it as chart-tag checkboxes.
 * On submit: POSTs name/email/password/conditions to POST /register.
 *
 * IMPORTANT — CORS note for local testing:
 * This page must be opened through a local static server (e.g. VS Code's
 * "Live Server" on port 5500, or `python -m http.server 5500`), NOT by
 * double-clicking register.html to open it as a file:// URL. Browsers
 * send file:// pages with no real Origin, which the backend's CORS
 * config (see backend/main.py) can't recognize, so every fetch() below
 * would fail with a CORS error. Ports 5500, 8080, 3000, and 5173 are all
 * already allowed by the backend's default CORS origins — pick any of
 * those when starting a static server for this folder.
 */

// Change this if the API is running somewhere other than local default.
const API_BASE_URL = "http://127.0.0.1:8000";

const form = document.getElementById("register-form");
const statusBox = document.getElementById("form-status");
const conditionsGrid = document.getElementById("conditions-grid");
const otherCheckbox = document.getElementById("condition-other");
const otherTextInput = document.getElementById("condition-other-text");
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

/** Build one chart-tag checkbox + label for a condition name. */
function buildConditionTag(conditionName, index) {
    const wrapper = document.createElement("div");
    wrapper.className = "chart-tag";

    const inputId = `condition-${index}`;

    const input = document.createElement("input");
    input.type = "checkbox";
    input.className = "condition-checkbox";
    input.id = inputId;
    input.value = conditionName;

    const label = document.createElement("label");
    label.setAttribute("for", inputId);

    const dot = document.createElement("span");
    dot.className = "pulse-dot";
    dot.setAttribute("aria-hidden", "true");

    label.appendChild(dot);
    label.appendChild(document.createTextNode(conditionName));

    wrapper.appendChild(input);
    wrapper.appendChild(label);
    return wrapper;
}

/** Load the fixed checklist from the backend and render it. */
async function loadAvailableConditions() {
    try {
        const response = await fetch(`${API_BASE_URL}/conditions/available`);
        if (!response.ok) {
            throw new Error(`Server responded with ${response.status}`);
        }
        const conditions = await response.json();

        conditionsGrid.innerHTML = "";
        conditions.forEach((name, index) => {
            conditionsGrid.appendChild(buildConditionTag(name, index));
        });
    } catch (err) {
        // The checklist failing to load shouldn't block registration entirely —
        // a patient can still register with name/email/password and add
        // conditions later. Show a quiet inline note instead of blocking the form.
        conditionsGrid.innerHTML =
            '<p class="conditions-error">Couldn\'t load the checklist right now. ' +
            "You can still register — conditions can be added later.</p>";
        console.error("Failed to load /conditions/available:", err);
    }
}

/** Enable/disable the free-text "Other" input based on its checkbox. */
otherCheckbox.addEventListener("change", () => {
    otherTextInput.disabled = !otherCheckbox.checked;
    if (!otherCheckbox.checked) {
        otherTextInput.value = "";
    } else {
        otherTextInput.focus();
    }
});

/** Gather every selected condition name, including a filled-in "Other". */
function collectSelectedConditions() {
    const selected = Array.from(
        conditionsGrid.querySelectorAll(".condition-checkbox:checked")
    ).map((checkbox) => checkbox.value);

    if (otherCheckbox.checked) {
        const otherValue = otherTextInput.value.trim();
        if (otherValue) {
            selected.push(otherValue);
        }
    }

    return selected;
}

/** Phase 20: reads the optional health-profile fields. Every field that
 * was left blank is sent as null rather than "" or NaN, so the backend
 * (Pydantic's `int | None` / `float | None` fields) doesn't have to
 * special-case an empty string — an untouched number input, a select
 * still on its default option, and a truly-not-answered field should
 * all mean the same thing: "not provided". */
function collectProfileFields() {
    const numOrNull = (id) => {
        const raw = document.getElementById(id).value.trim();
        return raw === "" ? null : Number(raw);
    };
    const strOrNull = (id) => {
        const raw = document.getElementById(id).value.trim();
        return raw === "" ? null : raw;
    };

    return {
        age: numOrNull("profile-age"),
        gender: strOrNull("profile-gender"),
        blood_group: strOrNull("profile-blood-group"),
        height_cm: numOrNull("profile-height"),
        weight_kg: numOrNull("profile-weight"),
        pregnancy_status: strOrNull("profile-pregnancy"),
        smoking_status: strOrNull("profile-smoking"),
        emergency_contact_name: strOrNull("profile-emergency-name"),
        emergency_contact_phone: strOrNull("profile-emergency-phone"),
        allergies: strOrNull("profile-allergies"),
        medications: strOrNull("profile-medications"),
        surgeries: strOrNull("profile-surgeries"),
        medical_history: strOrNull("profile-history"),
    };
}

/** True if every profile field is null — i.e. the patient skipped the
 * whole optional section. Sent as `profile: null` in that case (not an
 * object of all-nulls) so the backend doesn't create an empty
 * PatientProfile row for someone who deliberately left it blank; see
 * auth_routes.py's `if request.profile is not None` check. */
function isProfileEmpty(profile) {
    return Object.values(profile).every((value) => value === null);
}

form.addEventListener("submit", async (event) => {
    event.preventDefault();
    hideStatus();

    const name = document.getElementById("name").value.trim();
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;

    if (otherCheckbox.checked && !otherTextInput.value.trim()) {
        showStatus('Please specify your condition, or uncheck "Other".', "error");
        otherTextInput.focus();
        return;
    }

    const profileFields = collectProfileFields();

    const payload = {
        name,
        email,
        password,
        conditions: collectSelectedConditions(),
        profile: isProfileEmpty(profileFields) ? null : profileFields,
    };

    submitBtn.disabled = true;
    submitBtn.textContent = "Creating account…";

    try {
        const response = await fetch(`${API_BASE_URL}/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        if (response.status === 201) {
            showStatus(
                "Account created! You can now log in.",
                "success"
            );
            form.reset();
            otherTextInput.disabled = true;
        } else if (response.status === 409) {
            showStatus(
                "That email is already registered. Try logging in instead.",
                "error"
            );
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
        console.error("Registration request failed:", err);
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Create account";
    }
});

loadAvailableConditions();