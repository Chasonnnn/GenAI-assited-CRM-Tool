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
