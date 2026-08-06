/**
 * frontend/js/nav.js — Top/bottom navigation (single-workflow rebuild)
 *
 * Injects the sticky top navigation bar (and, on mobile, the bottom tab
 * bar) into every logged-in page. One component, reused everywhere,
 * instead of duplicating nav markup in home.html, history.html, and
 * chat.html — each of those pages just needs `<div id="app-nav"></div>`
 * + `<div id="app-bottomnav"></div>` and this script.
 *
 * Also fetches the patient's name (for the avatar/greeting) from
 * GET /profile, so the nav never has to guess it.
 *
 * Depends on common.js being loaded first (window.SehatAI.authedFetch).
 */

(function () {
  const NAV_ITEMS = [
    { href: "home.html", label: "Home", icon: "home" },
    { href: "history.html", label: "Patient History", icon: "history" },
    { href: "chat.html", label: "Chatbot", icon: "chat" },
  ];

  const ICONS = {
    home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V20a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1V9.5"/>',
    chat: '<path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5c-1.35 0-2.62-.32-3.75-.9L3 21l1.9-5.7A8.5 8.5 0 1 1 21 11.5Z"/>',
    history: '<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/><path d="M12 7v5l3.5 2"/>',
    chevron: '<path d="m6 9 6 6 6-6"/>',
    logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/>',
  };

  function svg(name, size = 18) {
    return `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ""}</svg>`;
  }

  function currentPage() {
    const path = window.location.pathname.split("/").pop();
    return path || "home.html";
  }

  function buildTopNav(name) {
    const active = currentPage();
    const links = NAV_ITEMS.map(
      (item) => `<a class="topnav-link${item.href === active ? " is-active" : ""}" href="${item.href}">${svg(item.icon, 16)}<span>${item.label}</span></a>`
    ).join("");

    return `
      <header class="topnav">
        <div class="topnav-inner">
          <a class="topnav-brand" href="home.html">
            <span class="topnav-brand-mark">🏥</span>
            <span class="topnav-brand-text">SehatAI</span>
          </a>
          <nav class="topnav-links">${links}</nav>
          <div class="topnav-actions">
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
    const items = NAV_ITEMS.map(
      (item) => `<a class="bottomnav-link${item.href === active ? " is-active" : ""}" href="${item.href}">${svg(item.icon, 20)}<span>${item.label.split(" ")[0]}</span></a>`
    ).join("");
    return `<nav class="bottomnav">${items}</nav>`;
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

    // Render immediately with a placeholder name so the nav never
    // flashes empty, then fill in the real name once /profile resolves.
    if (navMount) navMount.innerHTML = buildTopNav(null);
    if (bottomMount) bottomMount.innerHTML = buildBottomNav();
    wireDropdown("user-menu-btn", "user-dropdown");
    document.getElementById("nav-logout-btn")?.addEventListener("click", window.SehatAI.logout);

    try {
      const response = await window.SehatAI.authedFetch("/profile");
      if (!response.ok) return;
      const profile = await response.json();
      window.SehatAI.profileCache = profile;

      if (navMount) navMount.innerHTML = buildTopNav(profile.full_name);
      wireDropdown("user-menu-btn", "user-dropdown");
      document.getElementById("nav-logout-btn")?.addEventListener("click", window.SehatAI.logout);

      document.dispatchEvent(new CustomEvent("sehatai:profile-ready", { detail: profile }));
    } catch (err) {
      if (err.message !== "Session expired") {
        console.error("nav.js: failed to load /profile for nav", err);
      }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();