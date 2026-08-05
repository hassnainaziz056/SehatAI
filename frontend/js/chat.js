/**
 * frontend/js/chat.js — Phase 18: Chat UI
 *
 * Auth guard: this page requires a token from login.js's localStorage
 * write. No token -> straight back to login.html, no chat UI is shown.
 *
 * On load: GET /chat/history (Authorization: Bearer <token>), render
 * every past message so a returning patient sees their conversation,
 * not a blank screen — same idea as register.js reading /conditions/available
 * before the form is usable.
 *
 * On send: POST /chat with the new message, append both the patient's
 * message and SehatAI's reply to the thread. The backend persists both
 * turns itself (see backend/routes/chat_routes.py) — this page never
 * writes chat_messages directly, it only reads/displays what the API
 * already saved.
 *
 * Same CORS note as register.js/login.js: serve this folder from a local
 * static server, don't open chat.html as a file:// URL.
 */

const API_BASE_URL = "http://127.0.0.1:8000";
const SEHATAI_TOKEN_KEY = "sehatai_token"; // must match login.js

const token = localStorage.getItem(SEHATAI_TOKEN_KEY);
if (!token) {
    // No session — this page has nothing to show without a logged-in
    // patient, so send them to log in first rather than rendering a
    // broken/empty chat.
    window.location.href = "login.html";
}

const chatLog = document.getElementById("chat-log");
const composer = document.getElementById("composer");
const messageInput = document.getElementById("message-input");
const sendBtn = document.getElementById("send-btn");
const logoutBtn = document.getElementById("logout-btn");

/** Shared fetch wrapper: attaches the bearer token, and on a 401 (expired
 * or invalid token) clears it and bounces back to login.html instead of
 * silently failing every request. */
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
        // Throw so callers don't try to keep using a response that's
        // about to navigate away.
        throw new Error("Session expired");
    }

    return response;
}

/** Append one message bubble to the log and scroll it into view. */
function appendMessage(role, content) {
    const bubble = document.createElement("div");
    bubble.className = `bubble bubble--${role === "assistant" ? "assistant" : "patient"}`;

    const text = document.createElement("p");
    text.className = "bubble-text";
    text.textContent = content;

    bubble.appendChild(text);
    chatLog.appendChild(bubble);
    chatLog.scrollTop = chatLog.scrollHeight;
}

// Roughly how fast characters appear — small enough to feel snappy on a
// long reply, still visibly "typed" rather than an instant flash. Punctuation
// gets a slightly longer pause so it reads with natural rhythm instead of a
// flat, mechanical scroll — the same idea as how a person actually types.
const TYPEWRITER_MS_PER_CHAR = 14;
const TYPEWRITER_PAUSE_CHARS = new Set([".", "!", "?", ","]);
const TYPEWRITER_PAUSE_MS = 120;

/**
 * Same as appendMessage, but for a freshly-arrived assistant reply only —
 * reveals the text one character at a time instead of all at once, so a
 * live response feels like it's being written in the moment rather than
 * pasted in. Deliberately NOT used for loadHistory(): replaying an entire
 * past conversation character-by-character on every page load would be
 * slow and would misleadingly suggest old replies are being generated
 * again right now, so history still renders instantly via appendMessage.
 *
 * Returns a Promise that resolves once typing finishes, so callers that
 * need to know when it's done (none currently do, but keeps this composable)
 * can await it.
 */
function appendMessageTyped(role, content) {
    const bubble = document.createElement("div");
    bubble.className = `bubble bubble--${role === "assistant" ? "assistant" : "patient"}`;

    const text = document.createElement("p");
    text.className = "bubble-text";
    bubble.appendChild(text);
    chatLog.appendChild(bubble);
    chatLog.scrollTop = chatLog.scrollHeight;

    return new Promise((resolve) => {
        let i = 0;
        function typeNextChar() {
            if (i >= content.length) {
                resolve();
                return;
            }
            const ch = content[i];
            text.textContent += ch;
            i += 1;
            // Keep the log scrolled to the bottom as text grows, same as
            // a real chat app — otherwise a long reply types "off screen".
            chatLog.scrollTop = chatLog.scrollHeight;
            const delay = TYPEWRITER_PAUSE_CHARS.has(ch)
                ? TYPEWRITER_PAUSE_MS
                : TYPEWRITER_MS_PER_CHAR;
            setTimeout(typeNextChar, delay);
        }
        typeNextChar();
    });
}

/** Load and render prior conversation on page load. */
async function loadHistory() {
    try {
        const response = await authedFetch("/chat/history");
        if (!response.ok) {
            throw new Error(`Server responded with ${response.status}`);
        }
        const history = await response.json();

        chatLog.innerHTML = "";
        if (history.length === 0) {
            // First-ever visit for this patient — nothing to render yet.
            // SehatAI's own greeting will appear once they send their
            // first message (see chatbot.py's greeting handling), so an
            // empty state here is expected, not an error.
            const empty = document.createElement("p");
            empty.className = "chat-empty";
            empty.textContent = "Say hello to start your first conversation with SehatAI.";
            chatLog.appendChild(empty);
            return;
        }
        history.forEach((entry) => appendMessage(entry.role, entry.content));
    } catch (err) {
        if (err.message === "Session expired") return; // already redirecting
        chatLog.innerHTML =
            '<p class="chat-error">Couldn\'t load your conversation. Is the API running?</p>';
        console.error("Failed to load /chat/history:", err);
    }
}

/** Grow the textarea with content, up to a sensible max height (handled by CSS). */
messageInput.addEventListener("input", () => {
    messageInput.style.height = "auto";
    messageInput.style.height = `${messageInput.scrollHeight}px`;
});

// Enter sends, Shift+Enter inserts a newline — standard chat-input behavior.
messageInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        composer.requestSubmit();
    }
});

composer.addEventListener("submit", async (event) => {
    event.preventDefault();

    const message = messageInput.value.trim();
    if (!message) return;

    // Optimistically show the patient's own message immediately, then
    // clear the input and disable sending until the reply (or an error)
    // comes back — mirrors register.js's submit-button disable pattern.
    appendMessage("patient", message);
    messageInput.value = "";
    messageInput.style.height = "auto";
    sendBtn.disabled = true;
    messageInput.disabled = true;

    const thinking = document.createElement("p");
    thinking.className = "chat-thinking";
    thinking.textContent = "SehatAI is thinking…";
    chatLog.appendChild(thinking);
    chatLog.scrollTop = chatLog.scrollHeight;

    try {
        const response = await authedFetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message }),
        });

        thinking.remove();

        if (response.ok) {
            const data = await response.json();
            await appendMessageTyped("assistant", data.reply);
        } else if (response.status === 422) {
            await appendMessageTyped("assistant", "That message couldn't be sent — please try rephrasing it.");
        } else {
            await appendMessageTyped("assistant", "Something went wrong on our end. Please try again.");
        }
    } catch (err) {
        thinking.remove();
        if (err.message === "Session expired") return; // already redirecting
        await appendMessageTyped(
            "assistant",
            "Couldn't reach the server. Please check your connection and try again."
        );
        console.error("Chat request failed:", err);
    } finally {
        sendBtn.disabled = false;
        messageInput.disabled = false;
        messageInput.focus();
    }
});

logoutBtn.addEventListener("click", () => {
    localStorage.removeItem(SEHATAI_TOKEN_KEY);
    window.location.href = "login.html";
});

loadHistory();