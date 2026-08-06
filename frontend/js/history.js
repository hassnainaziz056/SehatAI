/**
 * frontend/js/history.js — Health History & Timeline Loader
 */
const API_BASE_URL = (window.location.port === "8000") ? window.location.origin : "http://127.0.0.1:8000";
const SEHATAI_TOKEN_KEY = "sehatai_token";

const token = localStorage.getItem(SEHATAI_TOKEN_KEY);
if (!token) {
    window.location.href = "login.html";
}

renderPortalLayout();

async function loadHistoryData() {
    try {
        const [dashResp, condResp, chatResp] = await Promise.all([
            fetch(`${API_BASE_URL}/dashboard`, { headers: { "Authorization": `Bearer ${token}` } }),
            fetch(`${API_BASE_URL}/conditions`, { headers: { "Authorization": `Bearer ${token}` } }),
            fetch(`${API_BASE_URL}/chat/history`, { headers: { "Authorization": `Bearer ${token}` } }),
        ]);

        if (dashResp.status === 401 || condResp.status === 401) {
            handleLogout();
            return;
        }

        if (dashResp.ok) {
            const dashData = await dashResp.json();
            renderTimeline(dashData.health_timeline);
            renderConsultSummaries(dashData.recent_conversations);
        }

        if (condResp.ok) {
            const conds = await condResp.json();
            renderConditions(conds);
        }

    } catch (err) {
        console.error("Error loading history:", err);
    }
}

function renderTimeline(events) {
    const list = document.getElementById("full-history-timeline");

    if (!events || events.length === 0) {
        list.innerHTML = `<p style="color: var(--color-text-muted); font-size: 0.88rem;">No events recorded in your health log yet.</p>`;
        return;
    }

    list.innerHTML = events.map(evt => {
        const dateStr = new Date(evt.occurred_at).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
        let icon = '📌';
        if (evt.event_type === 'condition') icon = '🩺';
        if (evt.event_type === 'medication') icon = '💊';

        return `
            <div class="timeline-item">
                <div class="timeline-icon">${icon}</div>
                <div class="timeline-content">
                    <div class="timeline-header">
                        <span class="timeline-title">${evt.title}</span>
                        <span class="timeline-time">${dateStr}</span>
                    </div>
                    ${evt.detail ? `<div class="timeline-detail">${evt.detail}</div>` : ''}
                </div>
            </div>
        `;
    }).join("");
}

function renderConditions(conds) {
    const box = document.getElementById("history-conditions-list");
    if (!conds || conds.length === 0) {
        box.innerHTML = `<span style="color: var(--color-text-muted); font-size: 0.85rem;">No conditions registered.</span>`;
        return;
    }

    box.innerHTML = conds.map(c => `
        <span class="badge badge-primary" style="padding: 6px 12px; font-size: 0.85rem;">
            🩺 ${c.condition_name}
        </span>
    `).join("");
}

function renderConsultSummaries(chats) {
    const list = document.getElementById("history-chats-list");
    if (!chats || chats.length === 0) {
        list.innerHTML = `<p style="color: var(--color-text-muted); font-size: 0.85rem;">No past consultations found.</p>`;
        return;
    }

    list.innerHTML = chats.map(chat => {
        const timeStr = new Date(chat.last_message_at).toLocaleDateString();
        return `
            <div style="background: var(--color-surface-raised); border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: 12px; cursor: pointer;" onclick="window.location.href='chat.html'">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <strong style="font-size: 0.86rem; color: var(--color-text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 170px;">"${chat.first_message}"</strong>
                    <span style="font-size: 0.74rem; color: var(--color-text-subtle);">${timeStr}</span>
                </div>
            </div>
        `;
    }).join("");
}

loadHistoryData();
