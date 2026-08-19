const appRoot = document.getElementById("app");

const STORAGE_KEYS = {
    access: "roomBookingWebAccess",
    refresh: "roomBookingWebRefresh",
    user: "roomBookingWebUser",
};

const BOOKING_VIEW_MODES = new Set(["cards", "sheet", "charge_sheet"]);

const STATUS_LABELS = {
    pending: "Pending",
    approved: "Approved",
    rejected: "Rejected",
    correction_required: "Correction Required",
    active: "Active",
    expired: "Expired",
};

const BUILDINGS = ["Delta", "Gamma", "Beta"];
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const SHEET_COOLING_HOURS = 1;
const SHEET_DAY_END_MINUTES = 18 * 60;

const state = {
    authRole: "admin",
    authMode: "login",
    user: null,
    access: localStorage.getItem(STORAGE_KEYS.access) || "",
    refresh: localStorage.getItem(STORAGE_KEYS.refresh) || "",
    view: "calendar",
    prefix: "Delta",
    calendarMonth: new Date().getMonth() + 1,
    calendarYear: new Date().getFullYear(),
    availability: null,
    selectedDate: "",
    rangeStart: "",
    rangeEnd: "",
    bookingStatusFilter: "all",
    bookingPrefixFilter: "all",
    bookingArrivalFrom: "",
    bookingDepartureTo: "",
    bookingViewMode: "cards",
    bookingNextUrl: "",
    bookingLoading: false,
    bookingLoadedCount: 0,
    bookingInfiniteObserver: null,
    chargeSheetPrefixFilter: "all",
    chargeSheetPaymentFilter: "all",
    chargeSheetCheckoutFrom: "",
    chargeSheetCheckoutTo: "",
    chargeSheetSearch: "",
    chargeSheetOrdering: "-created_at",
    chargeSheetRows: [],
    chargeSheetEditingId: "",
    chargeSheetSelectedId: "",
    bookingRequestFilter: "pending",
    requesterAccountFilter: "pending",
    myRequestFilter: "all",
    rooms: [],
};

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function titleCase(value) {
    return STATUS_LABELS[value] || String(value || "").replaceAll("_", " ");
}

function pad(value) {
    return String(value).padStart(2, "0");
}

function isoDate(year, month, day) {
    return `${year}-${pad(month)}-${pad(day)}`;
}

function todayIso() {
    const now = new Date();
    return isoDate(now.getFullYear(), now.getMonth() + 1, now.getDate());
}

function currentMonthRange() {
    const now = new Date();
    const year = now.getFullYear();
    const month = now.getMonth() + 1;
    return {
        start: isoDate(year, month, 1),
        end: isoDate(year, month, new Date(year, month, 0).getDate()),
    };
}

function addIsoDays(dateValue, days) {
    const date = new Date(`${dateValue}T00:00:00`);
    date.setDate(date.getDate() + days);
    return isoDate(date.getFullYear(), date.getMonth() + 1, date.getDate());
}

function addHoursToDateTime(value, hours) {
    return new Date(new Date(value).getTime() + hours * 60 * 60 * 1000);
}

function isoDateRange(start, end) {
    const dates = [];
    if (!start || !end) {
        return dates;
    }
    let cursor = start <= end ? start : end;
    const finalDate = start <= end ? end : start;
    while (cursor <= finalDate) {
        dates.push(cursor);
        cursor = addIsoDays(cursor, 1);
    }
    return dates;
}

function localIsoDateFromDateTime(value) {
    return indiaParts(value).date;
}

function localTimeMinutes(value) {
    const timeValue = indiaParts(value).time;
    const [hour = 0, minute = 0] = timeValue.split(":").map(Number);
    return hour * 60 + minute;
}

function formatSheetTime(value) {
    if (!value) {
        return "";
    }
    return new Intl.DateTimeFormat("en-IN", {
        timeZone: "Asia/Kolkata",
        hour: "2-digit",
        minute: "2-digit",
    }).format(new Date(value));
}

function formatSheetDate(value) {
    if (!value) {
        return "-";
    }
    return new Intl.DateTimeFormat("en-IN", {
        timeZone: "Asia/Kolkata",
        day: "2-digit",
        month: "short",
        year: "numeric",
    }).format(new Date(`${value}T00:00:00+05:30`));
}

function monthName(year, month) {
    return new Intl.DateTimeFormat("en", { month: "long", year: "numeric" }).format(
        new Date(year, month - 1, 1),
    );
}

function indiaParts(value) {
    if (!value) {
        return { date: "", time: "" };
    }
    const parts = new Intl.DateTimeFormat("en-CA", {
        timeZone: "Asia/Kolkata",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
    }).formatToParts(new Date(value));
    const lookup = Object.fromEntries(parts.map((part) => [part.type, part.value]));
    return {
        date: `${lookup.year}-${lookup.month}-${lookup.day}`,
        time: `${lookup.hour}:${lookup.minute}`,
    };
}

function formatDateTime(value) {
    if (!value) {
        return "-";
    }
    return new Intl.DateTimeFormat("en-IN", {
        timeZone: "Asia/Kolkata",
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    }).format(new Date(value));
}

function formatDateRange(item) {
    return `${formatDateTime(item.arrival_at)} to ${formatDateTime(item.departure_at)}`;
}

function isPastDateTime(value) {
    if (!value) {
        return false;
    }
    const date = new Date(value);
    return !Number.isNaN(date.getTime()) && date.getTime() < Date.now();
}

function selectedRangeText() {
    if (!state.rangeStart) {
        return "No dates selected";
    }
    if (!state.rangeEnd || state.rangeEnd === state.rangeStart) {
        return state.rangeStart;
    }
    return `${state.rangeStart} to ${state.rangeEnd}`;
}

function buildIsoDateTime(dateValue, timeValue) {
    return `${dateValue}T${timeValue || "10:00"}:00+05:30`;
}

function yesNo(value) {
    return value ? "Yes" : "No";
}

function valueOrDash(value) {
    if (value === true || value === false) {
        return yesNo(value);
    }
    if (value === 0) {
        return "0";
    }
    return value || "-";
}

function roomLabel(room) {
    if (!room) {
        return "";
    }
    const prefix = String(room.prefix || "").trim();
    const label = String(
        room.selection_label
        || room.room_name
        || room.number
        || room.room_number
        || ""
    ).trim();
    if (prefix && label && !label.toLowerCase().startsWith(prefix.toLowerCase())) {
        return `${prefix} ${label}`;
    }
    return label || `Room ${room.id}`;
}

function buildingRoomValue(value, prefix) {
    const label = String(value || "").trim();
    const building = String(prefix || "").trim();
    if (!label) {
        return "";
    }
    if (!building || label.toLowerCase().startsWith(building.toLowerCase())) {
        return label;
    }
    return `${building} ${label}`;
}

function shiftsText(item) {
    const shifts = [];
    if (item?.attender_general_shift) shifts.push("General shift");
    if (item?.attender_morning_shift) shifts.push("Morning shift");
    if (item?.attender_day_shift) shifts.push("Day shift");
    return shifts.length ? shifts.join(", ") : "-";
}

function htmlValue(value) {
    return escapeHtml(value ?? "");
}

function setTokens(payload) {
    state.access = payload.access || "";
    state.refresh = payload.refresh || "";
    state.user = payload.user || null;
    localStorage.setItem(STORAGE_KEYS.access, state.access);
    localStorage.setItem(STORAGE_KEYS.refresh, state.refresh);
    localStorage.setItem(STORAGE_KEYS.user, JSON.stringify(state.user));
}

function clearSession() {
    state.access = "";
    state.refresh = "";
    state.user = null;
    localStorage.removeItem(STORAGE_KEYS.access);
    localStorage.removeItem(STORAGE_KEYS.refresh);
    localStorage.removeItem(STORAGE_KEYS.user);
}

function messageFromErrors(payload) {
    if (!payload) {
        return "Request failed.";
    }
    if (payload.message) {
        return payload.message;
    }
    const errors = payload.errors || {};
    const firstKey = Object.keys(errors)[0];
    if (!firstKey) {
        return "Request failed.";
    }
    const value = errors[firstKey];
    return Array.isArray(value) ? value[0] : String(value);
}

async function apiFetch(path, options = {}, retry = true) {
    const headers = new Headers(options.headers || {});
    headers.set("Accept", "application/json");
    if (state.access) {
        headers.set("Authorization", `Bearer ${state.access}`);
    }
    let body = options.body;
    if (body && typeof body !== "string") {
        headers.set("Content-Type", "application/json");
        body = JSON.stringify(body);
    }
    const response = await fetch(path, { ...options, headers, body });
    let payload = null;
    try {
        payload = await response.json();
    } catch (error) {
        payload = null;
    }
    if (response.status === 401 && retry && state.refresh) {
        const refreshed = await refreshAccessToken();
        if (refreshed) {
            return apiFetch(path, options, false);
        }
        clearSession();
        renderAuth("Your session expired. Please login again.", true);
        throw new Error("Session expired.");
    }
    if (!response.ok || payload?.success === false) {
        throw new Error(messageFromErrors(payload));
    }
    return payload?.data;
}

async function refreshAccessToken() {
    try {
        const response = await fetch("/api/auth/token/refresh/", {
            method: "POST",
            headers: { "Content-Type": "application/json", Accept: "application/json" },
            body: JSON.stringify({ refresh: state.refresh }),
        });
        if (!response.ok) {
            return false;
        }
        const payload = await response.json();
        state.access = payload.access || payload.data?.access || "";
        if (!state.access) {
            return false;
        }
        localStorage.setItem(STORAGE_KEYS.access, state.access);
        return true;
    } catch (error) {
        return false;
    }
}

function toast(message, type = "success") {
    const existing = document.querySelector(".toast");
    if (existing) {
        existing.remove();
    }
    const node = document.createElement("div");
    node.className = `toast ${type}`;
    node.textContent = message;
    document.body.appendChild(node);
    window.setTimeout(() => node.remove(), 3200);
}

function renderAuth(message = "", isError = false) {
    const isSignup = state.authMode === "signup";
    appRoot.innerHTML = `
        <main class="login-shell">
            <section class="login-card">
                <div class="brand-row">
                    <div class="brand-mark">RB</div>
                    <div>
                        <h1 class="brand-title">Room Booking</h1>
                        <p class="brand-subtitle">Calendar, booking requests, and room management</p>
                    </div>
                </div>
                <div class="segmented" role="tablist" aria-label="Role">
                    <button class="segment-btn ${state.authRole === "admin" ? "active" : ""}" data-auth-role="admin">Admin</button>
                    <button class="segment-btn ${state.authRole === "requester" ? "active" : ""}" data-auth-role="requester">Requester</button>
                </div>
                <div class="segmented" role="tablist" aria-label="Mode">
                    <button class="segment-btn ${!isSignup ? "active" : ""}" data-auth-mode="login">Login</button>
                    <button class="segment-btn ${isSignup ? "active" : ""}" data-auth-mode="signup">Signup</button>
                </div>
                <form id="auth-form" class="field-grid">
                    ${isSignup ? `
                        <div class="field-row">
                            <label for="name">Full name</label>
                            <input id="name" name="name" autocomplete="name" required>
                        </div>
                    ` : ""}
                    <div class="field-row">
                        <label for="email">Email</label>
                        <input id="email" name="email" type="email" autocomplete="email" required>
                    </div>
                    <div class="field-row">
                        <label for="password">Password</label>
                        <div class="password-wrap">
                            <input id="password" name="password" type="password" autocomplete="${isSignup ? "new-password" : "current-password"}" required>
                            <button class="outline-btn" type="button" data-toggle-password="password">Show</button>
                        </div>
                    </div>
                    ${isSignup ? `
                        <div class="field-row">
                            <label for="confirm_password">Confirm password</label>
                            <div class="password-wrap">
                                <input id="confirm_password" name="confirm_password" type="password" autocomplete="new-password" required>
                                <button class="outline-btn" type="button" data-toggle-password="confirm_password">Show</button>
                            </div>
                        </div>
                        ${state.authRole === "admin" ? `
                            <div class="field-row">
                                <label for="admin_code">Admin invite code</label>
                                <input id="admin_code" name="admin_code" autocomplete="off" required>
                            </div>
                        ` : `
                            <div class="two-col">
                                <div class="field-row">
                                    <label for="department">Department</label>
                                    <input id="department" name="department">
                                </div>
                                <div class="field-row">
                                    <label for="designation">Designation</label>
                                    <input id="designation" name="designation">
                                </div>
                            </div>
                            <div class="field-row">
                                <label for="mobile">Mobile</label>
                                <input id="mobile" name="mobile" inputmode="tel">
                            </div>
                        `}
                    ` : ""}
                    <div class="form-actions">
                        <button class="primary-btn" type="submit">${isSignup ? "Create Account" : "Login"}</button>
                        <span class="brand-subtitle">${state.authRole === "admin" ? "Using Admin tab" : "Using Requester tab"}</span>
                    </div>
                </form>
                ${message ? `<div class="status-message ${isError ? "error" : "success"}">${escapeHtml(message)}</div>` : ""}
            </section>
        </main>
    `;

    appRoot.querySelectorAll("[data-auth-role]").forEach((button) => {
        button.addEventListener("click", () => {
            state.authRole = button.dataset.authRole;
            renderAuth();
        });
    });
    appRoot.querySelectorAll("[data-auth-mode]").forEach((button) => {
        button.addEventListener("click", () => {
            state.authMode = button.dataset.authMode;
            renderAuth();
        });
    });
    appRoot.querySelectorAll("[data-toggle-password]").forEach((button) => {
        button.addEventListener("click", () => {
            const input = document.getElementById(button.dataset.togglePassword);
            input.type = input.type === "password" ? "text" : "password";
            button.textContent = input.type === "password" ? "Show" : "Hide";
        });
    });
    document.getElementById("auth-form").addEventListener("submit", submitAuthForm);
}

async function submitAuthForm(event) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const body = Object.fromEntries(formData.entries());
    const endpoint = state.authMode === "signup"
        ? `/api/auth/${state.authRole}/signup/`
        : `/api/auth/${state.authRole}/login/`;
    try {
        const data = await apiFetch(endpoint, { method: "POST", body }, false);
        if (state.authMode === "signup") {
            const roleName = state.authRole === "admin" ? "admin" : "requester";
            renderAuth(`Your ${roleName} account was created and is pending approval.`, false);
            return;
        }
        setTokens(data);
        state.view = defaultViewForCurrentRole();
        syncRouteHash(true);
        renderDashboard();
    } catch (error) {
        renderAuth(error.message, true);
    }
}

function isAdminLike() {
    return state.user?.role === "admin" || state.user?.role === "superadmin";
}

function defaultViewForCurrentRole() {
    return "calendar";
}

function allowedViewIds() {
    return menuItems().map(([id]) => id);
}

