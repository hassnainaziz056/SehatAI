/**
 * frontend/js/wizard.js — Patient Profile Intake Wizard
 */
const API_BASE_URL = (window.location.port === "8000") ? window.location.origin : "http://127.0.0.1:8000";
const SEHATAI_TOKEN_KEY = "sehatai_token";

let currentStep = 1;
const totalSteps = 5;

// Check authentication
const token = localStorage.getItem(SEHATAI_TOKEN_KEY);
if (!token) {
    window.location.href = "login.html";
}

const progressBar = document.getElementById("progress-bar");
const prevBtn = document.getElementById("prev-btn");
const nextBtn = document.getElementById("next-btn");
const submitBtn = document.getElementById("submit-wizard-btn");
const wizardForm = document.getElementById("wizard-form");
const statusBox = document.getElementById("wizard-status");
const medicinesContainer = document.getElementById("medicines-container");
const addMedBtn = document.getElementById("add-med-btn");

function showStatus(msg, isError = true) {
    statusBox.textContent = msg;
    statusBox.hidden = false;
    statusBox.className = `form-status ${isError ? "form-status--error" : "form-status--success"}`;
}

function hideStatus() {
    statusBox.hidden = true;
    statusBox.textContent = "";
}

function updateStepperUI() {
    hideStatus();
    // Progress Bar
    const progressPercent = ((currentStep - 1) / (totalSteps - 1)) * 100;
    progressBar.style.width = `${progressPercent}%`;

    // Step Nodes
    document.querySelectorAll(".wizard-step-node").forEach((node) => {
        const stepNum = parseInt(node.getAttribute("data-step"));
        node.classList.remove("active", "completed");
        if (stepNum === currentStep) {
            node.classList.add("active");
        } else if (stepNum < currentStep) {
            node.classList.add("completed");
        }
    });

    // Step Contents
    document.querySelectorAll(".wizard-step-content").forEach((content) => {
        content.classList.remove("active");
    });
    document.getElementById(`step-${currentStep}`).classList.add("active");

    // Action Buttons
    prevBtn.style.visibility = currentStep === 1 ? "hidden" : "visible";
    if (currentStep === totalSteps) {
        nextBtn.style.display = "none";
        submitBtn.style.display = "inline-block";
        renderReviewSummary();
    } else {
        nextBtn.style.display = "inline-block";
        submitBtn.style.display = "none";
    }
}

function validateCurrentStep() {
    if (currentStep === 1) {
        const name = document.getElementById("full_name").value.trim();
        if (!name) {
            showStatus("Please enter your full name to proceed.");
            return false;
        }
    }
    return true;
}

nextBtn.addEventListener("click", () => {
    if (!validateCurrentStep()) return;
    if (currentStep < totalSteps) {
        currentStep++;
        updateStepperUI();
    }
});

prevBtn.addEventListener("click", () => {
    if (currentStep > 1) {
        currentStep--;
        updateStepperUI();
    }
});

