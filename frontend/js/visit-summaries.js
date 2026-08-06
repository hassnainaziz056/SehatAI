/**
 * frontend/js/visit-summaries.js — UI/UX redesign: the Visit Summaries
 * page. Talks to backend/routes/summary_routes.py (list/detail/generate),
 * same authedFetch/toast conventions as medicines.js and dashboard.js.
 *
 * "Download PDF" deliberately does NOT call a backend PDF endpoint --
 * summary_routes.py only exposes list/detail/generate (see its module
 * docstring: PDF export is a future layer on top of the same
 * VisitSummaryDetail this already returns). Instead it opens a small
 * print-formatted window and calls window.print(), which every modern
 * browser's print dialog can save as a PDF directly -- a real "download
 * a PDF" outcome for the patient, with no new dependency or route.
 */

const { authedFetch, toast } = window.SehatAI;

const listEl = document.getElementById("summaries-list");
const generateBtn = document.getElementById("generate-btn");
const generateBtnLabel = document.getElementById("generate-btn-label");

const modalOverlay = document.getElementById("summary-modal-overlay");
const modalTitle = document.getElementById("summary-modal-title");
const modalBody = document.getElementById("summary-modal-body");
const modalClose = document.getElementById("summary-modal-close");
const modalDownloadBtn = document.getElementById("summary-modal-download");

let currentDetail = null; // the summary currently open in the modal, for Download PDF

// ---------------------------------------------------------------------
// List rendering
// ---------------------------------------------------------------------

function formatDate(isoString) {
    return new Date(isoString).toLocaleDateString(undefined, {
        month: "short", day: "numeric", year: "numeric",
    });
}

function renderEmptyState() {
    // Same visual language as the app's other empty states (icon in a
    // soft circle, heading, short reassuring line, primary CTA) --
    // matches the tone of the profile-gate/completion-nudge copy
    // elsewhere in the app: encouraging, not just "nothing here."
    listEl.innerHTML = `
    <div class="panel">
      <div class="empty-state" style="padding: 48px 20px;">
        <div class="empty-state-icon">🩺</div>
        <h3>No visit summaries yet</h3>
        <p>Have a conversation with the AI Doctor, then come back here and generate a one-page
           summary you can print or bring to your next real appointment.</p>
        <a href="chat.html" class="btn btn--primary btn--sm">Chat with the AI Doctor</a>
      </div>
    </div>`;
}

function renderList(summaries) {
    if (!summaries || summaries.length === 0) {
        renderEmptyState();
        return;
    }

    listEl.innerHTML = `<div class="panel">${summaries
        .map(
            (s) => `
      <div class="summary-report-card" data-summary-id="${s.id}">
        <div class="summary-report-card-icon">🩺</div>
        <div class="summary-report-card-body">
          <strong>${escapeHtml(s.title)}</strong>
          <p>${escapeHtml(s.preview)}</p>
          <span class="summary-report-card-date">${formatDate(s.generated_date)}</span>
        </div>
        <div class="summary-report-card-actions">
          <button type="button" class="btn btn--secondary btn--sm" data-action="view" data-id="${s.id}">View</button>
          <button type="button" class="btn btn--ghost btn--sm" data-action="download" data-id="${s.id}">⬇ PDF</button>
        </div>
      </div>`
        )
        .join("")}</div>`;
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text || "";
    return div.innerHTML;
}

// ---------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------

async function loadSummaries() {
    try {
        const response = await authedFetch("/summaries");
        if (!response.ok) throw new Error(`Server responded with ${response.status}`);
        renderList(await response.json());
    } catch (err) {
        if (err.message !== "Session expired") {
            console.error("Failed to load /summaries:", err);
            toast("Couldn't load your visit summaries. Please refresh.", "error");
        }
    }
}

async function fetchSummaryDetail(id) {
    const response = await authedFetch(`/summaries/${id}`);
    if (!response.ok) throw new Error(`Server responded with ${response.status}`);
    return response.json();
}

// ---------------------------------------------------------------------
// Generate
// ---------------------------------------------------------------------

generateBtn.addEventListener("click", async () => {
    generateBtn.disabled = true;
    generateBtnLabel.textContent = "Generating…";

    try {
        const response = await authedFetch("/summaries/generate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({}),
        });

        if (response.status === 400) {
            const body = await response.json();
            toast(body.detail || "Nothing to summarize yet.", "error");
            return;
        }
        if (!response.ok) throw new Error(`Server responded with ${response.status}`);

        const detail = await response.json();
        toast("Visit summary generated.");
        await loadSummaries();
        openModal(detail);
    } catch (err) {
        if (err.message !== "Session expired") {
            console.error("Failed to generate summary:", err);
            toast("Couldn't generate a summary right now. Please try again.", "error");
        }
    } finally {
        generateBtn.disabled = false;
        generateBtnLabel.textContent = "✨ Generate Summary";
    }
});

// ---------------------------------------------------------------------
// Card actions (event delegation -- the list is rebuilt on every load)
// ---------------------------------------------------------------------

