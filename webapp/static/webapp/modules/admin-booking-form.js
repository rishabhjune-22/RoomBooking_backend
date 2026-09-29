export function renderAdminBookingForm(source = {}, context = "booking", dependencies) {
    const { state, todayIso, indiaParts, buildings: BUILDINGS, normalizedBudgetHeadFields, escapeHtml, htmlValue, titleCase, formatDateTime, previousBookingAutofillHtml: adminPreviousBookingAutofillHtml } = dependencies;
    const selectedStart = state.rangeStart || state.selectedDate || todayIso();
    const selectedEnd = state.rangeEnd || state.rangeStart || state.selectedDate || todayIso();
    const arrival = source.arrival_at ? indiaParts(source.arrival_at) : { date: selectedStart, time: "10:00" };
    const departure = source.departure_at ? indiaParts(source.departure_at) : { date: selectedEnd, time: "18:00" };
    const prefix = source.preferred_prefix || source.prefix || state.prefix || BUILDINGS[0];
    const budgetHead = normalizedBudgetHeadFields(source);
    const roomPreferencePanel = context === "request" ? `
        <div class="requester-room-preference" role="note">
            <strong>Requester Room Preference</strong>
            <span>${escapeHtml(source.room_preference_note || "No preference provided")}</span>
        </div>
    ` : "";
    const requestMeta = source.id && context === "request" ? `
        <div class="form-section-title">Request Review</div>
        <div class="two-col">
            <div class="field-row"><label>Request ID</label><input value="${htmlValue(source.id)}" readonly></div>
            <div class="field-row"><label>Status</label><input value="${htmlValue(titleCase(source.status))}" readonly></div>
            <div class="field-row"><label>Requester account</label><input value="${htmlValue(source.requester_name || source.requester_email)}" readonly></div>
            <div class="field-row"><label>Requester email</label><input value="${htmlValue(source.requester_email)}" readonly></div>
            <div class="field-row"><label>Requested at</label><input value="${htmlValue(formatDateTime(source.requested_at))}" readonly></div>
            <div class="field-row"><label>Reviewed by</label><input value="${htmlValue(source.reviewed_by_name)}" readonly></div>
            <div class="field-row"><label>Reviewed at</label><input value="${htmlValue(formatDateTime(source.reviewed_at))}" readonly></div>
            <div class="field-row"><label>Assigned booking</label><input value="${htmlValue(source.assigned_room_name || source.approved_booking_id || "")}" readonly></div>
        </div>
    ` : "";
    return `
        <form id="admin-booking-form" class="field-grid booking-form" novalidate>
            ${adminPreviousBookingAutofillHtml(source, context)}
            ${requestMeta}
            <div class="form-section-title">Visitor Details</div>
            <div class="two-col">
                <div class="field-row"><label for="admin-prefix">Building *</label><select id="admin-prefix">${BUILDINGS.map((item) => `<option value="${item}" ${item === prefix ? "selected" : ""}>${item}</option>`).join("")}</select></div>
                ${roomPreferencePanel}
                <div class="field-row"><label for="admin-room">Room No *</label><select id="admin-room" required><option value="">Loading rooms...</option></select></div>
                <div class="field-row"><label for="admin-arrival-date">Check-In date *</label><input id="admin-arrival-date" type="date" value="${htmlValue(arrival.date)}" required></div>
                <div class="field-row"><label for="admin-arrival-time">Check-In time *</label><input id="admin-arrival-time" type="time" value="${htmlValue(arrival.time || "10:00")}" required></div>
                <div class="field-row"><label for="admin-departure-date">Check-Out date *</label><input id="admin-departure-date" type="date" value="${htmlValue(departure.date)}" required></div>
                <div class="field-row"><label for="admin-departure-time">Check-Out time *</label><input id="admin-departure-time" type="time" value="${htmlValue(departure.time || "18:00")}" required></div>
                <div class="field-row"><label for="admin-visitor-name">Visitor name *</label><input id="admin-visitor-name" value="${htmlValue(source.visitor_name)}" required></div>
                <div class="field-row"><label for="admin-visitor-designation">Visitor designation (Optional)</label><input id="admin-visitor-designation" value="${htmlValue(source.visitor_designation)}"></div>
                <div class="field-row"><label for="admin-visitor-organisation">Visitor organisation (Optional)</label><input id="admin-visitor-organisation" value="${htmlValue(source.visitor_organisation)}"></div>
                <div class="field-row"><label for="admin-visitor-gender">Gender (Optional)</label><select id="admin-visitor-gender">
                    <option value="" ${!source.visitor_gender ? "selected" : ""}>Select Gender (Optional)</option>
                    <option value="Male" ${source.visitor_gender === "Male" ? "selected" : ""}>Male</option>
                    <option value="Female" ${source.visitor_gender === "Female" ? "selected" : ""}>Female</option>
                    <option value="Other" ${source.visitor_gender === "Other" ? "selected" : ""}>Other</option>
                </select></div>
                <div class="field-row"><label>Guest nationality (Optional)</label>
                    <div class="radio-list compact-radio-list">
                        <label class="check-row"><input name="admin-visitor-nationality" type="radio" value="indian" ${source.visitor_nationality === "indian" ? "checked" : ""}> Indian</label>
                        <label class="check-row"><input name="admin-visitor-nationality" type="radio" value="foreigner" ${source.visitor_nationality === "foreigner" ? "checked" : ""}> Foreigner</label>
                    </div>
                    <button class="outline-btn compact-btn" id="admin-clear-visitor-nationality" type="button">Clear Selection</button>
                </div>
                <div class="field-row"><label for="admin-visitor-mobile">Visitor mobile (Optional)</label><input id="admin-visitor-mobile" inputmode="tel" value="${htmlValue(source.visitor_mobile)}"></div>
                <div class="field-row"><label for="admin-visitor-email">Visitor email (Optional)</label><input id="admin-visitor-email" type="email" value="${htmlValue(source.visitor_email)}"></div>
            </div>
            <div class="field-row"><label for="admin-purpose">Purpose of visit (Optional)</label><textarea id="admin-purpose">${htmlValue(source.purpose_of_visit)}</textarea></div>
            <div class="field-row"><label for="admin-remarks">Remarks (Optional)</label><textarea id="admin-remarks">${htmlValue(source.remarks)}</textarea></div>

            <div class="form-section-title">Visitor Category (Optional)</div>
            <div class="radio-list">
                <label class="check-row"><input name="admin-visitor-category" type="radio" value="institute_guest" ${source.visitor_category === "institute_guest" ? "checked" : ""}> Institute Guest (Official Institute Guest)</label>
                <label class="check-row"><input name="admin-visitor-category" type="radio" value="conference_workshop_guest" ${source.visitor_category === "conference_workshop_guest" ? "checked" : ""}> Conference / Workshop Guest</label>
                <label class="check-row"><input name="admin-visitor-category" type="radio" value="other_guest" ${source.visitor_category === "other_guest" ? "checked" : ""}> Other Guest</label>
                <button class="outline-btn compact-btn" id="admin-clear-visitor-category" type="button">Clear Selection</button>
            </div>

            <div class="form-section-title">Budget Head (Optional)</div>
            <div class="budget-head-group">
                <label class="check-row"><input id="admin-budget-individual" data-budget-head-field="admin-budget-name" type="checkbox" ${budgetHead.individual ? "checked" : ""}> Individual</label>
                <div class="field-row budget-head-input" ${budgetHead.individual ? "" : "hidden"}><label for="admin-budget-name">Name (Optional)</label><input id="admin-budget-name" placeholder="Name (Optional)" value="${htmlValue(budgetHead.individual)}"></div>
                <label class="check-row"><input id="admin-budget-institute-head" data-budget-head-field="admin-budget-department" type="checkbox" ${budgetHead.instituteHead ? "checked" : ""}> Institute Head</label>
                <div class="field-row budget-head-input" ${budgetHead.instituteHead ? "" : "hidden"}><label for="admin-budget-department">Department Name (Optional)</label><input id="admin-budget-department" placeholder="Department Name (Optional)" value="${htmlValue(budgetHead.instituteHead)}"></div>
                <label class="check-row"><input id="admin-budget-project-head" data-budget-head-field="admin-budget-project-code" type="checkbox" ${budgetHead.projectHead ? "checked" : ""}> Project Head</label>
                <div class="field-row budget-head-input" ${budgetHead.projectHead ? "" : "hidden"}><label for="admin-budget-project-code">Project code (Optional)</label><input id="admin-budget-project-code" placeholder="Project code (Optional)" value="${htmlValue(budgetHead.projectHead)}"></div>
                <button class="outline-btn compact-btn budget-clear-btn" id="admin-clear-budget-head" type="button">Clear Budget Head</button>
            </div>

            <div class="form-section-title">Requestor Details (Optional)</div>
            <div class="two-col">
                <div class="field-row"><label for="admin-requestor-name">Requestor name (Optional)</label><input id="admin-requestor-name" value="${htmlValue(source.requestor_name || source.requester_name)}"></div>
                <div class="field-row"><label for="admin-requestor-designation">Requestor designation (Optional)</label><input id="admin-requestor-designation" value="${htmlValue(source.requestor_designation)}"></div>
                <div class="field-row"><label for="admin-requestor-department">Requestor department (Optional)</label><input id="admin-requestor-department" value="${htmlValue(source.requestor_department)}"></div>
                <div class="field-row"><label for="admin-requestor-mobile">Requestor mobile (Optional)</label><input id="admin-requestor-mobile" inputmode="tel" value="${htmlValue(source.requestor_mobile)}"></div>
                ${source.requestor_email || source.requester_email ? `<div class="field-row"><label>Requestor email</label><input value="${htmlValue(source.requestor_email || source.requester_email)}" readonly></div>` : ""}
            </div>

            <div class="form-section-title">Logistics(Food/Cab) will be looked after by (Optional)</div>
            <label class="check-row"><input id="admin-logistics-same-as-requestor" type="checkbox"> Same as requestor details</label>
            <div class="two-col">
                <div class="field-row"><label for="admin-logistics-name">Logistics Name (Optional)</label><input id="admin-logistics-name" value="${htmlValue(source.logistics_name)}"></div>
                <div class="field-row"><label for="admin-logistics-designation">Designation (Optional)</label><input id="admin-logistics-designation" value="${htmlValue(source.logistics_designation)}"></div>
                <div class="field-row"><label for="admin-logistics-mobile">Mobile Number (Optional)</label><input id="admin-logistics-mobile" inputmode="tel" value="${htmlValue(source.logistics_mobile)}"></div>
            </div>

            <div class="form-section-title">Attender Requirement (Optional)</div>
            <label class="check-row"><input id="admin-attender" type="checkbox" ${source.attender_required ? "checked" : ""}> Attender required (Optional)</label>
            <div class="field-row"><label>Shift(s) * (if attender required) - Attender charges Rs 850 per chargeable shift per day</label></div>
            <div class="two-col">
                <label class="check-row"><input id="admin-morning" type="checkbox" ${source.attender_morning_shift ? "checked" : ""}> Morning shift (7 AM - 3 PM)</label>
                <label class="check-row"><input id="admin-evening" type="checkbox" ${source.attender_evening_shift ? "checked" : ""}> Evening shift (3 PM - 11 PM)</label>
            </div>
            <div id="admin-morning-chargeability" class="radio-list compact-radio-list">
                <label class="check-row"><input name="admin-morning-chargeable" type="radio" value="yes" ${source.attender_morning_chargeable === false ? "" : "checked"}> Morning shift chargeable</label>
                <label class="check-row"><input name="admin-morning-chargeable" type="radio" value="no" ${source.attender_morning_chargeable === false ? "checked" : ""}> Morning shift non-chargeable</label>
            </div>

            <div class="form-section-title">Charges</div>
            <div class="two-col">
                <div class="field-row"><label for="admin-room-charge-status">Room charges (Beta/Gamma auto per day; Delta manual) (Optional)</label><select id="admin-room-charge-status">
                    <option value="no" ${(source.room_charges_status || "no") === "no" ? "selected" : ""}>No</option>
                    <option value="yes" ${source.room_charges_status === "yes" ? "selected" : ""}>Yes</option>
                    <option value="waived_off" ${source.room_charges_status === "waived_off" ? "selected" : ""}>Waived Off</option>
                </select></div>
                <div class="field-row"><label for="admin-room-charge-amount">Room charges amount * (auto-filled, editable)</label><input id="admin-room-charge-amount" type="number" min="0" step="0.01" value="${htmlValue(source.room_charges_amount || 0)}"></div>
                <div class="field-row"><label for="admin-attender-charge-status">Attender charges (Rs 850 per chargeable shift per day) (Optional)</label><select id="admin-attender-charge-status">
                    <option value="no" ${(source.attender_charges_status || "no") === "no" ? "selected" : ""}>No</option>
                    <option value="yes" ${source.attender_charges_status === "yes" ? "selected" : ""}>Yes</option>
                    <option value="waived_off" ${source.attender_charges_status === "waived_off" ? "selected" : ""}>Waived Off</option>
                </select></div>
                <div class="field-row"><label for="admin-attender-charge-amount">Attender charges amount * (auto-filled, editable)</label><input id="admin-attender-charge-amount" type="number" min="0" step="0.01" value="${htmlValue(source.attender_charges_amount || 0)}"></div>
            </div>
        </form>
    `;
}


