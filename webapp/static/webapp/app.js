import { createApiClient } from "./modules/api-client.js";
import {
    bindAdminBookingForm as bindAdminBookingFormController,
    readAdminBookingPayload as buildAdminBookingPayload,
    renderAdminBookingForm,
} from "./modules/admin-booking-form.js";
import {
    accountCard as renderAccountCard,
    accountsPageHtml as renderAccountsPageHtml,
    accountsEndpoint,
    actionButtons as accountActionButtons,
    detailRows as accountDetailRows,
    emptyText as accountEmptyText,
} from "./modules/account-view.js";
import { createAuthView } from "./modules/auth-view.js";
import {
    availableRoomsChooserHtml as renderAvailableRoomsChooserHtml,
    bookingCardHtml as renderBookingCardHtml,
    createdBookingSidePanelHtml,
    createdBookingSummary,
    createMoreBookingPrefill,
    bookingDisplayId,
    bookingSelectionId,
    bookingSheetEndpoint as buildBookingSheetEndpoint,
    bookingsEndpoint as buildBookingsEndpoint,
    nextPageUrl,
    unwrapList,
} from "./modules/booking-helpers.js";
import {
    availableRoomSelectLabel as formatAvailableRoomSelectLabel,
    calculateAttenderChargeAmount,
    calculateRoomChargeAmount,
    inclusiveStayDays,
    normalizedBudgetHeadFields,
} from "./modules/booking-domain.js";
import {
    buildBookingSheetCells as createBookingSheetCells,
    filterSheetRooms,
    sheetCellHtml as renderSheetCellHtml,
    sheetTableHtml as renderBookingSheetTableHtml,
} from "./modules/booking-sheet.js";
import { createBookingSelection } from "./modules/booking-selection.js";
import { createBookingList } from "./modules/booking-list.js";
import { renderBookingsLayout } from "./modules/bookings-view.js";
import { createBookingSheetController } from "./modules/booking-sheet-controller.js";
import { openBookingDateRangePicker } from "./modules/booking-date-picker.js";
import {
    availabilityClass as calendarAvailabilityClass,
    createCalendarView,
    rangeContains as calendarRangeContains,
} from "./modules/calendar-view.js";
import {
    bindHorizontalScroll as bindChargeScroll,
    bindTableActions as bindChargeTableActions,
    endpoint as buildChargeSheetEndpoint,
    headerHtml as renderChargeSheetHeader,
    nextOrdering as nextChargeSheetOrdering,
    readRowPayload as readChargeSheetRowPayload,
    rowHtml as renderChargeSheetRowHtml,
    tableHtml as renderChargeSheetTableHtml,
} from "./modules/charge-sheet.js";
import {
    addHoursToDateTime,
    addIsoDays,
    buildIsoDateTime,
    currentMonthRange,
    escapeHtml,
    formatDateOnly,
    formatDateRange,
    formatDateTime,
    formatSheetDate,
    formatSheetTime,
    indiaParts,
    isoDate,
    isoDateRange,
    isPastDateTime,
    localIsoDateFromDateTime,
    localTimeMinutes,
    monthName,
    parseDisplayTimeTo24,
    scheduleDisplayText,
    titleCase,
    todayIso,
    valueOrDash,
    visitorNationalityLabel,
    yesNo,
} from "./modules/formatters.js";
import { observeRequiredMarks } from "./modules/required-marks.js";
import {
    adminRequestCard,
    adminRequestsPageHtml,
    myRequestCard,
    myRequestsPageHtml,
    requestActions,
    requestDetailRows,
    requestEndpoint,
    reviewFooterHtml,
} from "./modules/request-view.js";
import {
    buildRequesterBookingPayload,
    renderRequesterBookingForm,
} from "./modules/requester-booking-form.js";
import { createSessionStore } from "./modules/session.js";
import {
    categoriesForView as notificationCategoriesForView,
    countForView as notificationCountForView,
    detailPanelHtml as notificationDetailPanelHtml,
    emptyCounts as emptyNotificationCounts,
    emptyItems as emptyNotificationItems,
    itemKey as notificationItemKey,
    reconcile as reconcileNotifications,
    rowsForUser as notificationRowsForUser,
    summaryHtml as notificationSummaryHtml,
    storageKey as notificationStorageKey,
} from "./modules/workflow-notifications.js";
import {
    applyRoute,
    syncRoute,
} from "./modules/router.js";
import { createSheetExporter } from "./modules/sheet-export.js";
import {
    bookingSharePayload as buildBookingSharePayload,
    chargeSharePayload as buildChargeSharePayload,
    copyHtml as copyHtmlContent,
    copyText as copyTextContent,
} from "./modules/sharing.js";
import {
    bookingMailTemplateContent,
    createModalController,
    shareLinkContent,
    shareOptionsContent,
} from "./modules/modal.js";
import {
    countBadgeHtml as renderCountBadge,
    dashboardHtml,
    menuItems as dashboardMenuItems,
} from "./modules/dashboard-view.js";
import {
    bookingDetailRows as buildBookingDetailRows,
    detailsRowsHtml as renderDetailsRowsHtml,
    printableDocumentHtml,
    printableDetailsRowsHtml as renderPrintableDetailsRowsHtml,
} from "./modules/details-view.js";

const appRoot = document.getElementById("app");

const STORAGE_KEYS = {
    access: "roomBookingWebAccess",
    refresh: "roomBookingWebRefresh",
    user: "roomBookingWebUser",
    workflowNotificationReadPrefix: "roomBookingWorkflowNotificationRead",
};
const sessionStore = createSessionStore(localStorage, STORAGE_KEYS);
const savedSession = sessionStore.read();

const BOOKING_VIEW_MODES = new Set(["cards", "sheet", "charge_sheet"]);
const BUILDINGS = ["Delta", "Gamma", "Beta"];
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const SHEET_COOLING_HOURS = 1;
const SHEET_DAY_END_MINUTES = 18 * 60;
const initialCalendarDateParts = todayIso().split("-").map(Number);

const state = {
    authRole: "admin",
    authMode: "login",
    user: savedSession.user,
    access: savedSession.access,
    refresh: savedSession.refresh,
    view: "calendar",
    prefix: "Delta",
    calendarMonth: initialCalendarDateParts[1],
    calendarYear: initialCalendarDateParts[0],
    availability: null,
    selectedDate: "",
    rangeStart: "",
    rangeEnd: "",
    bookingStatusFilter: "all",
    bookingPrefixFilter: "all",
    bookingSearch: "",
    bookingArrivalFrom: "",
    bookingDepartureTo: "",
    bookingViewMode: "cards",
    bookingNextUrl: "",
    bookingLoading: false,
    bookingLoadedCount: 0,
    bookingInfiniteObserver: null,
    selectedBookingIds: new Set(),
    chargeSheetPrefixFilter: "all",
    chargeSheetPaymentFilter: "all",
    chargeSheetCheckoutFrom: "",
    chargeSheetCheckoutTo: "",
    chargeSheetSearch: "",
    chargeSheetOrdering: "-created_at",
    chargeSheetRows: [],
    chargeSheetEditingId: "",
    chargeSheetSelectedId: "",
    chargeSheetScrollLeft: 0,
    bookingRequestFilter: "pending",
    superadminAccountRoleFilter: "all",
    superadminAccountStatusFilter: "pending",
    myRequestFilter: "all",
    rooms: [],
    workflowNotificationCounts: {
        total: 0,
        booking_requests: 0,
        requester_accounts: 0,
        admin_accounts: 0,
        my_requests: 0,
    },
    workflowNotificationRawCounts: {
        total: 0,
        booking_requests: 0,
        requester_accounts: 0,
        admin_accounts: 0,
        my_requests: 0,
    },
    workflowNotificationItems: {
        booking_requests: [],
        requester_accounts: [],
        admin_accounts: [],
        my_requests: [],
    },
    latestRecentBooking: null,
};
const bookingSelection = createBookingSelection(state.selectedBookingIds);

function emptyWorkflowNotificationCounts() {
    return emptyNotificationCounts();
}

function emptyWorkflowNotificationItems() {
    return emptyNotificationItems();
}

