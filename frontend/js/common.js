/**
 * frontend/js/common.js — UI/UX redesign (v2)
 *
 * Shared utilities every logged-in page (dashboard, chat, medicines,
 * history, profile) loads before its own page script. Centralizing this
 * here means the API base URL, the localStorage token key, and the
 * 401-handling fetch wrapper only exist in one place — every page script
 * that used to duplicate this (chat.js, profile.js, ...) now just calls
 * window.SehatAI.authedFetch(...) instead.
 *
 * Also runs the auth guard on load: no token -> straight to login.html,
 * same behavior every page already had individually.
 */

(function () {
    const API_BASE_URL = "http://127.0.0.1:8000";
    const TOKEN_KEY = "sehatai_token";

    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
        window.location.href = "login.html";
    }

    /** Fetch wrapper: attaches the bearer token, and on a 401 (expired or
     * invalid token) clears it and bounces to login.html instead of
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
            localStorage.removeItem(TOKEN_KEY);
            window.location.href = "login.html";
            throw new Error("Session expired");
        }

        return response;
    }

    function logout() {
        localStorage.removeItem(TOKEN_KEY);
        window.location.href = "login.html";
    }

    /** Two-letter initials for the avatar circle — falls back to "?" for
     * an account that hasn't set a name yet (shouldn't normally happen
     * once the profile gate is in place, but keeps the avatar from
     * rendering blank). */
    function initials(name) {
        if (!name) return "?";
        const parts = name.trim().split(/\s+/).filter(Boolean);
        if (parts.length === 0) return "?";
        if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
        return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }

    /** Small toast — used across pages for save confirmations/errors
     * instead of each page building its own status banner. */
    function toast(message, kind = "success") {
        let el = document.getElementById("sehatai-toast");
        if (!el) {
            el = document.createElement("div");
            el.id = "sehatai-toast";
            el.className = "toast";
            document.body.appendChild(el);
        }
        el.textContent = message;
        el.className = `toast is-visible${kind === "error" ? " toast--error" : ""}`;
        clearTimeout(el._hideTimer);
        el._hideTimer = setTimeout(() => {
            el.className = "toast";
        }, 3200);
    }

    /** Relative time label ("2 days ago", "Just now") for conversation/
     * timeline cards — small shared formatter so dashboard.js, chat.js,
     * medicines.js and history.js don't each reimplement it slightly
     * differently. */
    function relativeTime(isoString) {
        const then = new Date(isoString);
        const diffMs = Date.now() - then.getTime();
        const diffMin = Math.round(diffMs / 60000);
        if (diffMin < 1) return "Just now";
        if (diffMin < 60) return `${diffMin} min ago`;
        const diffHr = Math.round(diffMin / 60);
        if (diffHr < 24) return `${diffHr} hr${diffHr === 1 ? "" : "s"} ago`;
        const diffDay = Math.round(diffHr / 24);
        if (diffDay < 7) return `${diffDay} day${diffDay === 1 ? "" : "s"} ago`;
        return then.toLocaleDateString(undefined, { month: "short", day: "numeric" });
    }

    window.SehatAI = { API_BASE_URL, TOKEN_KEY, token, authedFetch, logout, initials, toast, relativeTime };
})();