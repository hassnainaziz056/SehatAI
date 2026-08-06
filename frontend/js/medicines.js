/**
 * frontend/js/medicines.js — UI/UX redesign (v2): the dedicated Medicines
 * page. Talks to backend/routes/medication_routes.py (list/add/edit/
 * delete/mark-taken/dose-logs) plus GET /dashboard for today's schedule
 * (same aggregate the Dashboard already uses, so "today's status" never
 * disagrees between the two pages).
 */

const { authedFetch, toast } = window.SehatAI;

const SLOT_ICONS = { morning: "🌅", afternoon: "☀️", night: "🌙" };
const SLOT_LABELS = { morning: "Morning", afternoon: "Afternoon", night: "Night" };

let allMedicines = [];
let todaySchedule = [];

// ---------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------
document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
        document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("is-active"));
        btn.classList.add("is-active");
        const tab = btn.dataset.tab;
        document.querySelectorAll("[data-tab-panel]").forEach((panel) => {
            panel.style.display = panel.dataset.tabPanel === tab ? "block" : "none";
        });
        if (tab === "history") loadDoseHistory();
    });
});

// ---------------------------------------------------------------------
// Stat row
// ---------------------------------------------------------------------
function renderStats() {
    const activeCount = allMedicines.filter((m) => m.active).length;
    const takenToday = todaySchedule.filter((s) => s.status === "taken").length;
    const pendingToday = todaySchedule.filter((s) => s.status === "pending").length;
    const totalToday = todaySchedule.length;

    const stats = [
        { label: "Active Medicines", value: activeCount },
        { label: "Doses Today", value: totalToday },
        { label: "Taken Today", value: takenToday },
        { label: "Pending Now", value: pendingToday },
    ];

    document.getElementById("med-stat-row").innerHTML = stats
        .map((stat) => `<div class="med-stat"><span>${stat.label}</span><strong>${stat.value}</strong></div>`)
        .join("");
}

// ---------------------------------------------------------------------
// Today's schedule tab
// ---------------------------------------------------------------------
function renderTodaySchedule() {
    const list = document.getElementById("today-schedule-list");
    if (todaySchedule.length === 0) {
        list.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">💊</div>
        <h3>No medicines scheduled today</h3>
        <p>Add a medicine below to start tracking your daily schedule.</p>
      </div>`;
        return;
    }

    list.innerHTML = todaySchedule
        .map((slot) => {
            const taken = slot.status === "taken";
            return `
        <div class="schedule-row${taken ? " is-taken" : ""}">
          <div class="schedule-row-icon">${taken ? "✓" : SLOT_ICONS[slot.slot] || "💊"}</div>
          <div class="schedule-row-body">
            <strong>${slot.medication_name}</strong>
            <span>${slot.dosage || ""} · ${slot.slot_time_label}</span>
          </div>
          ${taken
                    ? '<span class="badge badge--success">Taken</span>'
                    : `<button type="button" class="btn btn--sm btn--primary mark-taken-btn" data-med-id="${slot.medication_id}" data-slot="${slot.slot}">Mark taken</button>`
                }
        </div>`;
        })
        .join("");

    list.querySelectorAll(".mark-taken-btn").forEach((btn) => {
        btn.addEventListener("click", () => markTaken(btn.dataset.medId, btn.dataset.slot, btn));
    });
}

async function markTaken(medicationId, slot, btn) {
    btn.disabled = true;
    btn.textContent = "Saving…";
    try {
        const response = await authedFetch(`/medications/${medicationId}/taken`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ slot }),
        });
        if (!response.ok) throw new Error(`Server responded with ${response.status}`);
        toast("Marked as taken.");
        await loadDashboardSchedule();
        renderTodaySchedule();
        renderStats();
    } catch (err) {
        if (err.message === "Session expired") return;
        toast("Couldn't save that. Please try again.", "error");
        console.error("Mark taken failed:", err);
        btn.disabled = false;
        btn.textContent = "Mark taken";
    }
}

// ---------------------------------------------------------------------
// All medicines tab
// ---------------------------------------------------------------------
function renderAllMedicines() {
    const list = document.getElementById("all-medicines-list");
    if (allMedicines.length === 0) {
        list.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">💊</div>
        <h3>No medicines yet</h3>
        <p>Add your first medicine to start building your schedule.</p>
      </div>`;
        return;
    }

    list.innerHTML = allMedicines
        .map((med) => {
            const slots = ["morning", "afternoon", "night"].filter((s) => med[s]).map((s) => SLOT_LABELS[s]);
            return `
      <div class="med-card">
        <div class="med-card-icon">💊</div>
        <div class="med-card-body">
          <strong>${med.name} ${!med.active ? '<span class="badge badge--muted">Past</span>' : ""}</strong>
          <div class="med-card-meta">
            ${med.dosage ? `<span>${med.dosage}</span>` : ""}
            ${med.frequency ? `<span>· ${med.frequency}</span>` : ""}
            ${slots.length ? `<span>· ${slots.join(", ")}</span>` : ""}
            ${med.start_date ? `<span>· Since ${med.start_date}</span>` : ""}
          </div>
        </div>
        <div class="med-card-actions">
          <button type="button" class="btn btn--secondary btn--sm edit-med-btn" data-id="${med.id}">Edit</button>
          <button type="button" class="btn btn--danger btn--sm delete-med-btn" data-id="${med.id}">Delete</button>
        </div>
      </div>`;
        })
        .join("");

    list.querySelectorAll(".edit-med-btn").forEach((btn) => {
        btn.addEventListener("click", () => openModal(allMedicines.find((m) => m.id === Number(btn.dataset.id))));
    });
    list.querySelectorAll(".delete-med-btn").forEach((btn) => {
        btn.addEventListener("click", () => deleteMedicine(btn.dataset.id));
    });
}