listEl.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const id = button.dataset.id;

    if (button.dataset.action === "view") {
        try {
            openModal(await fetchSummaryDetail(id));
        } catch (err) {
            if (err.message !== "Session expired") {
                toast("Couldn't load that summary.", "error");
            }
        }
    } else if (button.dataset.action === "download") {
        try {
            downloadSummaryPdf(await fetchSummaryDetail(id));
        } catch (err) {
            if (err.message !== "Session expired") {
                toast("Couldn't load that summary.", "error");
            }
        }
    }
});

// ---------------------------------------------------------------------
// Detail modal
// ---------------------------------------------------------------------

function renderModalBody(detail) {
    const listOrNone = (items) =>
        items && items.length > 0
            ? `<ul class="summary-detail-list">${items.map((i) => `<li>${escapeHtml(i)}</li>`).join("")}</ul>`
            : "<p>None on file.</p>";

    modalBody.innerHTML = `
    <div class="summary-detail-section">
      <h3>Chief Complaint</h3>
      <p>${escapeHtml(detail.chief_complaint)}</p>
    </div>
    ${detail.duration ? `
    <div class="summary-detail-section">
      <h3>Duration</h3>
      <p>${escapeHtml(detail.duration)}</p>
    </div>` : ""}
    <div class="summary-detail-section">
      <h3>Symptoms Reported</h3>
      ${listOrNone(detail.symptoms)}
    </div>
    <div class="summary-detail-section">
      <h3>Relevant History</h3>
      <p>${escapeHtml(detail.relevant_history) || "None on file."}</p>
    </div>
    <div class="summary-detail-section">
      <h3>Current Medications</h3>
      ${listOrNone(detail.medications)}
    </div>
    <div class="summary-detail-section">
      <h3>Suggested Questions for Your Doctor</h3>
      ${listOrNone(detail.suggested_questions)}
    </div>`;
}

function openModal(detail) {
    currentDetail = detail;
    modalTitle.textContent = detail.title;
    renderModalBody(detail);
    modalOverlay.classList.add("is-open");
}

function closeModal() {
    modalOverlay.classList.remove("is-open");
    currentDetail = null;
}

modalClose.addEventListener("click", closeModal);
modalOverlay.addEventListener("click", (event) => {
    if (event.target === modalOverlay) closeModal();
});
document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && modalOverlay.classList.contains("is-open")) closeModal();
});

modalDownloadBtn.addEventListener("click", () => {
    if (currentDetail) downloadSummaryPdf(currentDetail);
});

// ---------------------------------------------------------------------
// Download as PDF (via print) -- see module docstring
// ---------------------------------------------------------------------

function downloadSummaryPdf(detail) {
    const win = window.open("", "_blank", "width=800,height=900");
    if (!win) {
        toast("Please allow pop-ups to download the PDF.", "error");
        return;
    }

    const section = (title, bodyHtml) => `<h2>${title}</h2>${bodyHtml}`;
    const list = (items) =>
        items && items.length > 0
            ? `<ul>${items.map((i) => `<li>${escapeHtml(i)}</li>`).join("")}</ul>`
            : "<p>None on file.</p>";

    win.document.write(`
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <title>${escapeHtml(detail.title)}</title>
      <style>
        body { font-family: -apple-system, Segoe UI, Inter, sans-serif; color: #1a1a1a; padding: 36px; max-width: 700px; margin: 0 auto; }
        h1 { font-size: 1.4rem; margin-bottom: 4px; }
        .meta { color: #666; font-size: 0.85rem; margin-bottom: 24px; }
        h2 { font-size: 0.95rem; text-transform: uppercase; letter-spacing: 0.03em; color: #555; margin: 20px 0 6px; }
        p, li { font-size: 0.95rem; line-height: 1.6; }
        ul { margin: 0; padding-left: 20px; }
        .footer { margin-top: 32px; font-size: 0.78rem; color: #999; border-top: 1px solid #ddd; padding-top: 12px; }
      </style>
    </head>
    <body>
      <h1>🩺 ${escapeHtml(detail.title)}</h1>
      <div class="meta">Generated ${formatDate(detail.generated_date)} · SehatAI Visit Summary</div>
      ${section("Chief Complaint", `<p>${escapeHtml(detail.chief_complaint)}</p>`)}
      ${detail.duration ? section("Duration", `<p>${escapeHtml(detail.duration)}</p>`) : ""}
      ${section("Symptoms Reported", list(detail.symptoms))}
      ${section("Relevant History", `<p>${escapeHtml(detail.relevant_history) || "None on file."}</p>`)}
      ${section("Current Medications", list(detail.medications))}
      ${section("Suggested Questions for Your Doctor", list(detail.suggested_questions))}
      <div class="footer">Generated by SehatAI. This summary is based on what you reported in chat and your saved profile -- it is not a diagnosis. Always confirm with a qualified doctor.</div>
    </body>
    </html>`);
    win.document.close();
    win.focus();
    // Small delay so the new window has actually painted before the
    // print dialog steals focus -- calling print() immediately on some
    // browsers opens a blank dialog.
    setTimeout(() => win.print(), 300);
}

loadSummaries();