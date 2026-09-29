export function filterSheetRooms(rooms, prefixFilter, buildings, roomLabel) {
    return rooms
        .filter((room) => prefixFilter === "all" || room.prefix === prefixFilter)
        .sort((a, b) => {
            const buildingOrder = buildings.indexOf(a.prefix) - buildings.indexOf(b.prefix);
            if (buildingOrder !== 0) return buildingOrder;
            return String(a.number || a.room_number || roomLabel(a)).localeCompare(
                String(b.number || b.room_number || roomLabel(b)),
                undefined,
                { numeric: true, sensitivity: "base" },
            );
        });
}

export function bookingCellText(booking) {
    const name = String(booking.visitor_name || "").trim();
    const organisation = String(booking.visitor_organisation || "").trim();
    return organisation ? `${name} (${organisation})` : name || "Booked";
}

export function buildBookingSheetCells(bookings, dates, {
    localIsoDateFromDateTime,
    localTimeMinutes,
    addHoursToDateTime,
    isPastDateTime,
    coolingHours,
    dayEndMinutes,
}) {
    function availabilityOnDate(booking, dateValue) {
        const arrivalDate = localIsoDateFromDateTime(booking.arrival_at);
        const departureDate = localIsoDateFromDateTime(booking.departure_at);
        if (!arrivalDate || !departureDate) return null;
        const coolingEnd = addHoursToDateTime(booking.departure_at, coolingHours);
        const coolingEndDate = localIsoDateFromDateTime(coolingEnd);
        const unavailableAfterDeparture = coolingEndDate !== dateValue || localTimeMinutes(coolingEnd) > dayEndMinutes;
        if (arrivalDate === departureDate && dateValue === arrivalDate) {
            return unavailableAfterDeparture ? { availabilityStatus: "full", availableFrom: null } : { availabilityStatus: "partial", availableFrom: coolingEnd };
        }
        if (arrivalDate <= dateValue && dateValue < departureDate) return { availabilityStatus: "full", availableFrom: null };
        if (dateValue === departureDate) {
            return unavailableAfterDeparture ? { availabilityStatus: "full", availableFrom: null } : { availabilityStatus: "partial", availableFrom: coolingEnd };
        }
        return null;
    }

    const cells = new Map();
    bookings.forEach((booking) => {
        if (!booking.room) return;
        dates.forEach((dateValue) => {
            const availability = availabilityOnDate(booking, dateValue);
            if (!availability) return;
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
        });
    });
    return cells;
}

export function sheetCellHtml(entries = [], dateValue = "", room = null, { escapeHtml, indiaParts, formatSheetTime }) {
    if (!entries.length) {
        return `<button class="sheet-create-btn" type="button" data-booking-action="create" data-room-id="${room?.id || ""}" data-room-prefix="${escapeHtml(room?.prefix || "")}" data-date="${escapeHtml(dateValue)}">+ Create</button>`;
    }
    const entryById = new Map();
    entries.forEach((entry) => {
        if (!entryById.has(entry.id)) entryById.set(entry.id, entry);
    });
    const hasFullDayBooking = entries.some((entry) => entry.availabilityStatus === "full");
    const availableFromValues = entries
        .filter((entry) => !entry.isExpired && entry.availabilityStatus === "partial" && entry.availableFrom)
        .map((entry) => entry.availableFrom);
    const latestAvailableFrom = availableFromValues.length
        ? new Date(Math.max(...availableFromValues.map((value) => new Date(value).getTime())))
        : null;
    const createAfterHtml = !hasFullDayBooking && latestAvailableFrom ? `
        <button class="sheet-create-btn partial" type="button" data-booking-action="create"
            data-room-id="${room?.id || ""}" data-room-prefix="${escapeHtml(room?.prefix || "")}"
            data-date="${escapeHtml(dateValue)}" data-arrival-time="${escapeHtml(indiaParts(latestAvailableFrom).time)}"
        >+ Create after ${escapeHtml(formatSheetTime(latestAvailableFrom))}</button>` : "";
    return Array.from(entryById.entries()).map(([id, entry]) => `
        <div class="sheet-booking-entry">
            <button class="sheet-booking-pill ${entry.availabilityStatus === "partial" ? "partial" : ""} ${entry.isExpired ? "expired" : ""}" type="button" data-sheet-booking-id="${id}">${escapeHtml(entry.text)}</button>
            <div class="sheet-inline-actions">
                <button class="sheet-action-btn" type="button" data-booking-action="edit" data-id="${id}">Edit</button>
                <button class="sheet-action-btn danger" type="button" data-booking-action="delete" data-id="${id}">Delete</button>
            </div>
        </div>`).join("") + createAfterHtml;
}

export function sheetTableHtml({ range, dates, rooms, cells, visibleBookingCount }, helpers) {
    const { escapeHtml, formatSheetDate, roomLabel, cellHtml, exportButtonsHtml, legendHtml } = helpers;
    return `<div class="sheet-summary"><div><h3>Visitor Room</h3><p>${formatSheetDate(range.start)} to ${formatSheetDate(range.end)}</p></div>
        <div class="sheet-summary-actions"><span>${visibleBookingCount} booking${visibleBookingCount === 1 ? "" : "s"}</span>${exportButtonsHtml}</div></div>
        ${legendHtml}<div class="sheet-scroll" role="region" aria-label="Booking sheet view"><table class="excel-table">
        <thead><tr><th class="date-col">Dates</th>${rooms.map((room) => `<th>${escapeHtml(roomLabel(room))}</th>`).join("")}</tr></thead>
        <tbody>${dates.map((dateValue) => `<tr><th class="date-col">${escapeHtml(formatSheetDate(dateValue))}</th>
            ${rooms.map((room) => `<td>${cellHtml(cells.get(`${dateValue}:${room.id}`), dateValue, room)}</td>`).join("")}</tr>`).join("")}</tbody>
        </table></div>`;
}
