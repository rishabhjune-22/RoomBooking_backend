import assert from "node:assert/strict";
import test from "node:test";

import {
    calculateAttenderChargeAmount,
    calculateRoomChargeAmount,
    inclusiveStayDays,
    normalizedBudgetHeadFields,
} from "./booking-domain.js";
import { filterSheetRooms, sheetTableHtml } from "./booking-sheet.js";
import { bindTableActions, tableHtml as chargeSheetTableHtml } from "./charge-sheet.js";
import { readAdminBookingPayload } from "./admin-booking-form.js";
import { bookingDetailRows } from "./details-view.js";
import { printableDocumentHtml } from "./details-view.js";
import { createdBookingSidePanelHtml, createdBookingSummary, createMoreBookingPrefill } from "./booking-helpers.js";
import { accountsPageHtml } from "./account-view.js";
import { adminRequestsPageHtml, myRequestsPageHtml } from "./request-view.js";
import { detailPanelHtml, rowsForUser, summaryHtml } from "./workflow-notifications.js";
import { bookingMailTemplateContent, shareLinkContent, shareOptionsContent } from "./modal.js";
import { reviewFooterHtml } from "./request-view.js";
import { buildRequesterBookingPayload } from "./requester-booking-form.js";

test("charges recalculate for stay length, shifts, room type, and nationality", () => {
    assert.equal(inclusiveStayDays("2026-10-01", "2026-10-03"), 3);
    assert.equal(calculateAttenderChargeAmount(true, true, true, true, 3), 5100);
    assert.equal(calculateAttenderChargeAmount(false, true, true, true, 3), 0);
    assert.equal(calculateRoomChargeAmount({ prefix: "Gamma", has_attached_bath: false }, "", 2), 2600);
    assert.equal(calculateRoomChargeAmount({ prefix: "Gamma", has_attached_bath: false }, "", 2, "foreigner"), 3600);
    assert.equal(calculateRoomChargeAmount({ prefix: "Delta" }, "Delta", 2), null);
});

test("sheet rooms filter by building and sort by configured building then room number", () => {
    const rooms = [
        { id: 1, prefix: "Gamma", number: "10" },
        { id: 2, prefix: "Beta", number: "2" },
        { id: 3, prefix: "Gamma", number: "3" },
    ];
    const label = (room) => `${room.prefix}-${room.number}`;
    assert.deepEqual(filterSheetRooms(rooms, "Gamma", ["Delta", "Gamma", "Beta"], label).map((room) => room.id), [3, 1]);
    assert.deepEqual(filterSheetRooms(rooms, "all", ["Delta", "Gamma", "Beta"], label).map((room) => room.id), [3, 1, 2]);
});

test("legacy and explicit budget-head form state normalize without losing values", () => {
    assert.deepEqual(normalizedBudgetHeadFields({ budget_head_type: "project_head", budget_head_value: "P-42" }), {
        individual: "",
        instituteHead: "",
        projectHead: "P-42",
    });
    assert.deepEqual(normalizedBudgetHeadFields({ budget_head_name: "Visitor", budget_head_department_name: "CSE" }), {
        individual: "Visitor",
        instituteHead: "CSE",
        projectHead: "",
    });
});

test("requester payload preserves form state and disables unchecked dependent values", () => {
    const values = {
        "req-arrival-date": "2026-10-01", "req-departure-date": "2026-10-03",
        "req-arrival-time": "10:00", "req-departure-time": "18:00",
        "req-room-preference-note": "Attached bath", "req-visitor-name": "Guest",
        "req-visitor-designation": "Professor", "req-visitor-organisation": "IIT",
        "req-visitor-gender": "Other", "req-visitor-mobile": "123", "req-visitor-email": "g@example.test",
        "req-purpose": "Workshop", "req-budget-name": "", "req-budget-department": "CSE",
        "req-budget-project-code": "", "req-requestor-name": "Fallback", "req-requestor-department": "EE",
        "req-requestor-designation": "Faculty", "req-requestor-mobile": "456", "req-requestor-email": "r@example.test",
    };
    const checked = new Set(["req-attender", "req-morning", "req-budget-institute-head"]);
    const document = {
        getElementById: (id) => ({ value: values[id] || "", checked: checked.has(id) }),
        querySelector: (selector) => ({ value: selector.includes("nationality") ? "indian" : selector.includes("category") ? "institute_guest" : "yes" }),
    };
    const payload = buildRequesterBookingPayload(document, { name: "Requester", email: "account@example.test" }, (date, time) => `${date}T${time}`);
    assert.equal(payload.requestor_name, "Requester");
    assert.equal(payload.budget_head_department_name, "CSE");
    assert.equal(payload.attender_morning_shift, true);
    assert.equal(payload.attender_evening_shift, false);
    assert.equal(payload.visitor_nationality, "indian");
});