// Dynamic Medicine Entry Builder
function createMedicineItemCard(data = {}) {
    const medCard = document.createElement("div");
    medCard.className = "medicine-item-card";
    medCard.style.cssText = "background: var(--color-surface-raised); border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: 16px; position: relative;";

    medCard.innerHTML = `
        <button type="button" class="remove-med-btn" style="position: absolute; top: 12px; right: 12px; background: transparent; border: none; color: var(--color-danger); cursor: pointer; font-size: 18px; font-weight: 700;">&times;</button>
        <div class="grid-2">
            <div class="form-group" style="margin-bottom: 8px;">
                <label>Medicine Name *</label>
                <input type="text" class="form-control med-name" placeholder="e.g. Metformin" value="${data.name || ''}" required>
            </div>
            <div class="form-group" style="margin-bottom: 8px;">
                <label>Dosage</label>
                <input type="text" class="form-control med-dosage" placeholder="e.g. 500mg" value="${data.dosage || ''}">
            </div>
        </div>
        <div class="grid-2">
            <div class="form-group" style="margin-bottom: 8px;">
                <label>Frequency</label>
                <input type="text" class="form-control med-frequency" placeholder="e.g. Twice daily" value="${data.frequency || ''}">
            </div>
            <div class="form-group" style="margin-bottom: 8px;">
                <label>Start Date</label>
                <input type="date" class="form-control med-start-date" value="${data.start_date || ''}">
            </div>
        </div>
        <div class="form-group" style="margin-bottom: 0;">
            <label>Dose Schedule</label>
            <div class="med-slot-picker">
                <label class="slot-chip"><input type="checkbox" class="med-morning" ${data.morning ? 'checked' : ''}> Morning (8 AM)</label>
                <label class="slot-chip"><input type="checkbox" class="med-afternoon" ${data.afternoon ? 'checked' : ''}> Afternoon (2 PM)</label>
                <label class="slot-chip"><input type="checkbox" class="med-night" ${data.night ? 'checked' : ''}> Night (9 PM)</label>
            </div>
        </div>
    `;

    medCard.querySelector(".remove-med-btn").addEventListener("click", () => {
        medCard.remove();
    });

    return medCard;
}

addMedBtn.addEventListener("click", () => {
    medicinesContainer.appendChild(createMedicineItemCard());
});

// Initialize with one default blank medicine card
medicinesContainer.appendChild(createMedicineItemCard());

// Collect Medicine Items Data
function getMedicinesData() {
    const items = [];
    document.querySelectorAll(".medicine-item-card").forEach((card) => {
        const name = card.querySelector(".med-name").value.trim();
        if (name) {
            items.push({
                name,
                dosage: card.querySelector(".med-dosage").value.trim() || null,
                frequency: card.querySelector(".med-frequency").value.trim() || null,
                morning: card.querySelector(".med-morning").checked,
                afternoon: card.querySelector(".med-afternoon").checked,
                night: card.querySelector(".med-night").checked,
                start_date: card.querySelector(".med-start-date").value || null,
            });
        }
    });
    return items;
}

// Render Review Summary
function renderReviewSummary() {
    const summaryBox = document.getElementById("review-summary");
    const name = document.getElementById("full_name").value.trim();
    const age = document.getElementById("age").value || "N/A";
    const gender = document.getElementById("gender").value || "N/A";
    const height = document.getElementById("height_cm").value || "N/A";
    const weight = document.getElementById("weight_kg").value || "N/A";
    const blood = document.getElementById("blood_group").value || "N/A";

    const selectedConditions = Array.from(document.querySelectorAll("#conditions-chips input:checked")).map(c => c.value);
    const otherConds = document.getElementById("other-conditions").value.trim();
    if (otherConds) selectedConditions.push(otherConds);

    const allergies = document.getElementById("allergies").value.trim() || "None reported";
    const medicines = getMedicinesData();

    const emergencyName = document.getElementById("emergency_name").value.trim() || "N/A";
    const emergencyRel = document.getElementById("emergency_relationship").value.trim() || "N/A";
    const emergencyPhone = document.getElementById("emergency_phone").value.trim() || "N/A";

    summaryBox.innerHTML = `
        <div style="border-bottom: 1px solid var(--color-border); padding-bottom: 12px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h4 style="font-weight: 700; color: var(--color-primary-hover);">1. Personal Information</h4>
                <button type="button" class="btn btn-secondary btn-sm" onclick="goToStep(1)">Edit</button>
            </div>
            <p style="font-size: 0.9rem; margin-top: 6px;">
                <strong>Name:</strong> ${name} | <strong>Age:</strong> ${age} | <strong>Gender:</strong> ${gender}<br>
                <strong>Height:</strong> ${height} cm | <strong>Weight:</strong> ${weight} kg | <strong>Blood Group:</strong> ${blood}
            </p>
        </div>

        <div style="border-bottom: 1px solid var(--color-border); padding-bottom: 12px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h4 style="font-weight: 700; color: var(--color-primary-hover);">2. Medical History</h4>
                <button type="button" class="btn btn-secondary btn-sm" onclick="goToStep(2)">Edit</button>
            </div>
            <p style="font-size: 0.9rem; margin-top: 6px;">
                <strong>Conditions:</strong> ${selectedConditions.length ? selectedConditions.join(", ") : "None"}<br>
                <strong>Allergies:</strong> ${allergies}
            </p>
        </div>

        <div style="border-bottom: 1px solid var(--color-border); padding-bottom: 12px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h4 style="font-weight: 700; color: var(--color-primary-hover);">3. Current Medicines</h4>
                <button type="button" class="btn btn-secondary btn-sm" onclick="goToStep(3)">Edit</button>
            </div>
            <p style="font-size: 0.9rem; margin-top: 6px;">
                ${medicines.length ? medicines.map(m => `• <strong>${m.name}</strong> (${m.dosage || 'Standard dose'}) - ${m.frequency || 'Daily'}`).join("<br>") : "No medicines added"}
            </p>
        </div>

        <div>
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h4 style="font-weight: 700; color: var(--color-primary-hover);">4. Emergency Contact</h4>
                <button type="button" class="btn btn-secondary btn-sm" onclick="goToStep(4)">Edit</button>
            </div>
            <p style="font-size: 0.9rem; margin-top: 6px;">
                <strong>Contact:</strong> ${emergencyName} (${emergencyRel}) - ${emergencyPhone}
            </p>
        </div>
    `;
}

