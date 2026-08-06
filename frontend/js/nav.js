/**
 * frontend/js/nav.js — UI/UX redesign (v2)
 *
 * Injects the sticky top navigation bar (and, on mobile, the bottom tab
 * bar) into every logged-in page. One component, reused everywhere,
 * instead of duplicating nav markup in dashboard.html, chat.html,
 * medicines.html, history.html, and profile.html — each of those pages
 * just needs `<div id="app-nav"></div>` + `<div id="app-bottomnav"></div>`
 * and this script.
 *
 * Also does the one piece of shared data-fetching every page's nav
 * needs: the patient's name (for the avatar/greeting) and a lightweight
 * "how many medicine doses are pending right now" count, reused as the
 * notification bell's badge/content — both come from the existing
 * GET /dashboard endpoint, so this adds no new network surface.
 *
 * Depends on common.js being loaded first (window.SehatAI.authedFetch).
 */

(function () {
    const NAV_ITEMS = [
        { href: "dashboard.html", label: "Home", icon: "home" },
        { href: "chat.html", label: "AI Doctor", icon: "chat" },
        { href: "medicines.html", label: "Medicines", icon: "pill" },
        { href: "history.html", label: "Health History", icon: "history" },
        { href: "visit-summaries.html", label: "Summaries", icon: "file" },
    ];

    const ICONS = {
        home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V20a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1V9.5"/>',
        chat: '<path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5c-1.35 0-2.62-.32-3.75-.9L3 21l1.9-5.7A8.5 8.5 0 1 1 21 11.5Z"/>',
        pill: '<rect x="3" y="10.5" width="18" height="7" rx="3.5" transform="rotate(-45 12 14)"/><path d="m8.5 9.5 6 6"/>',
        history: '<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/><path d="M12 7v5l3.5 2"/>',
        file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h6"/>',
        bell: '<path d="M6 8a6 6 0 1 1 12 0c0 4 1.5 5.5 1.5 5.5H4.5S6 12 6 8Z"/><path d="M10 19a2 2 0 0 0 4 0"/>',
        chevron: '<path d="m6 9 6 6 6-6"/>',
        user: '<circle cx="12" cy="8" r="3.5"/><path d="M5 20c1.2-3.6 4-5.5 7-5.5s5.8 1.9 7 5.5"/>',
        gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9c.4.3.9.5 1.5.5H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z"/>',
        logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/>',
    };

    function svg(name, size = 18) {
        return `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ""}</svg>`;
    }

    function currentPage() {
        const path = window.location.pathname.split("/").pop();
        return path || "dashboard.html";
    }

    function buildTopNav(name, pendingCount) {
        const active = currentPage();
        const links = NAV_ITEMS.map(
            (item) => `<a class="topnav-link${item.href === active ? " is-active" : ""}" href="${item.href}">${svg(item.icon, 16)}<span>${item.label}</span></a>`
        ).join("");

        return `
      <header class="topnav">
        <div class="topnav-inner">
          <a class="topnav-brand" href="dashboard.html">
            <span class="topnav-brand-mark">🏥</span>
            <span class="topnav-brand-text">SehatAI</span>
          </a>
          <nav class="topnav-links">${links}</nav>
          <div class="topnav-actions">
            <div class="dropdown-anchor">
              <button type="button" class="icon-btn" id="notif-btn" aria-label="Notifications">
                ${svg("bell")}
                ${pendingCount > 0 ? '<span class="notif-dot"></span>' : ""}
              </button>
              <div class="dropdown notif-panel" id="notif-dropdown"></div>
            </div>
            <div class="dropdown-anchor">
              <button type="button" class="user-menu-btn" id="user-menu-btn">
                <span class="avatar">${window.SehatAI.initials(name)}</span>
                <span class="user-menu-name">${name || "Patient"}</span>
                ${svg("chevron", 14)}
              </button>
              <div class="dropdown" id="user-dropdown">
                <div class="dropdown-header">
                  <strong>${name || "Patient"}</strong>
                  <span>Manage your account</span>
                </div>
                <a class="dropdown-item" href="profile.html">${svg("user", 16)} Profile</a>
                <a class="dropdown-item" href="profile.html#settings">${svg("gear", 16)} Settings</a>
                <div class="dropdown-divider"></div>
                <button type="button" class="dropdown-item dropdown-item--danger" id="nav-logout-btn">${svg("logout", 16)} Log out</button>
              </div>
            </div>
          </div>
        </div>
      </header>`;
    }

    function buildBottomNav() {
        const active = currentPage();
        const items = NAV_ITEMS.slice(0, 5)
            .map(
                (item) => `<a class="bottomnav-link${item.href === active ? " is-active" : ""}" href="${item.href}">${svg(item.icon, 20)}<span>${item.label.split(" ")[0]}</span></a>`
            )
            .join("");
        return `<nav class="bottomnav">${items}</nav>`;
    }

    function buildNotifPanel(schedule) {
        const pending = (schedule || []).filter((slot) => slot.status === "pending");
        if (pending.length === 0) {
            return '<div class="notif-empty">You\'re all caught up — no pending doses right now.</div>';
        }
        return pending
            .map(
                (slot) => `
        <div class="notif-item">
          <div class="notif-item-icon">💊</div>
          <div class="notif-item-body">
            <strong>${slot.medication_name}</strong>
            <span>${slot.slot_time_label} dose is pending</span>
          </div>
        </div>`
            )
            .join("");
    }

    function wireDropdown(btnId, dropdownId) {
        const btn = document.getElementById(btnId);
        const dropdown = document.getElementById(dropdownId);
        if (!btn || !dropdown) return;
        btn.addEventListener("click", (event) => {
            event.stopPropagation();
            const willOpen = !dropdown.classList.contains("is-open");
            document.querySelectorAll(".dropdown.is-open").forEach((el) => el.classList.remove("is-open"));
            if (willOpen) dropdown.classList.add("is-open");
        });
    }

    document.addEventListener("click", () => {
        document.querySelectorAll(".dropdown.is-open").forEach((el) => el.classList.remove("is-open"));
    });

    async function init() {
        const navMount = document.getElementById("app-nav");
        const bottomMount = document.getElementById("app-bottomnav");

        // Render immediately with placeholder name so the nav never
        // flashes empty, then fill in real data once /dashboard resolves.
        if (navMount) navMount.innerHTML = buildTopNav(null, 0);
        if (bottomMount) bottomMount.innerHTML = buildBottomNav();
        wireDropdown("notif-btn", "notif-dropdown");
        wireDropdown("user-menu-btn", "user-dropdown");
        document.getElementById("nav-logout-btn")?.addEventListener("click", window.SehatAI.logout);

        try {
            const response = await window.SehatAI.authedFetch("/dashboard");
            if (!response.ok) return;
            const dashboard = await response.json();
            window.SehatAI.dashboardCache = dashboard;

            const pending = (dashboard.medicine_schedule_today || []).filter((s) => s.status === "pending");
            if (navMount) navMount.innerHTML = buildTopNav(dashboard.health_summary.name, pending.length);
            wireDropdown("notif-btn", "notif-dropdown");
            wireDropdown("user-menu-btn", "user-dropdown");
            document.getElementById("nav-logout-btn")?.addEventListener("click", window.SehatAI.logout);
            document.getElementById("notif-dropdown").innerHTML = buildNotifPanel(dashboard.medicine_schedule_today);

            document.dispatchEvent(new CustomEvent("sehatai:dashboard-ready", { detail: dashboard }));
        } catch (err) {
            if (err.message !== "Session expired") {
                console.error("nav.js: failed to load /dashboard for nav", err);
            }
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();