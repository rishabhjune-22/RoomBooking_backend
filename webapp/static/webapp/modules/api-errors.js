import { formatDateTimesInText, titleCase } from "./formatters.js";

export function messageFromErrors(payload) {
    if (!payload) return "Request failed.";
    const errorMessage = firstFieldErrorMessage(payload.errors || {});
    return errorMessage
        ? formatDateTimesInText(errorMessage)
        : formatDateTimesInText(payload.message || "Request failed.");
}
function firstFieldErrorMessage(errors) {
    for (const [field, value] of Object.entries(errors)) {
        const message = firstErrorValue(value);
        if (!message) continue;
        const label = errorFieldLabel(field);
        const readableMessage = formatDateTimesInText(message);
        return label ? `${label}: ${readableMessage}` : readableMessage;
    }
    return "";
}
function firstErrorValue(value) {
    if (Array.isArray(value)) {
        for (const item of value) {
            const message = firstErrorValue(item);
            if (message) return message;
        }
        return "";
    }
    if (value && typeof value === "object") return firstFieldErrorMessage(value);
    return String(value || "").trim();
}
function errorFieldLabel(field) {
    const labels = { admin_code: "Admin invite code", confirm_password: "Confirm password", email: "Email", name: "Name", password: "Password" };
    if (field === "detail" || field === "non_field_errors") return "";
    return labels[field] || titleCase(field);
}