function resetWorkflowNotificationState() {
    state.workflowNotificationCounts = emptyWorkflowNotificationCounts();
    state.workflowNotificationRawCounts = emptyWorkflowNotificationCounts();
    state.workflowNotificationItems = emptyWorkflowNotificationItems();
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

function selectedRangeDisplayText() {
    if (!state.rangeStart) {
        return "No dates selected";
    }
    if (!state.rangeEnd || state.rangeEnd === state.rangeStart) {
        return formatDateOnly(state.rangeStart);
    }
    return `${formatDateOnly(state.rangeStart)} to ${formatDateOnly(state.rangeEnd)}`;
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

function requesterSelectedSchedule() {
    const arrivalDate = state.rangeStart || state.selectedDate || todayIso();
    const departureDate = state.rangeEnd || state.rangeStart || state.selectedDate || arrivalDate;
    return { arrivalDate, departureDate };
}

function selectedScheduleFromCalendar() {
    const arrivalDate = state.rangeStart || state.selectedDate || "";
    const departureDate = state.rangeEnd || state.rangeStart || state.selectedDate || arrivalDate;
    return { arrivalDate, departureDate };
}

function requesterRoomSelection(room = null, prefix = state.prefix) {
    if (!room) {
        return {
            roomId: "",
            roomName: `${prefix} - No specific room selected`,
            prefix,
            availabilityStatus: "",
            availableFrom: "",
        };
    }
    const roomPrefix = room.prefix || prefix;
    const roomId = room.roomId || room.room_id || room.id || "";
    return {
        roomId,
        roomName: roomLabel({
            id: roomId,
            prefix: roomPrefix,
            selection_label: room.selectionLabel || room.selection_label || room.roomName,
            room_name: room.roomName || room.room_name,
            number: room.room_number || room.number,
        }),
        prefix: roomPrefix,
        availabilityStatus: room.availabilityStatus || room.availability_status || "",
        availableFrom: room.availableFrom || room.available_from || room.available_from_time || "",
    };
}

function availableRoomPrefillArrivalTime(room, arrivalDate, fallback = "10:00") {
    if (room?.availability_status !== "partial") {
        return fallback;
    }
    if (room.available_from) {
        const parts = indiaParts(room.available_from);
        if (!room.available_from_date || parts.date === arrivalDate) {
            return parts.time || fallback;
        }
    }
    if (room.available_from_date && room.available_from_date !== arrivalDate) {
        return fallback;
    }
    return parseDisplayTimeTo24(room.available_from_time) || fallback;
}

function availableRoomStatusText(room) {
    if (room?.availability_status === "partial") {
        if (room.available_from) {
            return `Available from: ${formatDateTime(room.available_from)}`;
        }
        const dateText = room.available_from_date ? formatDateOnly(room.available_from_date) : "";
        const timeText = room.available_from_time || "";
        return `Available from: ${[dateText, timeText].filter(Boolean).join(", ") || "-"}`;
    }
    return "Available";
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
    if (item?.attender_morning_shift) {
        shifts.push(`Morning shift (7 AM - 3 PM, ${item?.attender_morning_chargeable === false ? "non-chargeable" : "chargeable"})`);
    }
    if (item?.attender_evening_shift) shifts.push("Evening shift (3 PM - 11 PM)");
    return shifts.length ? shifts.join(", ") : "-";
}

function htmlValue(value) {
    return escapeHtml(value ?? "");
}

function setTokens(payload) {
    resetWorkflowNotificationState();
    state.access = payload.access || "";
    state.refresh = payload.refresh || "";
    state.user = payload.user || null;
    sessionStore.write(state);
}

function clearSession() {
    state.access = "";
    state.refresh = "";
    state.user = null;
    resetWorkflowNotificationState();
    sessionStore.clear();
}

let renderAuth;
const apiFetch = createApiClient({
    getAccessToken: () => state.access,
    getRefreshToken: () => state.refresh,
    onAccessToken: (access) => {
        state.access = access;
        sessionStore.writeAccess(access);
    },
    onSessionExpired: () => {
        clearSession();
        renderAuth("Your session expired. Please login again.", true);
    },
});

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

const modalController = createModalController({ escapeHtml, toast });
const sheetExporter = createSheetExporter({ escapeHtml, toast });
const bookingList = createBookingList({
    state,
    apiFetch,
    endpoint: bookingsEndpoint,
    unwrapList,
    nextPageUrl,
    renderCard: bookingCardHtml,
    clearSelection: clearBookingSelection,
    escapeHtml,
});

renderAuth = createAuthView({
    root: appRoot,
    state,
    apiFetch,
    escapeHtml,
    onAuthenticated: (data) => {
        setTokens(data);
        state.view = defaultViewForCurrentRole();
        syncRouteHash(true);
        renderDashboard();
    },
}).render;

function isAdminLike() {
    return state.user?.role === "admin" || state.user?.role === "superadmin";
}

function isSuperadmin() {
    return state.user?.role === "superadmin";
}

function defaultViewForCurrentRole() {
    return "calendar";
}

function allowedViewIds() {
    return menuItems().map(([id]) => id);
}

function applyRouteFromHash() {
    applyRoute(state, {
        allowedViews: allowedViewIds(),
        bookingViewModes: BOOKING_VIEW_MODES,
        defaultView: defaultViewForCurrentRole(),
    });
}

function syncRouteHash(replace = false) {
    syncRoute(state, replace);
}

function navigateToView(view, replace = false) {
    state.view = view;
    syncRouteHash(replace);
    renderDashboard();
}

function menuItems() {
    return dashboardMenuItems(state.user?.role);
}

function workflowNotificationCountForView(viewId) {
    return notificationCountForView(state.workflowNotificationCounts, viewId);
}

function workflowNotificationCategoriesForView(viewId) {
    return notificationCategoriesForView(viewId);
}

function workflowNotificationReadStorageKey() {
    return notificationStorageKey(STORAGE_KEYS.workflowNotificationReadPrefix, state.user);
}

function getReadWorkflowNotificationKeys() {
    try {
        const raw = localStorage.getItem(workflowNotificationReadStorageKey());
        const values = JSON.parse(raw || "[]");
        return new Set(Array.isArray(values) ? values : []);
    } catch (error) {
        return new Set();
    }
}

function saveReadWorkflowNotificationKeys(keys) {
    localStorage.setItem(workflowNotificationReadStorageKey(), JSON.stringify(Array.from(keys)));
}

function workflowNotificationItemKey(item) {
    return notificationItemKey(item);
}

function applyWorkflowNotificationPayload(payload) {
    const readKeys = getReadWorkflowNotificationKeys();
    const { items, rawCounts, unreadCounts, prunedReadKeys } = reconcileNotifications(payload, readKeys);
    saveReadWorkflowNotificationKeys(prunedReadKeys);
    state.workflowNotificationItems = items;
    state.workflowNotificationRawCounts = rawCounts;
    state.workflowNotificationCounts = unreadCounts;
}

function markWorkflowNotificationCategoriesRead(categories) {
    const normalizedCategories = categories.filter(Boolean);
    if (!normalizedCategories.length) {
        return;
    }
    const readKeys = getReadWorkflowNotificationKeys();
    let changed = false;
    normalizedCategories.forEach((category) => {
        (state.workflowNotificationItems?.[category] || []).forEach((item) => {
            const key = workflowNotificationItemKey(item);
            if (!key) {
                return;
            }
            if (!readKeys.has(key)) {
                readKeys.add(key);
                changed = true;
            }
        });
    });
    if (!changed) {
        return;
    }
    saveReadWorkflowNotificationKeys(readKeys);
    applyWorkflowNotificationPayload({
        items: state.workflowNotificationItems,
    });
    updateWorkflowNotificationBell();
    updateVisibleMenuBadges();
}

function markWorkflowNotificationViewRead(viewId) {
    markWorkflowNotificationCategoriesRead(workflowNotificationCategoriesForView(viewId));
}

function countBadgeHtml(count) {
    return renderCountBadge(count);
}

function renderDashboard() {
    appRoot.innerHTML = dashboardHtml({
        user: state.user,
        activeView: state.view,
        items: menuItems(),
        countForView: workflowNotificationCountForView,
        escapeHtml,
        titleCase,
    });
    appRoot.querySelectorAll("[data-view]").forEach((button) => {
        button.addEventListener("click", () => {
            navigateToView(button.dataset.view);
        });
    });
    appRoot.querySelector("[data-notification-bell]").addEventListener("click", openWorkflowNotificationSummary);
    appRoot.querySelector("[data-logout]").addEventListener("click", logout);
    updateWorkflowNotificationBell();
    loadWorkflowNotificationCounts();
    renderCurrentView();
}

async function loadWorkflowNotificationCounts({ markCurrentViewRead = true, viewId = state.view } = {}) {
    if (!state.access || !state.user) {
        return;
    }
    try {
        const counts = await apiFetch("/api/workflow-notification-counts/");
        applyWorkflowNotificationPayload(counts);
        if (markCurrentViewRead && state.view === viewId) {
            markWorkflowNotificationViewRead(viewId);
        }
        updateWorkflowNotificationBell();
        updateVisibleMenuBadges();
    } catch (error) {
        updateWorkflowNotificationBell();
    }
}

function updateWorkflowNotificationBell() {
    const total = state.workflowNotificationCounts?.total || 0;
    const badge = document.getElementById("workflow-notification-badge");
    if (!badge) {
        return;
    }
    badge.textContent = total > 99 ? "99+" : String(total);
    badge.hidden = total <= 0;
}

function updateVisibleMenuBadges() {
    appRoot.querySelectorAll("[data-view]").forEach((button) => {
        const count = workflowNotificationCountForView(button.dataset.view);
        button.querySelector(".menu-count-badge")?.remove();
        if (count) {
            button.insertAdjacentHTML("beforeend", countBadgeHtml(count));
        }
    });
}

function workflowNotificationRows() {
    return notificationRowsForUser({
        counts: state.workflowNotificationCounts, rawCounts: state.workflowNotificationRawCounts,
        user: state.user, adminLike: isAdminLike(), superadmin: isSuperadmin(),
        detailsForView: workflowNotificationDetailsForView, items: state.workflowNotificationItems,
    });
}

function workflowNotificationDetailsForView(viewId) {
    return workflowNotificationCategoriesForView(viewId)
        .flatMap((category) => state.workflowNotificationItems?.[category] || [])
        .filter((item) => typeof item === "object" && (item.title || item.message));
}

function openWorkflowNotificationDetails(viewId) {
    const details = workflowNotificationDetailsForView(viewId);
    const title = menuItems().find(([id]) => id === viewId)?.[1] || "Notification Details";
    markWorkflowNotificationViewRead(viewId);
    openActionModal({
        title: `${title} Notifications`,
        body: notificationDetailPanelHtml(details, escapeHtml),
        footerHtml: `
            <button class="outline-btn" type="button" data-close-modal>Close</button>
            <button class="primary-btn" type="button" id="open-notification-view">Open ${escapeHtml(title)}</button>
        `,
        onBind: () => {
            document.getElementById("open-notification-view")?.addEventListener("click", () => {
                closeModal();
                navigateToView(viewId);
            });
        },
    });
}

function openWorkflowNotificationSummary() {
    const rows = workflowNotificationRows();
    const total = state.workflowNotificationCounts?.total || 0;
    openActionModal({
        title: "Workflow Notifications",
        body: notificationSummaryHtml(rows, total, escapeHtml),
        footerHtml: `<button class="outline-btn" type="button" data-close-modal>Close</button>`,
        onBind: () => {
            document.querySelectorAll("[data-notification-view]").forEach((button) => {
                button.addEventListener("click", () => {
                    const viewId = button.dataset.notificationView;
                    if (workflowNotificationDetailsForView(viewId).length) {
                        openWorkflowNotificationDetails(viewId);
                        return;
                    }
                    markWorkflowNotificationViewRead(viewId);
                    closeModal();
                    navigateToView(viewId);
                });
            });
        },
    });
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
    } else if (state.view === "accounts") {
        renderSuperadminAccountsView();
    } else if (state.view === "myRequests") {
        renderMyRequestsView();
    } else {
        renderCalendarView();
    }
    markWorkflowNotificationViewRead(state.view);
}

const calendarView = createCalendarView({
    state,
    viewRoot,
    buildings: BUILDINGS,
    weekdays: WEEKDAYS,
    apiFetch,
    isAdmin: isAdminLike,
    escapeHtml,
    titleCase,
    isoDate,
    monthName,
    selectedRangeDisplayText,
    onCreateBooking: () => openAdminAvailableRoomsChooser(),
    onRequestBooking: () => openRequestForm(),
});

function renderCalendarView() {
    calendarView.render();
}

function openAdminBookingDateRangePicker() {
    openBookingDateRangePicker({
        state, buildings: BUILDINGS, weekdays: WEEKDAYS, selectedRangeDisplayText,
        toast, closeModal, openAvailableRooms: openAdminAvailableRoomsChooser,
        escapeHtml, isoDate, rangeContains: calendarRangeContains,
        availabilityClass: calendarAvailabilityClass, monthName, apiFetch, openActionModal,
    });
}

function bookingPrefixFromSummary(booking = {}) {
    const roomName = String(booking.room_name || "");
    return BUILDINGS.find((prefix) => roomName.toLowerCase().startsWith(prefix.toLowerCase())) || state.prefix;
}

function buildCreatedBookingSummary(created = {}, payload = {}, rooms = []) {
    return createdBookingSummary(created, payload, rooms, { roomLabel, prefixFromSummary: bookingPrefixFromSummary });
}

function createMoreBookingPrefillFromSummary(booking = {}) {
    return createMoreBookingPrefill(booking, bookingPrefixFromSummary);
}

async function showCreatedBookingInCalendarSide(booking) {
    if (booking) {
        state.latestRecentBooking = booking;
    }
    if (state.view !== "calendar" || !booking) {
        await refreshVisibleBookingSurface();
        return;
    }

    const arrivalDate = indiaParts(booking.arrival_at).date;
    const departureDate = indiaParts(booking.departure_at).date || arrivalDate;
    if (arrivalDate) {
        const [year, month] = arrivalDate.split("-").map(Number);
        if (year && month) {
            state.calendarYear = year;
            state.calendarMonth = month;
        }
        state.selectedDate = arrivalDate;
        state.rangeStart = arrivalDate;
        state.rangeEnd = departureDate || arrivalDate;
    }
    state.prefix = bookingPrefixFromSummary(booking);

    if (document.getElementById("building-tabs")) {
        calendarView.drawBuildingTabs();
    }
    if (document.getElementById("calendar-grid")) {
        await calendarView.load();
        renderCreatedBookingSidePanel(booking);
    } else {
        await refreshVisibleBookingSurface();
    }
}

function renderCreatedBookingSidePanel(booking) {
    calendarView.renderSide(createdBookingSidePanelHtml(booking, {
        escapeHtml, selectedRangeDisplayText, titleCase, formatDateRange,
    }));
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
    return buildBookingsEndpoint(state);
}

function bookingSheetDateRange() {
    const fallback = currentMonthRange();
    return {
        start: state.bookingArrivalFrom || fallback.start,
        end: state.bookingDepartureTo || fallback.end,
    };
}

function bookingSheetEndpoint() {
    return buildBookingSheetEndpoint(state);
}

function chargeSheetEndpoint() {
    return buildChargeSheetEndpoint(state);
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
        { className: "expired", label: "Expired" },
    ]);
}