test("admin payload enforces required fields and dependent charge state", () => {
    const values = {
        "admin-room": "7", "admin-arrival-date": "2026-10-01", "admin-arrival-time": "10:00",
        "admin-departure-date": "2026-10-02", "admin-departure-time": "18:00",
        "admin-visitor-name": "Guest", "admin-room-charge-status": "no",
        "admin-room-charge-amount": "1500", "admin-attender-charge-status": "yes",
        "admin-attender-charge-amount": "850", "admin-budget-name": "Guest",
    };
    const checked = new Set(["admin-attender", "admin-morning", "admin-budget-individual"]);
    const document = {
        getElementById: (id) => ({ value: values[id] || "", checked: checked.has(id) }),
        querySelector: (selector) => ({ value: selector.includes("nationality") ? "foreigner" : selector.includes("category") ? "other_guest" : "yes" }),
    };
    const payload = readAdminBookingPayload(document, (date, time) => `${date}T${time}`);
    assert.equal(payload.room, "7");
    assert.equal(payload.room_charges_amount, 0);
    assert.equal(payload.attender_charges_amount, 850);
    assert.equal(payload.budget_head_name, "Guest");
});

test("booking detail rows include normalized values and edit history", () => {
    const rows = bookingDetailRows({
        id: 9, status: "active", attender_required: false,
        budget_head_type: "project_head", budget_head_value: "P-9",
        edit_history: [{ field_name: "remarks", edited_by_email: "admin@example.test", edited_at: "now", old_value: "a", new_value: "b" }],
    }, {
        bookingDisplayId: ({ id }) => `B-${id}`,
        normalizedBudgetHeadFields, titleCase: (value) => value,
        formatDateTime: (value) => value, visitorNationalityLabel: (value) => value,
        yesNo: (value) => value ? "Yes" : "No", shiftsText: () => "None",
    });
    assert.ok(rows.some((row) => Array.isArray(row) && row[0] === "Project code" && row[1] === "P-9"));
    assert.ok(rows.some((row) => Array.isArray(row) && row[0] === "New value" && row[1] === "b"));
});

test("sheet renderers preserve table hooks used by delegated event handlers", () => {
    const chargeHtml = chargeSheetTableHtml([{ id: 1 }], {
        headerHtml: (field) => `<th data-charge-sort="${field}"></th>`,
        rowHtml: ({ id }) => `<tr data-charge-row-id="${id}"></tr>`,
        exportButtonsHtml: `<button data-sheet-export="charge"></button>`, legendHtml: "",
    });
    assert.match(chargeHtml, /data-charge-sort="serial_no"/);
    assert.match(chargeHtml, /data-charge-row-id="1"/);

    const bookingHtml = sheetTableHtml({
        range: { start: "2026-10-01", end: "2026-10-01" }, dates: ["2026-10-01"],
        rooms: [{ id: 7, number: "7" }], cells: new Map(), visibleBookingCount: 0,
    }, {
        escapeHtml: String, formatSheetDate: String, roomLabel: ({ number }) => number,
        cellHtml: () => `<button data-booking-action="create"></button>`, exportButtonsHtml: "", legendHtml: "",
    });
    assert.match(bookingHtml, /data-booking-action="create"/);
    assert.match(bookingHtml, /Visitor Room/);
});

test("request and account layouts preserve filter and refresh hooks", () => {
    const tabs = (active) => `<button data-filter="${active}"></button>`;
    const adminHtml = adminRequestsPageHtml("pending", tabs);
    const requesterHtml = myRequestsPageHtml("all", tabs);
    const accountsHtml = accountsPageHtml("requester", "approved");
    assert.match(adminHtml, /id="refresh-booking-requests"/);
    assert.match(adminHtml, /id="booking-requests-list"/);
    assert.match(requesterHtml, /id="refresh-my-requests"/);
    assert.match(accountsHtml, /value="requester" selected/);
    assert.match(accountsHtml, /value="approved" selected/);
});

