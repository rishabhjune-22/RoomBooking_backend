function safeFilename(title, extension) {
    const base = String(title || "sheet").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "sheet";
    const timestamp = new Date().toISOString().slice(0, 16).replace("T", "-").replace(":", "");
    return `${base}-${timestamp}.${extension}`;
}

function cloneTable(selector) {
    const table = document.querySelector(selector);
    if (!table) return null;
    const clone = table.cloneNode(true);
    clone.querySelectorAll("input, textarea, select").forEach((control) => control.replaceWith(document.createTextNode(control.value || "")));
    clone.querySelectorAll(".sheet-booking-pill").forEach((button) => {
        const span = document.createElement("span");
        span.className = button.className;
        span.textContent = button.textContent.trim();
        button.replaceWith(span);
    });
    clone.querySelectorAll(".sheet-inline-actions, .sheet-create-btn").forEach((node) => node.remove());
    const actionIndexes = [];
    clone.querySelectorAll("thead th").forEach((header, index) => {
        const text = header.textContent.trim().toLowerCase();
        if (header.classList.contains("sheet-actions-col") || text === "edit" || text === "actions") actionIndexes.push(index);
    });
    actionIndexes.reverse().forEach((index) => clone.querySelectorAll("tr").forEach((row) => row.children[index]?.remove()));
    clone.querySelectorAll("[data-charge-sort], [tabindex], [aria-sort]").forEach((node) => {
        node.removeAttribute("data-charge-sort"); node.removeAttribute("tabindex"); node.removeAttribute("aria-sort");
    });
    clone.querySelectorAll(".selected-row").forEach((node) => node.classList.remove("selected-row"));
    return clone;
}

const normalize = (value) => String(value ?? "").replace(/\u00a0/g, " ").replace(/[ \t\r\f\v]+/g, " ").replace(/ *\n+ */g, "\n").replace(/\n{3,}/g, "\n\n").trim();
const xmlEscape = (value) => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&apos;");
const cellText = (cell) => Array.from(cell.childNodes).map((node) => normalize(node.textContent || "")).filter(Boolean).join("\n") || normalize(cell.textContent || "");
const spreadsheetCell = (value, style = "Cell") => `<Cell ss:StyleID="${style}"><Data ss:Type="String">${xmlEscape(normalize(value))}</Data></Cell>`;
const spreadsheetRow = (cells, style = "Cell") => `<Row>${cells.map((cell) => spreadsheetCell(cell, style)).join("")}</Row>`;

function workbookXml(title, table) {
    const rows = Array.from(table.querySelectorAll("tr")).map((row) => Array.from(row.children).map(cellText)).filter((row) => row.some(Boolean));
    const count = Math.max(...rows.map((row) => row.length), 1);
    const normalizedRows = rows.map((row) => [...row, ...Array(Math.max(0, count - row.length)).fill("")]);
    const header = normalizedRows.shift() || [];
    const widths = Array.from({ length: count }, (_, index) => {
        const longest = [header, ...normalizedRows].reduce((max, row) => Math.max(max, String(row[index] || "").length), 0);
        return `<Column ss:Width="${Math.min(Math.max(longest * 7, 70), 260)}"/>`;
    }).join("");
    return `<?xml version="1.0" encoding="UTF-8"?><?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"><Styles>
<Style ss:ID="Title"><Font ss:Bold="1" ss:Size="14"/><Alignment ss:Vertical="Center"/></Style>
<Style ss:ID="Header"><Font ss:Bold="1"/><Interior ss:Color="#DCEEFF" ss:Pattern="Solid"/><Alignment ss:Vertical="Center" ss:WrapText="1"/></Style>
<Style ss:ID="Cell"><Alignment ss:Vertical="Top" ss:WrapText="1"/></Style></Styles>
<Worksheet ss:Name="${xmlEscape(title.slice(0, 31) || "Sheet")}"><Table>${widths}<Row ss:Height="22"><Cell ss:MergeAcross="${Math.max(count - 1, 0)}" ss:StyleID="Title"><Data ss:Type="String">${xmlEscape(title)}</Data></Cell></Row><Row/>${header.length ? spreadsheetRow(header, "Header") : ""}${normalizedRows.map((row) => spreadsheetRow(row)).join("")}</Table></Worksheet></Workbook>`;
}

export function createSheetExporter({ escapeHtml, toast }) {
    function excel(selector, title) {
        const table = cloneTable(selector);
        if (!table) { toast("No sheet data available to download.", "error"); return; }
        const blob = new Blob([workbookXml(title, table)], { type: "application/vnd.ms-excel;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a"); link.href = url; link.download = safeFilename(title, "xls");
        document.body.appendChild(link); link.click(); link.remove(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
        toast("Excel download started.");
    }
    function pdf(selector, title) {
        const table = cloneTable(selector);
        if (!table) { toast("No sheet data available to download.", "error"); return; }
        const popup = window.open("", "_blank");
        if (!popup) { toast("Allow pop-ups to download PDF.", "error"); return; }
        popup.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>${escapeHtml(title)}</title><style>@page{size:A4 landscape;margin:10mm}*{box-sizing:border-box;-webkit-print-color-adjust:exact;print-color-adjust:exact}body{margin:0;font-family:Arial,sans-serif;color:#172033}h2{margin:0 0 12px;font-size:18px}table{width:100%;border-collapse:collapse;font-size:9px}th,td{border:1px solid #b7c6d8;padding:4px 5px;vertical-align:top;word-break:break-word}th{background:#dceeff;color:#0f4f86;font-weight:700}.sheet-booking-pill{display:block;border-radius:6px;background:#dff5ea;color:#248b5b;padding:4px 6px;font-weight:700}.sheet-booking-pill.partial{background:#fff1d6;color:#a45a00}.sheet-booking-pill.expired,.charge-sheet-table tbody tr.expired-row td{background:#ffe4e0;color:#b42318}</style></head><body><h2>${escapeHtml(title)}</h2>${table.outerHTML}</body></html>`);
        popup.document.close(); popup.focus(); window.setTimeout(() => popup.print(), 250);
    }
    return { excel, pdf };
}
