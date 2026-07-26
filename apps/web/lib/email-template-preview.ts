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

export function getEmailTemplateBodyMode(
    body: string | null | undefined,
): EmailTemplateBodyMode {
    return hasAdvancedEmailTemplateHtml(body) ? "html" : "visual"
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
                return orgCompanyName || "ABC Surrogacy"
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
