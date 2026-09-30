(function () {
    "use strict";

    const DATE_TYPES = new Set(["date"]);
    const TIME_TYPES = new Set(["time"]);
    const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
    const WEEKDAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];
    let activePicker = null;

    function pad(value) {
        return String(value).padStart(2, "0");
    }

    function todayValue() {
        const now = new Date();
        return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
    }

    function parseDate(value) {
        const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value || "");
        if (!match) return null;
        const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
        return Number.isNaN(date.getTime()) ? null : date;
    }

    function formatDate(value) {
        const date = parseDate(value);
        return date
            ? new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric" }).format(date)
            : "Select date";
    }

    function formatTime(value) {
        const match = /^(\d{2}):(\d{2})/.exec(value || "");
        if (!match) return "Select time";
        const hour = Number(match[1]);
        return `${hour % 12 || 12}:${match[2]} ${hour >= 12 ? "PM" : "AM"}`;
    }

    function pickerIcon(type) {
        if (type === "date") {
            return `<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"></rect><path d="M16 3v4M8 3v4M3 10h18"></path></svg>`;
        }
        return `<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 2"></path></svg>`;
    }

    function closePicker() {
        activePicker?.remove();
        activePicker = null;
        document.querySelectorAll(".app-picker-trigger[aria-expanded='true']").forEach((button) => button.setAttribute("aria-expanded", "false"));
    }

    function positionPicker(panel, trigger) {
        const rect = trigger.getBoundingClientRect();
        const width = Math.min(panel.offsetWidth, window.innerWidth - 16);
        let left = Math.min(rect.left, window.innerWidth - width - 8);
        left = Math.max(8, left);
        const roomBelow = window.innerHeight - rect.bottom;
        const top = roomBelow >= Math.min(panel.offsetHeight + 10, 390)
            ? rect.bottom + 8
            : Math.max(8, rect.top - panel.offsetHeight - 8);
        panel.style.left = `${left}px`;
        panel.style.top = `${top}px`;
    }

    function commitValue(input, value) {
        input.value = value;
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.dispatchEvent(new Event("change", { bubbles: true }));
        input.closest(".app-picker-field")?.querySelector(".app-picker-value")?.replaceChildren(
            document.createTextNode(input.dataset.pickerType === "date" ? formatDate(value) : formatTime(value))
        );
        closePicker();
    }

    function isAllowedDate(input, value) {
        return (!input.min || value >= input.min) && (!input.max || value <= input.max);
    }

    function renderCalendar(panel, input, trigger, shownDate) {
        const year = shownDate.getFullYear();
        const month = shownDate.getMonth();
        const firstWeekday = new Date(year, month, 1).getDay();
        const daysInMonth = new Date(year, month + 1, 0).getDate();
        const selected = input.value;
        const today = todayValue();
        const days = [];
        for (let i = 0; i < firstWeekday; i += 1) days.push(`<span class="app-picker-day empty"></span>`);
        for (let day = 1; day <= daysInMonth; day += 1) {
            const value = `${year}-${pad(month + 1)}-${pad(day)}`;
            const classes = ["app-picker-day"];
            if (value === selected) classes.push("selected");
            if (value === today) classes.push("today");
            days.push(`<button type="button" class="${classes.join(" ")}" data-picker-date="${value}" ${isAllowedDate(input, value) ? "" : "disabled"}>${day}</button>`);
        }
        panel.innerHTML = `
            <div class="app-picker-head">
                <button type="button" class="app-picker-nav" data-picker-prev aria-label="Previous month">&#8249;</button>
                <strong>${MONTH_NAMES[month]} ${year}</strong>
                <button type="button" class="app-picker-nav" data-picker-next aria-label="Next month">&#8250;</button>
            </div>
            <div class="app-picker-weekdays">${WEEKDAYS.map((day) => `<span>${day}</span>`).join("")}</div>
            <div class="app-picker-days">${days.join("")}</div>
            <div class="app-picker-actions">
                ${input.required ? "" : `<button type="button" class="ghost-btn compact-btn" data-picker-clear>Clear</button>`}
                <button type="button" class="outline-btn compact-btn" data-picker-today ${isAllowedDate(input, today) ? "" : "disabled"}>Today</button>
            </div>`;
        panel.querySelector("[data-picker-prev]").addEventListener("click", () => renderCalendar(panel, input, trigger, new Date(year, month - 1, 1)));
        panel.querySelector("[data-picker-next]").addEventListener("click", () => renderCalendar(panel, input, trigger, new Date(year, month + 1, 1)));
        panel.querySelectorAll("[data-picker-date]").forEach((button) => button.addEventListener("click", () => commitValue(input, button.dataset.pickerDate)));
        panel.querySelector("[data-picker-today]")?.addEventListener("click", () => commitValue(input, today));
        panel.querySelector("[data-picker-clear]")?.addEventListener("click", () => commitValue(input, ""));
        requestAnimationFrame(() => positionPicker(panel, trigger));
    }

    function timeParts(value) {
        const match = /^(\d{2}):(\d{2})/.exec(value || "");
        const now = new Date();
        const hour24 = match ? Number(match[1]) : now.getHours();
        const minute = match ? Number(match[2]) : Math.round(now.getMinutes() / 5) * 5 % 60;
        return { hour: hour24 % 12 || 12, minute, period: hour24 >= 12 ? "PM" : "AM" };
    }

    function roundedCurrentTime() {
        const now = new Date();
        now.setMinutes(Math.round(now.getMinutes() / 5) * 5, 0, 0);
        return `${pad(now.getHours())}:${pad(now.getMinutes())}`;
    }

    function renderTimePicker(panel, input, trigger) {
        const parts = timeParts(input.value);
        const minutes = Array.from({ length: 12 }, (_, index) => index * 5);
        if (!minutes.includes(parts.minute)) minutes.push(parts.minute);
        minutes.sort((a, b) => a - b);
        panel.innerHTML = `
            <div class="app-picker-time-title">Choose time</div>
            <div class="app-picker-time-controls">
                <label><span>Hour</span><select data-time-hour>${Array.from({ length: 12 }, (_, index) => index + 1).map((hour) => `<option ${hour === parts.hour ? "selected" : ""}>${hour}</option>`).join("")}</select></label>
                <span class="app-picker-time-colon">:</span>
                <label><span>Minute</span><select data-time-minute>${minutes.map((minute) => `<option value="${minute}" ${minute === parts.minute ? "selected" : ""}>${pad(minute)}</option>`).join("")}</select></label>
                <label><span>Period</span><select data-time-period><option ${parts.period === "AM" ? "selected" : ""}>AM</option><option ${parts.period === "PM" ? "selected" : ""}>PM</option></select></label>
            </div>
            <div class="app-picker-actions">
                ${input.required ? "" : `<button type="button" class="ghost-btn compact-btn" data-picker-clear>Clear</button>`}
                <button type="button" class="outline-btn compact-btn" data-picker-now>Now</button>
                <button type="button" class="primary-btn compact-btn" data-picker-apply>Apply</button>
            </div>`;
        panel.querySelector("[data-picker-apply]").addEventListener("click", () => {
            let hour = Number(panel.querySelector("[data-time-hour]").value) % 12;
            if (panel.querySelector("[data-time-period]").value === "PM") hour += 12;
            commitValue(input, `${pad(hour)}:${pad(panel.querySelector("[data-time-minute]").value)}`);
        });
        panel.querySelector("[data-picker-now]").addEventListener("click", () => {
            commitValue(input, roundedCurrentTime());
        });
        panel.querySelector("[data-picker-clear]")?.addEventListener("click", () => commitValue(input, ""));
        requestAnimationFrame(() => positionPicker(panel, trigger));
    }

    function openPicker(input, trigger) {
        const wasOpen = trigger.getAttribute("aria-expanded") === "true";
        closePicker();
        if (wasOpen) return;
        const panel = document.createElement("div");
        panel.className = `app-picker-popover ${input.dataset.pickerType === "time" ? "time-picker" : "date-picker"}`;
        panel.setAttribute("role", "dialog");
        panel.setAttribute("aria-label", input.dataset.pickerType === "date" ? "Choose date" : "Choose time");
        document.body.appendChild(panel);
        activePicker = panel;
        trigger.setAttribute("aria-expanded", "true");
        if (input.dataset.pickerType === "date") {
            renderCalendar(panel, input, trigger, parseDate(input.value) || parseDate(todayValue()));
        } else {
            renderTimePicker(panel, input, trigger);
        }
    }

    function enhanceInput(input) {
        if (input.dataset.appPickerEnhanced || input.disabled || input.readOnly) return;
        const type = input.type;
        if (!DATE_TYPES.has(type) && !TIME_TYPES.has(type)) return;
        input.dataset.appPickerEnhanced = "true";
        input.dataset.pickerType = type;
        const wrapper = document.createElement("div");
        wrapper.className = "app-picker-field";
        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(input);
        input.classList.add("app-picker-native-value");
        input.tabIndex = -1;
        input.setAttribute("aria-hidden", "true");
        const trigger = document.createElement("button");
        trigger.type = "button";
        trigger.className = "app-picker-trigger";
        trigger.setAttribute("aria-expanded", "false");
        const fieldLabel = input.id ? document.querySelector(`label[for="${CSS.escape(input.id)}"]`)?.textContent.trim() : "";
        trigger.setAttribute("aria-label", fieldLabel || (type === "date" ? "Choose date" : "Choose time"));
        trigger.innerHTML = `<span class="app-picker-value">${type === "date" ? formatDate(input.value) : formatTime(input.value)}</span><span class="app-picker-icon">${pickerIcon(type)}</span>`;
        wrapper.appendChild(trigger);
        trigger.addEventListener("click", () => openPicker(input, trigger));
        input.addEventListener("change", () => {
            trigger.querySelector(".app-picker-value").textContent = type === "date" ? formatDate(input.value) : formatTime(input.value);
        });
    }

    function enhanceAll(root) {
        if (root.nodeType !== Node.ELEMENT_NODE && root !== document) return;
        if (root.matches?.('input[type="date"], input[type="time"]')) enhanceInput(root);
        root.querySelectorAll?.('input[type="date"], input[type="time"]').forEach(enhanceInput);
    }

    document.addEventListener("pointerdown", (event) => {
        if (activePicker && !activePicker.contains(event.target) && !event.target.closest(".app-picker-trigger")) closePicker();
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closePicker();
    });
    window.addEventListener("resize", closePicker);
    document.addEventListener("scroll", closePicker, true);

    const observer = new MutationObserver((records) => records.forEach((record) => record.addedNodes.forEach(enhanceAll)));
    observer.observe(document.documentElement, { childList: true, subtree: true });
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => enhanceAll(document));
    else enhanceAll(document);
}());
