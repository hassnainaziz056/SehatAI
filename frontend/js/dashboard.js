/**
 * frontend/js/dashboard.js — UI/UX redesign (v2): the Home Dashboard.
 *
 * The Dashboard is now the app's landing page after login (see login.js).
 * Everything here is read from a single GET /dashboard call — the same
 * one nav.js already makes to populate the top nav's name/notifications,
 * so this listens for nav.js's "sehatai:dashboard-ready" event instead
 * of fetching a second time.
 */

const SLOT_ICONS = { morning: "🌅", afternoon: "☀️", night: "🌙" };
const EVENT_ICONS = { condition: "🩺", medication: "💊", chat: "💬" };

function timeOfDayGreeting() {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 17) return "Good afternoon";
    return "Good evening";
}

function renderGreeting(name) {
    const firstName = (name || "").split(" ")[0];
    document.getElementById("greeting-text").innerHTML =
        `<span class="greeting-emoji">👋</span> ${timeOfDayGreeting()}${firstName ? `, ${firstName}` : ""}`;
    document.getElementById("greeting-subtext").textContent = "How are you feeling today?";
}

function renderHealthSummary(summary) {
    const grid = document.getElementById("health-summary-grid");
    const tiles = [
        { label: "Age", value: summary.age != null ? summary.age : "—" },
        { label: "Gender", value: summary.gender || "—" },
        { label: "Blood Group", value: summary.blood_group || "—" },
        { label: "Allergies", value: summary.allergies || "None on file" },
    ];
    grid.innerHTML = tiles
        .map((tile) => `<div class="stat-tile"><span>${tile.label}</span><strong>${tile.value}</strong></div>`)
        .join("");

    const chipRow = document.getElementById("conditions-chip-row");
    if (summary.conditions && summary.conditions.length > 0) {
        chipRow.innerHTML = summary.conditions
            .map((c) => `<span class="chip chip--static">${c}</span>`)
            .join("");
    } else {
        chipRow.innerHTML = '<span style="font-size:0.83rem; color: var(--color-text-muted);">No conditions on file yet.</span>';
    }
}

function renderSchedule(schedule) {
    const list = document.getElementById("schedule-list");
    if (!schedule || schedule.length === 0) {
        list.innerHTML = `
      <div class="empty-state" style="padding: 24px 8px;">
        <div class="empty-state-icon">💊</div>
        <h3 style="font-size:0.92rem;">No medicines scheduled today</h3>
        <p style="font-size:0.82rem;"><a href="medicines.html" class="inline-link">Add a medicine</a> to start tracking your daily schedule.</p>
      </div>`;
        setRing(0, 0);
        return;
    }

    list.innerHTML = schedule
        .map((slot) => {
            const taken = slot.status === "taken";
            return `
        <div class="schedule-row${taken ? " is-taken" : ""}">
          <div class="schedule-row-icon">${taken ? "✓" : SLOT_ICONS[slot.slot] || "💊"}</div>
          <div class="schedule-row-body">
            <strong>${slot.medication_name}</strong>
            <span>${slot.dosage || ""}</span>
          </div>
          <span class="badge badge--${taken ? "success" : slot.status === "pending" ? "warning" : "muted"}">${slot.status}</span>
          <span class="schedule-row-time">${slot.slot_time_label}</span>
        </div>`;
        })
        .join("");

    const takenCount = schedule.filter((s) => s.status === "taken").length;
    setRing(takenCount, schedule.length);
}

function setRing(taken, total) {
    const circumference = 2 * Math.PI * 36;
    const fraction = total > 0 ? taken / total : 0;
    const fill = document.getElementById("med-ring-fill");
    fill.setAttribute("stroke-dasharray", circumference.toFixed(1));
    fill.setAttribute("stroke-dashoffset", (circumference * (1 - fraction)).toFixed(1));
    document.getElementById("med-ring-label").textContent = `${taken}/${total}`;
}

function renderTimeline(events) {
    const list = document.getElementById("timeline-list");
    if (!events || events.length === 0) {
        list.innerHTML = `
      <div class="empty-state" style="padding: 20px 8px;">
        <div class="empty-state-icon">📋</div>
        <h3 style="font-size:0.92rem;">No events yet</h3>
        <p style="font-size:0.82rem;">Conditions and medicines you add will show up here.</p>
      </div>`;
        return;
    }
    list.innerHTML = events
        .map(
            (event) => `
      <div class="timeline-item">
        <div class="timeline-dot">${EVENT_ICONS[event.event_type] || "•"}</div>
        <div class="timeline-body">
          <strong>${event.title}</strong>
          <span>${window.SehatAI.relativeTime(event.occurred_at)}${event.detail ? ` · ${event.detail}` : ""}</span>
        </div>
      </div>`
        )
        .join("");
}

function renderConversations(conversations) {
    const list = document.getElementById("conversations-list");
    if (!conversations || conversations.length === 0) {
        list.innerHTML = `
      <div class="empty-state" style="padding: 24px 8px;">
        <div class="empty-state-icon">💬</div>
        <h3 style="font-size:0.92rem;">No conversations yet</h3>
        <p style="font-size:0.82rem;"><a href="chat.html" class="inline-link">Talk to SehatAI</a> to start your first one.</p>
      </div>`;
        return;
    }
    list.innerHTML = conversations
        .map(
            (convo) => `
      <div class="convo-card">
        <div class="convo-card-text">
          <p>${convo.first_message}</p>
          <span>${window.SehatAI.relativeTime(convo.last_message_at)} · ${convo.message_count} message${convo.message_count === 1 ? "" : "s"}</span>
        </div>
        <a href="chat.html" class="btn btn--ghost btn--sm">Open</a>
      </div>`
        )
        .join("");
}

function render(dashboard) {
    renderGreeting(dashboard.health_summary.name);
    renderHealthSummary(dashboard.health_summary);
    renderSchedule(dashboard.medicine_schedule_today);
    renderTimeline(dashboard.health_timeline);
    renderConversations(dashboard.recent_conversations);

    document.getElementById("completion-nudge").style.display = dashboard.profile_completed ? "none" : "block";
}

// nav.js already fetches GET /dashboard once (to populate the top nav) —
// reuse that instead of a second request. If nav.js already finished by
// the time this runs, use its cache directly; otherwise wait for its event.
if (window.SehatAI && window.SehatAI.dashboardCache) {
    render(window.SehatAI.dashboardCache);
} else {
    document.addEventListener("sehatai:dashboard-ready", (event) => render(event.detail));
}