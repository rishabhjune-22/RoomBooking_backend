export function createBookingSheetController(dependencies) {
    const {
        document, dateRange, isoDateRange, fetchRooms, fetchAllPaginated, endpoint,
        filterRooms, buildCells, renderTable, renderCell, escapeHtml, formatSheetDate,
        roomLabel, exportButtonsHtml, legendHtml, onShare, onExport, onAction, onOpenDetails,
    } = dependencies;

    async function load() {
        const shell = document.getElementById("bookings-sheet");
        if (!shell) return;
        shell.innerHTML = `<div class="loading-state">Loading sheet view...</div>`;
        try {
            const range = dateRange();
            const dates = isoDateRange(range.start, range.end);
            if (!dates.length) {
                shell.innerHTML = `<div class="empty-state">Select a valid date range.</div>`;
                return;
            }
            const [rooms, bookings] = await Promise.all([fetchRooms(), fetchAllPaginated(endpoint())]);
            const sheetRooms = filterRooms(rooms);
            if (!sheetRooms.length) {
                shell.innerHTML = `<div class="empty-state">No rooms found for the selected building.</div>`;
                return;
            }
            const cells = buildCells(bookings, dates);
            const visibleBookingCount = new Set(Array.from(cells.values()).flatMap((entries) => entries.map((entry) => entry.id))).size;
            shell.innerHTML = renderTable({ range, dates, rooms: sheetRooms, cells, visibleBookingCount }, {
                escapeHtml, formatSheetDate, roomLabel, cellHtml: renderCell, exportButtonsHtml, legendHtml,
            });
            shell.onclick = (event) => {
                const share = event.target.closest("[data-sheet-share]");
                if (share) return onShare(share.dataset.sheetShare);
                const exportButton = event.target.closest("[data-sheet-export]");
                if (exportButton) return onExport(exportButton.dataset.sheetExport);
                const action = event.target.closest("[data-booking-action]");
                if (action) return onAction(action.dataset.bookingAction, action.dataset.id, action.dataset);
                const booking = event.target.closest("[data-sheet-booking-id]");
                if (booking) onOpenDetails(booking.dataset.sheetBookingId);
            };
        } catch (error) {
            shell.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
        }
    }
    return { load };
}