export function bindAdminBookingForm(rooms, selectedRoomId = "", preferredPrefix = "", options = {}, dependencies) {
    const { document, buildings: BUILDINGS, escapeHtml, roomLabel, availableRoomSelectLabel, apiFetch, toast, calculateRoomChargeAmount, calculateAttenderChargeAmount, inclusiveStayDays, fillFromPreviousBooking } = dependencies;
    const prefixSelect = document.getElementById("admin-prefix");
    const roomSelect = document.getElementById("admin-room");
    const arrivalDateInput = document.getElementById("admin-arrival-date");
    const departureDateInput = document.getElementById("admin-departure-date");
    const attender = document.getElementById("admin-attender");
    const morningShiftInput = document.getElementById("admin-morning");
    const eveningShiftInput = document.getElementById("admin-evening");
    const morningChargeableInputs = Array.from(document.querySelectorAll('input[name="admin-morning-chargeable"]'));
    const morningChargeability = document.getElementById("admin-morning-chargeability");
    const roomChargeStatus = document.getElementById("admin-room-charge-status");
    const roomChargeAmount = document.getElementById("admin-room-charge-amount");
    const attenderChargeStatus = document.getElementById("admin-attender-charge-status");
    const attenderChargeAmount = document.getElementById("admin-attender-charge-amount");
    const shiftInputs = ["admin-morning", "admin-evening"].map((id) => document.getElementById(id));
    const budgetOptions = Array.from(document.querySelectorAll("[data-budget-head-field]"));
    const sameAsRequestor = document.getElementById("admin-logistics-same-as-requestor");
    const requestorFields = {
        name: document.getElementById("admin-requestor-name"),
        designation: document.getElementById("admin-requestor-designation"),
        mobile: document.getElementById("admin-requestor-mobile"),
    };
    const logisticsFields = {
        name: document.getElementById("admin-logistics-name"),
        designation: document.getElementById("admin-logistics-designation"),
        mobile: document.getElementById("admin-logistics-mobile"),
    };
    if (!prefixSelect || !roomSelect) {
        return;
    }
    const bindChargeAmount = (statusId, amountId) => {
        const statusField = document.getElementById(statusId);
        const amountField = document.getElementById(amountId);
        if (!statusField || !amountField) {
            return;
        }

        const sync = () => {
            const enabled = statusField.value === "yes";
            amountField.disabled = !enabled;
            if (!enabled) {
                amountField.value = "";
            }
        };

        statusField.addEventListener("change", sync);
        sync();
        return sync;
    };
    const availabilityFilter = options.availabilityFilter !== false;
    const preserveInitialRoomChargeStatus = options.preserveRoomChargeStatus === true;
    let hasSyncedInitialRoomCharges = false;
    let currentRoomOptions = rooms;
    const selectedRoom = rooms.find((room) => String(room.id) === String(selectedRoomId));
    if (selectedRoom?.prefix) {
        prefixSelect.value = selectedRoom.prefix;
    } else if (preferredPrefix && BUILDINGS.includes(preferredPrefix)) {
        prefixSelect.value = preferredPrefix;
    }
    const selectedAdminRoom = () => {
        const selectedId = roomSelect.value;
        if (!selectedId) {
            return null;
        }
        return currentRoomOptions.find((room) => String(room.room_id || room.id) === String(selectedId)) || null;
    };
    const calculatedAdminRoomChargeAmount = () => calculateRoomChargeAmount(
        selectedAdminRoom(),
        prefixSelect.value,
        inclusiveStayDays(arrivalDateInput?.value, departureDateInput?.value),
        document.querySelector('input[name="admin-visitor-nationality"]:checked')?.value || "",
    );
    const syncCalculatedRoomCharges = ({ autoStatus = true } = {}) => {
        if (!roomChargeStatus || !roomChargeAmount) {
            return;
        }
        const room = selectedAdminRoom();
        const calculatedAmount = room ? calculatedAdminRoomChargeAmount() : null;
        const autoCalculated = calculatedAmount !== null;

        if (autoStatus && autoCalculated) {
            roomChargeStatus.value = "yes";
        }

        const chargesReceived = roomChargeStatus.value === "yes";
        roomChargeAmount.disabled = !chargesReceived || !room;
        roomChargeAmount.readOnly = false;

        if (!chargesReceived || !room) {
            roomChargeAmount.value = "";
            return;
        }

        if (autoCalculated) {
            roomChargeAmount.value = String(calculatedAmount);
        }
    };
    let roomLoadToken = 0;
    const renderAllRoomOptions = () => {
        const filtered = rooms.filter((room) => !prefixSelect.value || room.prefix === prefixSelect.value);
        currentRoomOptions = filtered;
        roomSelect.innerHTML = `<option value="">Select room</option>` + filtered.map((room) => `
            <option value="${room.id}" data-prefix="${escapeHtml(room.prefix || "")}" data-has-attached-bath="${room.has_attached_bath === false ? "false" : "true"}" ${String(room.id) === String(selectedRoomId) ? "selected" : ""}>${escapeHtml(roomLabel(room))}</option>
        `).join("");
    };
    const renderAvailableRoomOptions = async () => {
        const token = ++roomLoadToken;
        const prefix = prefixSelect.value;
        const arrivalDate = arrivalDateInput?.value || "";
        const departureDate = departureDateInput?.value || arrivalDate;

        if (!prefix || !arrivalDate || !departureDate) {
            currentRoomOptions = [];
            roomSelect.innerHTML = `<option value="">Select dates to load available rooms</option>`;
            roomSelect.disabled = false;
            return;
        }

        roomSelect.disabled = true;
        roomSelect.innerHTML = `<option value="">Loading available rooms...</option>`;
        try {
            const data = await apiFetch(`/api/room-available-rooms-range/?arrival_date=${encodeURIComponent(arrivalDate)}&departure_date=${encodeURIComponent(departureDate)}&prefix=${encodeURIComponent(prefix)}`);
            if (token !== roomLoadToken) {
                return;
            }
            const availableRooms = data?.rooms || [];
            if (!availableRooms.length) {
                currentRoomOptions = [];
                roomSelect.innerHTML = `<option value="">No available rooms for selected dates</option>`;
                roomSelect.disabled = false;
                return;
            }

            currentRoomOptions = availableRooms;
            roomSelect.innerHTML = `<option value="">Select room</option>` + availableRooms.map((room) => {
                const roomId = room.room_id || room.id || "";
                return `
                    <option value="${roomId}" data-prefix="${escapeHtml(room.prefix || prefix || "")}" data-has-attached-bath="${room.has_attached_bath === false ? "false" : "true"}" ${String(roomId) === String(selectedRoomId) ? "selected" : ""}>${escapeHtml(availableRoomSelectLabel(room, prefix))}</option>
                `;
            }).join("");
            roomSelect.disabled = false;
            syncCalculatedRoomCharges({ autoStatus: !preserveInitialRoomChargeStatus });
            hasSyncedInitialRoomCharges = true;
        } catch (error) {
            if (token !== roomLoadToken) {
                return;
            }
            roomSelect.innerHTML = `<option value="">Could not load available rooms</option>`;
            roomSelect.disabled = false;
            toast(error.message || "Could not load available rooms.", "error");
        }
    };
    const renderRoomOptions = () => {
        if (availabilityFilter) {
            renderAvailableRoomOptions();
            return;
        }
        renderAllRoomOptions();
    };
    prefixSelect.addEventListener("change", () => {
        selectedRoomId = "";
        renderRoomOptions();
        syncCalculatedRoomCharges({ autoStatus: false });
    });
    [arrivalDateInput, departureDateInput].forEach((input) => {
        input?.addEventListener("change", () => {
            selectedRoomId = "";
            renderRoomOptions();
            syncCalculatedRoomCharges({ autoStatus: false });
            syncCalculatedAttenderCharges();
        });
    });
    renderRoomOptions();
    const syncAttenderChargeAmountEnabled = bindChargeAmount("admin-attender-charge-status", "admin-attender-charge-amount");
    roomSelect.addEventListener("change", () => syncCalculatedRoomCharges({ autoStatus: true }));
    roomChargeStatus?.addEventListener("change", () => syncCalculatedRoomCharges({ autoStatus: false }));
    document.querySelectorAll('input[name="admin-visitor-nationality"]').forEach((input) => {
        input.addEventListener("change", () => syncCalculatedRoomCharges({ autoStatus: false }));
    });
    if (!availabilityFilter || currentRoomOptions.length) {
        syncCalculatedRoomCharges({ autoStatus: !preserveInitialRoomChargeStatus });
        hasSyncedInitialRoomCharges = true;
    }

    const selectedMorningChargeable = () => (
        document.querySelector('input[name="admin-morning-chargeable"]:checked')?.value !== "no"
    );
    const calculatedAdminAttenderChargeAmount = () => calculateAttenderChargeAmount(
        Boolean(attender?.checked),
        Boolean(morningShiftInput?.checked),
        selectedMorningChargeable(),
        Boolean(eveningShiftInput?.checked),
        inclusiveStayDays(arrivalDateInput?.value, departureDateInput?.value),
    );
    const syncMorningChargeability = () => {
        const enabled = Boolean(attender?.checked && morningShiftInput?.checked);
        if (morningChargeability) {
            morningChargeability.hidden = !enabled;
        }
        morningChargeableInputs.forEach((input) => {
            input.disabled = !enabled;
        });
    };
    const syncCalculatedAttenderCharges = ({ autoStatus = true } = {}) => {
        const amount = calculatedAdminAttenderChargeAmount();
        if (attenderChargeStatus && autoStatus) {
            if (amount > 0) {
                attenderChargeStatus.value = "yes";
            } else if (attenderChargeStatus.value === "yes") {
                attenderChargeStatus.value = "no";
            }
        }
        syncAttenderChargeAmountEnabled?.();
        if (attenderChargeStatus?.value === "yes" && attenderChargeAmount) {
            attenderChargeAmount.value = amount ? String(amount) : "";
        }
    };

    const syncAttender = () => {
        const enabled = attender?.checked;
        shiftInputs.forEach((input) => {
            if (!input) return;
            input.disabled = !enabled;
            if (!enabled) input.checked = false;
        });
        syncMorningChargeability();
        syncCalculatedAttenderCharges();
    };
    attender?.addEventListener("change", syncAttender);
    shiftInputs.forEach((input) => {
        input?.addEventListener("change", () => {
            syncMorningChargeability();
            syncCalculatedAttenderCharges();
        });
    });
    morningChargeableInputs.forEach((input) => {
        input.addEventListener("change", () => syncCalculatedAttenderCharges());
    });
    attenderChargeStatus?.addEventListener("change", () => syncCalculatedAttenderCharges({ autoStatus: false }));
    syncAttender();
    if (!hasSyncedInitialRoomCharges) {
        syncCalculatedRoomCharges({ autoStatus: !preserveInitialRoomChargeStatus });
    }

    const copyRequestorToLogistics = () => {
        if (logisticsFields.name && requestorFields.name) logisticsFields.name.value = requestorFields.name.value;
        if (logisticsFields.designation && requestorFields.designation) logisticsFields.designation.value = requestorFields.designation.value;
        if (logisticsFields.mobile && requestorFields.mobile) logisticsFields.mobile.value = requestorFields.mobile.value;
    };
    const clearLogisticsFields = () => {
        Object.values(logisticsFields).forEach((field) => {
            if (field) field.value = "";
        });
    };
    const updateLogisticsFields = () => {
        const locked = Boolean(sameAsRequestor?.checked);
        if (locked) {
            copyRequestorToLogistics();
        }
        Object.values(logisticsFields).forEach((field) => {
            if (field) field.disabled = locked;
        });
    };
    const requestorHasValue = Object.values(requestorFields).some((field) => field?.value?.trim());
    const logisticsMatchesRequestor = requestorHasValue
        && logisticsFields.name?.value === requestorFields.name?.value
        && logisticsFields.designation?.value === requestorFields.designation?.value
        && logisticsFields.mobile?.value === requestorFields.mobile?.value;
    if (sameAsRequestor) {
        sameAsRequestor.checked = logisticsMatchesRequestor;
        sameAsRequestor.addEventListener("change", () => {
            if (!sameAsRequestor.checked) {
                clearLogisticsFields();
            }
            updateLogisticsFields();
        });
        Object.values(requestorFields).forEach((field) => {
            field?.addEventListener("input", () => {
                if (sameAsRequestor.checked) {
                    copyRequestorToLogistics();
                }
            });
        });
        updateLogisticsFields();
    }

    const syncBudgetHeadOption = (checkbox, shouldFocus = false) => {
        const field = document.getElementById(checkbox.dataset.budgetHeadField);
        const wrapper = field?.closest(".budget-head-input");
        if (!field || !wrapper) return;
        wrapper.hidden = !checkbox.checked;
        if (checkbox.checked && shouldFocus) {
            field.focus();
        }
        if (!checkbox.checked) {
            field.value = "";
        }
    };
    budgetOptions.forEach((checkbox) => {
        syncBudgetHeadOption(checkbox);
        checkbox.addEventListener("change", () => syncBudgetHeadOption(checkbox, true));
    });
    document.getElementById("admin-clear-budget-head")?.addEventListener("click", () => {
        budgetOptions.forEach((checkbox) => {
            checkbox.checked = false;
            syncBudgetHeadOption(checkbox);
        });
    });
    document.getElementById("admin-clear-visitor-category")?.addEventListener("click", () => {
        document.querySelectorAll('input[name="admin-visitor-category"]').forEach((input) => {
            input.checked = false;
        });
    });
    document.getElementById("admin-clear-visitor-nationality")?.addEventListener("click", () => {
        document.querySelectorAll('input[name="admin-visitor-nationality"]').forEach((input) => {
            input.checked = false;
        });
    });
    document.getElementById("admin-fill-from-previous")?.addEventListener("change", async (event) => {
        if (!event.target.checked) {
            return;
        }
        event.target.disabled = true;
        try {
            await fillFromPreviousBooking();
        } catch (error) {
            event.target.checked = false;
            toast(error.message, "error");
        } finally {
            event.target.disabled = false;
        }
    });
}

