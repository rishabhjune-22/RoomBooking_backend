export function openBookingDateRangePicker(dependencies) {
    const { state, buildings: BUILDINGS, weekdays: WEEKDAYS, selectedRangeDisplayText, toast, closeModal, openAvailableRooms, escapeHtml, isoDate, rangeContains, availabilityClass, monthName, apiFetch, openActionModal } = dependencies;
    if (state.bookingPrefixFilter !== "all" && BUILDINGS.includes(state.bookingPrefixFilter)) {
        state.prefix = state.bookingPrefixFilter;
    }
    state.selectedDate = "";
    state.rangeStart = "";
    state.rangeEnd = "";

    let pickerAvailability = null;
    let selectedClickCount = 0;

    const pickerGroup = () => pickerAvailability?.groups?.find((group) => group.prefix === state.prefix) || null;

    const updatePickerSummary = () => {
        const summary = document.getElementById("booking-date-picker-summary");
        if (summary) {
            summary.textContent = `Selected range: ${selectedRangeDisplayText()}`;
        }
        const showRoomsButton = document.getElementById("booking-date-picker-show-rooms");
        if (showRoomsButton) {
            showRoomsButton.disabled = !state.rangeStart;
        }
    };

    const showPickerAvailableRooms = () => {
        if (!state.rangeStart) {
            toast("Select a date range first.", "error");
            return;
        }
        const arrivalDate = state.rangeStart;
        const departureDate = state.rangeEnd || state.rangeStart;
        const prefix = state.prefix;
        closeModal();
        openAvailableRooms({ arrivalDate, departureDate, prefix });
    };

    const drawPickerBuildingTabs = () => {
        const node = document.getElementById("booking-date-building-tabs");
        if (!node) {
            return;
        }
        node.innerHTML = BUILDINGS.map((prefix) => `
            <button class="chip ${state.prefix === prefix ? "active" : ""}" type="button" data-prefix="${prefix}">${prefix}</button>
        `).join("");
        node.querySelectorAll("[data-prefix]").forEach((button) => {
            button.addEventListener("click", () => {
                state.prefix = button.dataset.prefix;
                state.selectedDate = "";
                state.rangeStart = "";
                state.rangeEnd = "";
                selectedClickCount = 0;
                drawPickerBuildingTabs();
                drawPickerCalendar();
                updatePickerSummary();
            });
        });
    };

    const drawPickerCalendar = () => {
        const grid = document.getElementById("booking-date-picker-grid");
        const group = pickerGroup();
        if (!grid) {
            return;
        }
        if (!group) {
            grid.innerHTML = `<div class="empty-state" style="grid-column:1 / -1">No availability data for ${escapeHtml(state.prefix)}.</div>`;
            return;
        }

        const daysByDate = Object.fromEntries(group.calendar.map((day) => [day.date, day]));
        const firstDay = new Date(state.calendarYear, state.calendarMonth - 1, 1).getDay();
        const daysInMonth = new Date(state.calendarYear, state.calendarMonth, 0).getDate();
        const cells = [];
        WEEKDAYS.forEach((day) => cells.push(`<div class="weekday">${day}</div>`));
        for (let index = 0; index < firstDay; index += 1) {
            cells.push(`<button class="day-cell empty" type="button" tabindex="-1"></button>`);
        }
        for (let day = 1; day <= daysInMonth; day += 1) {
            const dateValue = isoDate(state.calendarYear, state.calendarMonth, day);
            const item = daysByDate[dateValue];
            const selectedClass = rangeContains(state, dateValue) ? "in-range" : "";
            cells.push(`
                <button class="day-cell ${availabilityClass(item)} ${selectedClass}" type="button" data-date="${dateValue}">
                    <span class="day-number">${day}</span>
                    <span class="availability-note">${item ? `${item.available_rooms}/${item.total_rooms} rooms` : "No rooms"}</span>
                </button>
            `);
        }
        grid.innerHTML = cells.join("");
        grid.querySelectorAll("[data-date]").forEach((button) => {
            button.addEventListener("click", () => {
                const dateValue = button.dataset.date;
                state.selectedDate = dateValue;
                if (selectedClickCount !== 1) {
                    state.rangeStart = dateValue;
                    state.rangeEnd = dateValue;
                    selectedClickCount = 1;
                    drawPickerCalendar();
                    updatePickerSummary();
                    return;
                }

                if (dateValue < state.rangeStart) {
                    state.rangeEnd = state.rangeStart;
                    state.rangeStart = dateValue;
                } else {
                    state.rangeEnd = dateValue;
                }
                selectedClickCount = 2;
                drawPickerCalendar();
                updatePickerSummary();
            });
        });
    };

    const loadPickerCalendar = async () => {
        const title = document.getElementById("booking-date-picker-month-title");
        const grid = document.getElementById("booking-date-picker-grid");
        if (title) {
            title.textContent = monthName(state.calendarYear, state.calendarMonth);
        }
        if (grid) {
            grid.innerHTML = `<div class="loading-state" style="grid-column:1 / -1">Loading availability...</div>`;
        }
        try {
            pickerAvailability = await apiFetch(`/api/bookings/availability/?month=${state.calendarMonth}&year=${state.calendarYear}`);
            drawPickerBuildingTabs();
            drawPickerCalendar();
            updatePickerSummary();
        } catch (error) {
            if (grid) {
                grid.innerHTML = `<div class="empty-state" style="grid-column:1 / -1">${escapeHtml(error.message)}</div>`;
            }
        }
    };

    const changePickerMonth = (delta) => {
        state.calendarMonth += delta;
        if (state.calendarMonth < 1) {
            state.calendarMonth = 12;
            state.calendarYear -= 1;
        } else if (state.calendarMonth > 12) {
            state.calendarMonth = 1;
            state.calendarYear += 1;
        }
        loadPickerCalendar();
    };

    openActionModal({
        title: "Select Booking Dates",
        body: `
            <section class="surface calendar-panel booking-date-picker">
                <div class="calendar-controls">
                    <button class="outline-btn" id="booking-date-picker-prev-month" type="button">Previous</button>
                    <div class="month-title" id="booking-date-picker-month-title"></div>
                    <button class="outline-btn" id="booking-date-picker-next-month" type="button">Next</button>
                </div>
                <div class="building-tabs" id="booking-date-building-tabs"></div>
                <p class="item-meta" id="booking-date-picker-summary">Selected range: ${escapeHtml(selectedRangeDisplayText())}</p>
                <div class="calendar-grid" id="booking-date-picker-grid"></div>
                <div class="legend">
                    <span class="legend-item"><span class="dot open"></span> Available</span>
                    <span class="legend-item"><span class="dot half"></span> Half Available</span>
                    <span class="legend-item"><span class="dot low"></span> Less Than Half</span>
                    <span class="legend-item"><span class="dot full"></span> Full</span>
                </div>
            </section>
        `,
        wide: true,
        footerHtml: `
            <button class="outline-btn" type="button" data-close-modal>Close</button>
            <button class="primary-btn" type="button" id="booking-date-picker-show-rooms" disabled>Create Booking</button>
        `,
        onBind: () => {
            document.getElementById("booking-date-picker-prev-month")?.addEventListener("click", () => changePickerMonth(-1));
            document.getElementById("booking-date-picker-next-month")?.addEventListener("click", () => changePickerMonth(1));
            document.getElementById("booking-date-picker-show-rooms")?.addEventListener("click", showPickerAvailableRooms);
            document.getElementById("booking-date-picker-grid")?.addEventListener("click", (event) => {
                const dayCell = event.target.closest(".day-cell");
                if (dayCell?.dataset?.date) {
                    return;
                }
                state.selectedDate = "";
                state.rangeStart = "";
                state.rangeEnd = "";
                selectedClickCount = 0;
                drawPickerCalendar();
                updatePickerSummary();
            });
            drawPickerBuildingTabs();
            loadPickerCalendar();
        },
    });
}

