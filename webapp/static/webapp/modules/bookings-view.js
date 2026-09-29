export function renderBookingsLayout(state, { buildings: BUILDINGS, htmlValue, escapeHtml, filterTabs, chargeSheetSortOptions }) {
    const statusTabs = [["all", "All"], ["active", "Active"], ["expired", "Expired"]];
    const isChargeSheet = state.bookingViewMode === "charge_sheet";
    return `
        <div class="section-header">
            <div>
                <h2>Bookings</h2>
                <p>Create and inspect direct room bookings.</p>
            </div>
            <div class="header-actions">
                <button class="primary-btn" id="create-booking">Create Booking</button>
                <button class="outline-btn" id="refresh-bookings">Refresh</button>
            </div>
        </div>
        <div class="segmented view-tabs" role="tablist" aria-label="Bookings view">
            <button class="segment-btn ${state.bookingViewMode === "cards" ? "active" : ""}" data-booking-view="cards">Cards</button>
            <button class="segment-btn ${state.bookingViewMode === "sheet" ? "active" : ""}" data-booking-view="sheet">Sheet View</button>
            <button class="segment-btn ${isChargeSheet ? "active" : ""}" data-booking-view="charge_sheet">Charges Sheet</button>
        </div>
        ${isChargeSheet ? `
            <section class="surface filter-panel">
                <div class="filter-grid charge-filter-grid">
                    <div class="field-row">
                        <label for="charge-sheet-search">Search</label>
                        <input id="charge-sheet-search" type="search" placeholder="Reference, requestor, guest, purpose, remarks, budget..." value="${htmlValue(state.chargeSheetSearch)}">
                    </div>
                    <div class="field-row">
                        <label for="charge-sheet-prefix">Building</label>
                        <select id="charge-sheet-prefix">
                            <option value="all" ${state.chargeSheetPrefixFilter === "all" ? "selected" : ""}>All buildings</option>
                            ${BUILDINGS.map((building) => `<option value="${building}" ${state.chargeSheetPrefixFilter === building ? "selected" : ""}>${building}</option>`).join("")}
                        </select>
                    </div>
                    <div class="field-row">
                        <label for="charge-sheet-payment">Payment</label>
                        <select id="charge-sheet-payment">
                            <option value="all" ${state.chargeSheetPaymentFilter === "all" ? "selected" : ""}>All</option>
                            <option value="received" ${state.chargeSheetPaymentFilter === "received" ? "selected" : ""}>Received</option>
                            <option value="pending" ${state.chargeSheetPaymentFilter === "pending" ? "selected" : ""}>Pending</option>
                        </select>
                    </div>
                    <div class="field-row">
                        <label for="charge-sheet-checkout-from">Check out from</label>
                        <input id="charge-sheet-checkout-from" type="date" value="${htmlValue(state.chargeSheetCheckoutFrom)}">
                    </div>
                    <div class="field-row">
                        <label for="charge-sheet-checkout-to">Check out to</label>
                        <input id="charge-sheet-checkout-to" type="date" value="${htmlValue(state.chargeSheetCheckoutTo)}">
                    </div>
                    <div class="field-row">
                        <label for="charge-sheet-sort">Sort</label>
                        <select id="charge-sheet-sort">
                            ${chargeSheetSortOptions().map(([value, label]) => `<option value="${value}" ${state.chargeSheetOrdering === value ? "selected" : ""}>${label}</option>`).join("")}
                        </select>
                    </div>
                    <div class="filter-actions">
                        <button class="primary-btn" id="apply-charge-sheet-filters" type="button">Apply</button>
                        <button class="outline-btn" id="clear-charge-sheet-filters" type="button">Clear</button>
                    </div>
                </div>
            </section>
            <section class="surface sheet-panel">
                <div id="charge-sheet" class="sheet-shell"><div class="loading-state">Loading charges sheet...</div></div>
            </section>
        ` : `
            <section class="surface filter-panel">
                <div>
                    <p class="filter-label">Status</p>
                    ${filterTabs(state.bookingStatusFilter, statusTabs)}
                </div>
                ${state.bookingViewMode === "cards" ? `
                <div class="bulk-booking-actions">
                    <button class="outline-btn" id="generate-selected-mail-template" type="button" disabled>Generate Email Template</button>
                    <button class="danger-btn" id="delete-selected-bookings" type="button" disabled>Delete Selected</button>
                </div>
                ` : ""}
                <div class="filter-grid">
                    <div class="field-row">
                        <label for="booking-search">Search</label>
                        <input id="booking-search" type="search" placeholder="Reference, requestor, guest, room, purpose, remarks..." value="${htmlValue(state.bookingSearch)}">
                    </div>
                    <div class="field-row">
                        <label for="booking-prefix-filter">Building</label>
                        <select id="booking-prefix-filter">
                            <option value="all" ${state.bookingPrefixFilter === "all" ? "selected" : ""}>All buildings</option>
                            ${BUILDINGS.map((building) => `<option value="${building}" ${state.bookingPrefixFilter === building ? "selected" : ""}>${building}</option>`).join("")}
                        </select>
                    </div>
                    <div class="field-row">
                        <label for="booking-arrival-from">Arrival from</label>
                        <input id="booking-arrival-from" type="date" value="${escapeHtml(state.bookingArrivalFrom)}">
                    </div>
                    <div class="field-row">
                        <label for="booking-departure-to">Departure to</label>
                        <input id="booking-departure-to" type="date" value="${escapeHtml(state.bookingDepartureTo)}">
                    </div>
                    <div class="filter-actions">
                        <button class="primary-btn" id="apply-booking-search" type="button">Search</button>
                        <button class="outline-btn" id="clear-booking-filters" type="button">Clear Filters</button>
                    </div>
                </div>
            </section>
            ${state.bookingViewMode === "sheet" ? `
            <section class="surface sheet-panel">
                <div id="bookings-sheet" class="sheet-shell"><div class="loading-state">Loading sheet view...</div></div>
            </section>
            ` : `
            <section class="surface side-panel">
                <div id="bookings-list" class="card-list"><div class="loading-state">Loading bookings...</div></div>
                <div id="bookings-sentinel" class="scroll-sentinel"></div>
            </section>
            `}
        `}
    `;
}