async function deleteMedicine(id) {
    if (!confirm("Remove this medicine from your list?")) return;
    try {
        const response = await authedFetch(`/medications/${id}`, { method: "DELETE" });
        if (!response.ok && response.status !== 204) throw new Error(`Server responded with ${response.status}`);
        toast("Medicine removed.");
        await loadAll();
    } catch (err) {
        if (err.message === "Session expired") return;
        toast("Couldn't remove that medicine.", "error");
        console.error("Delete medicine failed:", err);
    }
}

// ---------------------------------------------------------------------
// Dose history tab
// ---------------------------------------------------------------------
async function loadDoseHistory() {
    const list = document.getElementById("dose-history-list");
    list.innerHTML = '<div class="skeleton skeleton-block" style="margin-bottom:10px;"></div>';
    try {
        const response = await authedFetch("/medications/dose-logs?days=14");
        if (!response.ok) throw new Error(`Server responded with ${response.status}`);
        const logs = await response.json();

        if (logs.length === 0) {
            list.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">📅</div>
          <h3>No dose history yet</h3>
          <p>Doses you mark as taken will be listed here for the last 14 days.</p>
        </div>`;
            return;
        }

        list.innerHTML = logs
            .map(
                (log) => `
        <div class="summary-card">
          <div class="summary-card-icon">${SLOT_ICONS[log.slot] || "💊"}</div>
          <div class="summary-card-body">
            <strong>${log.medication_name} — ${SLOT_LABELS[log.slot] || log.slot}</strong>
            <span>${log.dose_date} · marked taken ${window.SehatAI.relativeTime(log.taken_at)}</span>
          </div>
        </div>`
            )
            .join("");
    } catch (err) {
        if (err.message === "Session expired") return;
        list.innerHTML = '<p style="color: var(--color-danger); font-size:0.88rem;">Couldn\'t load dose history.</p>';
        console.error("Failed to load dose history:", err);
    }
}

// ---------------------------------------------------------------------
// Add/Edit modal
// ---------------------------------------------------------------------
const modalOverlay = document.getElementById("med-modal-overlay");
const medForm = document.getElementById("med-form");

function openModal(medicine) {
    document.getElementById("med-modal-title").textContent = medicine ? "Edit Medicine" : "Add Medicine";
    document.getElementById("med-id").value = medicine ? medicine.id : "";
    document.getElementById("med-name").value = medicine ? medicine.name : "";
    document.getElementById("med-dosage").value = medicine ? medicine.dosage || "" : "";
    document.getElementById("med-frequency").value = medicine ? medicine.frequency || "" : "";
    document.getElementById("med-start-date").value = medicine ? medicine.start_date || "" : "";

    document.querySelectorAll(".slot-toggle-row .chip").forEach((chip) => {
        const slot = chip.dataset.slot;
        chip.classList.toggle("is-selected", medicine ? !!medicine[slot] : false);
    });

    modalOverlay.classList.add("is-open");
}

function closeModal() {
    modalOverlay.classList.remove("is-open");
    medForm.reset();
}

document.getElementById("add-med-btn").addEventListener("click", () => openModal(null));
document.getElementById("med-modal-close").addEventListener("click", closeModal);
document.getElementById("med-cancel-btn").addEventListener("click", closeModal);
modalOverlay.addEventListener("click", (event) => {
    if (event.target === modalOverlay) closeModal();
});

document.querySelectorAll(".slot-toggle-row .chip").forEach((chip) => {
    chip.addEventListener("click", () => chip.classList.toggle("is-selected"));
});

medForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const id = document.getElementById("med-id").value;
    const payload = {
        name: document.getElementById("med-name").value.trim(),
        dosage: document.getElementById("med-dosage").value.trim() || null,
        frequency: document.getElementById("med-frequency").value.trim() || null,
        start_date: document.getElementById("med-start-date").value || null,
        morning: document.querySelector('.chip[data-slot="morning"]').classList.contains("is-selected"),
        afternoon: document.querySelector('.chip[data-slot="afternoon"]').classList.contains("is-selected"),
        night: document.querySelector('.chip[data-slot="night"]').classList.contains("is-selected"),
    };

    const saveBtn = document.getElementById("med-save-btn");
    saveBtn.disabled = true;
    saveBtn.textContent = "Saving…";

    try {
        const response = await authedFetch(id ? `/medications/${id}` : "/medications", {
            method: id ? "PUT" : "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        if (!response.ok) throw new Error(`Server responded with ${response.status}`);
        toast(id ? "Medicine updated." : "Medicine added.");
        closeModal();
        await loadAll();
    } catch (err) {
        if (err.message === "Session expired") return;
        toast("Couldn't save that medicine. Please check the fields and try again.", "error");
        console.error("Save medicine failed:", err);
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = "Save Medicine";
    }
});

// ---------------------------------------------------------------------
// Load
// ---------------------------------------------------------------------
async function loadDashboardSchedule() {
    const response = await authedFetch("/dashboard");
    if (!response.ok) throw new Error(`Server responded with ${response.status}`);
    const dashboard = await response.json();
    todaySchedule = dashboard.medicine_schedule_today;
}

async function loadAll() {
    try {
        const [medsResponse] = await Promise.all([authedFetch("/medications"), loadDashboardSchedule()]);
        if (!medsResponse.ok) throw new Error(`Server responded with ${medsResponse.status}`);
        allMedicines = await medsResponse.json();

        renderStats();
        renderTodaySchedule();
        renderAllMedicines();
    } catch (err) {
        if (err.message === "Session expired") return;
        toast("Couldn't load your medicines. Please refresh.", "error");
        console.error("Failed to load medicines:", err);
    }
}

loadAll();