function chargeSheetLegendHtml() {
    return sheetLegend([
        { className: "normal-row", label: "Editable booking" },
        { className: "expired", label: "Expired" },
        { className: "selected", label: "Selected row" },
    ]);
}

function downloadSheetExcel(tableSelector, title) {
    sheetExporter.excel(tableSelector, title);
}

function downloadSheetPdf(tableSelector, title) {
    sheetExporter.pdf(tableSelector, title);
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
    return buildBookingSharePayload(state, bookingSheetDateRange(), validity);
}

function chargeSheetSharePayload(validity = "1w") {
    return buildChargeSharePayload(state, validity);
}

function sheetSharePayload(sheetName, validity = "1w") {
    return sheetName === "charge"
        ? chargeSheetSharePayload(validity)
        : bookingSharePayload(validity);
}

async function copyTextToClipboard(value) {
    await copyTextContent(value);
}

async function copyHtmlToClipboard(html, textFallback = "") {
    await copyHtmlContent(html, textFallback);
}

function openBookingMailTemplateModal(template = {}) {
    const content = bookingMailTemplateContent(template, { escapeHtml, htmlValue });
    openActionModal({
        title: "Booking Mail Template", body: content.body, wide: true, footerHtml: content.footerHtml,
        onBind: () => {
            document.getElementById("booking-mail-subject")?.select();
            document.getElementById("copy-mail-subject")?.addEventListener("click", async () => {
                await copyTextToClipboard(content.subject);
                toast("Mail subject copied.");
            });
            document.getElementById("copy-mail-body")?.addEventListener("click", async () => {
                await copyHtmlToClipboard(content.htmlBody, content.textBody);
                toast("Mail content copied.");
            });
        },
    });
}

