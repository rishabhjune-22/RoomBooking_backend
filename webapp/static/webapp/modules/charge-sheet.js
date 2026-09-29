export function endpoint(state) {
    const params = new URLSearchParams({ page_size: "100" });
    if (state.chargeSheetPrefixFilter !== "all") params.set("prefix", state.chargeSheetPrefixFilter);
    if (state.chargeSheetPaymentFilter !== "all") params.set("payment", state.chargeSheetPaymentFilter);
    if (state.chargeSheetCheckoutFrom) params.set("checkout_from", state.chargeSheetCheckoutFrom);
    if (state.chargeSheetCheckoutTo) params.set("checkout_to", state.chargeSheetCheckoutTo);
    if (state.chargeSheetSearch) params.set("search", state.chargeSheetSearch);
    if (state.chargeSheetOrdering) params.set("ordering", state.chargeSheetOrdering);
    return `/api/bookings/charge-sheet/?${params.toString()}`;
}

export function nextOrdering(current, field) {
    const active = current.startsWith("-") ? current.slice(1) : current;
    if (active !== field) return field;
    return current.startsWith("-") ? field : `-${field}`;
}

export function headerHtml(field, label, ordering, escapeHtml) {
    const active = ordering.startsWith("-") ? ordering.slice(1) : ordering;
    const selected = active === field;
    const direction = ordering.startsWith("-") ? "desc" : "asc";
    const classes = ["sortable-header", selected ? "sorted" : "", selected ? direction : ""].filter(Boolean);
    return `<th class="${classes.join(" ")}" data-charge-sort="${field}" tabindex="0" aria-sort="${selected ? (direction === "desc" ? "descending" : "ascending") : "none"}"><span class="header-label">${escapeHtml(label)}</span><span class="sort-caret" aria-hidden="true"></span></th>`;
}

export function rowHtml(row, { editingId, selectedId, escapeHtml, htmlValue, valueOrDash, formatDateTime, buildingRoomValue, isPastDateTime }) {
    const editing = String(editingId) === String(row.id);
    const selected = String(selectedId) === String(row.id);
    const input = (field, value, type = "text") => `<input class="sheet-inline-input" data-charge-field="${field}" type="${type}"${type === "number" ? ` min="0" step="0.01"` : ""} value="${htmlValue(value)}">`;
    const editable = (field, type = "text") => {
        if (!editing) return escapeHtml(valueOrDash(row[field]));
        if (field === "purpose_event" || field === "remarks") return `<textarea class="sheet-inline-input compact" data-charge-field="${field}">${htmlValue(row[field])}</textarea>`;
        return input(field, row[field] || "", type);
    };
    return `<tr class="${[selected ? "selected-row" : "", isPastDateTime(row?.check_out) ? "expired-row" : ""].filter(Boolean).join(" ")}" data-charge-row-id="${row.id}" aria-selected="${selected}">
        <td>${escapeHtml(row.serial_no || row.id)}</td><td>${escapeHtml(formatDateTime(row.check_in))}</td><td>${escapeHtml(formatDateTime(row.check_out))}</td><td>${escapeHtml(row.booking_reference_id || "-")}</td>
        <td>${editable("requestor_name")}</td><td>${editable("guest_name")}</td><td>${editable("purpose_event")}</td><td>${editable("remarks")}</td>
        <td>${escapeHtml(buildingRoomValue(row.delta, "Delta"))}</td><td>${escapeHtml(buildingRoomValue(row.gamma, "Gamma"))}</td><td>${escapeHtml(buildingRoomValue(row.beta, "Beta"))}</td>
        <td>${editable("room_charges_amount", "number")}</td><td>${editable("attender_charges_amount", "number")}</td><td>${escapeHtml(row.total_charges || "0.00")}</td>
        <td>${editing ? input("payment_received_date", row.payment_received_date || "", "date") : escapeHtml(row.payment_received_date || "-")}</td><td>${editable("budget_head_name")}</td>
        <td class="sheet-actions-col">${editing ? `<button class="sheet-action-btn" type="button" data-charge-action="save" data-id="${row.id}">Save</button><button class="sheet-action-btn" type="button" data-charge-action="cancel" data-id="${row.id}">Cancel</button>` : `<button class="sheet-action-btn" type="button" data-charge-action="edit" data-id="${row.id}">Edit</button><button class="sheet-action-btn danger" type="button" data-charge-action="delete" data-id="${row.id}" data-booking-id="${row.booking}">Delete</button>`}</td>
    </tr>`;
}

