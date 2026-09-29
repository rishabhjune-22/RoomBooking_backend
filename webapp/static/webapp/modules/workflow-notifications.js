const CATEGORIES = ["booking_requests", "requester_accounts", "admin_accounts", "my_requests"];

export function emptyCounts() {
    return { total: 0, booking_requests: 0, requester_accounts: 0, admin_accounts: 0, my_requests: 0 };
}

export function emptyItems() {
    return { booking_requests: [], requester_accounts: [], admin_accounts: [], my_requests: [] };
}

export function storageKey(prefix, user) {
    const userKey = user?.id || user?.email || "anonymous";
    return `${prefix}:${user?.role || "unknown"}:${userKey}`;
}

export function categoriesForView(viewId) {
    if (viewId === "bookingRequests") return ["booking_requests"];
    if (viewId === "accounts") return ["admin_accounts"];
    if (viewId === "myRequests") return ["my_requests"];
    return [];
}

export function countForView(counts, viewId) {
    const category = categoriesForView(viewId)[0];
    return category ? counts?.[category] || 0 : 0;
}

export function itemKey(item) {
    return typeof item === "string" ? item : item?.key;
}

function normalizeItems(category, payload) {
    const supplied = payload?.items?.[category];
    if (Array.isArray(supplied) && supplied.length) {
        return supplied.map((item) => typeof item === "string"
            ? item
            : { ...item, key: item?.key || `${category}:${item?.id}` }).filter(Boolean);
    }
    return Array.from({ length: Number(payload?.[category] || 0) }, (_, index) => `${category}:legacy:${index + 1}`);
}

export function reconcile(payload, readKeysInput) {
    const readKeys = new Set(readKeysInput || []);
    const currentKeys = new Set();
    const items = emptyItems();
    const rawCounts = emptyCounts();
    const unreadCounts = emptyCounts();
    CATEGORIES.forEach((category) => {
        items[category] = normalizeItems(category, payload);
        const keys = items[category].map(itemKey).filter(Boolean);
        rawCounts[category] = keys.length;
        keys.forEach((key) => currentKeys.add(key));
        unreadCounts[category] = keys.filter((key) => !readKeys.has(key)).length;
    });
    const prunedReadKeys = new Set(Array.from(readKeys).filter((key) => currentKeys.has(key)));
    rawCounts.total = CATEGORIES.reduce((total, category) => total + rawCounts[category], 0);
    unreadCounts.total = CATEGORIES.reduce((total, category) => total + unreadCounts[category], 0);
    return { items, rawCounts, unreadCounts, prunedReadKeys };
}

export function detailListHtml(details, escapeHtml) {
    if (!details.length) return "";
    return `<span class="notification-detail-list">${details.map((item) => `
        <span class="notification-detail-item">
            ${item.title ? `<strong>${escapeHtml(item.title)}</strong>` : ""}
            ${item.message ? `<small>${escapeHtml(item.message)}</small>` : ""}
        </span>`).join("")}</span>`;
}

export function detailPanelHtml(details, escapeHtml) {
    if (!details.length) return `<div class="empty-state">No notification details available.</div>`;
    return `<div class="notification-detail-panel">${details.map((item) => `
        <article class="notification-detail-card">
            ${item.title ? `<h4>${escapeHtml(item.title)}</h4>` : ""}
            ${item.message ? `<p>${escapeHtml(item.message)}</p>` : ""}
        </article>`).join("")}</div>`;
}

export function summaryHtml(rows, total, escapeHtml) {
    return `<div class="notification-summary"><div class="notification-total"><span>Total new items</span><strong>${total}</strong></div>
        ${rows.length ? rows.map((row) => `
            <button class="notification-summary-row" type="button" data-notification-view="${row.view}"><span>
                <strong>${escapeHtml(row.title)}</strong><small>${escapeHtml(row.description)}</small>
                ${detailListHtml(row.details, escapeHtml)}</span>
                ${row.count > 0 ? `<span class="notification-row-count">${row.count > 99 ? "99+" : row.count}</span>`
                    : `<span class="notification-read-chip">${row.rawCount > 0 ? "Read" : "None"}</span>`}
            </button>`).join("") : `<div class="empty-state">No workflow notifications.</div>`}
    </div>`;
}

export function rowsForUser({ counts = {}, rawCounts = {}, user, adminLike, superadmin, detailsForView, items = {} }) {
    const rows = [];
    if (adminLike) rows.push({ view: "bookingRequests", title: "Booking Requests",
        count: counts.booking_requests || 0, rawCount: rawCounts.booking_requests || 0,
        description: "Pending booking requests waiting for review.", details: detailsForView("bookingRequests").slice(0, 3) });
    if (superadmin) rows.push({ view: "accounts", title: "Admin Accounts",
        count: counts.admin_accounts || 0, rawCount: rawCounts.admin_accounts || 0,
        description: "Pending admin accounts waiting for superadmin approval.", details: detailsForView("accounts").slice(0, 3) });
    if (user?.role === "requester") rows.push({ view: "myRequests", title: "My Requests",
        count: counts.my_requests || 0, rawCount: rawCounts.my_requests || 0,
        description: "Reviewed requests waiting for you to read.",
        details: (items.my_requests || []).filter((item) => typeof item === "object" && (item.title || item.message)).slice(0, 3) });
    return rows;
}