function openShareLinkModal(data, sheetName) {
    const url = data.url;
    const title = sheetName === "charge" ? "Share Charges Sheet" : "Share Booking Sheet";
    openActionModal({
        title,
        body: shareLinkContent(data, sheetName, { escapeHtml, htmlValue, formatDateTime }),
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
        body: shareOptionsContent(),
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

function selectedBookingIds() {
    return bookingSelection.values();
}

function updateBookingSelectionUi() {
    bookingSelection.updateUi();
}

function clearBookingSelection() {
    bookingSelection.clear();
}

function setBookingSelection(bookingId, selected) {
    bookingSelection.set(bookingId, selected);
}

function bindBulkBookingActions() {
    bookingSelection.bind({
        onGenerateMail: generateSelectedBookingMailTemplate,
        onDelete: openBulkDeleteBookingsModal,
    });
}

async function generateSelectedBookingMailTemplate() {
    const ids = selectedBookingIds();
    if (!ids.length) {
        toast("Select at least one booking to generate an email template.", "error");
        return;
    }
    const button = document.getElementById("generate-selected-mail-template");
    if (button) {
        button.disabled = true;
    }
    try {
        const template = await apiFetch("/api/bookings/mail-template/", {
            method: "POST",
            body: { booking_ids: ids },
        });
        openBookingMailTemplateModal(template);
    } catch (error) {
        toast(error.message, "error");
    } finally {
        updateBookingSelectionUi();
    }
}

function openBulkDeleteBookingsModal() {
    const ids = selectedBookingIds();
    if (!ids.length) {
        toast("Select at least one booking to delete.", "error");
        return;
    }
    openActionModal({
        title: "Delete Selected Bookings",
        body: `<p class="item-meta">Are you sure you want to permanently delete ${ids.length} selected booking${ids.length === 1 ? "" : "s"}? This cannot be undone.</p>`,
        confirmText: `Delete ${ids.length} Booking${ids.length === 1 ? "" : "s"}`,
        confirmClass: "danger-btn",
        onConfirm: async () => {
            const deletingIds = selectedBookingIds();
            for (const id of deletingIds) {
                await apiFetch(`/api/bookings/${id}/delete/`, { method: "DELETE" });
            }
            bookingSelection.clear();
            toast(`${deletingIds.length} booking${deletingIds.length === 1 ? "" : "s"} deleted successfully.`);
            closeModal();
            await refreshVisibleBookingSurface();
        },
    });
}

function bookingCardHtml(booking) {
    return renderBookingCardHtml(booking, {
        selectedIds: state.selectedBookingIds,
        escapeHtml,
        formatDateRange,
        titleCase,
    });
}

function updateBookingScrollState(message = "") {
    bookingList.updateScrollState(message);
}

function setupBookingInfiniteScroll() {
    bookingList.setupInfiniteScroll();
}

function renderBookingsView() {
    const isChargeSheet = state.bookingViewMode === "charge_sheet";
    const root = viewRoot();
    root.classList.toggle("wide-dashboard", state.bookingViewMode === "sheet" || isChargeSheet);
    root.innerHTML = renderBookingsLayout(state, {
        buildings: BUILDINGS, htmlValue, escapeHtml, filterTabs, chargeSheetSortOptions,
    });
    appRoot.querySelectorAll("[data-booking-view]").forEach((button) => {
        button.addEventListener("click", () => {
            state.bookingViewMode = button.dataset.bookingView;
            syncRouteHash();
            clearBookingSelection();
            state.chargeSheetEditingId = "";
            renderBookingsView();
        });
    });
    document.getElementById("create-booking").addEventListener("click", () => openAdminBookingDateRangePicker());
    document.getElementById("refresh-bookings").addEventListener("click", refreshBookingsView);
    if (isChargeSheet) {
        bindChargeSheetFilters();
        loadChargeSheetView();
    } else if (state.bookingViewMode === "sheet") {
        bindFilterTabs(viewRoot(), (filter) => {
            state.bookingStatusFilter = filter;
            clearBookingSelection();
            renderBookingsView();
        });
        bindBookingFilters();
        loadBookingSheetView();
    } else {
        bindFilterTabs(viewRoot(), (filter) => {
            state.bookingStatusFilter = filter;
            clearBookingSelection();
            renderBookingsView();
        });
        bindBookingFilters();
        bindBulkBookingActions();
        document.getElementById("bookings-list").addEventListener("click", (event) => {
            const checkbox = event.target.closest("[data-booking-select-id]");
            if (checkbox) {
                event.stopPropagation();
                setBookingSelection(checkbox.dataset.bookingSelectId, checkbox.checked);
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
    const applySearch = () => {
        state.bookingSearch = document.getElementById("booking-search")?.value?.trim() || "";
        clearBookingSelection();
        refreshBookingsView();
    };
    document.getElementById("apply-booking-search")?.addEventListener("click", applySearch);
    document.getElementById("booking-search")?.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            applySearch();
        }
    });
    document.getElementById("booking-prefix-filter").addEventListener("change", (event) => {
        state.bookingPrefixFilter = event.target.value;
        clearBookingSelection();
        refreshBookingsView();
    });
    document.getElementById("booking-arrival-from").addEventListener("change", (event) => {
        state.bookingArrivalFrom = event.target.value;
        clearBookingSelection();
        refreshBookingsView();
    });
    document.getElementById("booking-departure-to").addEventListener("change", (event) => {
        state.bookingDepartureTo = event.target.value;
        clearBookingSelection();
        refreshBookingsView();
    });
    document.getElementById("clear-booking-filters").addEventListener("click", () => {
        state.bookingStatusFilter = "all";
        state.bookingPrefixFilter = "all";
        state.bookingSearch = "";
        state.bookingArrivalFrom = "";
        state.bookingDepartureTo = "";
        clearBookingSelection();
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
        ["remarks", "Remarks"],
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
    return renderChargeSheetHeader(field, label, state.chargeSheetOrdering, escapeHtml);
}

function setChargeSheetOrdering(field) {
    state.chargeSheetOrdering = nextChargeSheetOrdering(state.chargeSheetOrdering, field);
    const sortSelect = document.getElementById("charge-sheet-sort");
    if (sortSelect) {
        sortSelect.value = state.chargeSheetOrdering;
    }
    state.chargeSheetEditingId = "";
    loadChargeSheetView();
}

function chargeSheetRowHtml(row) {
    return renderChargeSheetRowHtml(row, {
        editingId: state.chargeSheetEditingId,
        selectedId: state.chargeSheetSelectedId,
        escapeHtml,
        htmlValue,
        valueOrDash,
        formatDateTime,
        buildingRoomValue,
        isPastDateTime,
    });
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
    shell.innerHTML = renderChargeSheetTableHtml(state.chargeSheetRows || [], {
        headerHtml: chargeSheetHeader, rowHtml: chargeSheetRowHtml,
        exportButtonsHtml: sheetExportButtons("charge"), legendHtml: chargeSheetLegendHtml(),
    });
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
    bindChargeTableActions(shell, {
        bindScroll: bindChargeSheetHorizontalScroll, onExport: handleSheetExport,
        onShare: createBookingShareLink, onSort: setChargeSheetOrdering,
        onEdit: (editingId, targetShell) => {
            state.chargeSheetEditingId = editingId;
            renderChargeSheetRows(targetShell);
            bindChargeSheetTable(targetShell);
        },
        onSave: saveChargeSheetRow, onDelete: openDeleteBookingModal,
    });
}

function bindChargeSheetHorizontalScroll(shell) {
    bindChargeScroll(
        shell,
        () => state.chargeSheetScrollLeft,
        (value) => { state.chargeSheetScrollLeft = value; },
    );
}

async function saveChargeSheetRow(rowId, shell) {
    const safeRowId = String(rowId).replaceAll('"', '\\"');
    const row = shell.querySelector(`[data-charge-row-id="${safeRowId}"]`);
    if (!row) {
        return;
    }
    const payload = readChargeSheetRowPayload(row);
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
        await calendarView.load();
    }
}

async function loadBookings(options = {}) {
    await bookingList.load(options);
}

function filteredSheetRooms(rooms) {
    return filterSheetRooms(rooms, state.bookingPrefixFilter, BUILDINGS, roomLabel);
}

function buildBookingSheetCells(bookings, dates) {
    return createBookingSheetCells(bookings, dates, {
        localIsoDateFromDateTime,
        localTimeMinutes,
        addHoursToDateTime,
        isPastDateTime,
        coolingHours: SHEET_COOLING_HOURS,
        dayEndMinutes: SHEET_DAY_END_MINUTES,
    });
}

function sheetCellHtml(entries = [], dateValue = "", room = null) {
    return renderSheetCellHtml(entries, dateValue, room, { escapeHtml, indiaParts, formatSheetTime });
}

const bookingSheetController = createBookingSheetController({
    document, dateRange: bookingSheetDateRange, isoDateRange, fetchRooms, fetchAllPaginated,
    endpoint: bookingSheetEndpoint, filterRooms: filteredSheetRooms, buildCells: buildBookingSheetCells,
    renderTable: renderBookingSheetTableHtml, renderCell: sheetCellHtml, escapeHtml, formatSheetDate, roomLabel,
    exportButtonsHtml: sheetExportButtons("booking"), legendHtml: bookingSheetLegendHtml(),
    onShare: createBookingShareLink, onExport: handleSheetExport, onAction: handleBookingInlineAction,
    onOpenDetails: openBookingDetails,
});

async function loadBookingSheetView() {
    await bookingSheetController.load();
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
            onBind: () => bindAdminBookingForm(
                rooms,
                booking.room || "",
                "",
                { availabilityFilter: false, preserveRoomChargeStatus: true },
            ),
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

function adminReviewRemarksHtml() {
    return `
        <div class="field-row review-remarks-field">
            <label for="admin-review-remarks">Remarks (Optional for approve; required for reject/send back/delete)</label>
            <textarea id="admin-review-remarks" placeholder="Optional for approve; required for reject, send back, or delete"></textarea>
        </div>
    `;
}

function adminPreviousBookingAutofillHtml(source = {}, context = "booking") {
    if (context !== "booking" || source.id) {
        return "";
    }
    return `
        <div class="previous-booking-fill">
            <label class="check-row">
                <input id="admin-fill-from-previous" type="checkbox">
                Fill from previous booking
            </label>
        </div>
    `;
}

async function openBookingDetails(bookingId) {
    try {
        const booking = await apiFetch(`/api/bookings/${bookingId}/`);
        const rows = buildBookingDetailRows(booking, {
            bookingDisplayId, normalizedBudgetHeadFields, titleCase, formatDateTime,
            visitorNationalityLabel, yesNo, shiftsText,
        });
        openActionModal({
            title: "Booking Details",
            body: detailsRowsHtml(rows),
            wide: true,
            footerHtml: `
                <button class="outline-btn" type="button" data-close-modal>Close</button>
                <button class="outline-btn" type="button" id="booking-detail-print">Print</button>
                <button class="outline-btn" type="button" id="booking-detail-mail-template">Generate Mail Template</button>
                <button class="outline-btn" type="button" id="booking-detail-edit">Edit Booking</button>
                <button class="danger-btn" type="button" id="booking-detail-delete">Delete Booking</button>
            `,
            onBind: () => {
                document.getElementById("booking-detail-print")?.addEventListener("click", () => {
                    printDetailsDocument(
                        `Booking Details - ${bookingDisplayId(booking)}`,
                        rows,
                        `${valueOrDash(booking.room_name)} | ${formatDateRange(booking)}`
                    );
                });
                document.getElementById("booking-detail-mail-template")?.addEventListener("click", async () => {
                    try {
                        const template = await apiFetch(`/api/bookings/${booking.id}/mail-template/`);
                        openBookingMailTemplateModal(template);
                    } catch (error) {
                        toast(error.message, "error");
                    }
                });
                document.getElementById("booking-detail-edit")?.addEventListener("click", () => {
                    closeModal();
                    openAdminBookingEditForm(booking.id);
                });
                document.getElementById("booking-detail-delete")?.addEventListener("click", () => {
                    closeModal();
                    openDeleteBookingModal(booking.id);
                });
            },
        });
    } catch (error) {
        toast(error.message, "error");
    }
}

function adminBookingFormHtml(source = {}, context = "booking") {
    return renderAdminBookingForm(source, context, {
        state, todayIso, indiaParts, buildings: BUILDINGS, normalizedBudgetHeadFields,
        escapeHtml, htmlValue, titleCase, formatDateTime,
        previousBookingAutofillHtml: adminPreviousBookingAutofillHtml,
    });
}

function setFieldValue(id, value, shouldDispatchChange = false) {
    const field = document.getElementById(id);
    if (!field) {
        return;
    }
    field.value = value ?? "";
    if (shouldDispatchChange) {
        field.dispatchEvent(new Event("change", { bubbles: true }));
    }
}

function setBudgetHeadValue(checkboxId, fieldId, value) {
    const checkbox = document.getElementById(checkboxId);
    const field = document.getElementById(fieldId);
    if (!checkbox || !field) {
        return;
    }
    const normalizedValue = value || "";
    checkbox.checked = Boolean(normalizedValue);
    checkbox.dispatchEvent(new Event("change", { bubbles: true }));
    if (normalizedValue) {
        field.value = normalizedValue;
    }
}

function setAdminVisitorCategory(value = "") {
    document.querySelectorAll('input[name="admin-visitor-category"]').forEach((input) => {
        input.checked = Boolean(value) && input.value === value;
    });
}

function setAdminVisitorNationality(value = "") {
    const normalized = value === "foreigner" || value === "indian" ? value : "";
    document.querySelectorAll('input[name="admin-visitor-nationality"]').forEach((input) => {
        input.checked = Boolean(normalized) && input.value === normalized;
    });
}

async function latestRecentBookingForAutofill() {
    if (state.latestRecentBooking) {
        return state.latestRecentBooking;
    }
    const data = await apiFetch("/api/bookings/?page=1");
    const latestBooking = unwrapList(data)[0];
    if (!latestBooking) {
        throw new Error("No previous booking is available yet.");
    }
    state.latestRecentBooking = latestBooking;
    return latestBooking;
}

function syncAdminLogisticsFromPreviousBooking(booking = {}) {
    const sameAsRequestor = document.getElementById("admin-logistics-same-as-requestor");
    const requestorValues = {
        name: booking.requestor_name || booking.requester_name || "",
        designation: booking.requestor_designation || "",
        mobile: booking.requestor_mobile || "",
    };
    const logisticsValues = {
        name: booking.logistics_name || "",
        designation: booking.logistics_designation || "",
        mobile: booking.logistics_mobile || "",
    };
    const requestorHasValue = Object.values(requestorValues).some((value) => String(value || "").trim());
    const logisticsMatchesRequestor = requestorHasValue
        && logisticsValues.name === requestorValues.name
        && logisticsValues.designation === requestorValues.designation
        && logisticsValues.mobile === requestorValues.mobile;

    if (sameAsRequestor && sameAsRequestor.checked && !logisticsMatchesRequestor) {
        sameAsRequestor.checked = false;
        sameAsRequestor.dispatchEvent(new Event("change", { bubbles: true }));
    }

    if (logisticsMatchesRequestor && sameAsRequestor) {
        sameAsRequestor.checked = true;
        sameAsRequestor.dispatchEvent(new Event("change", { bubbles: true }));
        return;
    }

    setFieldValue("admin-logistics-name", logisticsValues.name);
    setFieldValue("admin-logistics-designation", logisticsValues.designation);
    setFieldValue("admin-logistics-mobile", logisticsValues.mobile);
}

async function fillAdminBookingFormFromPreviousBooking() {
    const booking = await latestRecentBookingForAutofill();

    const arrival = indiaParts(booking.arrival_at || "");
    const departure = indiaParts(booking.departure_at || "");
    if (arrival.date) setFieldValue("admin-arrival-date", arrival.date, true);
    if (arrival.time) setFieldValue("admin-arrival-time", arrival.time, true);
    if (departure.date) setFieldValue("admin-departure-date", departure.date, true);
    if (departure.time) setFieldValue("admin-departure-time", departure.time, true);

    setFieldValue("admin-purpose", booking.purpose_of_visit || "");
    setAdminVisitorNationality(booking.visitor_nationality || "");
    setAdminVisitorCategory(booking.visitor_category || "");

    const budgetHead = normalizedBudgetHeadFields(booking);
    setBudgetHeadValue("admin-budget-individual", "admin-budget-name", budgetHead.individual);
    setBudgetHeadValue("admin-budget-institute-head", "admin-budget-department", budgetHead.instituteHead);
    setBudgetHeadValue("admin-budget-project-head", "admin-budget-project-code", budgetHead.projectHead);

    setFieldValue("admin-requestor-name", booking.requestor_name || booking.requester_name || "");
    setFieldValue("admin-requestor-designation", booking.requestor_designation || "");
    setFieldValue("admin-requestor-department", booking.requestor_department || "");
    setFieldValue("admin-requestor-mobile", booking.requestor_mobile || "");
    syncAdminLogisticsFromPreviousBooking(booking);

    const roomChargeStatus = booking.room_charges_status || "no";
    const attenderChargeStatus = booking.attender_charges_status || "no";
    setFieldValue("admin-room-charge-status", roomChargeStatus, true);
    setFieldValue(
        "admin-room-charge-amount",
        roomChargeStatus === "yes" ? booking.room_charges_amount ?? 0 : "",
    );
    document.getElementById("admin-room-charge-status")?.dispatchEvent(new Event("change", { bubbles: true }));
    setFieldValue("admin-attender-charge-status", attenderChargeStatus, true);
    document.getElementById("admin-attender-charge-status")?.dispatchEvent(new Event("change", { bubbles: true }));

    toast("Filled from previous booking.");
}

function availableRoomSelectLabel(room, prefix) {
    return formatAvailableRoomSelectLabel(room, prefix, roomLabel, availableRoomStatusText);
}

function bindAdminBookingForm(rooms, selectedRoomId = "", preferredPrefix = "", options = {}) {
    return bindAdminBookingFormController(rooms, selectedRoomId, preferredPrefix, options, {
        document, buildings: BUILDINGS, escapeHtml, roomLabel, availableRoomSelectLabel, apiFetch, toast,
        calculateRoomChargeAmount, calculateAttenderChargeAmount, inclusiveStayDays,
        fillFromPreviousBooking: fillAdminBookingFormFromPreviousBooking,
    });
}
function bindRequesterAttenderRequirement() {
    const attender = document.getElementById("req-attender");
    const morningShiftInput = document.getElementById("req-morning");
    const morningChargeability = document.getElementById("req-morning-chargeability");
    const morningChargeableInputs = Array.from(document.querySelectorAll('input[name="req-morning-chargeable"]'));
    const shiftInputs = ["req-morning", "req-evening"].map((id) => document.getElementById(id));
    const syncMorningChargeability = () => {
        const enabled = Boolean(attender?.checked && morningShiftInput?.checked);
        if (morningChargeability) {
            morningChargeability.hidden = !enabled;
        }
        morningChargeableInputs.forEach((input) => {
            input.disabled = !enabled;
        });
    };
    const syncAttender = () => {
        const enabled = Boolean(attender?.checked);
        shiftInputs.forEach((input) => {
            if (!input) return;
            input.disabled = !enabled;
            if (!enabled) {
                input.checked = false;
            }
        });
        syncMorningChargeability();
    };
    attender?.addEventListener("change", syncAttender);
    morningShiftInput?.addEventListener("change", syncMorningChargeability);
    syncAttender();
}

function bindRequesterBudgetHeadFields() {
    const budgetOptions = Array.from(document.querySelectorAll("[data-requester-budget-head-field]"));
    const syncBudgetHeadOption = (checkbox, shouldFocus = false) => {
        const field = document.getElementById(checkbox.dataset.requesterBudgetHeadField);
        const wrapper = field?.closest(".budget-head-input");
        if (!field || !wrapper) return;
        wrapper.hidden = !checkbox.checked;
        if (checkbox.checked && shouldFocus) {
            field.focus();
        }
        if (!checkbox.checked) {
            field.value = "";
        }
    };
    budgetOptions.forEach((checkbox) => {
        syncBudgetHeadOption(checkbox);
        checkbox.addEventListener("change", () => syncBudgetHeadOption(checkbox, true));
    });
    document.getElementById("req-clear-budget-head")?.addEventListener("click", () => {
        budgetOptions.forEach((checkbox) => {
            checkbox.checked = false;
            syncBudgetHeadOption(checkbox);
        });
    });
    document.getElementById("req-clear-visitor-category")?.addEventListener("click", () => {
        document.querySelectorAll('input[name="req-visitor-category"]').forEach((input) => {
            input.checked = false;
        });
    });
    document.getElementById("req-clear-visitor-nationality")?.addEventListener("click", () => {
        document.querySelectorAll('input[name="req-visitor-nationality"]').forEach((input) => {
            input.checked = false;
        });
    });
}

function readAdminBookingPayload() {
    return buildAdminBookingPayload(document, buildIsoDateTime);
}

async function openAdminBookingForm(prefill = null, context = "booking") {
    try {
        const rooms = await fetchRooms();
        const selectedRoomId = prefill?.room || prefill?.preferred_room || "";
        const createBookingFromForm = async ({ generateMailTemplate = false } = {}) => {
            const payload = readAdminBookingPayload();
            const endpoint = generateMailTemplate ? "/api/bookings/create-mail-template/" : "/api/bookings/create/";
            const created = await apiFetch(endpoint, { method: "POST", body: payload });
            const bookingSummary = buildCreatedBookingSummary(created, payload, rooms);
            toast(generateMailTemplate ? "Booking created and mail template generated." : "Booking created successfully.");
            closeModal();
            await showCreatedBookingInCalendarSide(bookingSummary);
            if (generateMailTemplate) {
                openBookingMailTemplateModal(created.mail_template || {});
            }
        };
        openActionModal({
            title: context === "request" ? "Create Booking From Request" : "Create Booking",
            body: adminBookingFormHtml(prefill || {}, context),
            confirmText: "Create Booking",
            confirmClass: "primary-btn",
            footerHtml: `
                <button class="outline-btn" type="button" data-close-modal>Cancel</button>
                <button class="outline-btn" type="button" id="modal-create-booking-mail">Create Booking and Mail</button>
                <button class="primary-btn" type="button" id="modal-confirm">Create Booking</button>
            `,
            wide: true,
            onBind: () => {
                bindAdminBookingForm(rooms, selectedRoomId, prefill?.preferred_prefix || state.prefix);
                const mailButton = document.getElementById("modal-create-booking-mail");
                mailButton?.addEventListener("click", async () => {
                    mailButton.disabled = true;
                    try {
                        await createBookingFromForm({ generateMailTemplate: true });
                    } catch (error) {
                        toast(error.message, "error");
                        mailButton.disabled = false;
                    }
                });
            },
            onConfirm: async () => createBookingFromForm(),
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
    viewRoot().innerHTML = adminRequestsPageHtml(state.bookingRequestFilter, filterTabs);
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
    try {
        const rows = await apiFetch(requestEndpoint("admin", state.bookingRequestFilter));
        if (!rows.length) {
            list.innerHTML = `<div class="empty-state">No ${state.bookingRequestFilter === "all" ? "" : titleCase(state.bookingRequestFilter).toLowerCase()} booking requests.</div>`;
            loadWorkflowNotificationCounts();
            return;
        }
        list.innerHTML = rows.map((request) => bookingRequestCard(request)).join("");
        list.querySelectorAll("[data-request-id]").forEach((card) => {
            card.addEventListener("click", () => openAdminBookingRequestDetails(rows.find((item) => String(item.id) === card.dataset.requestId)));
        });
        loadWorkflowNotificationCounts();
    } catch (error) {
        list.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
    }
}

function bookingRequestCard(request) {
    return adminRequestCard(request, { escapeHtml, formatDateRange, titleCase });
}

async function fetchRooms() {
    if (state.rooms.length) {
        return state.rooms;
    }
    state.rooms = await fetchAllPaginated("/api/rooms/?page_size=100");
    return state.rooms;
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
            title: "Create Booking From Request",
            body: adminBookingFormHtml(detail, "request"),
            wide: true,
            footerHtml: reviewFooterHtml(isPending, adminReviewRemarksHtml()),
            onBind: () => {
                bindAdminBookingForm(rooms, detail.preferred_room || "", detail.preferred_prefix || state.prefix);
                document.querySelectorAll("[data-review-action]").forEach((button) => {
                    button.addEventListener("click", () => {
                        if (button.dataset.reviewAction === "delete") {
                            const remarks = document.getElementById("admin-review-remarks")?.value?.trim() || "";
                            if (!remarks) {
                                toast("Remarks are required.", "error");
                                document.getElementById("admin-review-remarks")?.focus();
                                return;
                            }
                            openDeleteAdminBookingRequestModal(detail, remarks);
                            return;
                        }
                        runBookingRequestReviewAction(button, detail);
                    });
                });
            },
        });
    } catch (error) {
        toast(error.message, "error");
    }
}

async function runBookingRequestReviewAction(button, request) {
    const action = button.dataset.reviewAction;
    const remarks = document.getElementById("admin-review-remarks")?.value?.trim() || "";
    if ((action === "reject" || action === "sendBack") && !remarks) {
        toast("Remarks are required.", "error");
        document.getElementById("admin-review-remarks")?.focus();
        return;
    }
    button.disabled = true;
    try {
        if (action === "approve") {
            const { remarks: bookingRemarks, ...bookingPayload } = readAdminBookingPayload();
            const payload = { ...bookingPayload, booking_remarks: bookingRemarks, remarks };
            await apiFetch(`/api/admin/booking-requests/${request.id}/approve/`, { method: "POST", body: payload });
            toast("Booking request approved and booking created.");
        } else if (action === "reject") {
            await apiFetch(`/api/admin/booking-requests/${request.id}/reject/`, { method: "POST", body: { remarks } });
            toast("Booking request rejected.");
        } else if (action === "sendBack") {
            await apiFetch(`/api/admin/booking-requests/${request.id}/send-back/`, { method: "POST", body: { remarks } });
            toast("Request sent back for correction.");
        }
        closeModal();
        await loadBookingRequests();
    } catch (error) {
        toast(error.message, "error");
        button.disabled = false;
    }
}

function openDeleteAdminBookingRequestModal(request, remarks) {
    openActionModal({
        title: "Delete Booking Request",
        body: `
            <p class="item-meta">Are you sure you want to delete this booking request?</p>
            <p class="item-meta"><strong>Remarks:</strong> ${escapeHtml(remarks)}</p>
        `,
        confirmText: "Delete Request",
        confirmClass: "danger-btn",
        onConfirm: async () => {
            await apiFetch(`/api/admin/booking-requests/${request.id}/delete/`, { method: "DELETE", body: { remarks } });
            toast("Booking request deleted successfully.");
            await loadBookingRequests();
        },
    });
}

function openBookingRequestDetails(request) {
    openDetailsModal("Booking Request Details", bookingRequestDetailRows(request));
}

function bookingRequestDetailRows(request, options = {}) {
    return requestDetailRows(request, options, {
        normalizedBudgetHeadFields,
        titleCase,
        formatDateTime,
        visitorNationalityLabel,
        yesNo,
        shiftsText,
    });
}

function renderSuperadminAccountsView() {
    if (!isSuperadmin()) {
        navigateToView("calendar", true);
        return;
    }
    viewRoot().innerHTML = renderAccountsPageHtml(
        state.superadminAccountRoleFilter, state.superadminAccountStatusFilter,
    );
    document.getElementById("simple-account-role").addEventListener("change", (event) => {
        state.superadminAccountRoleFilter = event.target.value;
        loadSuperadminAccounts();
    });
    document.getElementById("simple-account-status").addEventListener("change", (event) => {
        state.superadminAccountStatusFilter = event.target.value;
        loadSuperadminAccounts();
    });
    document.getElementById("refresh-superadmin-accounts").addEventListener("click", loadSuperadminAccounts);
    loadSuperadminAccounts();
}

async function loadSuperadminAccounts() {
    const list = document.getElementById("superadmin-accounts-list");
    if (!list) {
        return;
    }
    list.innerHTML = `<div class="loading-state">Loading user profiles...</div>`;
    try {
        const rows = await apiFetch(accountsEndpoint(
            state.superadminAccountRoleFilter,
            state.superadminAccountStatusFilter,
        ));
        if (!rows.length) {
            list.innerHTML = `<div class="empty-state">${superadminAccountEmptyText()}</div>`;
            loadWorkflowNotificationCounts();
            return;
        }
        list.innerHTML = rows.map((account) => superadminAccountCard(account)).join("");
        list.querySelectorAll("[data-superadmin-account-id]").forEach((card) => {
            const account = rows.find((item) => String(item.id) === card.dataset.superadminAccountId);
            card.addEventListener("click", () => openSuperadminAccountDetails(account));
        });
        loadWorkflowNotificationCounts();
    } catch (error) {
        list.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
    }
}

function superadminAccountEmptyText() {
    return accountEmptyText(
        state.superadminAccountRoleFilter,
        state.superadminAccountStatusFilter,
        titleCase,
    );
}

function superadminAccountCard(account) {
    return renderAccountCard(account, escapeHtml, titleCase);
}

function superadminAccountActionButtonsHtml(account) {
    return accountActionButtons(account);
}

function openSuperadminAccountDetails(account) {
    if (!account) {
        return;
    }
    const rows = accountDetailRows(account, titleCase, formatDateTime);
    openActionModal({
        title: `${titleCase(account.role)} Profile`,
        body: detailsRowsHtml(rows),
        footerHtml: `
            <button class="outline-btn" type="button" data-close-modal>Close</button>
            ${superadminAccountActionButtonsHtml(account)}
        `,
        onBind: () => {
            document.querySelectorAll("[data-superadmin-account-action]").forEach((button) => {
                button.addEventListener("click", () => {
                    closeModal();
                    handleSuperadminAccountAction(button.dataset.superadminAccountAction, account);
                });
            });
        },
    });
}

function handleSuperadminAccountAction(action, account) {
    if (action === "approve") {
        openActionModal({
            title: `Approve ${titleCase(account.role)} Account`,
            body: `<p class="item-meta">Approve ${escapeHtml(account.name || account.email)}?</p>`,
            confirmText: "Approve",
            confirmClass: "success-btn",
            onConfirm: async () => {
                await apiFetch(`/api/superadmin/account-requests/${account.id}/approve/`, { method: "POST", body: {} });
                toast("Account approved successfully.");
                await loadSuperadminAccounts();
            },
        });
    } else if (action === "reject") {
        openRemarksModal(`Reject ${titleCase(account.role)} Account`, "Reject", "danger-btn", async (remarks) => {
            await apiFetch(`/api/superadmin/account-requests/${account.id}/reject/`, { method: "POST", body: { remarks } });
            toast("Account rejected successfully.");
            await loadSuperadminAccounts();
        });
    } else if (action === "delete") {
        openActionModal({
            title: "Delete Account",
            body: `
                <p class="item-meta">Delete ${escapeHtml(account.name || account.email)}?</p>
                <p class="item-meta">This deletes the linked user account and profile. This action cannot be undone.</p>
            `,
            confirmText: "Delete",
            confirmClass: "danger-btn",
            onConfirm: async () => {
                await apiFetch(`/api/superadmin/account-requests/${account.id}/delete/`, { method: "DELETE" });
                toast("Account deleted successfully.");
                await loadSuperadminAccounts();
            },
        });
    }
}

function renderMyRequestsView() {
    viewRoot().innerHTML = myRequestsPageHtml(state.myRequestFilter, filterTabs);
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
    try {
        const rows = await apiFetch(requestEndpoint("requester", state.myRequestFilter));
        if (!rows.length) {
            list.innerHTML = `<div class="empty-state">No booking requests found.</div>`;
            loadWorkflowNotificationCounts();
            return;
        }
        list.innerHTML = rows.map((request) => myRequestCard(request, {
            escapeHtml,
            formatDateRange,
            titleCase,
        })).join("");
        list.querySelectorAll("[data-my-request-id]").forEach((card) => {
            card.addEventListener("click", () => openMyRequestDetails(rows.find((item) => String(item.id) === card.dataset.myRequestId)));
        });
        loadWorkflowNotificationCounts();
    } catch (error) {
        list.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
    }
}

function openMyRequestDetails(request) {
    if (!request) {
        return;
    }
    const { canEdit, canPullBack, editText, pullBackUnavailableText } = requestActions(request);
    openActionModal({
        title: `Booking Request #${request.id}`,
        body: detailsRowsHtml(bookingRequestDetailRows(request, { requesterView: true })),
        wide: true,
        footerHtml: `
            <button class="outline-btn" type="button" data-close-modal>Close</button>
            ${canEdit ? `<button class="primary-btn" type="button" id="my-request-edit">${editText}</button>` : ""}
            ${canPullBack
                ? `<button class="danger-btn" type="button" id="my-request-pull-back">Pull Back</button>`
                : `<span class="item-meta">${pullBackUnavailableText}</span>`}
        `,
        onBind: () => {
            document.getElementById("my-request-edit")?.addEventListener("click", () => {
                closeModal();
                openRequestForm(request);
            });
            document.getElementById("my-request-pull-back")?.addEventListener("click", () => openPullBackMyRequestModal(request));
        },
    });
}

function openPullBackMyRequestModal(request) {
    openActionModal({
        title: "Pull Back Request",
        body: `
            <p class="item-meta">Pull back this request before an administrator reviews it?</p>
            <div class="field-row">
                <label for="pull-back-request-remarks">Reason (Optional)</label>
                <textarea id="pull-back-request-remarks" placeholder="Optional reason for pulling back"></textarea>
            </div>
        `,
        confirmText: "Pull Back",
        confirmClass: "danger-btn",
        onConfirm: async () => {
            const remarks = document.getElementById("pull-back-request-remarks")?.value?.trim() || "";
            await apiFetch(`/api/requester/booking-requests/${request.id}/delete/`, { method: "DELETE", body: { remarks } });
            toast("Request pulled back successfully.");
            await loadMyRequests();
        },
    });
}

async function openAdminAvailableRoomsChooser(options = {}) {
    const prefill = options.prefill || {};
    const prefillArrival = indiaParts(prefill.arrival_at || "");
    const prefillDeparture = indiaParts(prefill.departure_at || "");
    const calendarSchedule = selectedScheduleFromCalendar();
    const arrivalDate = options.arrivalDate || prefillArrival.date || calendarSchedule.arrivalDate;
    const departureDate = options.departureDate || prefillDeparture.date || calendarSchedule.departureDate;
    const arrivalTime = options.arrivalTime || prefillArrival.time || "10:00";
    const departureTime = options.departureTime || prefillDeparture.time || "18:00";
    const prefix = options.prefix || prefill.preferred_prefix || prefill.prefix || state.prefix;
    if (!arrivalDate) {
        toast("Select a date range first.", "error");
        return;
    }
    if (!departureDate) {
        toast("Select a departure date first.", "error");
        return;
    }
    if (departureDate < arrivalDate) {
        toast("Departure date cannot be before arrival date.", "error");
        return;
    }

    openActionModal({
        title: "Available Rooms",
        body: `<div class="loading-state">Loading available rooms...</div>`,
        footerHtml: `<button class="outline-btn" type="button" data-close-modal>Close</button>`,
    });

    try {
        const data = await apiFetch(`/api/room-available-rooms-range/?arrival_date=${arrivalDate}&departure_date=${departureDate}&prefix=${encodeURIComponent(prefix)}`);
        const rooms = data?.rooms || [];
        const body = document.querySelector(".modal-body");
        if (!body) {
            return;
        }
        body.innerHTML = renderAvailableRoomsChooserHtml(rooms, {
            prefix, responsePrefix: data?.prefix, arrivalDate, departureDate,
            escapeHtml, scheduleDisplayText, roomLabel, availableRoomStatusText,
        });
        body.querySelectorAll("[data-room-index]").forEach((button) => {
            button.addEventListener("click", () => {
                const room = rooms[Number(button.dataset.roomIndex)];
                const selectedPrefix = room?.prefix || data?.prefix || prefix;
                const selectedArrivalTime = availableRoomPrefillArrivalTime(room, arrivalDate, arrivalTime || "10:00");
                closeModal();
                openAdminBookingForm({
                    ...prefill,
                    room: room?.room_id || room?.id || "",
                    prefix: selectedPrefix,
                    preferred_prefix: selectedPrefix,
                    arrival_at: buildIsoDateTime(arrivalDate, selectedArrivalTime),
                    departure_at: buildIsoDateTime(departureDate, departureTime || "18:00"),
                });
            });
        });
    } catch (error) {
        const body = document.querySelector(".modal-body");
        if (body) {
            body.innerHTML = `<div class="empty-state">${escapeHtml(error.message || "Could not load available rooms. Please try again.")}</div>`;
        }
    }
}

async function openRequestForm(existing = null) {
    const editing = Boolean(existing);
    const arrival = editing ? indiaParts(existing.arrival_at) : { date: state.rangeStart || todayIso(), time: "10:00" };
    const departure = editing ? indiaParts(existing.departure_at) : { date: state.rangeEnd || state.rangeStart || todayIso(), time: "18:00" };
    if (!editing) {
        const calendarSchedule = requesterSelectedSchedule();
        arrival.date = calendarSchedule.arrivalDate;
        departure.date = calendarSchedule.departureDate;
    }
    openActionModal({
        title: editing ? "Edit Request" : "Request Booking",
        body: renderRequesterBookingForm(existing, {
            arrival, departure, user: state.user,
            budgetHead: normalizedBudgetHeadFields(existing || {}),
            escapeHtml, htmlValue, formatDateOnly,
        }),
        confirmText: editing ? "Resubmit Request" : "Submit Request",
        confirmClass: "primary-btn",
        onBind: () => {
            bindRequesterAttenderRequirement();
            bindRequesterBudgetHeadFields();
        },
        onConfirm: async () => submitRequesterRequest(existing),
    });
}

async function submitRequesterRequest(existing = null) {
    const payload = buildRequesterBookingPayload(document, state.user, buildIsoDateTime);
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
        body: `<div class="field-row"><label for="modal-remarks">Remarks (Optional)</label><textarea id="modal-remarks" placeholder="${escapeHtml(placeholder)}"></textarea></div>`,
        confirmText,
        confirmClass,
        onConfirm: async () => onConfirm(document.getElementById("modal-remarks").value),
    });
}

function openDetailsModal(title, rows) {
    openActionModal({
        title,
        body: detailsRowsHtml(rows),
        confirmText: "Close",
        confirmClass: "outline-btn",
        onConfirm: async () => {},
    });
}

function detailsRowsHtml(rows) {
    return renderDetailsRowsHtml(rows, escapeHtml, valueOrDash);
}

function printDetailsDocument(title, rows, subtitle = "") {
    const printWindow = window.open("", "_blank");
    if (!printWindow) {
        toast("Allow pop-ups to print booking details.", "error");
        return;
    }
    printWindow.document.write(printableDocumentHtml(
        title, printableDetailsRowsHtml(rows), subtitle, escapeHtml,
    ));
    printWindow.document.close();
    printWindow.focus();
    window.setTimeout(() => {
        printWindow.print();
    }, 250);
}

function printableDetailsRowsHtml(rows) {
    return renderPrintableDetailsRowsHtml(rows, escapeHtml, valueOrDash);
}

function openActionModal({ title, body, confirmText, confirmClass, onConfirm, onBind, wide = false, footerHtml = "" }) {
    modalController.open({ title, body, confirmText, confirmClass, onConfirm, onBind, wide, footerHtml });
}

function closeModal() {
    modalController.close();
}

async function boot() {
    if (!state.access) {
        renderAuth();
        return;
    }
    try {
        state.user = await apiFetch("/api/auth/me/");
        sessionStore.writeUser(state.user);
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

observeRequiredMarks();
boot();
