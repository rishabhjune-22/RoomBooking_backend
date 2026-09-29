export function readRoute(hash = window.location.hash) {
    const raw = String(hash || "").replace(/^#/, "");
    if (!raw) return {};
    if (!raw.includes("=")) return { view: decodeURIComponent(raw) };
    const params = new URLSearchParams(raw);
    return { view: params.get("view") || "", bookingView: params.get("bookingView") || "" };
}

export function applyRoute(state, { allowedViews, bookingViewModes, defaultView = "calendar", hash }) {
    const route = readRoute(hash);
    state.view = allowedViews.includes(route.view) ? route.view : defaultView;
    if (state.view === "bookings" && bookingViewModes.has(route.bookingView)) {
        state.bookingViewMode = route.bookingView;
    }
}

export function routeHash(state) {
    const params = new URLSearchParams({ view: state.view });
    if (state.view === "bookings") params.set("bookingView", state.bookingViewMode);
    return `#${params.toString()}`;
}

export function syncRoute(state, replace = false, browserWindow = window) {
    const nextHash = routeHash(state);
    if (browserWindow.location.hash === nextHash) return;
    const nextUrl = `${browserWindow.location.pathname}${browserWindow.location.search}${nextHash}`;
    browserWindow.history[replace ? "replaceState" : "pushState"](null, "", nextUrl);
}