test("notification presentation preserves navigation hooks and escapes content", () => {
    const escape = (value) => String(value).replaceAll("<", "&lt;");
    const rows = [{ view: "myRequests", title: "Mine", description: "<new>", count: 2, rawCount: 2, details: [] }];
    assert.match(summaryHtml(rows, 2, escape), /data-notification-view="myRequests"/);
    assert.match(summaryHtml(rows, 2, escape), /&lt;new>/);
    assert.match(detailPanelHtml([{ title: "Update", message: "Ready" }], escape), /notification-detail-card/);
    assert.match(detailPanelHtml([], escape), /No notification details available/);
});

test("modal content preserves clipboard, sharing, and review action hooks", () => {
    const helpers = { escapeHtml: String, htmlValue: String, formatDateTime: String };
    const mail = bookingMailTemplateContent({ subject: "Subject", body: "Hello" }, helpers);
    assert.match(mail.footerHtml, /id="copy-mail-body"/);
    assert.match(mail.body, /id="booking-mail-preview"/);
    assert.match(shareLinkContent({ url: "https:\/\/example.test" }, "booking", helpers), /id="open-share-link"/);
    assert.match(shareOptionsContent(), /id="share-validity"/);
    assert.match(reviewFooterHtml(true, `<textarea id="admin-review-remarks"></textarea>`), /data-review-action="approve"/);
    assert.doesNotMatch(reviewFooterHtml(false, ""), /data-review-action="approve"/);
});

test("created-booking helpers preserve API fallbacks and reusable prefill state", () => {
    const summary = createdBookingSummary({ booking_id: 4 }, {
        room: "2", visitor_name: "Guest", room_charges_amount: 0,
    }, [{ id: 2, number: "201" }], {
        roomLabel: ({ number }) => `Gamma-${number}`, prefixFromSummary: () => "Gamma",
    });
    assert.equal(summary.id, 4);
    assert.equal(summary.room_name, "Gamma-201");
    assert.equal(summary.preferred_prefix, "Gamma");
    const prefill = createMoreBookingPrefill({ requestor_name: "Host", room_charges_amount: 0 }, () => "Beta");
    assert.equal(prefill.requestor_name, "Host");
    assert.equal(prefill.preferred_prefix, "Beta");
    assert.equal(prefill.room_charges_amount, 0);
    assert.match(createdBookingSidePanelHtml(summary, {
        escapeHtml: String, selectedRangeDisplayText: () => "1–2 Oct",
        titleCase: String, formatDateRange: () => "1 to 2 Oct",
    }), /Recent booking created/);
});

test("printable document renderer escapes headings and includes detail rows", () => {
    const html = printableDocumentHtml("<Booking>", `<div class="row">Details</div>`, "Summary", (value) => String(value).replaceAll("<", "&lt;").replaceAll(">", "&gt;"));
    assert.match(html, /&lt;Booking&gt;/);
    assert.match(html, /class="row"/);
    assert.match(html, /@page/);
});

test("notification row model respects user roles", () => {
    const rows = rowsForUser({ counts: { my_requests: 2 }, rawCounts: { my_requests: 3 },
        user: { role: "requester" }, adminLike: false, superadmin: false,
        detailsForView: () => [], items: { my_requests: [{ title: "Approved" }] } });
    assert.equal(rows.length, 1);
    assert.equal(rows[0].view, "myRequests");
    assert.equal(rows[0].details.length, 1);
});

test("charge-sheet action binder routes delegated edit actions", async () => {
    let editingId = null;
    const shell = {};
    bindTableActions(shell, { bindScroll: () => {}, onExport: () => {}, onShare: () => {}, onSort: () => {},
        onEdit: (id) => { editingId = id; }, onSave: async () => {}, onDelete: () => {} });
    await shell.onclick({ target: { closest: (selector) => selector === "[data-charge-action]"
        ? { dataset: { chargeAction: "edit", id: "42" } } : null } });
    assert.equal(editingId, "42");
});
