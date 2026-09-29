export function renderRequesterBookingForm(existing, { arrival, departure, user, budgetHead, escapeHtml, htmlValue, formatDateOnly }) {
    const requestorName = user?.name || existing?.requestor_name || "";
    const requestorEmail = existing?.requestor_email || user?.email || "";
    const requesterMorningChargeable = existing?.attender_morning_chargeable !== false;
    const canEditDates = existing?.status === "correction_required";
    const arrivalDateField = canEditDates
        ? `<input id="req-arrival-date" type="date" value="${htmlValue(arrival.date)}" required>`
        : `<input id="req-arrival-date" type="hidden" value="${htmlValue(arrival.date)}"><input value="${htmlValue(formatDateOnly(arrival.date))}" readonly>`;
    const departureDateField = canEditDates
        ? `<input id="req-departure-date" type="date" value="${htmlValue(departure.date)}" required>`
        : `<input id="req-departure-date" type="hidden" value="${htmlValue(departure.date)}"><input value="${htmlValue(formatDateOnly(departure.date))}" readonly>`;
    return `
            <form id="request-form" class="field-grid">
                <div class="form-section-title">Room Preference</div>
                <div class="field-row"><label for="req-room-preference-note">Room preference note (Optional)</label><textarea id="req-room-preference-note" placeholder="Example: Ground floor room, attached bathroom, or any other preference">${escapeHtml(existing?.room_preference_note || "")}</textarea></div>

                <div class="form-section-title">Stay Details</div>
                <div class="two-col">
                    <div class="field-row"><label for="req-arrival-date">Arrival *</label>${arrivalDateField}</div>
                    <div class="field-row"><label>Arrival time *</label><input id="req-arrival-time" type="time" value="${htmlValue(arrival.time || "10:00")}" required></div>
                    <div class="field-row"><label for="req-departure-date">Departure *</label>${departureDateField}</div>
                    <div class="field-row"><label>Departure time *</label><input id="req-departure-time" type="time" value="${htmlValue(departure.time || "18:00")}" required></div>
                </div>

                <div class="form-section-title">Visitor Details</div>
                <div class="two-col">
                    <div class="field-row"><label>Visitor name *</label><input id="req-visitor-name" value="${escapeHtml(existing?.visitor_name || "")}" required></div>
                    <div class="field-row"><label>Designation (Optional)</label><input id="req-visitor-designation" value="${escapeHtml(existing?.visitor_designation || "")}"></div>
                    <div class="field-row"><label>Organisation (Optional)</label><input id="req-visitor-organisation" value="${escapeHtml(existing?.visitor_organisation || "")}"></div>
                    <div class="field-row"><label>Gender (Optional)</label><select id="req-visitor-gender">
                        <option value="" ${!existing?.visitor_gender ? "selected" : ""}>Select gender (Optional)</option>
                        <option value="Male" ${existing?.visitor_gender === "Male" ? "selected" : ""}>Male</option>
                        <option value="Female" ${existing?.visitor_gender === "Female" ? "selected" : ""}>Female</option>
                        <option value="Other" ${existing?.visitor_gender === "Other" ? "selected" : ""}>Other</option>
                    </select></div>
                    <div class="field-row"><label>Guest nationality (Optional)</label>
                        <div class="radio-list compact-radio-list">
                            <label class="check-row"><input name="req-visitor-nationality" type="radio" value="indian" ${existing?.visitor_nationality === "indian" ? "checked" : ""}> Indian</label>
                            <label class="check-row"><input name="req-visitor-nationality" type="radio" value="foreigner" ${existing?.visitor_nationality === "foreigner" ? "checked" : ""}> Foreigner</label>
                        </div>
                        <button class="outline-btn compact-btn" id="req-clear-visitor-nationality" type="button">Clear Selection</button>
                    </div>
                    <div class="field-row"><label>Visitor mobile (Optional)</label><input id="req-visitor-mobile" value="${escapeHtml(existing?.visitor_mobile || "")}"></div>
                    <div class="field-row"><label>Visitor email (Optional)</label><input id="req-visitor-email" type="email" value="${escapeHtml(existing?.visitor_email || "")}"></div>
                </div>
                <div class="field-row"><label>Purpose of visit (Optional)</label><textarea id="req-purpose">${escapeHtml(existing?.purpose_of_visit || "")}</textarea></div>

                <div class="form-section-title">Visitor Category (Optional)</div>
                <div class="radio-list">
                    <label class="check-row"><input name="req-visitor-category" type="radio" value="institute_guest" ${existing?.visitor_category === "institute_guest" ? "checked" : ""}> Institute Guest (Official Institute Guest)</label>
                    <label class="check-row"><input name="req-visitor-category" type="radio" value="conference_workshop_guest" ${existing?.visitor_category === "conference_workshop_guest" ? "checked" : ""}> Conference / Workshop Guest</label>
                    <label class="check-row"><input name="req-visitor-category" type="radio" value="other_guest" ${existing?.visitor_category === "other_guest" ? "checked" : ""}> Other Guest</label>
                    <button class="outline-btn compact-btn" id="req-clear-visitor-category" type="button">Clear Selection</button>
                </div>

                <div class="form-section-title">Budget Head (Optional)</div>
                <div class="budget-head-group">
                    <label class="check-row"><input id="req-budget-individual" data-requester-budget-head-field="req-budget-name" type="checkbox" ${budgetHead.individual ? "checked" : ""}> Individual</label>
                    <div class="field-row budget-head-input" ${budgetHead.individual ? "" : "hidden"}><label for="req-budget-name">Name (Optional)</label><input id="req-budget-name" placeholder="Name (Optional)" value="${htmlValue(budgetHead.individual)}"></div>
                    <label class="check-row"><input id="req-budget-institute-head" data-requester-budget-head-field="req-budget-department" type="checkbox" ${budgetHead.instituteHead ? "checked" : ""}> Institute Head</label>
                    <div class="field-row budget-head-input" ${budgetHead.instituteHead ? "" : "hidden"}><label for="req-budget-department">Department Name (Optional)</label><input id="req-budget-department" placeholder="Department Name (Optional)" value="${htmlValue(budgetHead.instituteHead)}"></div>
                    <label class="check-row"><input id="req-budget-project-head" data-requester-budget-head-field="req-budget-project-code" type="checkbox" ${budgetHead.projectHead ? "checked" : ""}> Project Head</label>
                    <div class="field-row budget-head-input" ${budgetHead.projectHead ? "" : "hidden"}><label for="req-budget-project-code">Project code (Optional)</label><input id="req-budget-project-code" placeholder="Project code (Optional)" value="${htmlValue(budgetHead.projectHead)}"></div>
                    <button class="outline-btn compact-btn budget-clear-btn" id="req-clear-budget-head" type="button">Clear Budget Head</button>
                </div>

                <div class="form-section-title">Attender Requirement (Optional)</div>
                <label style="display:flex;gap:8px;align-items:center;font-weight:800"><input id="req-attender" type="checkbox" ${existing?.attender_required ? "checked" : ""}> Attender required (Optional)</label>
                <div class="field-row"><label>Shift(s) * (if attender required) - Attender charges Rs 850 per chargeable shift per day</label></div>
                <div class="two-col">
                    <label style="display:flex;gap:8px;align-items:center"><input id="req-morning" type="checkbox" ${existing?.attender_morning_shift ? "checked" : ""}> Morning shift (7 AM - 3 PM)</label>
                    <label style="display:flex;gap:8px;align-items:center"><input id="req-evening" type="checkbox" ${existing?.attender_evening_shift ? "checked" : ""}> Evening shift (3 PM - 11 PM)</label>
                </div>
                <div id="req-morning-chargeability" class="radio-list compact-radio-list">
                    <label class="check-row"><input name="req-morning-chargeable" type="radio" value="yes" ${requesterMorningChargeable ? "checked" : ""}> Morning shift chargeable</label>
                    <label class="check-row"><input name="req-morning-chargeable" type="radio" value="no" ${requesterMorningChargeable ? "" : "checked"}> Morning shift non-chargeable</label>
                </div>

                <div class="form-section-title">Requester Details</div>
                <div class="two-col">
                    <div class="field-row"><label>Requester name (Optional)</label><input id="req-requestor-name" value="${escapeHtml(requestorName)}" disabled aria-readonly="true"></div>
                    <div class="field-row"><label>Department (Optional)</label><input id="req-requestor-department" value="${escapeHtml(existing?.requestor_department || user?.department || "")}"></div>
                    <div class="field-row"><label>Designation (Optional)</label><input id="req-requestor-designation" value="${escapeHtml(existing?.requestor_designation || user?.designation || "")}"></div>
                    <div class="field-row"><label>Mobile (Optional)</label><input id="req-requestor-mobile" value="${escapeHtml(existing?.requestor_mobile || user?.mobile || "")}"></div>
                    <div class="field-row"><label>Email (Optional)</label><input id="req-requestor-email" type="email" value="${escapeHtml(requestorEmail)}" readonly></div>
                </div>
            </form>
    `;
}