export function readRowPayload(row) {
    const value = (field) => row.querySelector(`[data-charge-field="${field}"]`)?.value?.trim() || "";
    return {
        requestor_name: value("requestor_name"), guest_name: value("guest_name"),
        purpose_event: value("purpose_event"), remarks: value("remarks"),
        room_charges_amount: Number(value("room_charges_amount") || 0),
        attender_charges_amount: Number(value("attender_charges_amount") || 0),
        payment_received_date: value("payment_received_date") || null,
        budget_head_name: value("budget_head_name"),
    };
}

export function bindHorizontalScroll(shell, getScrollLeft, setScrollLeft) {
    const top = shell.querySelector(".charge-sheet-scrollbar-top");
    const bottom = shell.querySelector(".charge-sheet-scroll");
    const spacer = top?.querySelector(".sheet-scrollbar-spacer");
    const table = bottom?.querySelector(".charge-sheet-table");
    if (!top || !bottom || !spacer || !table) return;
    shell._chargeSheetResizeObserver?.disconnect();
    const size = () => {
        spacer.style.width = `${table.scrollWidth}px`;
        const restored = Math.min(Math.max(Number(getScrollLeft()) || 0, 0), Math.max(0, table.scrollWidth - bottom.clientWidth));
        bottom.scrollLeft = restored;
        top.scrollLeft = restored;
    };
    let syncing = false;
    const sync = (source, target) => {
        if (syncing) return;
        syncing = true;
        target.scrollLeft = source.scrollLeft;
        setScrollLeft(source.scrollLeft);
        syncing = false;
    };
    top.addEventListener("scroll", () => sync(top, bottom));
    bottom.addEventListener("scroll", () => sync(bottom, top));
    size();
    if ("ResizeObserver" in window) {
        shell._chargeSheetResizeObserver = new ResizeObserver(size);
        shell._chargeSheetResizeObserver.observe(table);
        shell._chargeSheetResizeObserver.observe(bottom);
    }
}

export function tableHtml(rows, { headerHtml, rowHtml, exportButtonsHtml, legendHtml }) {
    if (!rows.length) return `<div class="empty-state">No charge sheet rows match the selected filters.</div>`;
    const headers = [
        ["serial_no", "Serial NO"], ["check_in", "Check in"], ["check_out", "Check out"],
        ["booking_reference_id", "Booking Reference ID"], ["requestor_name", "Requestor Name"],
        ["guest_name", "Name of Guest"], ["purpose_event", "Purpose(Event)"], ["remarks", "Remarks"],
        ["delta", "Delta"], ["gamma", "Gamma"], ["beta", "Beta"],
        ["room_charges_amount", "Room Charges Amount"], ["attender_charges_amount", "Attender Charges Amount"],
        ["total_charges", "Total Charges"], ["payment_received_date", "Payment Received Date"],
        ["budget_head_name", "Budget Head Name"],
    ];
    return `<div class="sheet-summary"><div><h3>Charges Sheet</h3><p>Booking charge and payment register</p></div>
        <div class="sheet-summary-actions"><span>${rows.length} row${rows.length === 1 ? "" : "s"}</span>${exportButtonsHtml}</div></div>
        ${legendHtml}<div class="sheet-scrollbar-top charge-sheet-scrollbar-top" aria-label="Horizontal charges sheet scrollbar"><div class="sheet-scrollbar-spacer"></div></div>
        <div class="sheet-scroll charge-sheet-scroll" role="region" aria-label="Booking charges sheet"><table class="excel-table charge-sheet-table">
        <thead><tr>${headers.map(([field, label]) => headerHtml(field, label)).join("")}<th class="sheet-actions-col">Actions</th></tr></thead>
        <tbody>${rows.map(rowHtml).join("")}</tbody></table></div>`;
}

export function bindTableActions(shell, callbacks) {
    callbacks.bindScroll(shell);
    shell.onclick = async (event) => {
        const exportButton = event.target.closest("[data-sheet-export]");
        if (exportButton) return callbacks.onExport(exportButton.dataset.sheetExport);
        const shareButton = event.target.closest("[data-sheet-share]");
        if (shareButton) return callbacks.onShare(shareButton.dataset.sheetShare);
        const sortButton = event.target.closest("[data-charge-sort]");
        if (sortButton) return callbacks.onSort(sortButton.dataset.chargeSort);
        const button = event.target.closest("[data-charge-action]");
        if (!button) return;
        const action = button.dataset.chargeAction;
        if (action === "edit" || action === "cancel") callbacks.onEdit(action === "edit" ? button.dataset.id : "", shell);
        else if (action === "save") await callbacks.onSave(button.dataset.id, shell);
        else if (action === "delete" && button.dataset.bookingId) callbacks.onDelete(button.dataset.bookingId);
    };
    shell.onkeydown = (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        const header = event.target.closest("[data-charge-sort]");
        if (!header) return;
        event.preventDefault();
        callbacks.onSort(header.dataset.chargeSort);
    };
}
