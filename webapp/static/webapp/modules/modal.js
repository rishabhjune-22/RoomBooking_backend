export function createModalController({ escapeHtml, toast }) {
    function close() {
        document.querySelector(".modal-backdrop")?.remove();
    }

    function open({ title, body, confirmText, confirmClass, onConfirm, onBind, wide = false, footerHtml = "" }) {
        close();
        const backdrop = document.createElement("div");
        backdrop.className = "modal-backdrop";
        backdrop.innerHTML = `
            <section class="modal-card ${wide ? "wide" : ""}" role="dialog" aria-modal="true" aria-label="${escapeHtml(title)}">
                <header class="modal-header"><h3>${escapeHtml(title)}</h3><button class="ghost-btn" type="button" data-close-modal>Close</button></header>
                <div class="modal-body">${body}</div>
                <footer class="modal-footer">${footerHtml || `<button class="outline-btn" type="button" data-close-modal>Cancel</button><button class="${confirmClass}" type="button" id="modal-confirm">${escapeHtml(confirmText)}</button>`}</footer>
            </section>`;
        document.body.appendChild(backdrop);
        backdrop.querySelectorAll("[data-close-modal]").forEach((button) => button.addEventListener("click", close));
        backdrop.addEventListener("click", (event) => { if (event.target === backdrop) close(); });
        const confirmButton = document.getElementById("modal-confirm");
        if (confirmButton && onConfirm) {
            confirmButton.addEventListener("click", async () => {
                confirmButton.disabled = true;
                try {
                    await onConfirm();
                    close();
                } catch (error) {
                    toast(error.message, "error");
                    confirmButton.disabled = false;
                }
            });
        }
        onBind?.();
    }

    return { open, close };
}

export function bookingMailTemplateContent(template, { escapeHtml, htmlValue }) {
    const subject = template.subject || "";
    const textBody = template.body || "";
    const htmlBody = template.html || `<div>${escapeHtml(textBody).replace(/\n/g, "<br>")}</div>`;
    return { subject, textBody, htmlBody,
        body: `<div class="details-list"><p class="item-meta">Copy this subject and email content into your mail client.</p>
            <div class="field-row"><label for="booking-mail-subject">Subject</label><input id="booking-mail-subject" value="${htmlValue(subject)}" readonly></div>
            <div class="field-row"><label>Email Content</label><div class="mail-template-preview" id="booking-mail-preview">${htmlBody}</div></div></div>`,
        footerHtml: `<button class="outline-btn" type="button" data-close-modal>Close</button><button class="outline-btn" type="button" id="copy-mail-subject">Copy Subject</button><button class="primary-btn" type="button" id="copy-mail-body">Copy Email Content</button>`,
    };
}

export function shareLinkContent(data, sheetName, { escapeHtml, htmlValue, formatDateTime }) {
    const expiresText = data.expires_at ? `Valid until ${escapeHtml(formatDateTime(data.expires_at))}` : "";
    return `<div class="details-list"><p class="item-meta">Anyone with this link can view this read-only ${sheetName === "charge" ? "charges" : "booking"} sheet until it expires.</p>
        ${expiresText ? `<div class="status-message success">${expiresText}</div>` : ""}<div class="share-link-row"><div class="field-row">
        <label for="share-link-url">Share URL</label><input id="share-link-url" value="${htmlValue(data.url)}" readonly></div>
        <button class="outline-btn" type="button" id="open-share-link">Open</button></div></div>`;
}

export function shareOptionsContent() {
    return `<div class="details-list"><p class="item-meta">Choose how long this read-only shared URL should remain valid.</p>
        <div class="field-row"><label for="share-validity">Valid for</label><select id="share-validity">
        <option value="24h">24 hours</option><option value="1w" selected>1 week</option><option value="1m">1 month</option></select></div></div>`;
}