window.goToStep = function(stepNum) {
    currentStep = stepNum;
    updateStepperUI();
};

wizardForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideStatus();

    const name = document.getElementById("full_name").value.trim();
    if (!name) {
        showStatus("Please enter your full name.");
        return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = "Saving Profile…";

    const selectedConditions = Array.from(document.querySelectorAll("#conditions-chips input:checked")).map(c => c.value);
    const otherConds = document.getElementById("other-conditions").value.trim();
    if (otherConds) {
        otherConds.split(",").forEach(c => { if(c.strip ? c.strip() : c.trim()) selectedConditions.push(c.trim()); });
    }

    const payload = {
        full_name: name,
        age: parseInt(document.getElementById("age").value) || null,
        gender: document.getElementById("gender").value || null,
        height_cm: parseFloat(document.getElementById("height_cm").value) || null,
        weight_kg: parseFloat(document.getElementById("weight_kg").value) || null,
        blood_group: document.getElementById("blood_group").value || null,
        conditions: selectedConditions,
        allergies: document.getElementById("allergies").value.trim() || null,
        surgeries: document.getElementById("surgeries").value.trim() || null,
        family_history: document.getElementById("family_history").value.trim() || null,
        smoking_status: document.getElementById("smoking_status").value || null,
        alcohol_status: document.getElementById("alcohol_status").value || null,
        pregnancy_status: document.getElementById("pregnancy_status").value || null,
        medicines: getMedicinesData(),
        emergency_contact_name: document.getElementById("emergency_name").value.trim() || null,
        emergency_contact_relationship: document.getElementById("emergency_relationship").value.trim() || null,
        emergency_contact_phone: document.getElementById("emergency_phone").value.trim() || null,
    };

    try {
        const response = await fetch(`${API_BASE_URL}/profile/wizard`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify(payload),
        });

        if (response.ok) {
            showStatus("Profile completed! Opening your health dashboard…", false);
            setTimeout(() => {
                window.location.href = "dashboard.html";
            }, 1000);
        } else {
            showStatus("Failed to save profile. Please check your entries and try again.");
        }
    } catch (err) {
        console.error("Wizard save error:", err);
        showStatus("Network error while saving profile. Please try again.");
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Complete Profile & Save";
    }
});

// Initialize Stepper
updateStepperUI();
