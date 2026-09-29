export function detailsRowsHtml(rows, escapeHtml, valueOrDash) {
    return `<div class="details-list">${rows.map((row) => {
        if (!Array.isArray(row)) return `<div class="detail-section-title">${escapeHtml(row.section || "Details")}</div>`;
        const [label, value] = row;
        return `<div class="detail-row"><span class="detail-label">${escapeHtml(label)}</span><span class="detail-value">${escapeHtml(valueOrDash(value))}</span></div>`;
    }).join("")}</div>`;
}

export function printableDetailsRowsHtml(rows, escapeHtml, valueOrDash) {
    return rows.map((row) => {
        if (!Array.isArray(row)) return `<div class="section">${escapeHtml(row.section || "Details")}</div>`;
        const [label, value] = row;
        return `<div class="row"><div class="label">${escapeHtml(label)}</div><div class="value">${escapeHtml(valueOrDash(value))}</div></div>`;
    }).join("");
}

export function bookingDetailRows(booking, {
    bookingDisplayId, normalizedBudgetHeadFields, titleCase, formatDateTime,
    visitorNationalityLabel, yesNo, shiftsText,
}) {
    const history = booking.edit_history || [];
    const budgetHead = normalizedBudgetHeadFields(booking);
    return [
        { section: "Booking" },
        ["ID", bookingDisplayId(booking)], ["Status", titleCase(booking.status)],
        ["Room", booking.room_name], ["Arrival", formatDateTime(booking.arrival_at)],
        ["Departure", formatDateTime(booking.departure_at)], ["Created by", booking.created_by_name],
        ["Created at", formatDateTime(booking.created_at)],
        { section: "Visitor Details" },
        ["Visitor name", booking.visitor_name], ["Designation", booking.visitor_designation],
        ["Organisation", booking.visitor_organisation], ["Gender", booking.visitor_gender],
        ["Guest nationality", visitorNationalityLabel(booking.visitor_nationality)],
        ["Mobile", booking.visitor_mobile], ["Email", booking.visitor_email],
        ["Category", titleCase(booking.visitor_category)], ["Purpose", booking.purpose_of_visit],
        ["Remarks", booking.remarks],
        { section: "Budget Head" },
        ["Individual", budgetHead.individual], ["Institute Head", budgetHead.instituteHead],
        ["Project code", budgetHead.projectHead],
        { section: "Requestor Details" },
        ["Requestor name", booking.requestor_name], ["Designation", booking.requestor_designation],
        ["Department", booking.requestor_department], ["Mobile", booking.requestor_mobile],
        { section: "Logistics(Food/Cab) will be looked after by" },
        ["Name", booking.logistics_name], ["Designation", booking.logistics_designation],
        ["Mobile", booking.logistics_mobile],
        { section: "Attender Requirement" },
        ["Attender required", yesNo(booking.attender_required)], ["Shifts", shiftsText(booking)],
        { section: "Charges" },
        ["Room charges", titleCase(booking.room_charges_status)],
        ["Room charges amount", booking.room_charges_amount],
        ["Attender charges", titleCase(booking.attender_charges_status)],
        ["Attender charges amount", booking.attender_charges_amount],
        { section: "Edit History" },
        ...(history.length ? history.flatMap((entry) => [
            ["Field", entry.field_label || entry.field_name],
            ["Changed by", entry.edited_by_name || entry.edited_by_email],
            ["Changed at", formatDateTime(entry.edited_at)],
            ["Old value", entry.old_value], ["New value", entry.new_value],
        ]) : [["History", "No edit history."]]),
    ];
}

export function printableDocumentHtml(title, rowsHtml, subtitle, escapeHtml) {
    return `<!doctype html><html><head><meta charset="utf-8"><title>${escapeHtml(title)}</title><style>
        @page { size: A4 portrait; margin: 14mm; } * { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
        body { margin: 0; font-family: Arial, sans-serif; color: #172033; } h1 { margin: 0 0 6px; font-size: 22px; }
        .subtitle { margin: 0 0 18px; color: #667085; font-size: 12px; }
        .section { margin: 16px 0 8px; padding: 7px 9px; background: #dbeeff; color: #0a4f8d; font-size: 11px; font-weight: 700; text-transform: uppercase; }
        .row { display: grid; grid-template-columns: 42mm 1fr; gap: 8px; border-bottom: 1px solid #d8e0ea; padding: 6px 0; page-break-inside: avoid; }
        .label { color: #667085; font-size: 11px; font-weight: 700; } .value { font-size: 12px; overflow-wrap: anywhere; white-space: pre-wrap; }
        </style></head><body><h1>${escapeHtml(title)}</h1>${subtitle ? `<p class="subtitle">${escapeHtml(subtitle)}</p>` : ""}${rowsHtml}</body></html>`;
}
