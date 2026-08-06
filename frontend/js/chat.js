/**
 * frontend/js/chat.js — Phase 18, completely redesigned (UI/UX redesign v2).
 *
 * Two things happen before any chat UI renders:
 *   1. GET /profile/status — if profile_completed is false, the profile
 *      gate is shown instead of the chat panel/composer, and no chat
 *      request is ever possible from this page (the composer form isn't
 *      even shown — see chat.html). This is a hard gate, not a
 *      dismissible banner: there is no way to bypass it from this page.
 *   2. GET /chat/history — once the gate passes, load and render the
 *      existing conversation.
 *
 * Sending a message now also reads is_emergency/sources off the response
 * (backend/schemas.py's ChatResponse, extended for this redesign) to
 * decide whether to render the full-width emergency banner and the
 * "Sources" row, instead of guessing from the reply text.
 */

const { authedFetch, toast } = window.SehatAI;

const gatePanel = document.getElementById("chat-gate-panel");
const realPanel = document.getElementById("chat-real-panel");
const composerForm = document.getElementById("composer");
const chatLog = document.getElementById("chat-log");
const messageInput = document.getElementById("message-input");
const sendBtn = document.getElementById("send-btn");

const GENERIC_FOLLOWUPS = [
    "What foods should I avoid?",
    "Is this something I should see a doctor for?",
    "How long should this usually last?",
];

function buildAvatar(role) {
    return role === "assistant" ? "🩺" : "🙂";
}

function formatTime(dateLike) {
    const date = dateLike ? new Date(dateLike) : new Date();
    return date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

function scrollToBottom() {
    chatLog.scrollTop = chatLog.scrollHeight;
}

/** Renders one full message row (avatar + bubble + timestamp), optionally
 * with a sources row or an emergency banner. Used for both history
 * replay and new messages. */
function appendMessage(role, content, { createdAt, sources, isEmergency } = {}) {
    const row = document.createElement("div");
    row.className = `chat-row chat-row--${role === "assistant" ? "assistant" : "patient"}`;

    const avatar = document.createElement("div");
    avatar.className = "chat-row-avatar";
    avatar.textContent = buildAvatar(role);

    const col = document.createElement("div");
    col.className = "chat-bubble-col";

    if (isEmergency) {
        const banner = document.createElement("div");
        banner.className = "emergency-banner";
        banner.innerHTML = '<span class="emergency-banner-icon">🚨</span><div><strong>This may be a medical emergency</strong><p></p></div>';
        banner.querySelector("p").textContent = content;
        col.appendChild(banner);
    } else {
        const bubble = document.createElement("div");
        bubble.className = "bubble";
        const text = document.createElement("p");
        text.className = "bubble-text";
        text.textContent = content;
        bubble.appendChild(text);
        col.appendChild(bubble);
    }

    const timestamp = document.createElement("div");
    timestamp.className = "chat-timestamp";
    timestamp.textContent = formatTime(createdAt);
    col.appendChild(timestamp);

    if (sources && sources.length > 0) {
        const details = document.createElement("details");
        details.className = "chat-sources";
        const summary = document.createElement("summary");
        summary.textContent = `Sources (${sources.length})`;
        details.appendChild(summary);
        const list = document.createElement("div");
        list.className = "chat-sources-list";
        sources.forEach((source) => {
            const chip = document.createElement("span");
            chip.className = "source-chip";
            chip.textContent = `${source.topic} · ${confidenceLabel(source.distance)}`;
            list.appendChild(chip);
        });
        details.appendChild(list);
        col.appendChild(details);
    }

    row.appendChild(avatar);
    row.appendChild(col);
    chatLog.appendChild(row);
    scrollToBottom();
    return row;
}

function confidenceLabel(distance) {
    if (distance <= 0.6) return "strong match";
    if (distance <= 0.85) return "fair match";
    return "loose match";
}

function appendSuggestedFollowups() {
    const row = document.createElement("div");
    row.className = "suggested-row";
    GENERIC_FOLLOWUPS.forEach((question) => {
        const pill = document.createElement("button");
        pill.type = "button";
        pill.className = "suggested-pill";
        pill.textContent = question;
        pill.addEventListener("click", () => {
            messageInput.value = question;
            composerForm.requestSubmit();
        });
        row.appendChild(pill);
    });
    chatLog.appendChild(row);
    scrollToBottom();
    return row;
}

function showTyping() {
    const row = document.createElement("div");
    row.className = "chat-row chat-row--assistant";
    row.id = "typing-row";
    row.innerHTML =
        '<div class="chat-row-avatar">🩺</div>' +
        '<div class="chat-bubble-col"><div class="bubble typing-row">' +
        '<span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>' +
        "</div></div>";
    chatLog.appendChild(row);
    scrollToBottom();
}

function hideTyping() {
    document.getElementById("typing-row")?.remove();
}

async function loadHistory() {
    try {
        const response = await authedFetch("/chat/history");
        if (!response.ok) throw new Error(`Server responded with ${response.status}`);
        const history = await response.json();

        chatLog.innerHTML = "";
        if (history.length === 0) {
            chatLog.innerHTML =
                '<p style="text-align:center; color: var(--color-text-muted); margin:auto 0; font-size:0.9rem;">Say hello to start your first conversation with SehatAI.</p>';
            return;
        }
        history.forEach((entry) => appendMessage(entry.role, entry.content, { createdAt: entry.created_at }));
    } catch (err) {
        if (err.message === "Session expired") return;
        chatLog.innerHTML =
            '<p style="text-align:center; color: var(--color-danger); margin:auto 0; font-size:0.9rem;">Couldn\'t load your conversation. Is the API running?</p>';
        console.error("Failed to load /chat/history:", err);
    }
}

messageInput?.addEventListener("input", () => {
    messageInput.style.height = "auto";
    messageInput.style.height = `${messageInput.scrollHeight}px`;
});

messageInput?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        composerForm.requestSubmit();
    }
});

