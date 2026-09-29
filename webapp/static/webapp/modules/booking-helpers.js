export function unwrapList(data) {
    if (Array.isArray(data)) return data;
    return Array.isArray(data?.results) ? data.results : [];
}

export function nextPageUrl(data, origin = window.location.origin) {
    if (!data || Array.isArray(data) || !data.next) return "";
    try {
        const parsed = new URL(data.next, origin);
        return `${parsed.pathname}${parsed.search}`;
    } catch (error) {
        return data.next;
    }
}

export function bookingsEndpoint(state) {
    const params = new URLSearchParams({ page_size: "50" });
    if (state.bookingStatusFilter !== "all") params.set("status", state.bookingStatusFilter);
    if (state.bookingPrefixFilter !== "all") params.set("prefix", state.bookingPrefixFilter);
    if (state.bookingSearch) params.set("search", state.bookingSearch);
    if (state.bookingArrivalFrom) params.set("arrival_from", state.bookingArrivalFrom);
    if (state.bookingDepartureTo) params.set("departure_to", state.bookingDepartureTo);
    return `/api/bookings/?${params.toString()}`;
}

export function bookingSheetEndpoint(state) {
    const params = new URLSearchParams({ page_size: "100" });
    if (state.bookingStatusFilter !== "all") params.set("status", state.bookingStatusFilter);
    if (state.bookingPrefixFilter !== "all") params.set("prefix", state.bookingPrefixFilter);
    if (state.bookingSearch) params.set("search", state.bookingSearch);
    return `/api/bookings/?${params.toString()}`;
}

export function bookingDisplayId(booking) {
    const reference = String(booking.booking_reference_number || "").trim();
    if (reference) return reference;
    const id = String(booking.id || "").trim();
    return id ? id.padStart(6, "0") : "-";
}

export function bookingSelectionId(value) {
    return String(value ?? "");
}

export function bookingCardHtml(booking, { selectedIds, escapeHtml, formatDateRange, titleCase }) {
    const bookingId = bookingSelectionId(booking.id);
    const selected = selectedIds.has(bookingId);
    return `
        <article class="item-card booking-card${selected ? " selected" : ""}" data-booking-id="${escapeHtml(bookingId)}">
            <div class="booking-card-row">
                <input class="booking-select-checkbox" type="checkbox" data-booking-select-id="${escapeHtml(bookingId)}" aria-label="Select booking ${escapeHtml(bookingDisplayId(booking))}" ${selected ? "checked" : ""}>
                <div class="item-main">
                    <div>
                        <h3 class="item-title">${escapeHtml(booking.visitor_name || "Visitor")}</h3>
                        <p class="item-meta">Booking ID: ${escapeHtml(bookingDisplayId(booking))}</p>
                        <p class="item-meta">${escapeHtml(booking.room_name)} - ${formatDateRange(booking)}</p>
                        <p class="item-meta">Requestor: ${escapeHtml(booking.requestor_name || "-")} - Created by: ${escapeHtml(booking.created_by_name || "-")}</p>
                    </div>
                    <span class="status-chip ${booking.status}">${titleCase(booking.status)}</span>
                </div>
            </div>
        </article>`;
}

export function availableRoomsChooserHtml(rooms, { prefix, responsePrefix, arrivalDate, departureDate, escapeHtml, scheduleDisplayText, roomLabel, availableRoomStatusText }) {
    if (!rooms.length) {
        return `<div class="empty-state">No rooms are available for the selected range.</div>`;
    }
    return `
        <p class="item-meta">Select a room to create a booking for ${escapeHtml(scheduleDisplayText(arrivalDate, departureDate))}.</p>
        <div class="available-room-list">
            ${rooms.map((room, index) => {
                const roomName = roomLabel({
                    id: room.room_id || room.id,
                    prefix: room.prefix || responsePrefix || prefix,
                    selection_label: room.selection_label,
                    room_name: room.room_name,
                    number: room.room_number || room.number,
                });
                return `
                    <button class="available-room-card" type="button" data-room-index="${index}">
                        <span class="available-room-title">${escapeHtml(roomName)}</span>
                        <span class="available-room-status ${room.availability_status === "partial" ? "partial" : "available"}">${escapeHtml(availableRoomStatusText(room))}</span>
                    </button>`;
            }).join("")}
        </div>`;
}

