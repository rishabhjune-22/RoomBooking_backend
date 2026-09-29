function styleRequiredMarks(root = document) {
    if (!root || typeof root.querySelectorAll !== "function") return;
    const labels = root.matches?.("label") ? [root, ...root.querySelectorAll("label")] : [...root.querySelectorAll("label")];
    labels.forEach((label) => Array.from(label.childNodes).forEach((node) => styleRequiredMarkNode(node)));
}
function styleRequiredMarkNode(node) {
    if (node.nodeType === Node.TEXT_NODE) {
        const text = node.nodeValue || "";
        if (!text.includes("*")) return;
        const fragment = document.createDocumentFragment();
        text.split(/(\*)/).forEach((part) => {
            if (!part) return;
            if (part === "*") {
                const mark = document.createElement("span");
                mark.className = "required-mark";
                mark.textContent = "*";
                fragment.appendChild(mark);
            } else {
                fragment.appendChild(document.createTextNode(part));
            }
        });
        node.replaceWith(fragment);
        return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE || node.classList?.contains("required-mark")) return;
    Array.from(node.childNodes).forEach((child) => styleRequiredMarkNode(child));
}
export function observeRequiredMarks() {
    styleRequiredMarks(document);
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => mutation.addedNodes.forEach((node) => {
            if (node.nodeType === Node.ELEMENT_NODE) styleRequiredMarks(node);
        }));
    });
    observer.observe(document.body, { childList: true, subtree: true });
}