composerForm?.addEventListener("submit", async (event) => {
    event.preventDefault();

    const message = messageInput.value.trim();
    if (!message) return;

    document.querySelectorAll(".suggested-row").forEach((el) => el.remove());
    appendMessage("patient", message);
    messageInput.value = "";
    messageInput.style.height = "auto";
    sendBtn.disabled = true;
    messageInput.disabled = true;
    showTyping();

    try {
        const response = await authedFetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message }),
        });

        hideTyping();

        if (response.ok) {
            const data = await response.json();
            appendMessage("assistant", data.reply, {
                sources: data.sources,
                isEmergency: data.is_emergency,
            });
            if (!data.is_emergency) appendSuggestedFollowups();
        } else if (response.status === 422) {
            appendMessage("assistant", "That message couldn't be sent — please try rephrasing it.");
        } else {
            appendMessage("assistant", "Something went wrong on our end. Please try again.");
        }
    } catch (err) {
        hideTyping();
        if (err.message === "Session expired") return;
        appendMessage("assistant", "Couldn't reach the server. Please check your connection and try again.");
        console.error("Chat request failed:", err);
    } finally {
        sendBtn.disabled = false;
        messageInput.disabled = false;
        messageInput.focus();
    }
});

async function init() {
    try {
        const response = await authedFetch("/profile/status");
        if (!response.ok) throw new Error(`Server responded with ${response.status}`);
        const status = await response.json();

        if (!status.profile_completed) {
            gatePanel.style.display = "flex";
            realPanel.style.display = "none";
            composerForm.style.display = "none";
            return;
        }

        gatePanel.style.display = "none";
        realPanel.style.display = "flex";
        composerForm.style.display = "block";
        await loadHistory();
    } catch (err) {
        if (err.message === "Session expired") return;
        toast("Couldn't verify your profile status. Please refresh.", "error");
        console.error("Failed to load /profile/status:", err);
    }
}

init();