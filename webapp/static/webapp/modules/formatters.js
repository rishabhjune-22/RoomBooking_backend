const STATUS_LABELS = {
    pending: "Pending", approved: "Approved", rejected: "Rejected",
    correction_required: "Correction Required", active: "Active", expired: "Expired",
};
const LOCALE = "en-IN";
const TIME_ZONE = "Asia/Kolkata";
const DATE_OPTIONS = { timeZone: TIME_ZONE, day: "2-digit", month: "short", year: "numeric" };
const DATETIME_OPTIONS = {
    ...DATE_OPTIONS, hour: "2-digit", minute: "2-digit", hour12: true,
};
const TIME_OPTIONS = { timeZone: TIME_ZONE, hour: "2-digit", minute: "2-digit", hour12: true };
const MONTH_YEAR_OPTIONS = { timeZone: TIME_ZONE, month: "long", year: "numeric" };
const API_DATE_TIME_IN_TEXT =
    /\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})/g;

export function escapeHtml(value) {
    return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}
export function titleCase(value) {
    return STATUS_LABELS[value] || String(value || "").replaceAll("_", " ");
}
export function pad(value) { return String(value).padStart(2, "0"); }
export function isoDate(year, month, day) { return `${year}-${pad(month)}-${pad(day)}`; }
export function todayIso() { return indiaParts(new Date()).date; }
export function currentMonthRange() {
    const [year, month] = todayIso().split("-").map(Number);
    return { start: isoDate(year, month, 1), end: isoDate(year, month, new Date(Date.UTC(year, month, 0)).getUTCDate()) };
}
export function addIsoDays(dateValue, days) {
    const date = new Date(`${dateValue}T00:00:00`);
    date.setDate(date.getDate() + days);
    return isoDate(date.getFullYear(), date.getMonth() + 1, date.getDate());
}
export function addHoursToDateTime(value, hours) {
    return new Date(new Date(value).getTime() + hours * 60 * 60 * 1000);
}
export function isoDateRange(start, end) {
    const dates = [];
    if (!start || !end) return dates;
    let cursor = start <= end ? start : end;
    const finalDate = start <= end ? end : start;
    while (cursor <= finalDate) { dates.push(cursor); cursor = addIsoDays(cursor, 1); }
    return dates;
}
export function indiaParts(value) {
    if (!value) return { date: "", time: "" };
    const parts = new Intl.DateTimeFormat("en-CA", {
        timeZone: TIME_ZONE, year: "numeric", month: "2-digit", day: "2-digit",
        hour: "2-digit", minute: "2-digit", hourCycle: "h23",
    }).formatToParts(new Date(value));
    const lookup = Object.fromEntries(parts.map((part) => [part.type, part.value]));
    return { date: `${lookup.year}-${lookup.month}-${lookup.day}`, time: `${lookup.hour}:${lookup.minute}` };
}
export function localIsoDateFromDateTime(value) { return indiaParts(value).date; }
export function localTimeMinutes(value) {
    const [hour = 0, minute = 0] = indiaParts(value).time.split(":").map(Number);
    return hour * 60 + minute;
}
export function normalizeDisplayPeriod(value) {
    return String(value || "").replace(/\b(am|pm)\b/gi, (period) => period.toUpperCase());
}
export function formatSheetTime(value) {
    return value ? normalizeDisplayPeriod(new Intl.DateTimeFormat(LOCALE, TIME_OPTIONS).format(new Date(value))) : "";
}
export function formatSheetDate(value) {
    return value ? new Intl.DateTimeFormat(LOCALE, DATE_OPTIONS).format(new Date(`${value}T00:00:00+05:30`)) : "-";
}
export function monthName(year, month) {
    return new Intl.DateTimeFormat(LOCALE, MONTH_YEAR_OPTIONS).format(new Date(`${isoDate(year, month, 1)}T00:00:00+05:30`));
}
export function formatDateTime(value) {
    return value ? normalizeDisplayPeriod(new Intl.DateTimeFormat(LOCALE, DATETIME_OPTIONS).format(new Date(value))) : "-";
}
export function formatDateOnly(value) {
    return value ? new Intl.DateTimeFormat(LOCALE, DATE_OPTIONS).format(new Date(`${value}T00:00:00+05:30`)) : "-";
}
export function formatDateTimesInText(text) {
    return text ? String(text).replace(API_DATE_TIME_IN_TEXT, (value) => formatDateTime(value)) : text;
}
export function formatDateRange(item) { return `${formatDateTime(item.arrival_at)} to ${formatDateTime(item.departure_at)}`; }
export function isPastDateTime(value) {
    if (!value) return false;
    const date = new Date(value);
    return !Number.isNaN(date.getTime()) && date.getTime() < Date.now();
}
export function scheduleDisplayText(arrivalDate, departureDate = arrivalDate) {
    if (!arrivalDate) return "No dates selected";
    return !departureDate || departureDate === arrivalDate
        ? formatDateOnly(arrivalDate)
        : `${formatDateOnly(arrivalDate)} to ${formatDateOnly(departureDate)}`;
}
export function buildIsoDateTime(dateValue, timeValue) { return `${dateValue}T${timeValue || "10:00"}:00+05:30`; }
export function yesNo(value) { return value ? "Yes" : "No"; }
export function valueOrDash(value) {
    if (value === true || value === false) return yesNo(value);
    if (value === 0) return "0";
    return value || "-";
}
export function visitorNationalityLabel(value) {
    if (value === "foreigner") return "Foreigner";
    if (value === "indian") return "Indian";
    return valueOrDash(value);
}
export function parseDisplayTimeTo24(value) {
    const match = String(value || "").trim().match(/^(\d{1,2}):(\d{2})\s*([AP]M)$/i);
    if (!match) return "";
    let hour = Number(match[1]);
    const minute = Number(match[2]);
    const meridiem = match[3].toUpperCase();
    if (Number.isNaN(hour) || Number.isNaN(minute)) return "";
    if (meridiem === "PM" && hour < 12) hour += 12;
    if (meridiem === "AM" && hour === 12) hour = 0;
    return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}