function readRouteFromHash() {
    const rawHash = window.location.hash.replace(/^#/, "");
    if (!rawHash) {
        return {};
    }
    if (!rawHash.includes("=")) {
        return { view: decodeURIComponent(rawHash) };
    }
    const params = new URLSearchParams(rawHash);
    return {
        view: params.get("view") || "",
        bookingView: params.get("bookingView") || "",
    };
}

function applyRouteFromHash() {
    const route = readRouteFromHash();
    const allowedViews = allowedViewIds();
    state.view = allowedViews.includes(route.view)
        ? route.view
        : defaultViewForCurrentRole();

    if (state.view === "bookings" && BOOKING_VIEW_MODES.has(route.bookingView)) {
        state.bookingViewMode = route.bookingView;
    }
}

function routeHash() {
    const params = new URLSearchParams({ view: state.view });
    if (state.view === "bookings") {
        params.set("bookingView", state.bookingViewMode);
    }
    return `#${params.toString()}`;
}

function syncRouteHash(replace = false) {
    const nextHash = routeHash();
    if (window.location.hash === nextHash) {
        return;
    }
    const nextUrl = `${window.location.pathname}${window.location.search}${nextHash}`;
    if (replace) {
        window.history.replaceState(null, "", nextUrl);
    } else {
        window.history.pushState(null, "", nextUrl);
    }
}

function navigateToView(view, replace = false) {
    state.view = view;
    syncRouteHash(replace);
    renderDashboard();
}

function menuItems() {
    if (isAdminLike()) {
        return [
            ["calendar", "Home / Calendar"],
            ["bookings", "Bookings"],
            ["bookingRequests", "Booking Requests"],
            ["requesters", "Manage Requesters"],
        ];
    }
    return [
        ["calendar", "Home / Calendar"],
        ["myRequests", "My Requests"],
    ];
}

function renderDashboard() {
    const roleLabel = state.user?.role === "superadmin" ? "Superadmin" : titleCase(state.user?.role);
    appRoot.innerHTML = `
        <header class="topbar">
            <div class="topbar-inner">
                <div class="topbar-title">
                    <div class="brand-mark">RB</div>
                    <div>
                        <h1>Room Booking</h1>
                        <p>${escapeHtml(state.user?.name || state.user?.email || "User")} - ${escapeHtml(roleLabel)}</p>
                    </div>
                </div>
                <nav class="toolbar-menu" aria-label="Main navigation">
                    ${menuItems().map(([id, label]) => `
                        <button class="menu-btn ${state.view === id ? "active" : ""}" data-view="${id}">${label}</button>
                    `).join("")}
                    <button class="menu-btn" data-logout>Logout</button>
                </nav>
            </div>
        </header>
        <main class="dashboard" id="view-root"></main>
    `;
    appRoot.querySelectorAll("[data-view]").forEach((button) => {
        button.addEventListener("click", () => {
            navigateToView(button.dataset.view);
        });
    });
    appRoot.querySelector("[data-logout]").addEventListener("click", logout);
    renderCurrentView();
}

function logout() {
    const refresh = state.refresh;
    clearSession();
    if (refresh) {
        apiFetch("/api/auth/logout/", { method: "POST", body: { refresh } }, false).catch(() => {});
    }
    renderAuth();
}

function viewRoot() {
    return document.getElementById("view-root");
}

function renderCurrentView() {
    viewRoot().classList.remove("wide-dashboard");
    if (state.view === "bookings") {
        renderBookingsView();
    } else if (state.view === "bookingRequests") {
        renderBookingRequestsView();
    } else if (state.view === "requesters") {
        renderRequesterAccountsView();
    } else if (state.view === "myRequests") {
        renderMyRequestsView();
    } else {
        renderCalendarView();
    }
}

function renderCalendarView() {
    viewRoot().innerHTML = `
        <div class="section-header">
            <div>
                <h2>Calendar</h2>
                <p>${isAdminLike() ? "Full room availability and booking details." : "Requester-safe availability with no private booking details."}</p>
            </div>
            ${isAdminLike()
                ? `<button class="primary-btn" id="calendar-create-booking">Create Booking</button>`
                : `<button class="primary-btn" id="request-booking-btn" disabled>Request Booking</button>`}
        </div>
        <div class="calendar-layout">
            <section class="surface calendar-panel">
                <div class="calendar-controls">
                    <button class="outline-btn" id="prev-month">Previous</button>
                    <div class="month-title" id="month-title"></div>
                    <button class="outline-btn" id="next-month">Next</button>
                </div>
                <div class="building-tabs" id="building-tabs"></div>
                <div class="calendar-grid" id="calendar-grid"></div>
                <div class="legend">
                    <span class="legend-item"><span class="dot open"></span> Available</span>
                    <span class="legend-item"><span class="dot partial"></span> Partial</span>
                    <span class="legend-item"><span class="dot full"></span> Full</span>
                </div>
            </section>
            <aside class="surface side-panel" id="calendar-side">
                <div class="loading-state">Loading calendar...</div>
            </aside>
        </div>
    `;
    document.getElementById("prev-month").addEventListener("click", () => changeMonth(-1));
    document.getElementById("next-month").addEventListener("click", () => changeMonth(1));
    if (isAdminLike()) {
        document.getElementById("calendar-create-booking").addEventListener("click", () => openAdminBookingForm());
    } else {
        document.getElementById("request-booking-btn").addEventListener("click", () => openRequestForm());
    }
    drawBuildingTabs();
    loadCalendar();
}

function drawBuildingTabs() {
    const node = document.getElementById("building-tabs");
    node.innerHTML = BUILDINGS.map((prefix) => `
        <button class="chip ${state.prefix === prefix ? "active" : ""}" data-prefix="${prefix}">${prefix}</button>
    `).join("");
    node.querySelectorAll("[data-prefix]").forEach((button) => {
        button.addEventListener("click", () => {
            state.prefix = button.dataset.prefix;
            state.selectedDate = "";
            state.rangeStart = "";
            state.rangeEnd = "";
            drawBuildingTabs();
            drawCalendar();
            renderCalendarSide();
        });
    });
}

function changeMonth(delta) {
    state.calendarMonth += delta;
    if (state.calendarMonth < 1) {
        state.calendarMonth = 12;
        state.calendarYear -= 1;
    } else if (state.calendarMonth > 12) {
        state.calendarMonth = 1;
        state.calendarYear += 1;
    }
    state.selectedDate = "";
    state.rangeStart = "";
    state.rangeEnd = "";
    loadCalendar();
}

async function loadCalendar() {
    document.getElementById("month-title").textContent = monthName(state.calendarYear, state.calendarMonth);
    document.getElementById("calendar-grid").innerHTML = `<div class="loading-state" style="grid-column:1 / -1">Loading availability...</div>`;
    const endpoint = isAdminLike()
        ? `/api/bookings/availability/?month=${state.calendarMonth}&year=${state.calendarYear}`
        : `/api/requester/availability/?month=${state.calendarMonth}&year=${state.calendarYear}`;
    try {
        state.availability = await apiFetch(endpoint);
        drawCalendar();
        renderCalendarSide();
    } catch (error) {
        document.getElementById("calendar-grid").innerHTML = `<div class="empty-state" style="grid-column:1 / -1">${escapeHtml(error.message)}</div>`;
    }
}

function currentCalendarGroup() {
    return state.availability?.groups?.find((group) => group.prefix === state.prefix) || null;
}

function availabilityClass(day) {
    if (!day) {
        return "empty";
    }
    if (day.available_rooms <= 0) {
        return "full";
    }
    if (day.has_before_6pm_booking || day.has_partial_booking || day.available_rooms < day.total_rooms) {
        return "partial";
    }
    return "open";
}

function isInSelectedRange(dateValue) {
    if (!state.rangeStart || !state.rangeEnd) {
        return dateValue === state.rangeStart;
    }
    return dateValue >= state.rangeStart && dateValue <= state.rangeEnd;
}

function drawCalendar() {
    const grid = document.getElementById("calendar-grid");
    const group = currentCalendarGroup();
    if (!grid || !group) {
        if (grid) {
            grid.innerHTML = `<div class="empty-state" style="grid-column:1 / -1">No availability data for ${escapeHtml(state.prefix)}.</div>`;
        }
        return;
    }
    const daysByDate = Object.fromEntries(group.calendar.map((day) => [day.date, day]));
    const firstDay = new Date(state.calendarYear, state.calendarMonth - 1, 1).getDay();
    const daysInMonth = new Date(state.calendarYear, state.calendarMonth, 0).getDate();
    const cells = [];
    WEEKDAYS.forEach((day) => cells.push(`<div class="weekday">${day}</div>`));
    for (let i = 0; i < firstDay; i += 1) {
        cells.push(`<button class="day-cell empty" type="button" tabindex="-1"></button>`);
    }
    for (let day = 1; day <= daysInMonth; day += 1) {
        const dateValue = isoDate(state.calendarYear, state.calendarMonth, day);
        const item = daysByDate[dateValue];
        const selectedClass = isInSelectedRange(dateValue) ? "in-range" : "";
        cells.push(`
            <button class="day-cell ${availabilityClass(item)} ${selectedClass}" type="button" data-date="${dateValue}">
                <span class="day-number">${day}</span>
                <span class="availability-note">${item ? `${item.available_rooms}/${item.total_rooms} rooms` : "No rooms"}</span>
            </button>
        `);
    }
    grid.innerHTML = cells.join("");
    grid.querySelectorAll("[data-date]").forEach((button) => {
        button.addEventListener("click", () => handleDateClick(button.dataset.date));
    });
}

function handleDateClick(dateValue) {
    if (isAdminLike()) {
        state.selectedDate = dateValue;
        if (!state.rangeStart || (state.rangeStart && state.rangeEnd && state.rangeStart !== state.rangeEnd)) {
            state.rangeStart = dateValue;
            state.rangeEnd = dateValue;
        } else if (dateValue < state.rangeStart) {
            state.rangeEnd = state.rangeStart;
            state.rangeStart = dateValue;
        } else {
            state.rangeEnd = dateValue;
        }
        drawCalendar();
        loadAdminDateDetails(dateValue);
        return;
    }
    if (!state.rangeStart || (state.rangeStart && state.rangeEnd && state.rangeStart !== state.rangeEnd)) {
        state.rangeStart = dateValue;
        state.rangeEnd = dateValue;
    } else if (dateValue < state.rangeStart) {
        state.rangeEnd = state.rangeStart;
        state.rangeStart = dateValue;
    } else {
        state.rangeEnd = dateValue;
    }
    drawCalendar();
    renderCalendarSide();
}

function renderCalendarSide(content = "") {
    const side = document.getElementById("calendar-side");
    if (!side) {
        return;
    }
    const group = currentCalendarGroup();
    if (!group) {
        side.innerHTML = `<div class="empty-state">No building data.</div>`;
        return;
    }
    if (isAdminLike()) {
        side.innerHTML = content || `
            <div class="details-list">
                <div>
                    <h3 style="margin:0 0 6px">${escapeHtml(state.prefix)} Availability</h3>
                    <p class="item-meta">Select one date for same-day booking or select a second date for a booking range.</p>
                </div>
                <div class="detail-row"><span class="detail-label">Total rooms</span><span class="detail-value">${group.total_rooms}</span></div>
                <div class="detail-row"><span class="detail-label">Month</span><span class="detail-value">${monthName(state.calendarYear, state.calendarMonth)}</span></div>
                <div class="detail-row"><span class="detail-label">Selected dates</span><span class="detail-value">${escapeHtml(selectedRangeText())}</span></div>
            </div>
        `;
        return;
    }
    const selectedText = selectedRangeText();
    side.innerHTML = `
        <div class="details-list">
            <div>
                <h3 style="margin:0 0 6px">Request Schedule</h3>
                <p class="item-meta">Select one date for same-day request or select another date for a range.</p>
            </div>
            <div class="detail-row"><span class="detail-label">Building</span><span class="detail-value">${escapeHtml(state.prefix)}</span></div>
            <div class="detail-row"><span class="detail-label">Selected dates</span><span class="detail-value">${escapeHtml(selectedText)}</span></div>
            <div class="detail-row"><span class="detail-label">Privacy</span><span class="detail-value">Only availability is shown. Booking names and details are hidden.</span></div>
        </div>
    `;
    const requestButton = document.getElementById("request-booking-btn");
    if (requestButton) {
        requestButton.disabled = !state.rangeStart;
    }
}

async function loadAdminDateDetails(dateValue) {
    renderCalendarSide(`<div class="loading-state">Loading details...</div>`);
    try {
        const data = await apiFetch(`/api/bookings/availability/details/?date=${dateValue}&prefix=${encodeURIComponent(state.prefix)}`);
        const rows = data.bookings || [];
        renderCalendarSide(`
            <div class="details-list">
                <div>
                    <h3 style="margin:0 0 6px">${escapeHtml(state.prefix)} - ${escapeHtml(dateValue)}</h3>
                    <p class="item-meta">${rows.length} booking${rows.length === 1 ? "" : "s"} touching this date.</p>
                    <p class="item-meta">Selected booking range: ${escapeHtml(selectedRangeText())}</p>
                </div>
                ${rows.length ? rows.map((booking) => `
                    <article class="item-card">
                        <div class="item-main">
                            <div>
                                <h4 class="item-title">${escapeHtml(booking.room_name)}</h4>
                                <p class="item-meta">${escapeHtml(booking.guest_name || "Guest")} - ${formatDateTime(booking.arrival_at)} to ${formatDateTime(booking.departure_at)}</p>
                            </div>
                            <span class="status-chip ${booking.status}">${titleCase(booking.status)}</span>
                        </div>
                    </article>
                `).join("") : `<div class="empty-state">No bookings on this date.</div>`}
            </div>
        `);
    } catch (error) {
        renderCalendarSide(`<div class="empty-state">${escapeHtml(error.message)}</div>`);
    }
}

function unwrapList(data) {
    if (Array.isArray(data)) {
        return data;
    }
    if (Array.isArray(data?.results)) {
        return data.results;
    }
    return [];
}

function nextPageUrl(data) {
    if (!data || Array.isArray(data)) {
        return "";
    }
    if (!data.next) {
        return "";
    }
    try {
        const parsed = new URL(data.next, window.location.origin);
        return `${parsed.pathname}${parsed.search}`;
    } catch (error) {
        return data.next;
    }
}

async function fetchAllPaginated(endpoint) {
    const rows = [];
    let nextUrl = endpoint;
    while (nextUrl) {
        const data = await apiFetch(nextUrl);
        rows.push(...unwrapList(data));
        nextUrl = nextPageUrl(data);
    }
    return rows;
}

function bookingsEndpoint() {
    const params = new URLSearchParams({ page_size: "50" });
    if (state.bookingStatusFilter !== "all") params.set("status", state.bookingStatusFilter);
    if (state.bookingPrefixFilter !== "all") params.set("prefix", state.bookingPrefixFilter);
    if (state.bookingArrivalFrom) params.set("arrival_from", state.bookingArrivalFrom);
    if (state.bookingDepartureTo) params.set("departure_to", state.bookingDepartureTo);
    return `/api/bookings/?${params.toString()}`;
}

function bookingSheetDateRange() {
    const fallback = currentMonthRange();
    return {
        start: state.bookingArrivalFrom || fallback.start,
        end: state.bookingDepartureTo || fallback.end,
    };
}

function bookingSheetEndpoint() {
    const params = new URLSearchParams({ page_size: "100" });
    if (state.bookingStatusFilter !== "all") params.set("status", state.bookingStatusFilter);
    if (state.bookingPrefixFilter !== "all") params.set("prefix", state.bookingPrefixFilter);
    return `/api/bookings/?${params.toString()}`;
}

function chargeSheetEndpoint() {
    const params = new URLSearchParams({ page_size: "100" });
    if (state.chargeSheetPrefixFilter !== "all") params.set("prefix", state.chargeSheetPrefixFilter);
    if (state.chargeSheetPaymentFilter !== "all") params.set("payment", state.chargeSheetPaymentFilter);
    if (state.chargeSheetCheckoutFrom) params.set("checkout_from", state.chargeSheetCheckoutFrom);
    if (state.chargeSheetCheckoutTo) params.set("checkout_to", state.chargeSheetCheckoutTo);
    if (state.chargeSheetSearch) params.set("search", state.chargeSheetSearch);
    if (state.chargeSheetOrdering) params.set("ordering", state.chargeSheetOrdering);
    return `/api/bookings/charge-sheet/?${params.toString()}`;
}

function bookingDisplayId(booking) {
    const reference = String(booking.booking_reference_number || "").trim();
    if (reference) return reference;
    const id = String(booking.id || "").trim();
    return id ? id.padStart(6, "0") : "-";
}

function sheetExportButtons(sheetName) {
    return `
        <button class="outline-btn compact-btn" type="button" data-sheet-export="${sheetName}-excel">Download Excel</button>
        <button class="outline-btn compact-btn" type="button" data-sheet-export="${sheetName}-pdf">Download PDF</button>
        <button class="outline-btn compact-btn" type="button" data-sheet-share="${sheetName}">Share</button>
    `;
}

function sheetLegend(items) {
    return `
        <div class="sheet-legend" aria-label="Sheet legend">
            ${items.map((item) => `
                <span class="sheet-legend-item">
                    <span class="sheet-legend-swatch ${escapeHtml(item.className)}" aria-hidden="true"></span>
                    ${escapeHtml(item.label)}
                </span>
            `).join("")}
        </div>
    `;
}

function bookingSheetLegendHtml() {
    return sheetLegend([
        { className: "available", label: "Available for create" },
        { className: "booked", label: "Booked" },
        { className: "partial", label: "Available after cooling" },
        { className: "expired", label: "Expired - delete only" },
    ]);
}

function chargeSheetLegendHtml() {
    return sheetLegend([
        { className: "normal-row", label: "Editable booking" },
        { className: "expired", label: "Expired - delete only" },
        { className: "selected", label: "Selected row" },
    ]);
}

function filenameTimestamp() {
    return new Date().toISOString().slice(0, 16).replace("T", "-").replace(":", "");
}

function safeFilename(title, extension) {
    const base = String(title || "sheet")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "") || "sheet";
    return `${base}-${filenameTimestamp()}.${extension}`;
}

