const ATTENDER_CHARGE_PER_SHIFT = 850;
const ROOM_CHARGE_RATES = {
    Gamma: { attached: 1500, nonAttached: 1300 },
    Beta: { attached: 1000, nonAttached: 800 },
};
const FOREIGN_ROOM_CHARGE_RATES = {
    Gamma: { attached: 2000, nonAttached: 1800 },
    Beta: { attached: 1500, nonAttached: 1300 },
};

export function inclusiveStayDays(arrivalDate, departureDate) {
    if (!arrivalDate || !departureDate) return 1;
    const arrival = new Date(`${arrivalDate}T00:00:00`);
    const departure = new Date(`${departureDate}T00:00:00`);
    if (Number.isNaN(arrival.getTime()) || Number.isNaN(departure.getTime())) return 1;
    return Math.max(Math.max(Math.round((departure - arrival) / 86400000), 0) + 1, 1);
}

export function calculateAttenderChargeAmount(attenderRequired, morningShift, morningChargeable, eveningShift, stayDays = 1) {
    if (!attenderRequired) return 0;
    const shifts = Number(Boolean(morningShift && morningChargeable)) + Number(Boolean(eveningShift));
    return shifts * ATTENDER_CHARGE_PER_SHIFT * Math.max(Number(stayDays) || 1, 1);
}

export function roomChargeRate(room, fallbackPrefix = "", visitorNationality = "") {
    const prefix = String(room?.prefix || fallbackPrefix || "").trim();
    const rates = (visitorNationality === "foreigner" ? FOREIGN_ROOM_CHARGE_RATES : ROOM_CHARGE_RATES)[prefix];
    if (!rates) return null;
    return room?.has_attached_bath === false ? rates.nonAttached : rates.attached;
}

export function calculateRoomChargeAmount(room, fallbackPrefix, stayDays = 1, visitorNationality = "") {
    const rate = roomChargeRate(room, fallbackPrefix, visitorNationality);
    return rate === null ? null : rate * Math.max(Number(stayDays) || 1, 1);
}

export function normalizedBudgetHeadFields(source = {}) {
    const type = source.budget_head_type || "";
    const value = source.budget_head_value || "";
    return {
        individual: source.budget_head_name || (type === "individual" || (!type && value) ? value : ""),
        instituteHead: source.budget_head_department_name || (type === "institute_head" ? value : ""),
        projectHead: source.budget_head_project_code || (type === "project_head" ? value : ""),
    };
}

export function availableRoomSelectLabel(room, prefix, roomLabel, availabilityText) {
    const label = roomLabel({
        id: room.room_id || room.id,
        prefix: room.prefix || prefix,
        selection_label: room.selection_label,
        room_name: room.room_name,
        number: room.room_number || room.number,
    });
    return room.availability_status === "partial" ? `${label} (${availabilityText(room)})` : label;
}
