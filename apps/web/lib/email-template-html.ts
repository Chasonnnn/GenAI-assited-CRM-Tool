/**
 * Normalize template HTML so empty paragraphs render as visible blank lines
 * in previews and when sent through email clients.
 *
 * - TipTap can produce `<p></p>` or `<p><br></p>` for blank lines.
 * - Many renderers/sanitizers collapse those to zero-height.
 * - Converting to `&nbsp;` preserves spacing without changing layout.
 */
export function normalizeTemplateHtml(html: string): string {
    if (!html) return ""

    return html.replace(
        /(<p\b[^>]*>)\s*(?:<br\b[^>]*>)?\s*<\/p>/gi,
        "$1&nbsp;</p>",
    )
}

function escapeTemplateText(text: string): string {
    return text
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
}

/**
 * Adapt legacy plain-text template bodies for TipTap without mutating the
 * stored value merely because a user opened Studio.
 *
 * TipTap treats a plain string as HTML input, so literal newlines otherwise
 * collapse into one paragraph. The adapter is used only at the visual-editor
 * boundary; after a real edit, TipTap emits canonical HTML for the save path.
 */
export function prepareTemplateHtmlForVisualEditor(body: string): string {
    if (!body || /<[a-z][\s\S]*>/i.test(body)) return body

    return body
        .replace(/\r\n?/g, "\n")
        .split("\n")
        .map((line) =>
            line.trim()
                ? `<p>${escapeTemplateText(line)}</p>`
                : "<p>&nbsp;</p>",
        )
        .join("")
}
