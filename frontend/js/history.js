/**
 * frontend/js/history.js — Patient History (single-workflow rebuild)
 *
 * Single page: loads the patient's record (GET /profile), their selected
 * conditions (GET /conditions) against the fixed catalog
 * (GET /conditions/available), and lets them edit and save everything in
 * one go. Saving does two things:
 *   1. PUT /profile with every form field (including full_name).
 *   2. Diffs the conditions checklist against what the server already
 *      has on file, and issues POST /conditions / DELETE /conditions/{id}
 *      only for what actually changed.
 *
 * Depends on common.js (window.SehatAI.authedFetch/toast) being loaded
 * first.
 */

const { authedFetch, toast } = window.SehatAI;

const form = document.getElementById("record-form");
const saveBtn = document.getElementById("record-save-btn");
const statusEl = document.getElementById("record-status");
const checklistEl = document.getElementById("conditions-checklist");
const ringFill = document.getElementById("completion-ring-fill");
const ringLabel = document.getElementById("completion-ring-label");
const progressBar = document.getElementById("completion-bar");
const missingEl = document.getElementById("completion-missing");

// Circumference of the progress ring circle (r=36 -> 2*pi*36 ≈ 226.19,
// matching the stroke-dasharray already set in history.html).
const RING_CIRCUMFERENCE = 226;

const FIELD_IDS = {
    full_name: "rf-name",
    age: "rf-age",
    gender: "rf-gender",
    blood_group: "rf-blood-group",
    height_cm: "rf-height",
    weight_kg: "rf-weight",
    allergies: "rf-allergies",
    medications: "rf-medications",
    surgeries: "rf-surgeries",
    family_history: "rf-family-history",
    smoking_status: "rf-smoking",
    alcohol_status: "rf-alcohol",
    pregnancy_status: "rf-pregnancy",
    emergency_contact_name: "rf-emergency-name",
    emergency_contact_phone: "rf-emergency-phone",
};

const NUMBER_FIELDS = new Set(["age", "height_cm", "weight_kg"]);

// Fields counted toward the completion ring. full_name is deliberately
// excluded -- it's collected at registration already, so it shouldn't
// hold the ring back for someone who hasn't touched this page yet.
const COMPLETION_FIELDS = [
    "age", "gender", "blood_group", "height_cm", "weight_kg",
    "allergies", "medications", "surgeries", "family_history",
    "smoking_status", "alcohol_status",
    "emergency_contact_name", "emergency_contact_phone",
];

let availableConditions = [];
let currentConditions = []; // [{id, condition_name}]
let selectedConditionNames = new Set();

function setFieldValue(key, value) {
    const el = document.getElementById(FIELD_IDS[key]);
    if (!el) return;
    el.value = value === null || value === undefined ? "" : value;
}

function getFieldValue(key) {
    const el = document.getElementById(FIELD_IDS[key]);
    if (!el) return null;
    const raw = el.value.trim();
    if (raw === "") return null;
    if (NUMBER_FIELDS.has(key)) {
        const num = Number(raw);
        return Number.isNaN(num) ? null : num;
    }
    return raw;
}

function updateCompletionRing() {
    const filled = COMPLETION_FIELDS.filter((key) => getFieldValue(key) !== null).length;
    const total = COMPLETION_FIELDS.length;
    const pct = Math.round((filled / total) * 100);

    ringLabel.textContent = `${pct}%`;
    progressBar.style.width = `${pct}%`;
    const offset = RING_CIRCUMFERENCE - (RING_CIRCUMFERENCE * pct) / 100;
    ringFill.style.strokeDashoffset = String(offset);

    const missing = total - filled;
    missingEl.textContent = missing === 0
        ? "Your Patient History record is fully filled in."
        : `${missing} field${missing === 1 ? "" : "s"} left to fill in.`;
}

function renderChecklist() {
    checklistEl.innerHTML = availableConditions
        .map((name) => {
            const isSelected = selectedConditionNames.has(name);
            return `<button type="button" class="chip${isSelected ? " is-selected" : ""}" data-condition="${name}">${name}</button>`;
        })
        .join("");

    checklistEl.querySelectorAll(".chip").forEach((chip) => {
        chip.addEventListener("click", () => {
            const name = chip.dataset.condition;
            if (selectedConditionNames.has(name)) {
                selectedConditionNames.delete(name);
                chip.classList.remove("is-selected");
            } else {
                selectedConditionNames.add(name);
                chip.classList.add("is-selected");
            }
        });
    });
}

async function loadAll() {
    try {
        const [profileResp, availableResp, conditionsResp] = await Promise.all([
            authedFetch("/profile"),
            authedFetch("/conditions/available"),
            authedFetch("/conditions"),
        ]);

        if (profileResp.ok) {
            const profile = await profileResp.json();
            Object.keys(FIELD_IDS).forEach((key) => setFieldValue(key, profile[key]));
        }

        if (availableResp.ok) {
            availableConditions = await availableResp.json();
        }

        if (conditionsResp.ok) {
            currentConditions = await conditionsResp.json();
            selectedConditionNames = new Set(currentConditions.map((c) => c.condition_name));
        }

        renderChecklist();
        updateCompletionRing();
    } catch (err) {
        if (err.message === "Session expired") return;
        console.error("Failed to load Patient History:", err);
        toast("Couldn't load your Patient History. Please refresh.", "error");
    }
}

form.addEventListener("input", updateCompletionRing);

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    saveBtn.disabled = true;
    saveBtn.textContent = "Saving…";
    statusEl.textContent = "";

    try {
        const payload = {};
        Object.keys(FIELD_IDS).forEach((key) => {
            payload[key] = getFieldValue(key);
        });

        const saveResp = await authedFetch("/profile", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        if (!saveResp.ok) {
            throw new Error(`Server responded with ${saveResp.status}`);
        }

        // Diff the conditions checklist against what the server had.
        const originalNames = new Set(currentConditions.map((c) => c.condition_name));
        const toAdd = [...selectedConditionNames].filter((name) => !originalNames.has(name));
        const toRemove = currentConditions.filter((c) => !selectedConditionNames.has(c.condition_name));

        await Promise.all([
            ...toAdd.map((condition_name) =>
                authedFetch("/conditions", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ condition_name }),
                })
            ),
            ...toRemove.map((c) => authedFetch(`/conditions/${c.id}`, { method: "DELETE" })),
        ]);

        // Refresh currentConditions to the new server state for the next save.
        const conditionsResp = await authedFetch("/conditions");
        if (conditionsResp.ok) {
            currentConditions = await conditionsResp.json();
            selectedConditionNames = new Set(currentConditions.map((c) => c.condition_name));
        }

        updateCompletionRing();
        toast("Patient History saved.");
        statusEl.textContent = "Saved just now.";

        // The nav shows the patient's name — refresh it in case full_name changed.
        document.dispatchEvent(new CustomEvent("sehatai:profile-updated"));
    } catch (err) {
        if (err.message === "Session expired") return;
        console.error("Failed to save Patient History:", err);
        toast("Couldn't save your Patient History. Please try again.", "error");
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = "Save Record";
    }
});

loadAll();