export function createdBookingSummary(created = {}, payload = {}, rooms = [], { roomLabel, prefixFromSummary }) {
    const roomId = created.room_id || created.room || payload.room || "";
    const room = rooms.find((item) => String(item.id) === String(roomId));
    const roomName = created.room_name || (room ? roomLabel(room) : "");
    const copy = (key, fallback = "") => payload[key] || created[key] || fallback;
    return {
        id: created.id || created.booking_id || "", booking_reference_number: created.booking_reference_number || "",
        room: roomId, room_name: roomName,
        preferred_prefix: created.preferred_prefix || prefixFromSummary({ room_name: roomName }),
        visitor_name: copy("visitor_name"), arrival_at: copy("arrival_at"), departure_at: copy("departure_at"),
        purpose_of_visit: copy("purpose_of_visit"), visitor_nationality: copy("visitor_nationality"),
        visitor_category: copy("visitor_category"), budget_head_type: copy("budget_head_type"),
        budget_head_value: copy("budget_head_value"), budget_head_name: copy("budget_head_name"),
        budget_head_department_name: copy("budget_head_department_name"), budget_head_project_code: copy("budget_head_project_code"),
        requestor_name: copy("requestor_name"), requestor_designation: copy("requestor_designation"),
        requestor_department: copy("requestor_department"), requestor_mobile: copy("requestor_mobile"),
        logistics_name: copy("logistics_name"), logistics_designation: copy("logistics_designation"), logistics_mobile: copy("logistics_mobile"),
        room_charges_status: copy("room_charges_status", "no"),
        room_charges_amount: payload.room_charges_amount ?? created.room_charges_amount ?? 0,
        attender_charges_status: copy("attender_charges_status", "no"),
        attender_charges_amount: payload.attender_charges_amount ?? created.attender_charges_amount ?? 0,
        status: created.status || payload.status || "active",
    };
}

export function createMoreBookingPrefill(booking = {}, prefixFromSummary) {
    const keys = ["arrival_at", "departure_at", "purpose_of_visit", "visitor_nationality", "visitor_category",
        "budget_head_type", "budget_head_value", "budget_head_name", "budget_head_department_name",
        "budget_head_project_code", "requestor_name", "requestor_designation", "requestor_department",
        "requestor_mobile", "logistics_name", "logistics_designation", "logistics_mobile"];
    const result = { preferred_prefix: booking.preferred_prefix || prefixFromSummary(booking) };
    keys.forEach((key) => { result[key] = booking[key] || ""; });
    result.room_charges_status = booking.room_charges_status || "no";
    result.room_charges_amount = booking.room_charges_amount ?? 0;
    result.attender_charges_status = booking.attender_charges_status || "no";
    result.attender_charges_amount = booking.attender_charges_amount ?? 0;
    return result;
}

export function createdBookingSidePanelHtml(booking, { escapeHtml, selectedRangeDisplayText, titleCase, formatDateRange }) {
    return `<div class="details-list"><div><h3 style="margin:0 0 6px">Recent booking created</h3>
        <p class="item-meta">Compact summary of the booking just created.</p></div>
        <div class="detail-row"><span class="detail-label">Selected range</span><span class="detail-value">${escapeHtml(selectedRangeDisplayText())}</span></div>
        <article class="item-card"><div class="item-main"><div><h4 class="item-title">${escapeHtml(booking.room_name || "Room")}</h4>
        <p class="item-meta">${escapeHtml(booking.visitor_name || "Guest")}</p></div>
        <span class="status-chip ${escapeHtml(booking.status || "active")}">${titleCase(booking.status || "active")}</span></div>
        <p class="item-meta">${escapeHtml(formatDateRange(booking))}</p>
        ${booking.booking_reference_number ? `<p class="item-meta">Reference #${escapeHtml(booking.booking_reference_number)}</p>` : ""}</article></div>`;
}
