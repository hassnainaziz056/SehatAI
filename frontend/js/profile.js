/**
 * frontend/js/profile.js — Patient Health Profile Page
 */
const API_BASE_URL = (window.location.port === "8000") ? window.location.origin : "http://127.0.0.1:8000";
const SEHATAI_TOKEN_KEY = "sehatai_token";

const token = localStorage.getItem(SEHATAI_TOKEN_KEY);
if (!token) {
    window.location.href = "login.html";
}

renderPortalLayout();

let isEditing = false;
const toggleBtn = document.getElementById("toggle-edit-btn");
const saveBar = document.getElementById("save-profile-bar");
const saveBtn = document.getElementById("save-profile-btn");
const profileForm = document.getElementById("profile-form");
const statusBox = document.getElementById("profile-status");

const fields = [
    "prof-age", "prof-gender", "prof-height", "prof-weight", "prof-blood",
    "prof-smoking", "prof-alcohol", "prof-emergency-name", "prof-emergency-phone",
    "prof-allergies", "prof-surgeries", "prof-family", "prof-medical-history"
];

function showStatus(msg, isError = true) {
    statusBox.textContent = msg;
    statusBox.hidden = false;
    statusBox.className = `form-status ${isError ? "form-status--error" : "form-status--success"}`;
}

function hideStatus() {
    statusBox.hidden = true;
    statusBox.textContent = "";
}

window.toggleProfileEdit = function(forceState = null) {
    isEditing = forceState !== null ? forceState : !isEditing;
    fields.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.disabled = !isEditing;
    });

    if (isEditing) {
        toggleBtn.style.display = "none";
        saveBar.style.display = "flex";
    } else {
        toggleBtn.style.display = "inline-block";
        saveBar.style.display = "none";
        loadProfileData();
    }
};

async function loadProfileData() {
    try {
        const response = await fetch(`${API_BASE_URL}/profile`, {
            headers: { "Authorization": `Bearer ${token}` }
        });

        if (response.status === 401) {
            handleLogout();
            return;
        }

        if (response.ok) {
            const data = await response.json();
            document.getElementById("prof-age").value = data.age || "";
            document.getElementById("prof-gender").value = data.gender || "";
            document.getElementById("prof-height").value = data.height_cm || "";
            document.getElementById("prof-weight").value = data.weight_kg || "";
            document.getElementById("prof-blood").value = data.blood_group || "";
            document.getElementById("prof-smoking").value = data.smoking_status || "Never smoked";
            document.getElementById("prof-alcohol").value = data.alcohol_status || "Never";
            document.getElementById("prof-emergency-name").value = data.emergency_contact_name || "";
            document.getElementById("prof-emergency-phone").value = data.emergency_contact_phone || "";
            document.getElementById("prof-allergies").value = data.allergies || "";
            document.getElementById("prof-surgeries").value = data.surgeries || "";
            document.getElementById("prof-family").value = data.family_history || "";
            document.getElementById("prof-medical-history").value = data.medical_history || "";
        }
    } catch (err) {
        console.error("Profile load error:", err);
    }
}

profileForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideStatus();

    saveBtn.disabled = true;
    saveBtn.textContent = "Saving…";

    const payload = {
        age: parseInt(document.getElementById("prof-age").value) || null,
        gender: document.getElementById("prof-gender").value || null,
        height_cm: parseFloat(document.getElementById("prof-height").value) || null,
        weight_kg: parseFloat(document.getElementById("prof-weight").value) || null,
        blood_group: document.getElementById("prof-blood").value || null,
        smoking_status: document.getElementById("prof-smoking").value || null,
        alcohol_status: document.getElementById("prof-alcohol").value || null,
        emergency_contact_name: document.getElementById("prof-emergency-name").value.trim() || null,
        emergency_contact_phone: document.getElementById("prof-emergency-phone").value.trim() || null,
        allergies: document.getElementById("prof-allergies").value.trim() || null,
        surgeries: document.getElementById("prof-surgeries").value.trim() || null,
        family_history: document.getElementById("prof-family").value.trim() || null,
        medical_history: document.getElementById("prof-medical-history").value.trim() || null,
    };

    try {
        const response = await fetch(`${API_BASE_URL}/profile`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            showStatus("Profile updated successfully!", false);
            toggleProfileEdit(false);
        } else {
            showStatus("Failed to update profile. Please try again.");
        }
    } catch (err) {
        console.error("Update profile error:", err);
        showStatus("Network error while updating profile.");
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = "Save Profile Changes";
    }
});

loadProfileData();