function exportTableClone(tableSelector) {
    const table = document.querySelector(tableSelector);
    if (!table) {
        toast("No sheet data available to download.", "error");
        return null;
    }
    const clone = table.cloneNode(true);

    clone.querySelectorAll("input, textarea, select").forEach((control) => {
        control.replaceWith(document.createTextNode(control.value || ""));
    });
    clone.querySelectorAll(".sheet-booking-pill").forEach((button) => {
        const span = document.createElement("span");
        span.textContent = button.textContent.trim();
        button.replaceWith(span);
    });
    clone.querySelectorAll(".sheet-inline-actions, .sheet-create-btn").forEach((node) => node.remove());

    const actionIndexes = [];
    clone.querySelectorAll("thead th").forEach((header, index) => {
        const text = header.textContent.trim().toLowerCase();
        if (header.classList.contains("sheet-actions-col") || text === "edit" || text === "actions") {
            actionIndexes.push(index);
        }
    });
    actionIndexes.reverse().forEach((index) => {
        clone.querySelectorAll("tr").forEach((row) => row.children[index]?.remove());
    });

    clone.querySelectorAll("[data-charge-sort], [tabindex], [aria-sort]").forEach((node) => {
        node.removeAttribute("data-charge-sort");
        node.removeAttribute("tabindex");
        node.removeAttribute("aria-sort");
    });
    clone.querySelectorAll("[class]").forEach((node) => {
        node.removeAttribute("class");
    });
    return clone;
}

function downloadBlob(filename, content, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function downloadSheetExcel(tableSelector, title) {
    const table = exportTableClone(tableSelector);
    if (!table) {
        return;
    }
    const html = `
        <!doctype html>
        <html>
            <head>
                <meta charset="utf-8">
                <style>
                    table { border-collapse: collapse; }
                    th, td { border: 1px solid #b7c6d8; padding: 6px 8px; vertical-align: top; }
                    th { background: #dceeff; font-weight: 700; }
                </style>
            </head>
            <body>
                <h2>${escapeHtml(title)}</h2>
                ${table.outerHTML}
            </body>
        </html>
    `;
    downloadBlob(safeFilename(title, "xls"), `\ufeff${html}`, "application/vnd.ms-excel;charset=utf-8");
    toast("Excel download started.");
}

function downloadSheetPdf(tableSelector, title) {
    const table = exportTableClone(tableSelector);
    if (!table) {
        return;
    }
    const printWindow = window.open("", "_blank");
    if (!printWindow) {
        toast("Allow pop-ups to download PDF.", "error");
        return;
    }
    printWindow.document.write(`
        <!doctype html>
        <html>
            <head>
                <meta charset="utf-8">
                <title>${escapeHtml(title)}</title>
                <style>
                    @page { size: A4 landscape; margin: 10mm; }
                    * { box-sizing: border-box; }
                    body { margin: 0; font-family: Arial, sans-serif; color: #172033; }
                    h2 { margin: 0 0 12px; font-size: 18px; }
                    table { width: 100%; border-collapse: collapse; font-size: 9px; }
                    th, td { border: 1px solid #b7c6d8; padding: 4px 5px; vertical-align: top; word-break: break-word; }
                    th { background: #dceeff; color: #0f4f86; font-weight: 700; }
                </style>
            </head>
            <body>
                <h2>${escapeHtml(title)}</h2>
                ${table.outerHTML}
            </body>
        </html>
    `);
    printWindow.document.close();
    printWindow.focus();
    window.setTimeout(() => {
        printWindow.print();
    }, 250);
}

function handleSheetExport(exportType) {
    if (exportType === "booking-excel") {
        downloadSheetExcel("#bookings-sheet table", "Booking Sheet");
    } else if (exportType === "booking-pdf") {
        downloadSheetPdf("#bookings-sheet table", "Booking Sheet");
    } else if (exportType === "charge-excel") {
        downloadSheetExcel("#charge-sheet table", "Charges Sheet");
    } else if (exportType === "charge-pdf") {
        downloadSheetPdf("#charge-sheet table", "Charges Sheet");
    }
}

function bookingSharePayload(validity = "1w") {
    const range = bookingSheetDateRange();
    const filters = {
        arrival_from: range.start,
        departure_to: range.end,
    };
    if (state.bookingStatusFilter !== "all") {
        filters.status = state.bookingStatusFilter;
    }
    if (state.bookingPrefixFilter !== "all") {
        filters.prefix = state.bookingPrefixFilter;
    }
    return {
        share_type: "booking_sheet",
        title: "Booking Sheet",
        validity,
        filters,
    };
}

function chargeSheetSharePayload(validity = "1w") {
    const filters = {};
    if (state.chargeSheetPrefixFilter !== "all") {
        filters.prefix = state.chargeSheetPrefixFilter;
    }
    if (state.chargeSheetPaymentFilter !== "all") {
        filters.payment = state.chargeSheetPaymentFilter;
    }
    if (state.chargeSheetCheckoutFrom) {
        filters.checkout_from = state.chargeSheetCheckoutFrom;
    }
    if (state.chargeSheetCheckoutTo) {
        filters.checkout_to = state.chargeSheetCheckoutTo;
    }
    if (state.chargeSheetSearch) {
        filters.search = state.chargeSheetSearch;
    }
    if (state.chargeSheetOrdering) {
        filters.ordering = state.chargeSheetOrdering;
    }
    return {
        share_type: "charge_sheet",
        title: "Charges Sheet",
        validity,
        filters,
    };
}

function sheetSharePayload(sheetName, validity = "1w") {
    return sheetName === "charge"
        ? chargeSheetSharePayload(validity)
        : bookingSharePayload(validity);
}

async function copyTextToClipboard(value) {
    if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(value);
        return;
    }
    const input = document.createElement("input");
    input.value = value;
    document.body.appendChild(input);
    input.select();
    document.execCommand("copy");
    input.remove();
}

function openShareLinkModal(data, sheetName) {
    const url = data.url;
    const title = sheetName === "charge" ? "Share Charges Sheet" : "Share Booking Sheet";
    const expiresText = data.expires_at ? `Valid until ${escapeHtml(formatDateTime(data.expires_at))}` : "";
    openActionModal({
        title,
        body: `
            <div class="details-list">
                <p class="item-meta">Anyone with this link can view this read-only ${sheetName === "charge" ? "charges" : "booking"} sheet until it expires.</p>
                ${expiresText ? `<div class="status-message success">${expiresText}</div>` : ""}
                <div class="share-link-row">
                    <div class="field-row">
                        <label for="share-link-url">Share URL</label>
                        <input id="share-link-url" value="${htmlValue(url)}" readonly>
                    </div>
                    <button class="outline-btn" type="button" id="open-share-link">Open</button>
                </div>
            </div>
        `,
        confirmText: "Copy Link",
        confirmClass: "primary-btn",
        onBind: () => {
            const input = document.getElementById("share-link-url");
            input?.focus();
            input?.select();
            document.getElementById("open-share-link")?.addEventListener("click", () => {
                window.open(url, "_blank", "noopener");
            });
        },
        onConfirm: async () => {
            await copyTextToClipboard(url);
            toast("Share link copied.");
        },
    });
}

function openShareOptionsModal(sheetName) {
    const title = sheetName === "charge" ? "Share Charges Sheet" : "Share Booking Sheet";
    openActionModal({
        title,
        body: `
            <div class="details-list">
                <p class="item-meta">Choose how long this read-only shared URL should remain valid.</p>
                <div class="field-row">
                    <label for="share-validity">Valid for</label>
                    <select id="share-validity">
                        <option value="24h">24 hours</option>
                        <option value="1w" selected>1 week</option>
                        <option value="1m">1 month</option>
                    </select>
                </div>
            </div>
        `,
        confirmText: "Generate Link",
        confirmClass: "primary-btn",
        onConfirm: async () => {
            const validity = document.getElementById("share-validity")?.value || "1w";
            const data = await createSheetShareLink(sheetName, validity);
            window.setTimeout(() => openShareLinkModal(data, sheetName), 0);
        },
    });
}

async function createSheetShareLink(sheetName, validity = "1w") {
    const data = await apiFetch("/api/bookings/share-links/", {
        method: "POST",
        body: sheetSharePayload(sheetName, validity),
    });
    if (!data?.url) {
        throw new Error("Share link could not be generated.");
    }
    return data;
}

async function createBookingShareLink(sheetName = "booking") {
    try {
        openShareOptionsModal(sheetName);
    } catch (error) {
        toast(error.message, "error");
    }
}

function bookingCardHtml(booking) {
    const expired = booking.status === "expired" || isPastDateTime(booking.departure_at);
    return `
        <article class="item-card" data-booking-id="${booking.id}">
            <div class="item-main">
                <div>
                    <h3 class="item-title">${escapeHtml(booking.visitor_name || "Visitor")}</h3>
                    <p class="item-meta">Booking ID: ${escapeHtml(bookingDisplayId(booking))}</p>
                    <p class="item-meta">${escapeHtml(booking.room_name)} - ${formatDateRange(booking)}</p>
                    <p class="item-meta">Requestor: ${escapeHtml(booking.requestor_name || "-")} - Created by: ${escapeHtml(booking.created_by_name || "-")}</p>
                </div>
                <span class="status-chip ${booking.status}">${titleCase(booking.status)}</span>
            </div>
            <div class="card-actions inline-card-actions">
                ${expired ? "" : `<button class="outline-btn compact-btn" type="button" data-booking-action="edit" data-id="${booking.id}">Edit</button>`}
                <button class="danger-btn compact-btn" type="button" data-booking-action="delete" data-id="${booking.id}">Delete</button>
            </div>
        </article>
    `;
}

function updateBookingScrollState(message = "") {
    const sentinel = document.getElementById("bookings-sentinel");
    if (!sentinel) {
        return;
    }
    if (message) {
        sentinel.innerHTML = message;
        return;
    }
    if (!state.bookingLoadedCount) {
        sentinel.innerHTML = "";
        return;
    }
    if (state.bookingLoading && state.bookingNextUrl) {
        sentinel.innerHTML = `<div class="loading-state compact">Loading more bookings...</div>`;
    } else if (state.bookingNextUrl) {
        sentinel.innerHTML = `<div class="scroll-hint">Scroll to load more bookings.</div>`;
    } else {
        sentinel.innerHTML = `<div class="scroll-hint">All loaded.</div>`;
    }
}

function setupBookingInfiniteScroll() {
    if (state.bookingInfiniteObserver) {
        state.bookingInfiniteObserver.disconnect();
        state.bookingInfiniteObserver = null;
    }
    const sentinel = document.getElementById("bookings-sentinel");
    if (!sentinel) {
        return;
    }
    if (!("IntersectionObserver" in window)) {
        sentinel.innerHTML = `<button class="outline-btn" type="button" id="load-more-bookings">Load More</button>`;
        document.getElementById("load-more-bookings")?.addEventListener("click", () => loadBookings({ reset: false }));
        return;
    }
    state.bookingInfiniteObserver = new IntersectionObserver((entries) => {
        if (entries.some((entry) => entry.isIntersecting) && state.bookingNextUrl && !state.bookingLoading) {
            loadBookings({ reset: false });
        }
    }, { rootMargin: "260px 0px" });
    state.bookingInfiniteObserver.observe(sentinel);
}

function renderBookingsView() {
    const statusTabs = [["all", "All"], ["active", "Active"], ["expired", "Expired"]];
    const isChargeSheet = state.bookingViewMode === "charge_sheet";
    viewRoot().classList.toggle("wide-dashboard", state.bookingViewMode === "sheet" || isChargeSheet);
    viewRoot().innerHTML = `
        <div class="section-header">
            <div>
                <h2>Bookings</h2>
                <p>Create and inspect direct room bookings.</p>
            </div>
            <div class="header-actions">
                <button class="primary-btn" id="create-booking">Create Booking</button>
                <button class="outline-btn" id="refresh-bookings">Refresh</button>
            </div>
        </div>
        <div class="segmented view-tabs" role="tablist" aria-label="Bookings view">
            <button class="segment-btn ${state.bookingViewMode === "cards" ? "active" : ""}" data-booking-view="cards">Cards</button>
            <button class="segment-btn ${state.bookingViewMode === "sheet" ? "active" : ""}" data-booking-view="sheet">Sheet View</button>
            <button class="segment-btn ${isChargeSheet ? "active" : ""}" data-booking-view="charge_sheet">Charges Sheet</button>
        </div>
        ${isChargeSheet ? `
            <section class="surface filter-panel">
                <div class="filter-grid charge-filter-grid">
                    <div class="field-row">
                        <label for="charge-sheet-search">Search</label>
                        <input id="charge-sheet-search" type="search" placeholder="Reference, requestor, guest, purpose, budget..." value="${htmlValue(state.chargeSheetSearch)}">
                    </div>
                    <div class="field-row">
                        <label for="charge-sheet-prefix">Building</label>
                        <select id="charge-sheet-prefix">
                            <option value="all" ${state.chargeSheetPrefixFilter === "all" ? "selected" : ""}>All buildings</option>
                            ${BUILDINGS.map((building) => `<option value="${building}" ${state.chargeSheetPrefixFilter === building ? "selected" : ""}>${building}</option>`).join("")}
                        </select>
                    </div>
                    <div class="field-row">
                        <label for="charge-sheet-payment">Payment</label>
                        <select id="charge-sheet-payment">
                            <option value="all" ${state.chargeSheetPaymentFilter === "all" ? "selected" : ""}>All</option>
                            <option value="received" ${state.chargeSheetPaymentFilter === "received" ? "selected" : ""}>Received</option>
                            <option value="pending" ${state.chargeSheetPaymentFilter === "pending" ? "selected" : ""}>Pending</option>
                        </select>
                    </div>
                    <div class="field-row">
                        <label for="charge-sheet-checkout-from">Check out from</label>
                        <input id="charge-sheet-checkout-from" type="date" value="${htmlValue(state.chargeSheetCheckoutFrom)}">
                    </div>
                    <div class="field-row">
                        <label for="charge-sheet-checkout-to">Check out to</label>
                        <input id="charge-sheet-checkout-to" type="date" value="${htmlValue(state.chargeSheetCheckoutTo)}">
                    </div>
                    <div class="field-row">
                        <label for="charge-sheet-sort">Sort</label>
                        <select id="charge-sheet-sort">
                            ${chargeSheetSortOptions().map(([value, label]) => `<option value="${value}" ${state.chargeSheetOrdering === value ? "selected" : ""}>${label}</option>`).join("")}
                        </select>
                    </div>
                    <div class="filter-actions">
                        <button class="primary-btn" id="apply-charge-sheet-filters" type="button">Apply</button>
                        <button class="outline-btn" id="clear-charge-sheet-filters" type="button">Clear</button>
                    </div>
                </div>
            </section>
            <section class="surface sheet-panel">
                <div id="charge-sheet" class="sheet-shell"><div class="loading-state">Loading charges sheet...</div></div>
            </section>
        ` : `
            <section class="surface filter-panel">
                <div>
                    <p class="filter-label">Status</p>
                    ${filterTabs(state.bookingStatusFilter, statusTabs)}
                </div>
                <div class="filter-grid">
                    <div class="field-row">
                        <label for="booking-prefix-filter">Building</label>
                        <select id="booking-prefix-filter">
                            <option value="all" ${state.bookingPrefixFilter === "all" ? "selected" : ""}>All buildings</option>
                            ${BUILDINGS.map((building) => `<option value="${building}" ${state.bookingPrefixFilter === building ? "selected" : ""}>${building}</option>`).join("")}
                        </select>
                    </div>
                    <div class="field-row">
                        <label for="booking-arrival-from">Arrival from</label>
                        <input id="booking-arrival-from" type="date" value="${escapeHtml(state.bookingArrivalFrom)}">
                    </div>
                    <div class="field-row">
                        <label for="booking-departure-to">Departure to</label>
                        <input id="booking-departure-to" type="date" value="${escapeHtml(state.bookingDepartureTo)}">
                    </div>
                    <div class="filter-actions">
                        <button class="outline-btn" id="clear-booking-filters" type="button">Clear Filters</button>
                    </div>
                </div>
            </section>
            ${state.bookingViewMode === "sheet" ? `
            <section class="surface sheet-panel">
                <div id="bookings-sheet" class="sheet-shell"><div class="loading-state">Loading sheet view...</div></div>
            </section>
            ` : `
            <section class="surface side-panel">
                <div id="bookings-list" class="card-list"><div class="loading-state">Loading bookings...</div></div>
                <div id="bookings-sentinel" class="scroll-sentinel"></div>
            </section>
            `}
        `}
    `;
    appRoot.querySelectorAll("[data-booking-view]").forEach((button) => {
        button.addEventListener("click", () => {
            state.bookingViewMode = button.dataset.bookingView;
            syncRouteHash();
            state.chargeSheetEditingId = "";
            renderBookingsView();
        });
    });
    document.getElementById("create-booking").addEventListener("click", () => openAdminBookingForm());
    document.getElementById("refresh-bookings").addEventListener("click", refreshBookingsView);
    if (isChargeSheet) {
        bindChargeSheetFilters();
        loadChargeSheetView();
    } else if (state.bookingViewMode === "sheet") {
        bindFilterTabs(viewRoot(), (filter) => {
            state.bookingStatusFilter = filter;
            renderBookingsView();
        });
        bindBookingFilters();
        loadBookingSheetView();
    } else {
        bindFilterTabs(viewRoot(), (filter) => {
            state.bookingStatusFilter = filter;
            renderBookingsView();
        });
        bindBookingFilters();
        document.getElementById("bookings-list").addEventListener("click", (event) => {
            const actionButton = event.target.closest("[data-booking-action]");
            if (actionButton) {
                handleBookingInlineAction(actionButton.dataset.bookingAction, actionButton.dataset.id);
                return;
            }
            const card = event.target.closest("[data-booking-id]");
            if (card) {
                openBookingDetails(card.dataset.bookingId);
            }
        });
        setupBookingInfiniteScroll();
        loadBookings({ reset: true });
    }
}

