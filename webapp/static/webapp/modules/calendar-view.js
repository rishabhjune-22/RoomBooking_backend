export function availabilityClass(day) {
    if (!day) return "empty";
    const total = Math.max(0, Number(day.total_rooms || 0));
    const available = Math.max(0, Number(day.available_rooms || 0));
    if (total <= 0 || available >= total) return "open";
    if (available <= 0) return "full";
    return ((available * 100) / total) < 50 ? "low" : "half";
}

export function rangeContains(state, dateValue) {
    if (!state.rangeStart || !state.rangeEnd) return dateValue === state.rangeStart;
    return dateValue >= state.rangeStart && dateValue <= state.rangeEnd;
}

export function selectCalendarDate(state, dateValue) {
    state.selectedDate = dateValue;
    if (!state.rangeStart || (state.rangeEnd && state.rangeStart !== state.rangeEnd)) {
        state.rangeStart = dateValue;
        state.rangeEnd = dateValue;
    } else if (dateValue < state.rangeStart) {
        state.rangeEnd = state.rangeStart;
        state.rangeStart = dateValue;
    } else {
        state.rangeEnd = dateValue;
    }
}

export function createCalendarView({
    state, viewRoot, buildings, weekdays, apiFetch, isAdmin,
    escapeHtml, titleCase, isoDate, monthName, selectedRangeDisplayText,
    onCreateBooking, onRequestBooking,
}) {
    const group = () => state.availability?.groups?.find((item) => item.prefix === state.prefix) || null;

    function render() {
        viewRoot().innerHTML = `
            <div class="section-header"><div><h2>Calendar</h2><p>${isAdmin() ? "Full room availability and booking details." : "Select your requested arrival and departure dates."}</p></div>
            ${isAdmin() ? `<button class="primary-btn" id="calendar-create-booking">Create Booking</button>` : `<button class="primary-btn" id="request-booking-btn" disabled>Request Booking</button>`}</div>
            <div class="calendar-layout"><section class="surface calendar-panel">
                <div class="calendar-controls"><button class="outline-btn" id="prev-month">Previous</button><div class="month-title" id="month-title"></div><button class="outline-btn" id="next-month">Next</button></div>
                ${isAdmin() ? `<div class="building-tabs" id="building-tabs"></div>` : ""}<div class="calendar-grid" id="calendar-grid"></div>
                ${isAdmin() ? `<div class="legend"><span class="legend-item"><span class="dot open"></span> Available</span><span class="legend-item"><span class="dot half"></span> Half Available</span><span class="legend-item"><span class="dot low"></span> Less Than Half</span><span class="legend-item"><span class="dot full"></span> Full</span></div>` : ""}
            </section><aside class="surface side-panel" id="calendar-side"><div class="loading-state">Loading calendar...</div></aside></div>`;
        document.getElementById("prev-month").addEventListener("click", () => changeMonth(-1));
        document.getElementById("next-month").addEventListener("click", () => changeMonth(1));
        document.getElementById("calendar-grid").addEventListener("click", handleBlankClick);
        document.getElementById(isAdmin() ? "calendar-create-booking" : "request-booking-btn")
            .addEventListener("click", isAdmin() ? onCreateBooking : onRequestBooking);
        if (isAdmin()) drawBuildingTabs();
        load();
    }

    function drawBuildingTabs() {
        const node = document.getElementById("building-tabs");
        if (!node) return;
        node.innerHTML = buildings.map((prefix) => `<button class="chip ${state.prefix === prefix ? "active" : ""}" data-prefix="${prefix}">${prefix}</button>`).join("");
        node.querySelectorAll("[data-prefix]").forEach((button) => button.addEventListener("click", () => {
            state.prefix = button.dataset.prefix;
            clearSelection(false);
            drawBuildingTabs();
            draw();
            renderSide();
        }));
    }

    function changeMonth(delta) {
        state.calendarMonth += delta;
        if (state.calendarMonth < 1) { state.calendarMonth = 12; state.calendarYear -= 1; }
        else if (state.calendarMonth > 12) { state.calendarMonth = 1; state.calendarYear += 1; }
        load();
    }

    async function load({ silent = false } = {}) {
        const title = document.getElementById("month-title");
        const grid = document.getElementById("calendar-grid");
        if (!grid) return;
        if (title) title.textContent = monthName(state.calendarYear, state.calendarMonth);
        if (!silent) grid.innerHTML = `<div class="loading-state" style="grid-column:1 / -1">Loading availability...</div>`;
        if (!isAdmin()) {
            state.availability = null;
            draw();
            renderSide();
            return;
        }
        try {
            state.availability = await apiFetch(`/api/bookings/availability/?month=${state.calendarMonth}&year=${state.calendarYear}`);
            draw();
            renderSide();
        } catch (error) {
            if (!silent) grid.innerHTML = `<div class="empty-state" style="grid-column:1 / -1">${escapeHtml(error.message)}</div>`;
        }
    }

    function draw() {
        const grid = document.getElementById("calendar-grid");
        const currentGroup = group();
        if (!grid) return;
        if (isAdmin() && !currentGroup) {
            grid.innerHTML = `<div class="empty-state" style="grid-column:1 / -1">No availability data for ${escapeHtml(state.prefix)}.</div>`;
            return;
        }
        const byDate = Object.fromEntries((currentGroup?.calendar || []).map((day) => [day.date, day]));
        const firstDay = new Date(state.calendarYear, state.calendarMonth - 1, 1).getDay();
        const days = new Date(state.calendarYear, state.calendarMonth, 0).getDate();
        const cells = weekdays.map((day) => `<div class="weekday">${day}</div>`);
        for (let index = 0; index < firstDay; index += 1) cells.push(`<button class="day-cell empty" type="button" tabindex="-1"></button>`);
        for (let day = 1; day <= days; day += 1) {
            const date = isoDate(state.calendarYear, state.calendarMonth, day);
            const item = byDate[date];
            cells.push(`<button class="day-cell ${isAdmin() ? availabilityClass(item) : "requester-date"} ${rangeContains(state, date) ? "in-range" : ""}" type="button" data-date="${date}"><span class="day-number">${day}</span>${isAdmin() ? `<span class="availability-note">${item ? `${item.available_rooms}/${item.total_rooms} rooms` : "No rooms"}</span>` : ""}</button>`);
        }
        grid.innerHTML = cells.join("");
        grid.querySelectorAll("[data-date]").forEach((button) => button.addEventListener("click", () => handleDateClick(button.dataset.date)));
    }

    function handleDateClick(date) {
        selectCalendarDate(state, date);
        draw();
        if (isAdmin()) loadDetails(date);
        else renderSide();
    }

    function handleBlankClick(event) {
        if (!event.target.closest(".day-cell")?.dataset?.date) clearSelection();
    }

    function clearSelection(redraw = true) {
        state.selectedDate = "";
        state.rangeStart = "";
        state.rangeEnd = "";
        if (redraw) { draw(); renderSide(); }
    }

    function renderSide(content = "") {
        const side = document.getElementById("calendar-side");
        if (!side) return;
        const currentGroup = group();
        if (isAdmin() && !currentGroup) { side.innerHTML = `<div class="empty-state">No building data.</div>`; return; }
        if (isAdmin()) {
            side.innerHTML = content || `<div class="details-list"><div><h3 style="margin:0 0 6px">${escapeHtml(state.prefix)} Availability</h3><p class="item-meta">Select one date for same-day booking or select a second date for a booking range.</p></div><div class="detail-row"><span class="detail-label">Total rooms</span><span class="detail-value">${currentGroup.total_rooms}</span></div><div class="detail-row"><span class="detail-label">Month</span><span class="detail-value">${monthName(state.calendarYear, state.calendarMonth)}</span></div><div class="detail-row"><span class="detail-label">Selected range</span><span class="detail-value">${escapeHtml(selectedRangeDisplayText())}</span></div></div>`;
            return;
        }
        side.innerHTML = `<div class="details-list"><div><h3 style="margin:0 0 6px">Request Schedule</h3><p class="item-meta">Select one date for same-day request or select another date for a range.</p></div><div class="detail-row"><span class="detail-label">Selected range</span><span class="detail-value">${escapeHtml(selectedRangeDisplayText())}</span></div></div>`;
        const button = document.getElementById("request-booking-btn");
        if (button) button.disabled = !state.rangeStart;
    }

    async function loadDetails(date) {
        renderSide(`<div class="loading-state">Loading details...</div>`);
        try {
            const data = await apiFetch(`/api/bookings/availability/details/?date=${date}&prefix=${encodeURIComponent(state.prefix)}`);
            const rows = data.bookings || [];
            renderSide(`<div class="details-list"><div><h3 style="margin:0 0 6px">${escapeHtml(state.prefix)} Availability</h3><p class="item-meta">${rows.length} booking${rows.length === 1 ? "" : "s"} touching this date.</p></div><div class="detail-row"><span class="detail-label">Selected range</span><span class="detail-value">${escapeHtml(selectedRangeDisplayText())}</span></div>${rows.length ? rows.map((booking) => `<article class="item-card"><div class="item-main"><div><h4 class="item-title">${escapeHtml(booking.room_name)}</h4><p class="item-meta">${escapeHtml(booking.guest_name || "Guest")}</p></div><span class="status-chip ${booking.status}">${titleCase(booking.status)}</span></div></article>`).join("") : `<div class="empty-state">No bookings on this date.</div>`}</div>`);
        } catch (error) {
            renderSide(`<div class="empty-state">${escapeHtml(error.message)}</div>`);
        }
    }

    return { render, draw, drawBuildingTabs, load, renderSide, clearSelection };
}
