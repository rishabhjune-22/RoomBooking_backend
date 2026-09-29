export function menuItems(role) {
    if (role === "admin" || role === "superadmin") {
        const items = [["calendar", "Home / Calendar"], ["bookings", "Bookings"], ["bookingRequests", "Booking Requests"]];
        if (role === "superadmin") items.push(["accounts", "User Profiles"]);
        return items;
    }
    return [["calendar", "Home / Calendar"], ["myRequests", "My Requests"]];
}

export function countBadgeHtml(count) {
    return count ? `<span class="menu-count-badge">${count > 99 ? "99+" : count}</span>` : "";
}

function bellIcon() {
    return `<svg class="bell-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M18 16v-5a6 6 0 0 0-12 0v5l-2 2h16l-2-2Z"></path><path d="M9.5 20a2.5 2.5 0 0 0 5 0"></path></svg>`;
}

export function dashboardHtml({ user, activeView, items, countForView, escapeHtml, titleCase }) {
    const roleLabel = user?.role === "superadmin" ? "Superadmin" : titleCase(user?.role);
    const visible = items.filter(([id]) => id !== activeView);
    return `<header class="topbar"><div class="topbar-inner"><div class="topbar-title">
        <div class="brand-mark"><img class="brand-logo" src="/static/webapp/mainlogo.jpeg" alt="Room Booking logo"></div>
        <div><h1>Room Booking</h1><p>${escapeHtml(user?.name || user?.email || "User")} - ${escapeHtml(roleLabel)}</p></div>
        </div><nav class="toolbar-menu" aria-label="Main navigation">
        ${visible.map(([id, label]) => `<button class="menu-btn" data-view="${id}"><span>${label}</span>${countBadgeHtml(countForView(id))}</button>`).join("")}
        <button class="notification-bell" type="button" data-notification-bell aria-label="Workflow notifications">${bellIcon()}<span id="workflow-notification-badge" class="notification-badge" hidden>0</span></button>
        <button class="menu-btn" data-logout>Logout</button></nav></div></header><main class="dashboard" id="view-root"></main>`;
}