function bindBookingFilters() {
    document.getElementById("booking-prefix-filter").addEventListener("change", (event) => {
        state.bookingPrefixFilter = event.target.value;
        refreshBookingsView();
    });
    document.getElementById("booking-arrival-from").addEventListener("change", (event) => {
        state.bookingArrivalFrom = event.target.value;
        refreshBookingsView();
    });
    document.getElementById("booking-departure-to").addEventListener("change", (event) => {
        state.bookingDepartureTo = event.target.value;
        refreshBookingsView();
    });
    document.getElementById("clear-booking-filters").addEventListener("click", () => {
        state.bookingStatusFilter = "all";
        state.bookingPrefixFilter = "all";
        state.bookingArrivalFrom = "";
        state.bookingDepartureTo = "";
        renderBookingsView();
    });
}

async function refreshBookingsView() {
    if (state.bookingViewMode === "charge_sheet") {
        await loadChargeSheetView();
        return;
    }
    if (state.bookingViewMode === "sheet") {
        await loadBookingSheetView();
        return;
    }
    await loadBookings({ reset: true });
}

function chargeSheetSortOptions() {
    return [
        ["-created_at", "Date created - newest first"],
        ["created_at", "Date created - oldest first"],
        ["check_in", "Check in - oldest first"],
        ["-check_in", "Check in - newest first"],
        ["check_out", "Check out - oldest first"],
        ["-check_out", "Check out - newest first"],
        ["serial_no", "Serial no."],
        ["booking_reference_id", "Booking reference"],
        ["requestor_name", "Requestor name"],
        ["guest_name", "Guest name"],
        ["purpose_event", "Purpose/Event"],
        ["room_charges_amount", "Room charges"],
        ["attender_charges_amount", "Attender charges"],
        ["total_charges", "Total charges"],
        ["payment_received_date", "Payment received date"],
        ["budget_head_name", "Budget head name"],
    ];
}

function bindChargeSheetFilters() {
    const applyFilters = () => {
        state.chargeSheetSearch = document.getElementById("charge-sheet-search")?.value?.trim() || "";
        state.chargeSheetPrefixFilter = document.getElementById("charge-sheet-prefix")?.value || "all";
        state.chargeSheetPaymentFilter = document.getElementById("charge-sheet-payment")?.value || "all";
        state.chargeSheetCheckoutFrom = document.getElementById("charge-sheet-checkout-from")?.value || "";
        state.chargeSheetCheckoutTo = document.getElementById("charge-sheet-checkout-to")?.value || "";
        state.chargeSheetOrdering = document.getElementById("charge-sheet-sort")?.value || "-created_at";
        state.chargeSheetEditingId = "";
        loadChargeSheetView();
    };
    document.getElementById("apply-charge-sheet-filters")?.addEventListener("click", applyFilters);
    document.getElementById("charge-sheet-sort")?.addEventListener("change", applyFilters);
    document.getElementById("charge-sheet-search")?.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            applyFilters();
        }
    });
    document.getElementById("clear-charge-sheet-filters")?.addEventListener("click", () => {
        state.chargeSheetPrefixFilter = "all";
        state.chargeSheetPaymentFilter = "all";
        state.chargeSheetCheckoutFrom = "";
        state.chargeSheetCheckoutTo = "";
        state.chargeSheetSearch = "";
        state.chargeSheetOrdering = "-created_at";
        state.chargeSheetEditingId = "";
        renderBookingsView();
    });
}

function chargeSheetHeader(field, label) {
    const activeField = state.chargeSheetOrdering.startsWith("-")
        ? state.chargeSheetOrdering.slice(1)
        : state.chargeSheetOrdering;
    const isActive = activeField === field;
    const direction = state.chargeSheetOrdering.startsWith("-") ? "desc" : "asc";
    const classes = ["sortable-header"];
    if (isActive) {
        classes.push("sorted", direction);
    }
    return `
        <th class="${classes.join(" ")}" data-charge-sort="${field}" tabindex="0" aria-sort="${isActive ? (direction === "desc" ? "descending" : "ascending") : "none"}">
            <span class="header-label">${escapeHtml(label)}</span>
            <span class="sort-caret" aria-hidden="true"></span>
        </th>
    `;
}

function setChargeSheetOrdering(field) {
    const activeField = state.chargeSheetOrdering.startsWith("-")
        ? state.chargeSheetOrdering.slice(1)
        : state.chargeSheetOrdering;
    if (activeField === field) {
        state.chargeSheetOrdering = state.chargeSheetOrdering.startsWith("-") ? field : `-${field}`;
    } else {
        state.chargeSheetOrdering = field;
    }
    const sortSelect = document.getElementById("charge-sheet-sort");
    if (sortSelect) {
        sortSelect.value = state.chargeSheetOrdering;
    }
    state.chargeSheetEditingId = "";
    loadChargeSheetView();
}

function chargeSheetInput(field, value, type = "text") {
    const numberAttrs = type === "number" ? ` min="0" step="0.01"` : "";
    return `<input class="sheet-inline-input" data-charge-field="${field}" type="${type}"${numberAttrs} value="${htmlValue(value)}">`;
}

function chargeSheetTextarea(field, value) {
    return `<textarea class="sheet-inline-input compact" data-charge-field="${field}">${htmlValue(value)}</textarea>`;
}

function chargeSheetEditableCell(row, field, type = "text") {
    if (isChargeSheetRowExpired(row) || String(state.chargeSheetEditingId) !== String(row.id)) {
        return escapeHtml(valueOrDash(row[field]));
    }
    if (field === "purpose_event") {
        return chargeSheetTextarea(field, row[field]);
    }
    return chargeSheetInput(field, row[field] || "", type);
}

function isChargeSheetRowExpired(row) {
    return isPastDateTime(row?.check_out);
}

function chargeSheetRowHtml(row) {
    const expired = isChargeSheetRowExpired(row);
    const editing = !expired && String(state.chargeSheetEditingId) === String(row.id);
    const selected = String(state.chargeSheetSelectedId) === String(row.id);
    return `
        <tr class="${[selected ? "selected-row" : "", expired ? "expired-row" : ""].filter(Boolean).join(" ")}" data-charge-row-id="${row.id}" aria-selected="${selected ? "true" : "false"}">
            <td>${escapeHtml(row.serial_no || row.id)}</td>
            <td>${escapeHtml(formatDateTime(row.check_in))}</td>
            <td>${escapeHtml(formatDateTime(row.check_out))}</td>
            <td>${escapeHtml(row.booking_reference_id || "-")}</td>
            <td>${chargeSheetEditableCell(row, "requestor_name")}</td>
            <td>${chargeSheetEditableCell(row, "guest_name")}</td>
            <td>${chargeSheetEditableCell(row, "purpose_event")}</td>
            <td>${escapeHtml(buildingRoomValue(row.delta, "Delta"))}</td>
            <td>${escapeHtml(buildingRoomValue(row.gamma, "Gamma"))}</td>
            <td>${escapeHtml(buildingRoomValue(row.beta, "Beta"))}</td>
            <td>${chargeSheetEditableCell(row, "room_charges_amount", "number")}</td>
            <td>${chargeSheetEditableCell(row, "attender_charges_amount", "number")}</td>
            <td>${escapeHtml(row.total_charges || "0.00")}</td>
            <td>${editing ? chargeSheetInput("payment_received_date", row.payment_received_date || "", "date") : escapeHtml(row.payment_received_date || "-")}</td>
            <td>${chargeSheetEditableCell(row, "budget_head_name")}</td>
            <td class="sheet-actions-col">
                ${editing ? `
                    <button class="sheet-action-btn" type="button" data-charge-action="save" data-id="${row.id}">Save</button>
                    <button class="sheet-action-btn" type="button" data-charge-action="cancel" data-id="${row.id}">Cancel</button>
                ` : `
                    ${expired ? "" : `<button class="sheet-action-btn" type="button" data-charge-action="edit" data-id="${row.id}">Edit</button>`}
                    <button class="sheet-action-btn danger" type="button" data-charge-action="delete" data-id="${row.id}" data-booking-id="${row.booking}">Delete</button>
                `}
            </td>
        </tr>
    `;
}

function setChargeSheetSelectedRow(rowId, shell) {
    state.chargeSheetSelectedId = String(rowId || "");
    shell.querySelectorAll("[data-charge-row-id]").forEach((row) => {
        const selected = row.dataset.chargeRowId === state.chargeSheetSelectedId;
        row.classList.toggle("selected-row", selected);
        row.setAttribute("aria-selected", selected ? "true" : "false");
    });
}

function clearChargeSheetSelectedRow() {
    if (!state.chargeSheetSelectedId) {
        return;
    }
    state.chargeSheetSelectedId = "";
    document.querySelectorAll(".charge-sheet-table .selected-row").forEach((row) => {
        row.classList.remove("selected-row");
    });
}

function renderChargeSheetRows(shell) {
    const rows = state.chargeSheetRows || [];
    if (!rows.length) {
        shell.innerHTML = `<div class="empty-state">No charge sheet rows match the selected filters.</div>`;
        return;
    }
    shell.innerHTML = `
        <div class="sheet-summary">
            <div>
                <h3>Charges Sheet</h3>
                <p>Booking charge and payment register</p>
            </div>
            <div class="sheet-summary-actions">
                <span>${rows.length} row${rows.length === 1 ? "" : "s"}</span>
                ${sheetExportButtons("charge")}
            </div>
        </div>
        ${chargeSheetLegendHtml()}
        <div class="sheet-scroll charge-sheet-scroll" role="region" aria-label="Booking charges sheet">
            <table class="excel-table charge-sheet-table">
                <thead>
                    <tr>
                        ${chargeSheetHeader("serial_no", "Serial NO")}
                        ${chargeSheetHeader("check_in", "Check in")}
                        ${chargeSheetHeader("check_out", "Check out")}
                        ${chargeSheetHeader("booking_reference_id", "Booking Reference ID")}
                        ${chargeSheetHeader("requestor_name", "Requestor Name")}
                        ${chargeSheetHeader("guest_name", "Name of Guest")}
                        ${chargeSheetHeader("purpose_event", "Purpose(Event)")}
                        ${chargeSheetHeader("delta", "Delta")}
                        ${chargeSheetHeader("gamma", "Gamma")}
                        ${chargeSheetHeader("beta", "Beta")}
                        ${chargeSheetHeader("room_charges_amount", "Room Charges Amount")}
                        ${chargeSheetHeader("attender_charges_amount", "Attender Charges Amount")}
                        ${chargeSheetHeader("total_charges", "Total Charges")}
                        ${chargeSheetHeader("payment_received_date", "Payment Received Date")}
                        ${chargeSheetHeader("budget_head_name", "Budget Head Name")}
                        <th class="sheet-actions-col">Actions</th>
                    </tr>
                </thead>
                <tbody>${rows.map(chargeSheetRowHtml).join("")}</tbody>
            </table>
        </div>
    `;
}

async function loadChargeSheetView() {
    const shell = document.getElementById("charge-sheet");
    if (!shell) {
        return;
    }
    shell.innerHTML = `<div class="loading-state">Loading charges sheet...</div>`;
    try {
        state.chargeSheetRows = await fetchAllPaginated(chargeSheetEndpoint());
        renderChargeSheetRows(shell);
        bindChargeSheetTable(shell);
    } catch (error) {
        shell.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
    }
}

function bindChargeSheetTable(shell) {
    shell.onclick = async (event) => {
        const exportButton = event.target.closest("[data-sheet-export]");
        if (exportButton) {
            handleSheetExport(exportButton.dataset.sheetExport);
            return;
        }
        const shareButton = event.target.closest("[data-sheet-share]");
        if (shareButton) {
            createBookingShareLink(shareButton.dataset.sheetShare);
            return;
        }
        const sortButton = event.target.closest("[data-charge-sort]");
        if (sortButton) {
            setChargeSheetOrdering(sortButton.dataset.chargeSort);
            return;
        }
        const actionButton = event.target.closest("[data-charge-action]");
        if (!actionButton) {
            return;
        }
        const rowId = actionButton.dataset.id;
        const action = actionButton.dataset.chargeAction;
        if (action === "edit") {
            const row = state.chargeSheetRows.find((item) => String(item.id) === String(rowId));
            if (isChargeSheetRowExpired(row)) {
                toast("Expired bookings can only be deleted.", "error");
                return;
            }
            state.chargeSheetEditingId = rowId;
            renderChargeSheetRows(shell);
            bindChargeSheetTable(shell);
        } else if (action === "cancel") {
            state.chargeSheetEditingId = "";
            renderChargeSheetRows(shell);
            bindChargeSheetTable(shell);
        } else if (action === "save") {
            await saveChargeSheetRow(rowId, shell);
        } else if (action === "delete") {
            const bookingId = actionButton.dataset.bookingId;
            if (bookingId) {
                openDeleteBookingModal(bookingId);
            }
        }
    };
    shell.onkeydown = (event) => {
        if (event.key !== "Enter" && event.key !== " ") {
            return;
        }
        const sortHeader = event.target.closest("[data-charge-sort]");
        if (!sortHeader) {
            return;
        }
        event.preventDefault();
        setChargeSheetOrdering(sortHeader.dataset.chargeSort);
    };
}

