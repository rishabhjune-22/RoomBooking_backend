export function accountsEndpoint(roleFilter, statusFilter) {
    const params = new URLSearchParams();
    if (roleFilter !== "all") params.set("role", roleFilter);
    if (statusFilter !== "all") params.set("status", statusFilter);
    return `/api/superadmin/account-requests/${params.size ? `?${params}` : ""}`;
}

export function accountsPageHtml(roleFilter, statusFilter) {
    const option = (value, selected, label = value) => `<option value="${value}" ${selected === value ? "selected" : ""}>${label}</option>`;
    return `<div class="section-header"><div><h2>User Profiles</h2>
        <p>Manage administrator accounts and approval requests.</p></div>
        <button class="outline-btn" id="refresh-superadmin-accounts">Refresh</button></div>
        <section class="surface side-panel"><div class="simple-filter-grid">
            <div class="field-row"><label for="simple-account-role">Role</label><select id="simple-account-role">
                ${option("all", roleFilter, "All")}${option("admin", roleFilter, "Admin")}${option("requester", roleFilter, "Requester")}
            </select></div>
            <div class="field-row"><label for="simple-account-status">Approval Status</label><select id="simple-account-status">
                ${option("all", statusFilter, "All")}${option("pending", statusFilter, "Pending")}
                ${option("approved", statusFilter, "Approved")}${option("rejected", statusFilter, "Rejected")}
            </select></div>
        </div><div id="superadmin-accounts-list" class="card-list"><div class="loading-state">Loading user profiles...</div></div></section>`;
}

export function emptyText(role, status, titleCase) {
    if (role === "all" && status === "all") return "No admin or requester profiles found.";
    const roleText = role === "all" ? "accounts" : `${role} accounts`;
    return status === "all" ? `No ${roleText} found.` : `No ${titleCase(status).toLowerCase()} ${roleText} found.`;
}

export function accountCard(account, escapeHtml, titleCase) {
    return `<article class="item-card" data-superadmin-account-id="${account.id}"><div class="item-main"><div>
        <h3 class="item-title">${escapeHtml(account.name || account.email)}</h3><p class="item-meta">${escapeHtml(account.email || "-")}</p>
        <p class="item-meta">${titleCase(account.role)} - ${escapeHtml(account.department || "No department")}</p>
        </div><span class="status-chip ${account.approval_status}">${titleCase(account.approval_status)}</span></div></article>`;
}

export function actionButtons(account) {
    const actions = [];
    if (account.approval_status === "pending") {
        actions.push(`<button class="success-btn" type="button" data-superadmin-account-action="approve">Approve</button>`);
        actions.push(`<button class="danger-btn" type="button" data-superadmin-account-action="reject">Reject</button>`);
    } else if (account.approval_status === "approved") {
        actions.push(`<button class="danger-btn" type="button" data-superadmin-account-action="reject">Reject</button>`);
    } else if (account.approval_status === "rejected") {
        actions.push(`<button class="success-btn" type="button" data-superadmin-account-action="approve">Approve Again</button>`);
    }
    actions.push(`<button class="danger-btn" type="button" data-superadmin-account-action="delete">Delete</button>`);
    return actions.join("");
}

export function detailRows(account, titleCase, formatDateTime) {
    return [
        { section: "Account" }, ["Name", account.name], ["Email", account.email], ["Role", titleCase(account.role)],
        ["Approval Status", titleCase(account.approval_status)], ["Department", account.department], ["Designation", account.designation],
        ["Mobile", account.mobile], { section: "Approval" }, ["Approved by", account.approved_by_name],
        ["Approved at", formatDateTime(account.approved_at)], ["Remarks", account.remarks], { section: "Audit" },
        ["Created at", formatDateTime(account.created_at)], ["Updated at", formatDateTime(account.updated_at)],
    ];
}
