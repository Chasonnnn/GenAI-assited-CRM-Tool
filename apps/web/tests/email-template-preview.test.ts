import { describe, expect, it } from "vitest"

import {
    buildEmailTemplatePreviewHtml,
    extractEmailTemplateVariables,
    getEmailTemplateBodyMode,
    hasAdvancedEmailTemplateHtml,
} from "@/lib/email-template-preview"

describe("email template preview", () => {
    it("detects advanced legacy markup without rewriting it", () => {
        expect(
            hasAdvancedEmailTemplateHtml(
                '<table style="mso-table-lspace:0"><tr><td>Hello</td></tr></table>',
            ),
        ).toBe(true)
        expect(getEmailTemplateBodyMode("<p>Hello</p>")).toBe("visual")
        expect(getEmailTemplateBodyMode("<div>Hello</div>")).toBe("html")
    })

    it("extracts unique variables with optional whitespace", () => {
        expect(
            extractEmailTemplateVariables(
                "Hello {{ full_name }} from {{org_name}} and {{ full_name }}",
            ),
        ).toEqual(["full_name", "org_name"])
    })

    it("uses organization preview data and appends one managed unsubscribe footer", () => {
        const preview = buildEmailTemplatePreviewHtml(
            "<p>Hello {{ full_name }}</p><p>{{ org_name }}</p>",
            {
                scope: "org",
                orgCompanyName: "Bright Futures",
                orgSignatureHtml: '<div data-testid="org-signature">Org Signature</div>',
                personalSignatureHtml:
                    '<div data-testid="personal-signature">Personal Signature</div>',
            },
        )

        expect(preview).toContain("John Smith")
        expect(preview).toContain("Bright Futures")
        expect(preview).toContain("Org Signature")
        expect(preview).not.toContain("Personal Signature")
        expect(preview.match(/Manage email preferences:/g)).toHaveLength(1)
    })

    it("removes unsafe markup and legacy unsubscribe tokens before previewing", () => {
        const preview = buildEmailTemplatePreviewHtml(
            [
                '<table><tr><td><img src="https://example.com/a.png" onerror="alert(1)"></td></tr></table>',
                "<script>alert(1)</script>",
                '<a href="{{ unsubscribe_url }}">Old unsubscribe link</a>',
                "{{unsubscribe_url}}",
            ].join(""),
            {
                scope: "org",
                orgCompanyName: null,
                orgSignatureHtml: null,
                personalSignatureHtml: null,
            },
        )

        expect(preview).toContain("<table>")
        expect(preview).toContain("https://example.com/a.png")
        expect(preview).not.toContain("<script")
        expect(preview).not.toContain("onerror")
        expect(preview).not.toContain("Old unsubscribe link")
        expect(preview).not.toContain("{{unsubscribe_url}}")
        expect(preview.match(/Manage email preferences:/g)).toHaveLength(1)
    })
})