async function saveChargeSheetRow(rowId, shell) {
    const rowData = state.chargeSheetRows.find((item) => String(item.id) === String(rowId));
    if (isChargeSheetRowExpired(rowData)) {
        state.chargeSheetEditingId = "";
        toast("Expired bookings can only be deleted.", "error");
        renderChargeSheetRows(shell);
        bindChargeSheetTable(shell);
        return;
    }
    const safeRowId = String(rowId).replaceAll('"', '\\"');
    const row = shell.querySelector(`[data-charge-row-id="${safeRowId}"]`);
    if (!row) {
        return;
    }
    const fieldValue = (field) => row.querySelector(`[data-charge-field="${field}"]`)?.value?.trim() || "";
    const payload = {
        requestor_name: fieldValue("requestor_name"),
        guest_name: fieldValue("guest_name"),
        purpose_event: fieldValue("purpose_event"),
        room_charges_amount: Number(fieldValue("room_charges_amount") || 0),
        attender_charges_amount: Number(fieldValue("attender_charges_amount") || 0),
        payment_received_date: fieldValue("payment_received_date") || null,
        budget_head_name: fieldValue("budget_head_name"),
    };
    try {
        const updated = await apiFetch(`/api/bookings/charge-sheet/${rowId}/`, { method: "PATCH", body: payload });
        state.chargeSheetRows = state.chargeSheetRows.map((item) => String(item.id) === String(rowId) ? updated : item);
        state.chargeSheetEditingId = "";
        toast("Charge sheet row updated.");
        renderChargeSheetRows(shell);
        bindChargeSheetTable(shell);
    } catch (error) {
        toast(error.message, "error");
    }
}

async function refreshVisibleBookingSurface() {
    if (state.view === "bookings") {
        await refreshBookingsView();
    } else if (state.view === "calendar") {
        await loadCalendar();
    }
}

async function loadBookings({ reset = true } = {}) {
    const list = document.getElementById("bookings-list");
    let sentinelMessage = "";
    if (!list || state.bookingLoading) {
        return;
    }
    if (!reset && !state.bookingNextUrl) {
        updateBookingScrollState();
        return;
    }
    state.bookingLoading = true;
    if (reset) {
        state.bookingNextUrl = "";
        state.bookingLoadedCount = 0;
        list.innerHTML = `<div class="loading-state">Loading bookings...</div>`;
        updateBookingScrollState("");
    } else {
        updateBookingScrollState(`<div class="loading-state compact">Loading more bookings...</div>`);
    }
    try {
        const data = await apiFetch(reset ? bookingsEndpoint() : state.bookingNextUrl);
        const rows = unwrapList(data);
        state.bookingNextUrl = nextPageUrl(data);
        if (!rows.length && reset) {
            list.innerHTML = `<div class="empty-state">No bookings match the selected filters.</div>`;
            updateBookingScrollState("");
            return;
        }
        if (reset) {
            list.innerHTML = "";
        }
        list.insertAdjacentHTML("beforeend", rows.map((booking) => bookingCardHtml(booking)).join(""));
        state.bookingLoadedCount += rows.length;
        updateBookingScrollState();
    } catch (error) {
        if (reset) {
            list.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
            sentinelMessage = "";
        } else {
            sentinelMessage = `<div class="empty-state compact">${escapeHtml(error.message)}</div>`;
        }
    } finally {
        state.bookingLoading = false;
        updateBookingScrollState(sentinelMessage);
    }
}

function filteredSheetRooms(rooms) {
    return rooms
        .filter((room) => state.bookingPrefixFilter === "all" || room.prefix === state.bookingPrefixFilter)
        .sort((a, b) => {
            const buildingOrder = BUILDINGS.indexOf(a.prefix) - BUILDINGS.indexOf(b.prefix);
            if (buildingOrder !== 0) return buildingOrder;
            return String(a.number || a.room_number || roomLabel(a)).localeCompare(
                String(b.number || b.room_number || roomLabel(b)),
                undefined,
                { numeric: true, sensitivity: "base" },
            );
        });
}

function bookingCellText(booking) {
    const name = String(booking.visitor_name || "").trim();
    const organisation = String(booking.visitor_organisation || "").trim();
    if (organisation) {
        return `${name} (${organisation})`;
    }
    return name || "Booked";
}

function bookingSheetAvailabilityOnDate(booking, dateValue) {
    const arrivalDate = localIsoDateFromDateTime(booking.arrival_at);
    const departureDate = localIsoDateFromDateTime(booking.departure_at);
    if (!arrivalDate || !departureDate) {
        return null;
    }
    const coolingEnd = addHoursToDateTime(booking.departure_at, SHEET_COOLING_HOURS);
    const coolingEndDate = localIsoDateFromDateTime(coolingEnd);
    const coolingEndsAfterUsableDay = coolingEndDate !== dateValue || localTimeMinutes(coolingEnd) > SHEET_DAY_END_MINUTES;

    if (arrivalDate === departureDate && dateValue === arrivalDate) {
        return coolingEndsAfterUsableDay
            ? { availabilityStatus: "full", availableFrom: null }
            : { availabilityStatus: "partial", availableFrom: coolingEnd };
    }

    if (arrivalDate <= dateValue && dateValue < departureDate) {
        return { availabilityStatus: "full", availableFrom: null };
    }

    if (dateValue === departureDate) {
        return coolingEndsAfterUsableDay
            ? { availabilityStatus: "full", availableFrom: null }
            : { availabilityStatus: "partial", availableFrom: coolingEnd };
    }

    return null;
}

function buildBookingSheetCells(bookings, dates) {
    const dateSet = new Set(dates);
    const cells = new Map();
    bookings.forEach((booking) => {
        if (!booking.room) {
            return;
        }
        dates.forEach((dateValue) => {
            const availability = bookingSheetAvailabilityOnDate(booking, dateValue);
            if (dateSet.has(dateValue) && availability) {
                const key = `${dateValue}:${booking.room}`;
                const entries = cells.get(key) || [];
                entries.push({
                    id: booking.id,
                    text: bookingCellText(booking),
                    status: booking.status,
                    availabilityStatus: availability.availabilityStatus,
                    availableFrom: availability.availableFrom,
                    isExpired: isPastDateTime(booking.departure_at),
                });
                cells.set(key, entries);
            }
        });
    });
    return cells;
}

function sheetCellHtml(entries = [], dateValue = "", room = null) {
    if (!entries.length) {
        return `
            <button
                class="sheet-create-btn"
                type="button"
                data-booking-action="create"
                data-room-id="${room?.id || ""}"
                data-room-prefix="${escapeHtml(room?.prefix || "")}"
                data-date="${escapeHtml(dateValue)}"
            >+ Create</button>
        `;
    }
    const entryById = new Map();
    entries.forEach((entry) => {
        if (!entryById.has(entry.id)) {
            entryById.set(entry.id, entry);
        }
    });
    const hasFullDayBooking = entries.some((entry) => entry.availabilityStatus === "full");
    const availableFromValues = entries
        .filter((entry) => entry.availabilityStatus === "partial" && entry.availableFrom)
        .map((entry) => entry.availableFrom);
    const latestAvailableFrom = availableFromValues.length
        ? new Date(Math.max(...availableFromValues.map((value) => new Date(value).getTime())))
        : null;
    const createAfterHtml = !hasFullDayBooking && latestAvailableFrom ? `
        <button
            class="sheet-create-btn partial"
            type="button"
            data-booking-action="create"
            data-room-id="${room?.id || ""}"
            data-room-prefix="${escapeHtml(room?.prefix || "")}"
            data-date="${escapeHtml(dateValue)}"
            data-arrival-time="${escapeHtml(indiaParts(latestAvailableFrom).time)}"
        >+ Create after ${escapeHtml(formatSheetTime(latestAvailableFrom))}</button>
    ` : "";

    return Array.from(entryById.entries()).map(([id, entry]) => `
        <div class="sheet-booking-entry">
            <button class="sheet-booking-pill ${entry.availabilityStatus === "partial" ? "partial" : ""} ${entry.isExpired ? "expired" : ""}" type="button" data-sheet-booking-id="${id}">${escapeHtml(entry.text)}</button>
            <div class="sheet-inline-actions">
                ${entry.isExpired ? "" : `<button class="sheet-action-btn" type="button" data-booking-action="edit" data-id="${id}">Edit</button>`}
                <button class="sheet-action-btn danger" type="button" data-booking-action="delete" data-id="${id}">Delete</button>
            </div>
        </div>
    `).join("") + createAfterHtml;
}

async function loadBookingSheetView() {
    const shell = document.getElementById("bookings-sheet");
    if (!shell) {
        return;
    }
    shell.innerHTML = `<div class="loading-state">Loading sheet view...</div>`;
    try {
        const range = bookingSheetDateRange();
        const dates = isoDateRange(range.start, range.end);
        if (!dates.length) {
            shell.innerHTML = `<div class="empty-state">Select a valid date range.</div>`;
            return;
        }
        const [rooms, bookings] = await Promise.all([
            fetchRooms(),
            fetchAllPaginated(bookingSheetEndpoint()),
        ]);
        const sheetRooms = filteredSheetRooms(rooms);
        if (!sheetRooms.length) {
            shell.innerHTML = `<div class="empty-state">No rooms found for the selected building.</div>`;
            return;
        }
        const cells = buildBookingSheetCells(bookings, dates);
        const visibleBookingCount = new Set(
            Array.from(cells.values()).flatMap((entries) => entries.map((entry) => entry.id)),
        ).size;
        shell.innerHTML = `
            <div class="sheet-summary">
                <div>
                    <h3>Visitor Room</h3>
                    <p>${formatSheetDate(range.start)} to ${formatSheetDate(range.end)}</p>
                </div>
                <div class="sheet-summary-actions">
                    <span>${visibleBookingCount} booking${visibleBookingCount === 1 ? "" : "s"}</span>
                    ${sheetExportButtons("booking")}
                </div>
            </div>
            ${bookingSheetLegendHtml()}
            <div class="sheet-scroll" role="region" aria-label="Booking sheet view">
                <table class="excel-table">
                    <thead>
                        <tr>
                            <th class="date-col">Dates</th>
                            ${sheetRooms.map((room) => `<th>${escapeHtml(roomLabel(room))}</th>`).join("")}
                        </tr>
                    </thead>
                    <tbody>
                        ${dates.map((dateValue) => `
                            <tr>
                                <th class="date-col">${escapeHtml(formatSheetDate(dateValue))}</th>
                                ${sheetRooms.map((room) => `
                                    <td>${sheetCellHtml(cells.get(`${dateValue}:${room.id}`), dateValue, room)}</td>
                                `).join("")}
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            </div>
        `;
        shell.onclick = (event) => {
            const shareButton = event.target.closest("[data-sheet-share]");
            if (shareButton) {
                createBookingShareLink(shareButton.dataset.sheetShare);
                return;
            }
            const exportButton = event.target.closest("[data-sheet-export]");
            if (exportButton) {
                handleSheetExport(exportButton.dataset.sheetExport);
                return;
            }
            const actionButton = event.target.closest("[data-booking-action]");
            if (actionButton) {
                handleBookingInlineAction(actionButton.dataset.bookingAction, actionButton.dataset.id, actionButton.dataset);
                return;
            }
            const bookingButton = event.target.closest("[data-sheet-booking-id]");
            if (bookingButton) {
                openBookingDetails(bookingButton.dataset.sheetBookingId);
            }
        };
    } catch (error) {
        shell.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
    }
}

function handleBookingInlineAction(action, bookingId, dataset = {}) {
    if (action === "create") {
        const dateValue = dataset.date || todayIso();
        const arrivalTime = dataset.arrivalTime || "10:00";
        openAdminBookingForm({
            room: dataset.roomId || "",
            prefix: dataset.roomPrefix || state.prefix,
            arrival_at: buildIsoDateTime(dateValue, arrivalTime),
            departure_at: buildIsoDateTime(dateValue, "18:00"),
        }, "booking");
        return;
    }
    if (action === "edit") {
        if (dataset.expired === "true") {
            toast("Expired bookings can only be deleted.", "error");
            return;
        }
        openAdminBookingEditForm(bookingId);
    } else if (action === "delete") {
        openDeleteBookingModal(bookingId);
    }
}

async function openAdminBookingEditForm(bookingId) {
    try {
        const [booking, rooms] = await Promise.all([
            apiFetch(`/api/bookings/${bookingId}/`),
            fetchRooms(),
        ]);
        openActionModal({
            title: `Edit Booking #${booking.id}`,
            body: adminBookingFormHtml(booking, "booking"),
            confirmText: "Save Changes",
            confirmClass: "primary-btn",
            wide: true,
            onBind: () => bindAdminBookingForm(rooms, booking.room || "", ""),
            onConfirm: async () => {
                await apiFetch(`/api/bookings/${booking.id}/edit/`, { method: "PATCH", body: readAdminBookingPayload() });
                toast("Booking updated successfully.");
                closeModal();
                await refreshVisibleBookingSurface();
            },
        });
    } catch (error) {
        toast(error.message, "error");
    }
}

function openDeleteBookingModal(bookingId) {
    openActionModal({
        title: "Delete Booking",
        body: `<p class="item-meta">Are you sure you want to permanently delete this booking? This cannot be undone.</p>`,
        confirmText: "Delete Booking",
        confirmClass: "danger-btn",
        onConfirm: async () => {
            await apiFetch(`/api/bookings/${bookingId}/delete/`, { method: "DELETE" });
            toast("Booking deleted successfully.");
            closeModal();
            await refreshVisibleBookingSurface();
        },
    });
}

async function openBookingDetails(bookingId) {
    try {
        const booking = await apiFetch(`/api/bookings/${bookingId}/`);
        const history = booking.edit_history || [];
        openDetailsModal("Booking Details", [
            { section: "Booking" },
            ["ID", bookingDisplayId(booking)],
            ["Status", titleCase(booking.status)],
            ["Room", booking.room_name],
            ["Arrival", formatDateTime(booking.arrival_at)],
            ["Departure", formatDateTime(booking.departure_at)],
            ["Created by", booking.created_by_name],
            ["Created at", formatDateTime(booking.created_at)],
            { section: "Visitor Details" },
            ["Visitor name", booking.visitor_name],
            ["Designation", booking.visitor_designation],
            ["Organisation", booking.visitor_organisation],
            ["Gender", booking.visitor_gender],
            ["Mobile", booking.visitor_mobile],
            ["Email", booking.visitor_email],
            ["Category", titleCase(booking.visitor_category)],
            ["Purpose", booking.purpose_of_visit],
            { section: "Requestor Details" },
            ["Requestor name", booking.requestor_name],
            ["Designation", booking.requestor_designation],
            ["Department", booking.requestor_department],
            ["Mobile", booking.requestor_mobile],
            { section: "Attender Requirement" },
            ["Attender required", yesNo(booking.attender_required)],
            ["Attender count", booking.attender_count_per_day],
            ["Shifts", shiftsText(booking)],
            { section: "Charges" },
            ["Room charges", titleCase(booking.room_charges_status)],
            ["Room charges amount", booking.room_charges_amount],
            ["Attender charges", titleCase(booking.attender_charges_status)],
            ["Attender charges amount", booking.attender_charges_amount],
            { section: "Budget Head" },
            ["Budget head type", titleCase(booking.budget_head_type)],
            ["Budget head value", booking.budget_head_value],
            ["Name / Organisation", booking.budget_head_name],
            ["Department name", booking.budget_head_department_name],
            ["Project code", booking.budget_head_project_code],
            { section: "Logistics" },
            ["Name", booking.logistics_name],
            ["Designation", booking.logistics_designation],
            ["Mobile", booking.logistics_mobile],
            { section: "Edit History" },
            ...(history.length ? history.flatMap((entry) => [
                ["Field", entry.field_label || entry.field_name],
                ["Changed by", entry.edited_by_name || entry.edited_by_email],
                ["Changed at", formatDateTime(entry.edited_at)],
                ["Old value", entry.old_value],
                ["New value", entry.new_value],
            ]) : [["History", "No edit history."]]),
        ]);
    } catch (error) {
        toast(error.message, "error");
    }
}

