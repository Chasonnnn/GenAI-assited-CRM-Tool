import DOMPurify from "dompurify"

import { normalizeTemplateHtml } from "@/lib/email-template-html"

const PREVIEW_FONT_STACK =
    '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif'

const PREVIEW_VARIABLES: Record<string, string> = {
    first_name: "John",
    full_name: "John Smith",
    email: "john@example.com",
    phone: "(555) 123-4567",
    surrogate_number: "S10001",
    intended_parent_number: "I10001",
    status_label: "Pre-Qualified",
    owner_name: "Sara Manager",
    form_link: "https://app.surrogacyforce.com/intake/EXAMPLE_SLUG",
    appointment_link:
        "https://app.surrogacyforce.com/book/EXAMPLE_APPOINTMENT_SLUG",
    appointment_manage_url:
        "https://app.surrogacyforce.com/book/self-service/EXAMPLE_ORG/manage/EXAMPLE_TOKEN",
    appointment_reschedule_url:
        "https://app.surrogacyforce.com/book/self-service/EXAMPLE_ORG/reschedule/EXAMPLE_TOKEN",
    appointment_cancel_url:
        "https://app.surrogacyforce.com/book/self-service/EXAMPLE_ORG/cancel/EXAMPLE_TOKEN",
    appointment_date: "January 15, 2025",
    appointment_time: "2:00 PM PST",
    appointment_location: "Virtual Appointment",
}

export type EmailTemplateBodyMode = "visual" | "html"

export type EmailTemplateVisualEditorSupport = {
    supported: boolean
    reason: string | null
}

export type EmailTemplatePreviewOptions = {
    scope: "org" | "personal"
    orgCompanyName: string | null | undefined
    personalSignatureHtml: string | null | undefined
    orgSignatureHtml: string | null | undefined
}

export function hasAdvancedEmailTemplateHtml(
    body: string | null | undefined,
): boolean {
    return /<table|<tbody|<thead|<tr|<td|<img|<div/i.test(body || "")
}

const VISUAL_EDITOR_FRAGMENT_TAGS = new Set([
    "a",
    "b",
    "blockquote",
    "br",
    "center",
    "code",
    "col",
    "colgroup",
    "div",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "i",
    "img",
    "li",
    "ol",
    "p",
    "pre",
    "s",
    "small",
    "span",
    "strong",
    "sub",
    "sup",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "u",
    "ul",
])

const visualAttributes = (value: string) => new Set(value.split(" ").filter(Boolean))
const VISUAL_EDITOR_FRAGMENT_ATTRIBUTES: Record<string, ReadonlySet<string>> = {
    a: visualAttributes("href target style class title"),
    blockquote: visualAttributes("style class"),
    center: visualAttributes("style class"),
    code: visualAttributes("style class"),
    col: visualAttributes("style span width"),
    colgroup: visualAttributes("style span width"),
    div: visualAttributes("style class align"),
    h1: visualAttributes("style class align"),
    h2: visualAttributes("style class align"),
    h3: visualAttributes("style class align"),
    h4: visualAttributes("style class align"),
    h5: visualAttributes("style class align"),
    h6: visualAttributes("style class align"),
    hr: visualAttributes("style class"),
    img: visualAttributes("src alt title width height style"),
    li: visualAttributes("style class"),
    ol: visualAttributes("style class"),
    p: visualAttributes("style class align"),
    pre: visualAttributes("style class"),
    small: visualAttributes("style class"),
    span: visualAttributes("style class"),
    sub: visualAttributes("style class"),
    sup: visualAttributes("style class"),
    table: visualAttributes(
        "width cellpadding cellspacing border align role style bgcolor",
    ),
    tbody: visualAttributes("style align valign"),
    td: visualAttributes(
        "style align valign width height colspan rowspan bgcolor",
    ),
    tfoot: visualAttributes("style align valign"),
    th: visualAttributes(
        "style align valign width height colspan rowspan bgcolor scope",
    ),
    thead: visualAttributes("style align valign"),
    tr: visualAttributes("style align valign bgcolor"),
    ul: visualAttributes("style class"),
}

