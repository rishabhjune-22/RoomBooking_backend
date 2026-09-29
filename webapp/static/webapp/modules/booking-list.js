export function createBookingList({ state, apiFetch, endpoint, unwrapList, nextPageUrl, renderCard, clearSelection, escapeHtml }) {
    function updateScrollState(message = "") {
        const sentinel = document.getElementById("bookings-sentinel");
        if (!sentinel) return;
        if (message) { sentinel.innerHTML = message; return; }
        if (!state.bookingLoadedCount) { sentinel.innerHTML = ""; return; }
        if (state.bookingLoading && state.bookingNextUrl) sentinel.innerHTML = `<div class="loading-state compact">Loading more bookings...</div>`;
        else if (state.bookingNextUrl) sentinel.innerHTML = `<div class="scroll-hint">Scroll to load more bookings.</div>`;
        else sentinel.innerHTML = `<div class="scroll-hint">All loaded.</div>`;
    }

    function setupInfiniteScroll() {
        state.bookingInfiniteObserver?.disconnect();
        state.bookingInfiniteObserver = null;
        const sentinel = document.getElementById("bookings-sentinel");
        if (!sentinel) return;
        if (!("IntersectionObserver" in window)) {
            sentinel.innerHTML = `<button class="outline-btn" type="button" id="load-more-bookings">Load More</button>`;
            document.getElementById("load-more-bookings")?.addEventListener("click", () => load({ reset: false }));
            return;
        }
        state.bookingInfiniteObserver = new IntersectionObserver((entries) => {
            if (entries.some((entry) => entry.isIntersecting) && state.bookingNextUrl && !state.bookingLoading) load({ reset: false });
        }, { rootMargin: "260px 0px" });
        state.bookingInfiniteObserver.observe(sentinel);
    }

    async function load({ reset = true, silent = false } = {}) {
        const list = document.getElementById("bookings-list");
        let sentinelMessage = "";
        if (!list || state.bookingLoading) return;
        if (!reset && !state.bookingNextUrl) { updateScrollState(); return; }
        state.bookingLoading = true;
        if (reset) {
            if (!silent) clearSelection();
            state.bookingNextUrl = "";
            state.bookingLoadedCount = 0;
            if (!silent) {
                list.innerHTML = `<div class="loading-state">Loading bookings...</div>`;
                updateScrollState("");
            }
        } else {
            updateScrollState(`<div class="loading-state compact">Loading more bookings...</div>`);
        }
        try {
            const data = await apiFetch(reset ? endpoint() : state.bookingNextUrl);
            const rows = unwrapList(data);
            state.bookingNextUrl = nextPageUrl(data);
            if (!rows.length && reset) {
                list.innerHTML = `<div class="empty-state">No bookings match the selected filters.</div>`;
                updateScrollState("");
                return;
            }
            if (reset) list.innerHTML = "";
            list.insertAdjacentHTML("beforeend", rows.map(renderCard).join(""));
            state.bookingLoadedCount += rows.length;
            updateScrollState();
        } catch (error) {
            if (silent) return;
            if (reset) list.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
            else sentinelMessage = `<div class="empty-state compact">${escapeHtml(error.message)}</div>`;
        } finally {
            state.bookingLoading = false;
            updateScrollState(sentinelMessage);
        }
    }

    return { load, setupInfiniteScroll, updateScrollState };
}