function adminBookingFormHtml(source = {}, context = "booking") {
    const selectedStart = state.rangeStart || state.selectedDate || todayIso();
    const selectedEnd = state.rangeEnd || state.rangeStart || state.selectedDate || todayIso();
    const arrival = source.arrival_at ? indiaParts(source.arrival_at) : { date: selectedStart, time: "10:00" };
    const departure = source.departure_at ? indiaParts(source.departure_at) : { date: selectedEnd, time: "18:00" };
    const prefix = source.preferred_prefix || source.prefix || state.prefix || BUILDINGS[0];
    const requestMeta = source.id && context === "request" ? `
        <div class="form-section-title">Request Review</div>
        <div class="two-col">
            <div class="field-row"><label>Request ID</label><input value="${htmlValue(source.id)}" readonly></div>
            <div class="field-row"><label>Status</label><input value="${htmlValue(titleCase(source.status))}" readonly></div>
            <div class="field-row"><label>Requester account</label><input value="${htmlValue(source.requester_name || source.requester_email)}" readonly></div>
            <div class="field-row"><label>Requester email</label><input value="${htmlValue(source.requester_email)}" readonly></div>
            <div class="field-row"><label>Requested at</label><input value="${htmlValue(formatDateTime(source.requested_at))}" readonly></div>
            <div class="field-row"><label>Reviewed by</label><input value="${htmlValue(source.reviewed_by_name)}" readonly></div>
            <div class="field-row"><label>Reviewed at</label><input value="${htmlValue(formatDateTime(source.reviewed_at))}" readonly></div>
            <div class="field-row"><label>Assigned booking</label><input value="${htmlValue(source.assigned_room_name || source.approved_booking_id || "")}" readonly></div>
        </div>
        <div class="field-row"><label for="admin-review-remarks">Remarks</label><textarea id="admin-review-remarks" placeholder="Approval, rejection, send-back, or delete remarks">${htmlValue(source.admin_remarks || source.remarks || "")}</textarea></div>
    ` : "";

    return `
        <form id="admin-booking-form" class="field-grid booking-form" novalidate>
            ${requestMeta}
            <div class="form-section-title">Schedule & Room</div>
            <div class="two-col">
                <div class="field-row"><label for="admin-prefix">Building</label><select id="admin-prefix">${BUILDINGS.map((item) => `<option value="${item}" ${item === prefix ? "selected" : ""}>${item}</option>`).join("")}</select></div>
                <div class="field-row"><label for="admin-room">Room</label><select id="admin-room" required><option value="">Loading rooms...</option></select></div>
                <div class="field-row"><label for="admin-arrival-date">Arrival date</label><input id="admin-arrival-date" type="date" value="${htmlValue(arrival.date)}" required></div>
                <div class="field-row"><label for="admin-arrival-time">Arrival time</label><input id="admin-arrival-time" type="time" value="${htmlValue(arrival.time || "10:00")}" required></div>
                <div class="field-row"><label for="admin-departure-date">Departure date</label><input id="admin-departure-date" type="date" value="${htmlValue(departure.date)}" required></div>
                <div class="field-row"><label for="admin-departure-time">Departure time</label><input id="admin-departure-time" type="time" value="${htmlValue(departure.time || "18:00")}" required></div>
                <div class="field-row"><label for="admin-room-note">Room preference note</label><input id="admin-room-note" value="${htmlValue(source.room_preference_note)}"></div>
            </div>

            <div class="form-section-title">Visitor Details</div>
            <div class="two-col">
                <div class="field-row"><label for="admin-visitor-name">Visitor name</label><input id="admin-visitor-name" value="${htmlValue(source.visitor_name)}" required></div>
                <div class="field-row"><label for="admin-visitor-designation">Visitor designation</label><input id="admin-visitor-designation" value="${htmlValue(source.visitor_designation)}"></div>
                <div class="field-row"><label for="admin-visitor-organisation">Visitor organisation</label><input id="admin-visitor-organisation" value="${htmlValue(source.visitor_organisation)}"></div>
                <div class="field-row"><label for="admin-visitor-gender">Visitor gender</label><input id="admin-visitor-gender" value="${htmlValue(source.visitor_gender)}"></div>
                <div class="field-row"><label for="admin-visitor-mobile">Visitor mobile</label><input id="admin-visitor-mobile" inputmode="tel" value="${htmlValue(source.visitor_mobile)}"></div>
                <div class="field-row"><label for="admin-visitor-email">Visitor email</label><input id="admin-visitor-email" type="email" value="${htmlValue(source.visitor_email)}"></div>
                <div class="field-row"><label for="admin-visitor-category">Visitor category</label><select id="admin-visitor-category">
                    <option value="">Select category</option>
                    <option value="institute_guest" ${source.visitor_category === "institute_guest" ? "selected" : ""}>Institute Guest</option>
                    <option value="conference_workshop_guest" ${source.visitor_category === "conference_workshop_guest" ? "selected" : ""}>Conference/Workshop Guest</option>
                    <option value="other_guest" ${source.visitor_category === "other_guest" ? "selected" : ""}>Other Guest</option>
                </select></div>
            </div>
            <div class="field-row"><label for="admin-purpose">Purpose of visit</label><textarea id="admin-purpose">${htmlValue(source.purpose_of_visit)}</textarea></div>

            <div class="form-section-title">Requestor Details</div>
            <div class="two-col">
                <div class="field-row"><label for="admin-requestor-name">Requestor name</label><input id="admin-requestor-name" value="${htmlValue(source.requestor_name || source.requester_name)}"></div>
                <div class="field-row"><label for="admin-requestor-designation">Requestor designation</label><input id="admin-requestor-designation" value="${htmlValue(source.requestor_designation)}"></div>
                <div class="field-row"><label for="admin-requestor-department">Requestor department</label><input id="admin-requestor-department" value="${htmlValue(source.requestor_department)}"></div>
                <div class="field-row"><label for="admin-requestor-mobile">Requestor mobile</label><input id="admin-requestor-mobile" inputmode="tel" value="${htmlValue(source.requestor_mobile)}"></div>
                ${source.requestor_email || source.requester_email ? `<div class="field-row"><label>Requestor email</label><input value="${htmlValue(source.requestor_email || source.requester_email)}" readonly></div>` : ""}
            </div>

            <div class="form-section-title">Attender Requirement</div>
            <label class="check-row"><input id="admin-attender" type="checkbox" ${source.attender_required ? "checked" : ""}> Attender required</label>
            <div class="two-col">
                <div class="field-row"><label for="admin-attender-count">No. of attenders</label><input id="admin-attender-count" type="number" min="0" value="${htmlValue(source.attender_count_per_day || 0)}"></div>
                <label class="check-row"><input id="admin-general" type="checkbox" ${source.attender_general_shift ? "checked" : ""}> General shift</label>
                <label class="check-row"><input id="admin-morning" type="checkbox" ${source.attender_morning_shift ? "checked" : ""}> Morning shift</label>
                <label class="check-row"><input id="admin-day" type="checkbox" ${source.attender_day_shift ? "checked" : ""}> Day shift</label>
            </div>

            <div class="form-section-title">Charges</div>
            <div class="two-col">
                <div class="field-row"><label for="admin-room-charge-status">Room charges</label><select id="admin-room-charge-status">
                    <option value="no" ${(source.room_charges_status || "no") === "no" ? "selected" : ""}>No</option>
                    <option value="yes" ${source.room_charges_status === "yes" ? "selected" : ""}>Yes</option>
                    <option value="waived_off" ${source.room_charges_status === "waived_off" ? "selected" : ""}>Waived Off</option>
                </select></div>
                <div class="field-row"><label for="admin-room-charge-amount">Room charges amount</label><input id="admin-room-charge-amount" type="number" min="0" step="0.01" value="${htmlValue(source.room_charges_amount || 0)}"></div>
                <div class="field-row"><label for="admin-attender-charge-status">Attender charges</label><select id="admin-attender-charge-status">
                    <option value="no" ${(source.attender_charges_status || "no") === "no" ? "selected" : ""}>No</option>
                    <option value="yes" ${source.attender_charges_status === "yes" ? "selected" : ""}>Yes</option>
                    <option value="waived_off" ${source.attender_charges_status === "waived_off" ? "selected" : ""}>Waived Off</option>
                </select></div>
                <div class="field-row"><label for="admin-attender-charge-amount">Attender charges amount</label><input id="admin-attender-charge-amount" type="number" min="0" step="0.01" value="${htmlValue(source.attender_charges_amount || 0)}"></div>
            </div>

            <div class="form-section-title">Budget Head</div>
            <div class="two-col">
                <div class="field-row"><label for="admin-budget-type">Budget head type</label><select id="admin-budget-type">
                    <option value="" ${!source.budget_head_type ? "selected" : ""}>Not specified</option>
                    <option value="individual" ${source.budget_head_type === "individual" ? "selected" : ""}>Individual</option>
                    <option value="institute_head" ${source.budget_head_type === "institute_head" ? "selected" : ""}>Institute Head</option>
                    <option value="project_head" ${source.budget_head_type === "project_head" ? "selected" : ""}>Project Head</option>
                </select></div>
                <div class="field-row"><label for="admin-budget-value">Budget head value</label><input id="admin-budget-value" value="${htmlValue(source.budget_head_value)}"></div>
                <div class="field-row"><label for="admin-budget-name">Name / Organisation</label><input id="admin-budget-name" value="${htmlValue(source.budget_head_name)}"></div>
                <div class="field-row"><label for="admin-budget-department">Department name</label><input id="admin-budget-department" value="${htmlValue(source.budget_head_department_name)}"></div>
                <div class="field-row"><label for="admin-budget-project-code">Project code</label><input id="admin-budget-project-code" value="${htmlValue(source.budget_head_project_code)}"></div>
            </div>

            <div class="form-section-title">Logistics</div>
            <div class="two-col">
                <div class="field-row"><label for="admin-logistics-name">Logistics name</label><input id="admin-logistics-name" value="${htmlValue(source.logistics_name)}"></div>
                <div class="field-row"><label for="admin-logistics-designation">Logistics designation</label><input id="admin-logistics-designation" value="${htmlValue(source.logistics_designation)}"></div>
                <div class="field-row"><label for="admin-logistics-mobile">Logistics mobile</label><input id="admin-logistics-mobile" inputmode="tel" value="${htmlValue(source.logistics_mobile)}"></div>
            </div>
        </form>
    `;
}

function bindAdminBookingForm(rooms, selectedRoomId = "", preferredPrefix = "") {
    const prefixSelect = document.getElementById("admin-prefix");
    const roomSelect = document.getElementById("admin-room");
    const attender = document.getElementById("admin-attender");
    const attenderCount = document.getElementById("admin-attender-count");
    const shiftInputs = ["admin-general", "admin-morning", "admin-day"].map((id) => document.getElementById(id));
    if (!prefixSelect || !roomSelect) {
        return;
    }
    const selectedRoom = rooms.find((room) => String(room.id) === String(selectedRoomId));
    if (selectedRoom?.prefix) {
        prefixSelect.value = selectedRoom.prefix;
    } else if (preferredPrefix && BUILDINGS.includes(preferredPrefix)) {
        prefixSelect.value = preferredPrefix;
    }
    const renderRoomOptions = () => {
        const filtered = rooms.filter((room) => !prefixSelect.value || room.prefix === prefixSelect.value);
        roomSelect.innerHTML = `<option value="">Select room</option>` + filtered.map((room) => `
            <option value="${room.id}" ${String(room.id) === String(selectedRoomId) ? "selected" : ""}>${escapeHtml(roomLabel(room))}</option>
        `).join("");
    };
    prefixSelect.addEventListener("change", () => {
        selectedRoomId = "";
        renderRoomOptions();
    });
    renderRoomOptions();

    const syncAttender = () => {
        const enabled = attender?.checked;
        if (attenderCount) {
            attenderCount.disabled = !enabled;
            if (!enabled) attenderCount.value = "0";
        }
        shiftInputs.forEach((input) => {
            if (!input) return;
            input.disabled = !enabled;
            if (!enabled) input.checked = false;
        });
    };
    attender?.addEventListener("change", syncAttender);
    syncAttender();
}

function readAdminBookingPayload() {
    const val = (id) => document.getElementById(id)?.value?.trim() || "";
    const checked = (id) => Boolean(document.getElementById(id)?.checked);
    const room = val("admin-room");
    const arrivalAt = buildIsoDateTime(val("admin-arrival-date"), val("admin-arrival-time"));
    const departureAt = buildIsoDateTime(val("admin-departure-date"), val("admin-departure-time"));
    if (!room) {
        throw new Error("Room is required.");
    }
    if (!val("admin-arrival-date") || !val("admin-departure-date")) {
        throw new Error("Arrival and departure dates are required.");
    }
    if (new Date(departureAt) <= new Date(arrivalAt)) {
        throw new Error("Departure datetime must be after arrival datetime.");
    }
    if (!val("admin-visitor-name")) {
        throw new Error("Visitor name is required.");
    }
    const attenderRequired = checked("admin-attender");
    const roomChargeStatus = val("admin-room-charge-status") || "no";
    const attenderChargeStatus = val("admin-attender-charge-status") || "no";
    const budgetType = val("admin-budget-type");
    const budgetValue = val("admin-budget-value")
        || (budgetType === "project_head" ? val("admin-budget-project-code") : "")
        || (budgetType === "institute_head" ? val("admin-budget-department") : "")
        || val("admin-budget-name");
    return {
        room,
        arrival_at: arrivalAt,
        departure_at: departureAt,
        visitor_name: val("admin-visitor-name"),
        visitor_designation: val("admin-visitor-designation"),
        visitor_organisation: val("admin-visitor-organisation"),
        visitor_gender: val("admin-visitor-gender"),
        visitor_mobile: val("admin-visitor-mobile"),
        visitor_email: val("admin-visitor-email"),
        visitor_category: val("admin-visitor-category"),
        purpose_of_visit: val("admin-purpose"),
        requestor_name: val("admin-requestor-name"),
        requestor_designation: val("admin-requestor-designation"),
        requestor_department: val("admin-requestor-department"),
        requestor_mobile: val("admin-requestor-mobile"),
        attender_required: attenderRequired,
        attender_count_per_day: attenderRequired ? Number(val("admin-attender-count") || 0) : 0,
        attender_general_shift: attenderRequired && checked("admin-general"),
        attender_morning_shift: attenderRequired && checked("admin-morning"),
        attender_day_shift: attenderRequired && checked("admin-day"),
        room_charges_status: roomChargeStatus,
        room_charges_amount: roomChargeStatus === "yes" ? Number(val("admin-room-charge-amount") || 0) : 0,
        attender_charges_status: attenderChargeStatus,
        attender_charges_amount: attenderChargeStatus === "yes" ? Number(val("admin-attender-charge-amount") || 0) : 0,
        budget_head_type: budgetType,
        budget_head_value: budgetValue,
        budget_head_name: val("admin-budget-name"),
        budget_head_department_name: val("admin-budget-department"),
        budget_head_project_code: val("admin-budget-project-code"),
        logistics_name: val("admin-logistics-name"),
        logistics_designation: val("admin-logistics-designation"),
        logistics_mobile: val("admin-logistics-mobile"),
    };
}