const VISUAL_EDITOR_STYLE_PROPERTIES = new Set([
    "background-color",
    "border",
    "border-bottom",
    "border-collapse",
    "border-color",
    "border-left",
    "border-radius",
    "border-right",
    "border-spacing",
    "border-style",
    "border-top",
    "border-width",
    "box-sizing",
    "color",
    "display",
    "font-family",
    "font-size",
    "font-style",
    "font-weight",
    "height",
    "letter-spacing",
    "line-height",
    "list-style",
    "list-style-position",
    "list-style-type",
    "margin",
    "margin-bottom",
    "margin-left",
    "margin-right",
    "margin-top",
    "max-height",
    "max-width",
    "min-height",
    "min-width",
    "mso-line-height-rule",
    "padding",
    "padding-bottom",
    "padding-left",
    "padding-right",
    "padding-top",
    "table-layout",
    "text-align",
    "text-decoration",
    "text-transform",
    "vertical-align",
    "white-space",
    "width",
    "word-break",
])

const UNSUPPORTED_VISUAL_HTML_MESSAGE =
    "Visual editing is unavailable because this template contains unsupported document-level or custom HTML."

function hasUnsupportedVisualAttributes(tagName: string, rawAttributes: string) {
    const allowedAttributes =
        VISUAL_EDITOR_FRAGMENT_ATTRIBUTES[tagName] ?? new Set<string>()
    const attributePattern = /([^\s=/>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g

    for (const match of rawAttributes.matchAll(attributePattern)) {
        const attributeName = match[1]?.toLowerCase()
        if (!attributeName || !allowedAttributes.has(attributeName)) return true

        if (attributeName === "style") {
            const styleValue = match[2] ?? match[3] ?? match[4] ?? ""
            if (/expression\s*\(|url\s*\(\s*['"]?\s*javascript:/i.test(styleValue)) {
                return true
            }
            for (const declaration of styleValue.split(";")) {
                const property = declaration.split(":", 1)[0]?.trim().toLowerCase()
                if (property && !VISUAL_EDITOR_STYLE_PROPERTIES.has(property)) {
                    return true
                }
            }
        }
    }
    return false
}

export function getEmailTemplateVisualEditorSupport(
    body: string | null | undefined,
): EmailTemplateVisualEditorSupport {
    const html = body || ""
    if (
        /<!doctype\b|<!--[\s]*\[if\b|<\/?(?:html|head|body|style|script)\b/i.test(
            html,
        )
    ) {
        return {
            supported: false,
            reason: UNSUPPORTED_VISUAL_HTML_MESSAGE,
        }
    }

    for (const match of html.matchAll(/<\s*\/?\s*([a-zA-Z][\w:-]*)\b/g)) {
        const tagName = match[1]?.toLowerCase()
        if (tagName && !VISUAL_EDITOR_FRAGMENT_TAGS.has(tagName)) {
            return {
                supported: false,
                reason: UNSUPPORTED_VISUAL_HTML_MESSAGE,
            }
        }
    }

    for (const match of html.matchAll(/<\s*([a-zA-Z][\w:-]*)\b([^>]*)>/g)) {
        const tagName = match[1]?.toLowerCase()
        if (
            tagName &&
            hasUnsupportedVisualAttributes(tagName, match[2] ?? "")
        ) {
            return {
                supported: false,
                reason: UNSUPPORTED_VISUAL_HTML_MESSAGE,
            }
        }
    }

    return { supported: true, reason: null }
}

export function getEmailTemplateBodyMode(
    body: string | null | undefined,
): EmailTemplateBodyMode {
    return getEmailTemplateVisualEditorSupport(body).supported
        ? "visual"
        : "html"
}

export function extractEmailTemplateVariables(text: string): string[] {
    if (!text) return []
    const matches = text.match(/{{\s*([a-zA-Z0-9_]+)\s*}}/g) ?? []
    const variables = matches.map((match) =>
        match.replace(/{{\s*|\s*}}/g, ""),
    )
    return Array.from(new Set(variables))
}

export function sanitizeEmailTemplatePreviewHtml(html: string): string {
    return DOMPurify.sanitize(html, {
        USE_PROFILES: { html: true },
        ADD_TAGS: [
            "table",
            "thead",
            "tbody",
            "tfoot",
            "tr",
            "td",
            "th",
            "colgroup",
            "col",
            "img",
            "hr",
            "div",
            "span",
            "center",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
        ],
        ADD_ATTR: [
            "style",
            "class",
            "align",
            "valign",
            "width",
            "height",
            "cellpadding",
            "cellspacing",
            "border",
            "bgcolor",
            "colspan",
            "rowspan",
            "role",
            "target",
            "rel",
            "href",
            "src",
            "alt",
            "title",
        ],
    })
}

function removeLegacyUnsubscribeMarkup(html: string): string {
    return html
        .replace(
            /<a\b[^>]*\bhref\s*=\s*(["'])\s*\{\{\s*unsubscribe_url\s*\}\}\s*\1[^>]*>[\s\S]*?<\/a>/gi,
            "",
        )
        .replace(/\{\{\s*unsubscribe_url\s*\}\}/gi, "")
}

function substitutePreviewVariables(
    html: string,
    orgCompanyName: string | null | undefined,
): string {
    return html.replace(
        /\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g,
        (token, variableName: string) => {
            if (variableName === "org_name") {
                return orgCompanyName || "Your organization"
            }
            return PREVIEW_VARIABLES[variableName] ?? token
        },
    )
}

function normalizePreviewBody(html: string): string {
    if (!/<[a-z][\s\S]*>/i.test(html)) {
        return html
            .split(/\n/)
            .map((line) =>
                line.trim()
                    ? `<p style="margin: 0 0 1em 0;">${line}</p>`
                    : '<p style="margin: 0 0 1em 0;">&nbsp;</p>',
            )
            .join("")
    }
    return normalizeTemplateHtml(html)
}

function appendManagedFooter(
    html: string,
    signatureHtml: string,
): string {
    const includeDivider = !signatureHtml
    const unsubscribeFooterHtml = `
        <div style="margin-top: 14px; font-size: 12px; color: #6b7280; ${includeDivider ? "padding-top: 16px; border-top: 1px solid #e5e7eb;" : ""}">
            <p style="margin: 0;">
                Manage email preferences:
                <a href="https://app.surrogacyforce.com/email/unsubscribe/EXAMPLE" target="_blank" rel="noreferrer" style="color: #2563eb; text-decoration: none;">Unsubscribe</a>
            </p>
        </div>
    `.trim()
    const insertion = `${signatureHtml}${unsubscribeFooterHtml}`

    if (/<\/body\s*>/i.test(html)) {
        return html.replace(/<\/body\s*>/i, `${insertion}</body>`)
    }
    if (/<\/html\s*>/i.test(html)) {
        return html.replace(/<\/html\s*>/i, `${insertion}</html>`)
    }
    return `${html}${insertion}`
}

export function buildEmailTemplatePreviewHtml(
    rawHtml: string,
    options: EmailTemplatePreviewOptions,
): string {
    let html = removeLegacyUnsubscribeMarkup(rawHtml)
    html = substitutePreviewVariables(html, options.orgCompanyName)
    html = normalizePreviewBody(html)

    if (!/<html\b|<body\b/i.test(html)) {
        html = `<div style="font-family: ${PREVIEW_FONT_STACK}; font-size: 16px; line-height: 24px; color: #111827;">${html}</div>`
    }

    const signatureHtml =
        options.scope === "personal"
            ? options.personalSignatureHtml || ""
            : options.orgSignatureHtml || ""
    return sanitizeEmailTemplatePreviewHtml(
        appendManagedFooter(html, signatureHtml),
    )
}
