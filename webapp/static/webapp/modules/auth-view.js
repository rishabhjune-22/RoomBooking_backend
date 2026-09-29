export function passwordsMatch(password = "", confirmation = "") {
    return Boolean(confirmation) && password === confirmation;
}

export function createAuthView({ root, state, apiFetch, escapeHtml, onAuthenticated }) {
    function render(message = "", isError = false) {
        const isSignup = state.authMode === "signup";
        root.innerHTML = `
            <main class="login-shell">
                <section class="login-card">
                    <div class="brand-row">
                        <div class="brand-mark"><img class="brand-logo" src="/static/webapp/mainlogo.jpeg" alt="Room Booking logo"></div>
                        <div><h1 class="brand-title">Room Booking</h1></div>
                    </div>
                    <div class="segmented" role="tablist" aria-label="Role">
                        <button class="segment-btn ${state.authRole === "admin" ? "active" : ""}" data-auth-role="admin" aria-label="Use admin role" aria-pressed="${state.authRole === "admin"}">Admin</button>
                        <button class="segment-btn ${state.authRole === "requester" ? "active" : ""}" data-auth-role="requester" aria-label="Use requester role" aria-pressed="${state.authRole === "requester"}">Requester</button>
                    </div>
                    <div class="segmented" role="tablist" aria-label="Mode">
                        <button class="segment-btn ${!isSignup ? "active" : ""}" data-auth-mode="login" aria-label="Use login mode" aria-pressed="${!isSignup}">Login</button>
                        <button class="segment-btn ${isSignup ? "active" : ""}" data-auth-mode="signup" aria-label="Use signup mode" aria-pressed="${isSignup}">Signup</button>
                    </div>
                    <form id="auth-form" class="field-grid">
                        ${isSignup ? `<div class="field-row"><label for="name">Full name *</label><input id="name" name="name" autocomplete="name" required></div>` : ""}
                        <div class="field-row"><label for="email">Email *</label><input id="email" name="email" type="email" autocomplete="email" required></div>
                        <div class="field-row">
                            <label for="password">Password *</label>
                            <div class="password-wrap"><input id="password" name="password" type="password" autocomplete="${isSignup ? "new-password" : "current-password"}" required><button class="outline-btn" type="button" data-toggle-password="password">Show</button></div>
                        </div>
                        ${isSignup ? `
                            <div class="field-row"><label for="confirm_password">Confirm password *</label><div class="password-wrap"><input id="confirm_password" name="confirm_password" type="password" autocomplete="new-password" required><button class="outline-btn" type="button" data-toggle-password="confirm_password">Show</button></div><div id="password-match-status" class="password-match-status" aria-live="polite"></div></div>
                            ${state.authRole === "admin" ? `<div class="field-row"><label for="admin_code">Admin invite code *</label><input id="admin_code" name="admin_code" autocomplete="off" required></div>` : `
                                <div class="two-col"><div class="field-row"><label for="department">Department (Optional)</label><input id="department" name="department"></div><div class="field-row"><label for="designation">Designation (Optional)</label><input id="designation" name="designation"></div></div>
                                <div class="field-row"><label for="mobile">Mobile (Optional)</label><input id="mobile" name="mobile" inputmode="tel"></div>
                            `}
                        ` : ""}
                        <div class="form-actions"><button class="primary-btn" type="submit">${isSignup ? "Create Account" : "Login"}</button><span class="brand-subtitle">${state.authRole === "admin" ? "Using Admin tab" : "Using Requester tab"}</span></div>
                    </form>
                    ${message ? `<div class="status-message ${isError ? "error" : "success"}">${escapeHtml(message)}</div>` : ""}
                </section>
            </main>`;

        root.querySelectorAll("[data-auth-role]").forEach((button) => button.addEventListener("click", () => {
            state.authRole = button.dataset.authRole;
            render();
        }));
        root.querySelectorAll("[data-auth-mode]").forEach((button) => button.addEventListener("click", () => {
            state.authMode = button.dataset.authMode;
            render();
        }));
        root.querySelectorAll("[data-toggle-password]").forEach((button) => button.addEventListener("click", () => {
            const input = document.getElementById(button.dataset.togglePassword);
            input.type = input.type === "password" ? "text" : "password";
            button.textContent = input.type === "password" ? "Show" : "Hide";
        }));
        if (isSignup) {
            const passwordInput = document.getElementById("password");
            const confirmInput = document.getElementById("confirm_password");
            const updatePasswordMatch = () => {
                const status = document.getElementById("password-match-status");
                if (!confirmInput.value) {
                    status.className = "password-match-status";
                    status.textContent = "";
                    return;
                }
                const matches = passwordsMatch(passwordInput.value, confirmInput.value);
                status.className = `password-match-status ${matches ? "met" : "unmet"}`;
                status.textContent = matches ? "Passwords match." : "Passwords do not match.";
            };
            [passwordInput, confirmInput].forEach((input) => input.addEventListener("input", updatePasswordMatch));
        }
        root.querySelector("#auth-form").addEventListener("submit", submit);
    }

    async function submit(event) {
        event.preventDefault();
        const body = Object.fromEntries(new FormData(event.currentTarget).entries());
        const endpoint = state.authMode === "signup"
            ? `/api/auth/${state.authRole}/signup/`
            : `/api/auth/${state.authRole}/login/`;
        try {
            const data = await apiFetch(endpoint, { method: "POST", body }, false);
            if (state.authMode === "signup") {
                render(state.authRole === "admin"
                    ? "Your admin account was created and is pending approval."
                    : "Your requester account was created. You can log in now.");
                return;
            }
            onAuthenticated(data);
        } catch (error) {
            render(error.message, true);
        }
    }

    return { render };
}
