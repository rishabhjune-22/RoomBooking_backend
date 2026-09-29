export function createBookingSelection(selectedIds) {
    const normalize = (value) => String(value ?? "");

    function values() {
        return Array.from(selectedIds).filter(Boolean);
    }

    function updateUi(root = document) {
        root.querySelectorAll("[data-booking-select-id]").forEach((checkbox) => {
            const selected = selectedIds.has(checkbox.dataset.bookingSelectId);
            checkbox.checked = selected;
            checkbox.closest(".item-card")?.classList.toggle("selected", selected);
        });
        const count = selectedIds.size;
        const deleteButton = root.getElementById?.("delete-selected-bookings") || root.querySelector?.("#delete-selected-bookings");
        if (deleteButton) {
            deleteButton.disabled = count === 0;
            deleteButton.textContent = count ? `Delete Selected (${count})` : "Delete Selected";
        }
        const mailButton = root.getElementById?.("generate-selected-mail-template") || root.querySelector?.("#generate-selected-mail-template");
        if (mailButton) {
            mailButton.disabled = count === 0;
            mailButton.textContent = count ? `Generate Email Template (${count})` : "Generate Email Template";
        }
    }

    function clear(root = document) {
        selectedIds.clear();
        updateUi(root);
    }

    function set(bookingId, selected, root = document) {
        const id = normalize(bookingId);
        if (!id) return;
        if (selected) selectedIds.add(id);
        else selectedIds.delete(id);
        updateUi(root);
    }

    function bind({ onGenerateMail, onDelete }, root = document) {
        root.getElementById?.("generate-selected-mail-template")?.addEventListener("click", onGenerateMail);
        root.getElementById?.("delete-selected-bookings")?.addEventListener("click", onDelete);
        updateUi(root);
    }

    return { values, updateUi, clear, set, bind };
}
