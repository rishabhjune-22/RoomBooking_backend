import { messageFromErrors } from "./api-errors.js";

export function createApiClient({
    getAccessToken,
    getRefreshToken,
    onAccessToken,
    onSessionExpired,
    fetchImpl = window.fetch.bind(window),
}) {
    async function refreshAccessToken() {
        try {
            const response = await fetchImpl("/api/auth/token/refresh/", {
                method: "POST",
                headers: { "Content-Type": "application/json", Accept: "application/json" },
                body: JSON.stringify({ refresh: getRefreshToken() }),
            });
            if (!response.ok) return false;
            const payload = await response.json();
            const access = payload.access || payload.data?.access || "";
            if (!access) return false;
            onAccessToken(access);
            return true;
        } catch (error) {
            return false;
        }
    }

    async function apiFetch(path, options = {}, retry = true) {
        const headers = new Headers(options.headers || {});
        headers.set("Accept", "application/json");
        const access = getAccessToken();
        if (access) headers.set("Authorization", `Bearer ${access}`);

        let body = options.body;
        if (body && typeof body !== "string") {
            headers.set("Content-Type", "application/json");
            body = JSON.stringify(body);
        }

        const response = await fetchImpl(path, { ...options, headers, body });
        let payload = null;
        try {
            payload = await response.json();
        } catch (error) {
            payload = null;
        }

        if (response.status === 401 && retry && getRefreshToken()) {
            if (await refreshAccessToken()) return apiFetch(path, options, false);
            onSessionExpired();
            throw new Error("Session expired.");
        }
        if (!response.ok || payload?.success === false) {
            throw new Error(messageFromErrors(payload));
        }
        return payload?.data;
    }

    return apiFetch;
}