async function openAdminBookingForm(prefill = null, context = "booking") {
    try {
        const rooms = await fetchRooms();
        const selectedRoomId = prefill?.room || prefill?.preferred_room || "";
        openActionModal({
            title: context === "request" ? "Create Booking From Request" : "Create Booking",
            body: adminBookingFormHtml(prefill || {}, context),
            confirmText: "Create Booking",
            confirmClass: "primary-btn",
            wide: true,
            onBind: () => bindAdminBookingForm(rooms, selectedRoomId, prefill?.preferred_prefix || state.prefix),
            onConfirm: async () => {
                await apiFetch("/api/bookings/create/", { method: "POST", body: readAdminBookingPayload() });
                toast("Booking created successfully.");
                closeModal();
                await refreshVisibleBookingSurface();
            },
        });
    } catch (error) {
        toast(error.message, "error");
    }
}

function filterTabs(active, tabs, onClick) {
    return `<div class="filter-tabs">${tabs.map(([id, label]) => `
        <button class="chip ${active === id ? "active" : ""}" data-filter="${id}">${label}</button>
    `).join("")}</div>`;
}

function bindFilterTabs(container, onClick) {
    container.querySelectorAll("[data-filter]").forEach((button) => {
        button.addEventListener("click", () => onClick(button.dataset.filter));
    });
}

function renderBookingRequestsView() {
    const tabs = [
        ["all", "All"],
        ["pending", "Pending"],
        ["correction_required", "Correction Required"],
        ["approved", "Approved"],
        ["rejected", "Rejected"],
    ];
    viewRoot().innerHTML = `
        <div class="section-header">
            <div>
                <h2>Booking Requests</h2>
                <p>Review requester submissions and take approval actions.</p>
            </div>
            <button class="outline-btn" id="refresh-booking-requests">Refresh</button>
        </div>
        ${filterTabs(state.bookingRequestFilter, tabs)}
        <section class="surface side-panel">
            <div id="booking-requests-list" class="card-list"><div class="loading-state">Loading booking requests...</div></div>
        </section>
    `;
    bindFilterTabs(viewRoot(), (filter) => {
        state.bookingRequestFilter = filter;
        renderBookingRequestsView();
    });
    document.getElementById("refresh-booking-requests").addEventListener("click", loadBookingRequests);
    loadBookingRequests();
}

async function loadBookingRequests() {
    const list = document.getElementById("booking-requests-list");
    list.innerHTML = `<div class="loading-state">Loading booking requests...</div>`;
    const statusParam = state.bookingRequestFilter === "all" ? "" : `?status=${state.bookingRequestFilter}`;
    try {
        const rows = await apiFetch(`/api/admin/booking-requests/${statusParam}`);
        if (!rows.length) {
            list.innerHTML = `<div class="empty-state">No ${state.bookingRequestFilter === "all" ? "" : titleCase(state.bookingRequestFilter).toLowerCase()} booking requests.</div>`;
            return;
        }
        list.innerHTML = rows.map((request) => bookingRequestCard(request)).join("");
        list.querySelectorAll("[data-request-id]").forEach((card) => {
            card.addEventListener("click", () => openAdminBookingRequestDetails(rows.find((item) => String(item.id) === card.dataset.requestId)));
        });
        bindRequestActionButtons(list, rows);
    } catch (error) {
        list.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
    }
}

function bookingRequestCard(request) {
    return `
        <article class="item-card" data-request-id="${request.id}">
            <div class="item-main">
                <div>
                    <h3 class="item-title">${escapeHtml(request.visitor_name || request.requester_name || "Booking request")}</h3>
                    <p class="item-meta">${escapeHtml(request.requestor_department || request.requester_email || "-")} - ${formatDateRange(request)}</p>
                    <p class="item-meta">Room: ${escapeHtml(request.preferred_room_name || request.preferred_prefix || "No preference")}</p>
                </div>
                <span class="status-chip ${request.status}">${titleCase(request.status)}</span>
            </div>
            <div class="card-actions">
                ${request.status === "pending" ? `
                    <button class="success-btn" data-request-action="approve" data-id="${request.id}">Approve</button>
                    <button class="danger-btn" data-request-action="reject" data-id="${request.id}">Reject</button>
                    <button class="warn-btn" data-request-action="sendBack" data-id="${request.id}">Send Back</button>
                ` : ""}
                <button class="outline-btn" data-request-action="delete" data-id="${request.id}">Delete Request</button>
            </div>
        </article>
    `;
}

function bindRequestActionButtons(container, rows) {
    container.querySelectorAll("[data-request-action]").forEach((button) => {
        button.addEventListener("click", (event) => {
            event.stopPropagation();
            const request = rows.find((item) => String(item.id) === button.dataset.id);
            handleBookingRequestAction(button.dataset.requestAction, request);
        });
    });
}

async function fetchRooms() {
    if (state.rooms.length) {
        return state.rooms;
    }
    state.rooms = await fetchAllPaginated("/api/rooms/?page_size=100");
    return state.rooms;
}

async function handleBookingRequestAction(action, request) {
    if (action === "approve") {
        try {
            const rooms = await fetchRooms();
            const roomOptions = rooms
                .filter((room) => !request.preferred_prefix || room.prefix === request.preferred_prefix)
                .map((room) => `<option value="${room.id}" ${String(room.id) === String(request.preferred_room) ? "selected" : ""}>${escapeHtml(roomLabel(room))}</option>`)
                .join("");
            openActionModal({
                title: "Approve Booking Request",
                body: `
                    <div class="field-grid">
                        <div class="field-row"><label for="approve-room">Final room</label><select id="approve-room" required>${roomOptions}</select></div>
                        <div class="field-row"><label for="approve-remarks">Remarks</label><textarea id="approve-remarks" placeholder="Optional remarks"></textarea></div>
                    </div>
                `,
                confirmText: "Approve",
                confirmClass: "success-btn",
                onConfirm: async () => {
                    const room = document.getElementById("approve-room").value;
                    const remarks = document.getElementById("approve-remarks").value;
                    await apiFetch(`/api/admin/booking-requests/${request.id}/approve/`, { method: "POST", body: { room, remarks } });
                    toast("Booking request approved.");
                    loadBookingRequests();
                },
            });
        } catch (error) {
            toast(error.message, "error");
        }
    } else if (action === "reject") {
        openRemarksModal("Reject Booking Request", "Reject", "danger-btn", async (remarks) => {
            await apiFetch(`/api/admin/booking-requests/${request.id}/reject/`, { method: "POST", body: { remarks } });
            toast("Booking request rejected.");
            loadBookingRequests();
        });
    } else if (action === "sendBack") {
        openRemarksModal("Send Back for Correction", "Send Back", "warn-btn", async (remarks) => {
            if (!remarks.trim()) {
                throw new Error("Remarks are required.");
            }
            await apiFetch(`/api/admin/booking-requests/${request.id}/send-back/`, { method: "POST", body: { remarks } });
            toast("Request sent back for correction.");
            loadBookingRequests();
        }, "Explain what needs to be corrected");
    } else if (action === "delete") {
        openRemarksModal("Delete Booking Request", "Delete Request", "danger-btn", async (remarks) => {
            await apiFetch(`/api/admin/booking-requests/${request.id}/delete/`, { method: "DELETE", body: { remarks } });
            toast("Booking request deleted successfully.");
            loadBookingRequests();
        }, "Optional deletion remarks");
    }
}

async function openAdminBookingRequestDetails(request) {
    if (!request?.id) {
        return;
    }
    try {
        const [detail, rooms] = await Promise.all([
            apiFetch(`/api/admin/booking-requests/${request.id}/`),
            fetchRooms(),
        ]);
        const isPending = detail.status === "pending";
        openActionModal({
            title: "Booking Request Review",
            body: adminBookingFormHtml(detail, "request"),
            wide: true,
            footerHtml: `
                <button class="outline-btn" type="button" data-close-modal>Close</button>
                ${isPending ? `
                    <button class="success-btn" type="button" data-review-action="approve">Approve / Create Booking</button>
                    <button class="danger-btn" type="button" data-review-action="reject">Reject</button>
                    <button class="warn-btn" type="button" data-review-action="sendBack">Send Back</button>
                ` : ""}
                <button class="danger-btn" type="button" data-review-action="delete">Delete Request</button>
            `,
            onBind: () => {
                bindAdminBookingForm(rooms, detail.preferred_room || "", detail.preferred_prefix || state.prefix);
                document.querySelectorAll("[data-review-action]").forEach((button) => {
                    button.addEventListener("click", () => runBookingRequestReviewAction(button, detail));
                });
            },
        });
    } catch (error) {
        toast(error.message, "error");
    }
}

async function runBookingRequestReviewAction(button, request) {
    const action = button.dataset.reviewAction;
    button.disabled = true;
    const remarks = document.getElementById("admin-review-remarks")?.value?.trim() || "";
    try {
        if (action === "approve") {
            const payload = { ...readAdminBookingPayload(), remarks };
            await apiFetch(`/api/admin/booking-requests/${request.id}/approve/`, { method: "POST", body: payload });
            toast("Booking request approved and booking created.");
        } else if (action === "reject") {
            await apiFetch(`/api/admin/booking-requests/${request.id}/reject/`, { method: "POST", body: { remarks } });
            toast("Booking request rejected.");
        } else if (action === "sendBack") {
            if (!remarks) {
                throw new Error("Remarks are required.");
            }
            await apiFetch(`/api/admin/booking-requests/${request.id}/send-back/`, { method: "POST", body: { remarks } });
            toast("Request sent back for correction.");
        } else if (action === "delete") {
            if (!window.confirm("Are you sure you want to delete this booking request?")) {
                button.disabled = false;
                return;
            }
            await apiFetch(`/api/admin/booking-requests/${request.id}/delete/`, { method: "DELETE", body: { remarks } });
            toast("Booking request deleted successfully.");
        }
        closeModal();
        await loadBookingRequests();
    } catch (error) {
        toast(error.message, "error");
        button.disabled = false;
    }
}

function openBookingRequestDetails(request) {
    openDetailsModal("Booking Request Details", [
        { section: "Request Status" },
        ["ID", request.id],
        ["Status", titleCase(request.status)],
        ["Requested at", formatDateTime(request.requested_at)],
        ["Reviewed by", request.reviewed_by_name],
        ["Reviewed at", formatDateTime(request.reviewed_at)],
        ["Admin remarks", request.admin_remarks],
        { section: "Schedule & Room" },
        ["Arrival", formatDateTime(request.arrival_at)],
        ["Departure", formatDateTime(request.departure_at)],
        ["Building preference", request.preferred_prefix],
        ["Preferred room", request.preferred_room_name || "No specific room"],
        ["Room note", request.room_preference_note],
        { section: "Visitor Details" },
        ["Visitor name", request.visitor_name],
        ["Designation", request.visitor_designation],
        ["Organisation", request.visitor_organisation],
        ["Gender", request.visitor_gender],
        ["Mobile", request.visitor_mobile],
        ["Email", request.visitor_email],
        ["Category", titleCase(request.visitor_category)],
        ["Purpose", request.purpose_of_visit],
        { section: "Requester Details" },
        ["Requester account", request.requester_name],
        ["Requester email", request.requester_email],
        ["Requestor name", request.requestor_name],
        ["Designation", request.requestor_designation],
        ["Department", request.requestor_department],
        ["Mobile", request.requestor_mobile],
        ["Requestor email", request.requestor_email],
        { section: "Attender Requirement" },
        ["Attender required", yesNo(request.attender_required)],
        ["Attender count", request.attender_count_per_day],
        ["Shifts", shiftsText(request)],
        { section: "Deletion Audit" },
        ["Deleted", yesNo(request.is_deleted)],
        ["Deleted at", formatDateTime(request.deleted_at)],
        ["Deleted by", request.deleted_by_name],
        ["Deleted by role", titleCase(request.deleted_by_role)],
        ["Delete remarks", request.remarks],
    ]);
}

function renderRequesterAccountsView() {
    const tabs = [["all", "All"], ["pending", "Pending"], ["approved", "Approved"], ["rejected", "Rejected"]];
    viewRoot().innerHTML = `
        <div class="section-header">
            <div>
                <h2>Manage Requesters</h2>
                <p>Approve or reject requester accounts.</p>
            </div>
            <button class="outline-btn" id="refresh-requesters">Refresh</button>
        </div>
        ${filterTabs(state.requesterAccountFilter, tabs)}
        <section class="surface side-panel">
            <div id="requesters-list" class="card-list"><div class="loading-state">Loading requester accounts...</div></div>
        </section>
    `;
    bindFilterTabs(viewRoot(), (filter) => {
        state.requesterAccountFilter = filter;
        renderRequesterAccountsView();
    });
    document.getElementById("refresh-requesters").addEventListener("click", loadRequesterAccounts);
    loadRequesterAccounts();
}

async function loadRequesterAccounts() {
    const list = document.getElementById("requesters-list");
    list.innerHTML = `<div class="loading-state">Loading requester accounts...</div>`;
    const statusParam = state.requesterAccountFilter === "all" ? "" : `?status=${state.requesterAccountFilter}`;
    try {
        const rows = await apiFetch(`/api/admin/requester-accounts/${statusParam}`);
        if (!rows.length) {
            list.innerHTML = `<div class="empty-state">No requester accounts found.</div>`;
            return;
        }
        list.innerHTML = rows.map((account) => `
            <article class="item-card" data-account-id="${account.id}">
                <div class="item-main">
                    <div>
                        <h3 class="item-title">${escapeHtml(account.name || account.email)}</h3>
                        <p class="item-meta">${escapeHtml(account.department || "No department")} - ${escapeHtml(account.designation || "No designation")}</p>
                    </div>
                    <span class="status-chip ${account.approval_status}">${titleCase(account.approval_status)}</span>
                </div>
                ${account.approval_status === "pending" || account.approval_status === "rejected" ? `
                    <div class="card-actions">
                        <button class="success-btn" data-account-action="approve" data-id="${account.id}">${account.approval_status === "rejected" ? "Approve Again" : "Approve"}</button>
                        ${account.approval_status === "pending" ? `<button class="danger-btn" data-account-action="reject" data-id="${account.id}">Reject</button>` : ""}
                    </div>
                ` : ""}
            </article>
        `).join("");
        list.querySelectorAll("[data-account-id]").forEach((card) => {
            card.addEventListener("click", () => openAccountDetails(rows.find((item) => String(item.id) === card.dataset.accountId)));
        });
        list.querySelectorAll("[data-account-action]").forEach((button) => {
            button.addEventListener("click", (event) => {
                event.stopPropagation();
                const account = rows.find((item) => String(item.id) === button.dataset.id);
                handleAccountAction(button.dataset.accountAction, account);
            });
        });
    } catch (error) {
        list.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
    }
}

function openAccountDetails(account) {
    openDetailsModal("Requester Account", [
        ["Name", account.name],
        ["Email", account.email],
        ["Role", titleCase(account.role)],
        ["Status", titleCase(account.approval_status)],
        ["Department", account.department],
        ["Designation", account.designation],
        ["Mobile", account.mobile],
        ["Approved by", account.approved_by_name],
        ["Approved at", formatDateTime(account.approved_at)],
        ["Remarks", account.remarks],
    ]);
}

function handleAccountAction(action, account) {
    if (action === "approve") {
        openActionModal({
            title: "Approve Requester Account",
            body: `<p class="item-meta">Approve ${escapeHtml(account.name || account.email)}?</p>`,
            confirmText: "Approve",
            confirmClass: "success-btn",
            onConfirm: async () => {
                await apiFetch(`/api/admin/requester-accounts/${account.id}/approve/`, { method: "POST", body: {} });
                toast("Requester account approved.");
                loadRequesterAccounts();
            },
        });
    } else if (action === "reject") {
        openRemarksModal("Reject Requester Account", "Reject", "danger-btn", async (remarks) => {
            await apiFetch(`/api/admin/requester-accounts/${account.id}/reject/`, { method: "POST", body: { remarks } });
            toast("Requester account rejected.");
            loadRequesterAccounts();
        });
    }
}

