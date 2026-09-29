export function bookingSharePayload(state, range, validity = "1w") {
    const filters = { arrival_from: range.start, departure_to: range.end };
    if (state.bookingStatusFilter !== "all") filters.status = state.bookingStatusFilter;
    if (state.bookingPrefixFilter !== "all") filters.prefix = state.bookingPrefixFilter;
    return { share_type: "booking_sheet", title: "Booking Sheet", validity, filters };
}

export function chargeSharePayload(state, validity = "1w") {
    const filters = {};
    if (state.chargeSheetPrefixFilter !== "all") filters.prefix = state.chargeSheetPrefixFilter;
    if (state.chargeSheetPaymentFilter !== "all") filters.payment = state.chargeSheetPaymentFilter;
    if (state.chargeSheetCheckoutFrom) filters.checkout_from = state.chargeSheetCheckoutFrom;
    if (state.chargeSheetCheckoutTo) filters.checkout_to = state.chargeSheetCheckoutTo;
    if (state.chargeSheetSearch) filters.search = state.chargeSheetSearch;
    if (state.chargeSheetOrdering) filters.ordering = state.chargeSheetOrdering;
    return { share_type: "charge_sheet", title: "Charges Sheet", validity, filters };
}

export async function copyText(value) {
    if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(value);
        return;
    }
    const input = document.createElement("textarea");
    input.value = value;
    input.style.position = "fixed";
    input.style.opacity = "0";
    document.body.appendChild(input);
    input.select();
    document.execCommand("copy");
    input.remove();
}

export async function copyHtml(html, textFallback = "") {
    if (navigator.clipboard?.write && window.ClipboardItem) {
        await navigator.clipboard.write([new ClipboardItem({
            "text/html": new Blob([html], { type: "text/html" }),
            "text/plain": new Blob([textFallback || html], { type: "text/plain" }),
        })]);
        return;
    }
    const container = document.createElement("div");
    container.innerHTML = html;
    container.contentEditable = "true";
    container.style.position = "fixed";
    container.style.left = "-9999px";
    document.body.appendChild(container);
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(container);
    selection.removeAllRanges();
    selection.addRange(range);
    const copied = document.execCommand("copy");
    selection.removeAllRanges();
    container.remove();
    if (!copied) await copyText(textFallback || html);
}