export function readAdminBookingPayload(document, buildIsoDateTime) {
    const val = (id) => document.getElementById(id)?.value?.trim() || "";
    const checked = (id) => Boolean(document.getElementById(id)?.checked);
    const room = val("admin-room");
    const arrivalAt = buildIsoDateTime(val("admin-arrival-date"), val("admin-arrival-time"));
    const departureAt = buildIsoDateTime(val("admin-departure-date"), val("admin-departure-time"));
    if (!room) {
        throw new Error("Room is required.");
    }
    if (!val("admin-arrival-date") || !val("admin-departure-date")) {
        throw new Error("Arrival and departure dates are required.");
    }
    if (new Date(departureAt) <= new Date(arrivalAt)) {
        throw new Error("Departure datetime must be after arrival datetime.");
    }
    if (!val("admin-visitor-name")) {
        throw new Error("Visitor name is required.");
    }
    const attenderRequired = checked("admin-attender");
    const attenderMorningShift = attenderRequired && checked("admin-morning");
    const attenderEveningShift = attenderRequired && checked("admin-evening");
    const morningChargeable = attenderMorningShift
        && document.querySelector('input[name="admin-morning-chargeable"]:checked')?.value !== "no";
    const roomChargeStatus = val("admin-room-charge-status") || "no";
    const attenderChargeStatus = val("admin-attender-charge-status") || "no";
    const budgetName = checked("admin-budget-individual") ? val("admin-budget-name") : "";
    const budgetDepartment = checked("admin-budget-institute-head") ? val("admin-budget-department") : "";
    const budgetProjectCode = checked("admin-budget-project-head") ? val("admin-budget-project-code") : "";
    return {
        room,
        arrival_at: arrivalAt,
        departure_at: departureAt,
        visitor_name: val("admin-visitor-name"),
        visitor_designation: val("admin-visitor-designation"),
        visitor_organisation: val("admin-visitor-organisation"),
        visitor_gender: val("admin-visitor-gender"),
        visitor_nationality: document.querySelector('input[name="admin-visitor-nationality"]:checked')?.value || "",
        visitor_mobile: val("admin-visitor-mobile"),
        visitor_email: val("admin-visitor-email"),
        visitor_category: document.querySelector('input[name="admin-visitor-category"]:checked')?.value || "",
        purpose_of_visit: val("admin-purpose"),
        remarks: val("admin-remarks"),
        requestor_name: val("admin-requestor-name"),
        requestor_designation: val("admin-requestor-designation"),
        requestor_department: val("admin-requestor-department"),
        requestor_mobile: val("admin-requestor-mobile"),
        attender_required: attenderRequired,
        attender_morning_shift: attenderMorningShift,
        attender_morning_chargeable: morningChargeable,
        attender_evening_shift: attenderEveningShift,
        room_charges_status: roomChargeStatus,
        room_charges_amount: roomChargeStatus === "yes" ? Number(val("admin-room-charge-amount") || 0) : 0,
        attender_charges_status: attenderChargeStatus,
        attender_charges_amount: attenderChargeStatus === "yes" ? Number(val("admin-attender-charge-amount") || 0) : 0,
        budget_head_type: "",
        budget_head_value: "",
        budget_head_name: budgetName,
        budget_head_department_name: budgetDepartment,
        budget_head_project_code: budgetProjectCode,
        logistics_name: val("admin-logistics-name"),
        logistics_designation: val("admin-logistics-designation"),
        logistics_mobile: val("admin-logistics-mobile"),
    };
}