function renderMyRequestsView() {
    const tabs = [["all", "All"], ["pending", "Pending"], ["correction_required", "Correction Required"], ["approved", "Approved"], ["rejected", "Rejected"]];
    viewRoot().innerHTML = `
        <div class="section-header">
            <div>
                <h2>My Requests</h2>
                <p>Track and manage your submitted booking requests.</p>
            </div>
            <button class="outline-btn" id="refresh-my-requests">Refresh</button>
        </div>
        ${filterTabs(state.myRequestFilter, tabs)}
        <section class="surface side-panel">
            <div id="my-requests-list" class="card-list"><div class="loading-state">Loading requests...</div></div>
        </section>
    `;
    bindFilterTabs(viewRoot(), (filter) => {
        state.myRequestFilter = filter;
        renderMyRequestsView();
    });
    document.getElementById("refresh-my-requests").addEventListener("click", loadMyRequests);
    loadMyRequests();
}

async function loadMyRequests() {
    const list = document.getElementById("my-requests-list");
    list.innerHTML = `<div class="loading-state">Loading requests...</div>`;
    const statusParam = state.myRequestFilter === "all" ? "" : `?status=${state.myRequestFilter}`;
    try {
        const rows = await apiFetch(`/api/requester/booking-requests/${statusParam}`);
        if (!rows.length) {
            list.innerHTML = `<div class="empty-state">No booking requests found.</div>`;
            return;
        }
        list.innerHTML = rows.map((request) => `
            <article class="item-card" data-my-request-id="${request.id}">
                <div class="item-main">
                    <div>
                        <h3 class="item-title">${escapeHtml(request.visitor_name || "Booking request")}</h3>
                        <p class="item-meta">${formatDateRange(request)} - ${escapeHtml(request.preferred_room_name || request.preferred_prefix || "No room preference")}</p>
                        ${request.admin_remarks ? `<p class="item-meta">Remarks: ${escapeHtml(request.admin_remarks)}</p>` : ""}
                    </div>
                    <span class="status-chip ${request.status}">${titleCase(request.status)}</span>
                </div>
                <div class="card-actions">
                    ${request.status === "pending" || request.status === "correction_required" ? `<button class="outline-btn" data-my-action="edit" data-id="${request.id}">Edit</button>` : ""}
                    <button class="danger-btn" data-my-action="delete" data-id="${request.id}">Delete Request</button>
                </div>
            </article>
        `).join("");
        list.querySelectorAll("[data-my-request-id]").forEach((card) => {
            card.addEventListener("click", () => openBookingRequestDetails(rows.find((item) => String(item.id) === card.dataset.myRequestId)));
        });
        list.querySelectorAll("[data-my-action]").forEach((button) => {
            button.addEventListener("click", (event) => {
                event.stopPropagation();
                const request = rows.find((item) => String(item.id) === button.dataset.id);
                if (button.dataset.myAction === "edit") {
                    openRequestForm(request);
                } else {
                    openRemarksModal("Delete Request", "Delete Request", "danger-btn", async (remarks) => {
                        await apiFetch(`/api/requester/booking-requests/${request.id}/delete/`, { method: "DELETE", body: { remarks } });
                        toast("Request deleted successfully.");
                        loadMyRequests();
                    }, "Optional deletion remarks");
                }
            });
        });
    } catch (error) {
        list.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
    }
}

async function openRequestForm(existing = null) {
    const editing = Boolean(existing);
    const arrival = editing ? indiaParts(existing.arrival_at) : { date: state.rangeStart || todayIso(), time: "10:00" };
    const departure = editing ? indiaParts(existing.departure_at) : { date: state.rangeEnd || state.rangeStart || todayIso(), time: "18:00" };
    const prefix = editing ? (existing.preferred_prefix || state.prefix) : state.prefix;
    openActionModal({
        title: editing ? "Edit Request" : "Request Booking",
        body: `
            <form id="request-form" class="field-grid">
                <div class="two-col">
                    <div class="field-row"><label>Arrival date</label><input id="req-arrival-date" type="date" value="${arrival.date}" required></div>
                    <div class="field-row"><label>Arrival time</label><input id="req-arrival-time" type="time" value="${arrival.time || "10:00"}" required></div>
                    <div class="field-row"><label>Departure date</label><input id="req-departure-date" type="date" value="${departure.date}" required></div>
                    <div class="field-row"><label>Departure time</label><input id="req-departure-time" type="time" value="${departure.time || "18:00"}" required></div>
                </div>
                <div class="two-col">
                    <div class="field-row"><label>Building</label><select id="req-prefix">${BUILDINGS.map((item) => `<option value="${item}" ${item === prefix ? "selected" : ""}>${item}</option>`).join("")}</select></div>
                    <div class="field-row"><label>Preferred room</label><select id="req-room"><option value="">No specific room</option></select></div>
                </div>
                <div class="two-col">
                    <div class="field-row"><label>Visitor name</label><input id="req-visitor-name" value="${escapeHtml(existing?.visitor_name || "")}" required></div>
                    <div class="field-row"><label>Visitor mobile</label><input id="req-visitor-mobile" value="${escapeHtml(existing?.visitor_mobile || "")}"></div>
                    <div class="field-row"><label>Visitor email</label><input id="req-visitor-email" type="email" value="${escapeHtml(existing?.visitor_email || "")}"></div>
                    <div class="field-row"><label>Visitor category</label><select id="req-visitor-category">
                        <option value="">Select category</option>
                        <option value="institute_guest" ${existing?.visitor_category === "institute_guest" ? "selected" : ""}>Institute Guest</option>
                        <option value="conference_workshop_guest" ${existing?.visitor_category === "conference_workshop_guest" ? "selected" : ""}>Conference/Workshop Guest</option>
                        <option value="other_guest" ${existing?.visitor_category === "other_guest" ? "selected" : ""}>Other Guest</option>
                    </select></div>
                </div>
                <div class="field-row"><label>Purpose of visit</label><textarea id="req-purpose">${escapeHtml(existing?.purpose_of_visit || "")}</textarea></div>
                <div class="two-col">
                    <div class="field-row"><label>Requester name</label><input id="req-requestor-name" value="${escapeHtml(existing?.requestor_name || state.user?.name || "")}"></div>
                    <div class="field-row"><label>Department</label><input id="req-requestor-department" value="${escapeHtml(existing?.requestor_department || state.user?.department || "")}"></div>
                    <div class="field-row"><label>Designation</label><input id="req-requestor-designation" value="${escapeHtml(existing?.requestor_designation || state.user?.designation || "")}"></div>
                    <div class="field-row"><label>Mobile</label><input id="req-requestor-mobile" value="${escapeHtml(existing?.requestor_mobile || state.user?.mobile || "")}"></div>
                </div>
                <label style="display:flex;gap:8px;align-items:center;font-weight:800"><input id="req-attender" type="checkbox" ${existing?.attender_required ? "checked" : ""}> Attender required</label>
                <div class="two-col">
                    <div class="field-row"><label>No. of attenders</label><input id="req-attender-count" type="number" min="0" value="${existing?.attender_count_per_day || 0}"></div>
                    <label style="display:flex;gap:8px;align-items:center"><input id="req-general" type="checkbox" ${existing?.attender_general_shift ? "checked" : ""}> General shift</label>
                    <label style="display:flex;gap:8px;align-items:center"><input id="req-morning" type="checkbox" ${existing?.attender_morning_shift ? "checked" : ""}> Morning shift</label>
                    <label style="display:flex;gap:8px;align-items:center"><input id="req-day" type="checkbox" ${existing?.attender_day_shift ? "checked" : ""}> Day shift</label>
                </div>
            </form>
        `,
        confirmText: editing ? "Resubmit Request" : "Submit Request",
        confirmClass: "primary-btn",
        onBind: () => populateRequesterRoomSelect(existing?.preferred_room || ""),
        onConfirm: async () => submitRequesterRequest(existing),
    });
}

async function populateRequesterRoomSelect(selectedRoomId = "") {
    const select = document.getElementById("req-room");
    const prefixSelect = document.getElementById("req-prefix");
    if (!select || !prefixSelect) {
        return;
    }
    const load = async () => {
        select.innerHTML = `<option value="">Loading rooms...</option>`;
        try {
            const arrivalDate = document.getElementById("req-arrival-date").value;
            const departureDate = document.getElementById("req-departure-date").value;
            const prefix = prefixSelect.value;
            const data = await apiFetch(`/api/requester/available-rooms-range/?arrival_date=${arrivalDate}&departure_date=${departureDate}&prefix=${encodeURIComponent(prefix)}`);
            const rooms = data.rooms || [];
            select.innerHTML = `<option value="">No specific room</option>` + rooms.map((room) => `
                <option value="${room.room_id}" ${String(room.room_id) === String(selectedRoomId) ? "selected" : ""}>${escapeHtml(room.room_name)}${room.availability_status === "partial" ? " - Available from " + escapeHtml(room.available_from_time || room.available_from || "") : ""}</option>
            `).join("");
        } catch (error) {
            select.innerHTML = `<option value="">No specific room</option>`;
        }
    };
    ["req-arrival-date", "req-departure-date", "req-prefix"].forEach((id) => {
        document.getElementById(id)?.addEventListener("change", load);
    });
    load();
}

async function submitRequesterRequest(existing = null) {
    const arrivalDate = document.getElementById("req-arrival-date").value;
    const departureDate = document.getElementById("req-departure-date").value;
    const arrivalTime = document.getElementById("req-arrival-time").value;
    const departureTime = document.getElementById("req-departure-time").value;
    const arrivalAt = buildIsoDateTime(arrivalDate, arrivalTime);
    const departureAt = buildIsoDateTime(departureDate, departureTime);
    if (new Date(departureAt) <= new Date(arrivalAt)) {
        throw new Error("Departure datetime must be after arrival datetime.");
    }
    const attenderRequired = document.getElementById("req-attender").checked;
    const payload = {
        arrival_at: arrivalAt,
        departure_at: departureAt,
        preferred_prefix: document.getElementById("req-prefix").value,
        preferred_room: document.getElementById("req-room").value || null,
        visitor_name: document.getElementById("req-visitor-name").value.trim(),
        visitor_mobile: document.getElementById("req-visitor-mobile").value.trim(),
        visitor_email: document.getElementById("req-visitor-email").value.trim(),
        visitor_category: document.getElementById("req-visitor-category").value,
        purpose_of_visit: document.getElementById("req-purpose").value.trim(),
        requestor_name: document.getElementById("req-requestor-name").value.trim(),
        requestor_department: document.getElementById("req-requestor-department").value.trim(),
        requestor_designation: document.getElementById("req-requestor-designation").value.trim(),
        requestor_mobile: document.getElementById("req-requestor-mobile").value.trim(),
        requestor_email: state.user?.email || "",
        attender_required: attenderRequired,
        attender_count_per_day: attenderRequired ? Number(document.getElementById("req-attender-count").value || 0) : 0,
        attender_general_shift: attenderRequired && document.getElementById("req-general").checked,
        attender_morning_shift: attenderRequired && document.getElementById("req-morning").checked,
        attender_day_shift: attenderRequired && document.getElementById("req-day").checked,
    };
    if (!payload.visitor_name) {
        throw new Error("Visitor name is required.");
    }
    const endpoint = existing ? `/api/requester/booking-requests/${existing.id}/` : "/api/requester/booking-requests/";
    const method = existing ? "PATCH" : "POST";
    await apiFetch(endpoint, { method, body: payload });
    toast(existing ? "Request resubmitted successfully." : "Your booking request has been submitted for admin approval.");
    closeModal();
    navigateToView("myRequests");
}

function openRemarksModal(title, confirmText, confirmClass, onConfirm, placeholder = "Optional remarks") {
    openActionModal({
        title,
        body: `<div class="field-row"><label for="modal-remarks">Remarks</label><textarea id="modal-remarks" placeholder="${escapeHtml(placeholder)}"></textarea></div>`,
        confirmText,
        confirmClass,
        onConfirm: async () => onConfirm(document.getElementById("modal-remarks").value),
    });
}

function openDetailsModal(title, rows) {
    openActionModal({
        title,
        body: `<div class="details-list">${rows.map((row) => {
            if (!Array.isArray(row)) {
                return `<div class="detail-section-title">${escapeHtml(row.section || "Details")}</div>`;
            }
            const [label, value] = row;
            return `<div class="detail-row"><span class="detail-label">${escapeHtml(label)}</span><span class="detail-value">${escapeHtml(valueOrDash(value))}</span></div>`;
        }).join("")}</div>`,
        confirmText: "Close",
        confirmClass: "outline-btn",
        onConfirm: async () => {},
    });
}

function openActionModal({ title, body, confirmText, confirmClass, onConfirm, onBind, wide = false, footerHtml = "" }) {
    closeModal();
    const backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop";
    backdrop.innerHTML = `
        <section class="modal-card ${wide ? "wide" : ""}" role="dialog" aria-modal="true" aria-label="${escapeHtml(title)}">
            <header class="modal-header">
                <h3>${escapeHtml(title)}</h3>
                <button class="ghost-btn" type="button" data-close-modal>Close</button>
            </header>
            <div class="modal-body">${body}</div>
            <footer class="modal-footer">
                ${footerHtml || `
                    <button class="outline-btn" type="button" data-close-modal>Cancel</button>
                    <button class="${confirmClass}" type="button" id="modal-confirm">${escapeHtml(confirmText)}</button>
                `}
            </footer>
        </section>
    `;
    document.body.appendChild(backdrop);
    backdrop.querySelectorAll("[data-close-modal]").forEach((button) => button.addEventListener("click", closeModal));
    backdrop.addEventListener("click", (event) => {
        if (event.target === backdrop) {
            closeModal();
        }
    });
    const confirmButton = document.getElementById("modal-confirm");
    if (confirmButton && onConfirm) {
        confirmButton.addEventListener("click", async () => {
            confirmButton.disabled = true;
            try {
                await onConfirm();
                closeModal();
            } catch (error) {
                toast(error.message, "error");
                confirmButton.disabled = false;
            }
        });
    }
    if (onBind) {
        onBind();
    }
}

function closeModal() {
    document.querySelector(".modal-backdrop")?.remove();
}

async function boot() {
    const savedUser = localStorage.getItem(STORAGE_KEYS.user);
    if (savedUser) {
        try {
            state.user = JSON.parse(savedUser);
        } catch (error) {
            state.user = null;
        }
    }
    if (!state.access) {
        renderAuth();
        return;
    }
    try {
        state.user = await apiFetch("/api/auth/me/");
        localStorage.setItem(STORAGE_KEYS.user, JSON.stringify(state.user));
        applyRouteFromHash();
        syncRouteHash(true);
        renderDashboard();
    } catch (error) {
        clearSession();
        renderAuth("Please login again.", true);
    }
}

function handleRouteChange() {
    if (!state.access || !state.user) {
        return;
    }
    const previousView = state.view;
    const previousBookingViewMode = state.bookingViewMode;
    applyRouteFromHash();
    if (state.view !== previousView || state.bookingViewMode !== previousBookingViewMode) {
        renderDashboard();
    }
}

function handleChargeSheetPointerDown(event) {
    const target = event.target;
    if (!target || typeof target.closest !== "function") {
        return;
    }
    const chargeSheet = document.getElementById("charge-sheet");
    const row = target.closest(".charge-sheet-table tbody [data-charge-row-id]");
    if (row && chargeSheet?.contains(row)) {
        setChargeSheetSelectedRow(row.dataset.chargeRowId, chargeSheet);
        return;
    }
    if (state.chargeSheetSelectedId && !target.closest(".charge-sheet-scroll")) {
        clearChargeSheetSelectedRow();
    }
}

window.addEventListener("hashchange", handleRouteChange);
window.addEventListener("popstate", handleRouteChange);
document.addEventListener("pointerdown", handleChargeSheetPointerDown, true);

boot();
