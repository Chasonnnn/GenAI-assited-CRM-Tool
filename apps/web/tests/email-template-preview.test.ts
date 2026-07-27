import { describe, expect, it } from "vitest"

import {
    buildEmailTemplatePreviewHtml,
    extractEmailTemplateVariables,
    getEmailTemplateBodyMode,
    getEmailTemplateVisualEditorSupport,
    hasAdvancedEmailTemplateHtml,
} from "@/lib/email-template-preview"

describe("email template preview", () => {
    it("routes supported advanced fragments to the visual editor", () => {
        const appointmentFragment =
            '<div style="padding:20px"><table width="100%"><tbody><tr><td>{{appointment_type}}</td></tr></tbody></table></div>'

        expect(
            hasAdvancedEmailTemplateHtml(appointmentFragment),
        ).toBe(true)
        expect(getEmailTemplateBodyMode("<p>Hello</p>")).toBe("visual")
        expect(getEmailTemplateBodyMode(appointmentFragment)).toBe("visual")
        expect(getEmailTemplateVisualEditorSupport(appointmentFragment)).toEqual({
            supported: true,
            reason: null,
        })
    })

    it("keeps safe external links available to the visual editor", () => {
        const personalTemplateBody =
            '<p>Application link: <a target="_blank" class="text-primary underline cursor-pointer" href="https://form.jotform.com/example" rel="noopener noreferrer"><u>Surrogate Full Application Form</u></a></p>'

        expect(getEmailTemplateVisualEditorSupport(personalTemplateBody)).toEqual({
            supported: true,
            reason: null,
        })
    })

    it.each([
        ["full email documents", "<!doctype html><html><body><p>Hello</p></body></html>"],
        ["unsupported elements", "<section><p>Hello</p></section>"],
        ["unsupported attributes", '<div data-layout="legacy">Hello</div>'],
        ["unsupported styles", '<div style="background:linear-gradient(red, blue)">Hello</div>'],
        ["embedded styles", "<style>p{color:red}</style><p>Hello</p>"],
        ["conditional comments", "<!--[if mso]><table><tr><td>Hello</td></tr></table><![endif]-->"],
    ])("keeps %s in source mode", (_label, body) => {
        expect(getEmailTemplateBodyMode(body)).toBe("html")
        expect(getEmailTemplateVisualEditorSupport(body).supported).toBe(false)
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
