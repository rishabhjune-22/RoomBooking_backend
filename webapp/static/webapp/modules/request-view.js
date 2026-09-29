export const ADMIN_REQUEST_TABS = [
    ["all", "All"], ["pending", "Pending"], ["correction_required", "Correction Required"],
    ["approved", "Approved"], ["rejected", "Rejected"],
];
export const MY_REQUEST_TABS = ADMIN_REQUEST_TABS;

export function adminRequestsPageHtml(activeFilter, filterTabs) {
    return `<div class="section-header"><div><h2>Booking Requests</h2>
        <p>Review requester submissions and take approval actions.</p></div>
        <button class="outline-btn" id="refresh-booking-requests">Refresh</button></div>
        ${filterTabs(activeFilter, ADMIN_REQUEST_TABS)}
        <section class="surface side-panel"><div id="booking-requests-list" class="card-list">
            <div class="loading-state">Loading booking requests...</div>
        </div></section>`;
}

export function myRequestsPageHtml(activeFilter, filterTabs) {
    return `<div class="section-header"><div><h2>My Requests</h2>
        <p>Track and manage your submitted booking requests.</p></div>
        <button class="outline-btn" id="refresh-my-requests">Refresh</button></div>
        ${filterTabs(activeFilter, MY_REQUEST_TABS)}
        <section class="surface side-panel"><div id="my-requests-list" class="card-list">
            <div class="loading-state">Loading requests...</div>
        </div></section>`;
}

export function requestEndpoint(role, statusFilter) {
    const status = statusFilter === "all" ? "" : `?status=${encodeURIComponent(statusFilter)}`;
    return role === "admin" ? `/api/admin/booking-requests/${status}` : `/api/requester/booking-requests/${status}`;
}

export function adminRequestCard(request, { escapeHtml, formatDateRange, titleCase }) {
    return `<article class="item-card" data-request-id="${request.id}"><div class="item-main"><div>
        <h3 class="item-title">${escapeHtml(request.visitor_name || request.requester_name || "Booking request")}</h3>
        <p class="item-meta">${escapeHtml(request.requestor_department || request.requester_email || "-")} - ${formatDateRange(request)}</p>
        <p class="item-meta">Room: ${escapeHtml(request.preferred_room_name || request.preferred_prefix || "No preference")}</p>
        </div><span class="status-chip ${request.status}">${titleCase(request.status)}</span></div></article>`;
}

export function myRequestCard(request, { escapeHtml, formatDateRange, titleCase }) {
    return `<article class="item-card" data-my-request-id="${request.id}"><div class="item-main"><div>
        <h3 class="item-title">${escapeHtml(request.visitor_name || "Booking request")}</h3>
        <p class="item-meta">${formatDateRange(request)} - ${escapeHtml(request.room_preference_note || "No room preference note")}</p>
        ${request.admin_remarks ? `<p class="item-meta">Remarks: ${escapeHtml(request.admin_remarks)}</p>` : ""}
        </div><span class="status-chip ${request.status}">${titleCase(request.status)}</span></div></article>`;
}

export function requestDetailRows(request, options, helpers) {
    const { normalizedBudgetHeadFields, titleCase, formatDateTime, visitorNationalityLabel, yesNo, shiftsText } = helpers;
    const budget = normalizedBudgetHeadFields(request);
    const requesterView = options?.requesterView === true;
    return [
        { section: "Request Status" }, ["ID", request.id], ["Status", titleCase(request.status)],
        ["Requested at", formatDateTime(request.requested_at)], ["Reviewed by", request.reviewed_by_name],
        ["Reviewed at", formatDateTime(request.reviewed_at)], ["Admin remarks", request.admin_remarks],
        { section: "Schedule & Room" }, ["Arrival", formatDateTime(request.arrival_at)], ["Departure", formatDateTime(request.departure_at)],
        ...(!requesterView ? [["Building preference", request.preferred_prefix], ["Preferred room", request.preferred_room_name || "No specific room"]] : []),
        ["Room note", request.room_preference_note], { section: "Visitor Details" },
        ["Visitor name", request.visitor_name], ["Designation", request.visitor_designation], ["Organisation", request.visitor_organisation],
        ["Gender", request.visitor_gender], ["Guest nationality", visitorNationalityLabel(request.visitor_nationality)],
        ["Mobile", request.visitor_mobile], ["Email", request.visitor_email], ["Category", titleCase(request.visitor_category)],
        ["Purpose", request.purpose_of_visit], { section: "Budget Head" }, ["Individual", budget.individual],
        ["Institute Head", budget.instituteHead], ["Project code", budget.projectHead], { section: "Requester Details" },
        ["Requester account", request.requester_name], ["Requester email", request.requester_email], ["Requestor name", request.requestor_name],
        ["Designation", request.requestor_designation], ["Department", request.requestor_department], ["Mobile", request.requestor_mobile],
        ["Requestor email", request.requestor_email], { section: "Attender Requirement" },
        ["Attender required", yesNo(request.attender_required)], ["Shifts", shiftsText(request)], { section: "Deletion Audit" },
        ["Deleted", yesNo(request.is_deleted)], ["Deleted at", formatDateTime(request.deleted_at)], ["Deleted by", request.deleted_by_name],
        ["Deleted by role", titleCase(request.deleted_by_role)], ["Delete remarks", request.remarks],
    ];
}

export function requestActions(request) {
    return {
        canEdit: request.status === "pending" || request.status === "correction_required",
        canPullBack: request.can_pull_back === true,
        editText: request.status === "correction_required" ? "Edit & Resubmit" : "Edit",
        pullBackUnavailableText: request.admin_seen_at
            ? "Already seen by admin — pull back is no longer available."
            : "Pull back is unavailable for this request.",
    };
}

export function reviewFooterHtml(isPending, remarksHtml) {
    return `<div class="review-footer-stack"><div><div class="form-section-title">Review Remarks</div>${remarksHtml}</div>
        <div class="review-action-row">${isPending ? `<button class="success-btn" type="button" data-review-action="approve">Approve</button>
            <button class="danger-btn" type="button" data-review-action="reject">Reject</button>
            <button class="warn-btn" type="button" data-review-action="sendBack">Send Back</button>` : ""}
            <button class="danger-btn" type="button" data-review-action="delete">Delete Request</button></div></div>`;
}