export function buildRequesterBookingPayload(document, user, buildIsoDateTime) {
    const arrivalDate = document.getElementById("req-arrival-date").value;
    const departureDate = document.getElementById("req-departure-date").value;
    const arrivalTime = document.getElementById("req-arrival-time").value;
    const departureTime = document.getElementById("req-departure-time").value;
    const arrivalAt = buildIsoDateTime(arrivalDate, arrivalTime);
    const departureAt = buildIsoDateTime(departureDate, departureTime);
    if (new Date(departureAt) <= new Date(arrivalAt)) {
        throw new Error("Departure datetime must be after arrival datetime.");
    }
    const attenderRequired = document.getElementById("req-attender").checked;
    const checked = (id) => Boolean(document.getElementById(id)?.checked);
    const val = (id) => document.getElementById(id)?.value?.trim() || "";
    const reqMorningShift = attenderRequired && checked("req-morning");
    const budgetName = checked("req-budget-individual") ? val("req-budget-name") : "";
    const budgetDepartment = checked("req-budget-institute-head") ? val("req-budget-department") : "";
    const budgetProjectCode = checked("req-budget-project-head") ? val("req-budget-project-code") : "";
    const payload = {
        arrival_at: arrivalAt,
        departure_at: departureAt,
        room_preference_note: document.getElementById("req-room-preference-note").value.trim(),
        visitor_name: document.getElementById("req-visitor-name").value.trim(),
        visitor_designation: document.getElementById("req-visitor-designation").value.trim(),
        visitor_organisation: document.getElementById("req-visitor-organisation").value.trim(),
        visitor_gender: document.getElementById("req-visitor-gender").value,
        visitor_nationality: document.querySelector('input[name="req-visitor-nationality"]:checked')?.value || "",
        visitor_mobile: document.getElementById("req-visitor-mobile").value.trim(),
        visitor_email: document.getElementById("req-visitor-email").value.trim(),
        visitor_category: document.querySelector('input[name="req-visitor-category"]:checked')?.value || "",
        purpose_of_visit: document.getElementById("req-purpose").value.trim(),
        budget_head_type: "",
        budget_head_value: "",
        budget_head_name: budgetName,
        budget_head_department_name: budgetDepartment,
        budget_head_project_code: budgetProjectCode,
        requestor_name: (user?.name || document.getElementById("req-requestor-name").value).trim(),
        requestor_department: document.getElementById("req-requestor-department").value.trim(),
        requestor_designation: document.getElementById("req-requestor-designation").value.trim(),
        requestor_mobile: document.getElementById("req-requestor-mobile").value.trim(),
        requestor_email: document.getElementById("req-requestor-email").value.trim() || user?.email || "",
        attender_required: attenderRequired,
        attender_morning_shift: reqMorningShift,
        attender_morning_chargeable: reqMorningShift
            && document.querySelector('input[name="req-morning-chargeable"]:checked')?.value !== "no",
        attender_evening_shift: attenderRequired && document.getElementById("req-evening").checked,
    };
    if (!payload.visitor_name) {
        throw new Error("Visitor name is required.");
    }
    return payload;
}
