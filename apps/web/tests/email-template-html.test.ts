import { describe, expect, it } from "vitest"
import {
    normalizeTemplateHtml,
    prepareTemplateHtmlForVisualEditor,
} from "@/lib/email-template-html"

describe("normalizeTemplateHtml", () => {
    it("preserves empty paragraphs as visible blank lines", () => {
        expect(normalizeTemplateHtml("<p></p>")).toBe("<p>&nbsp;</p>")
        expect(normalizeTemplateHtml("<p>   </p>")).toBe("<p>&nbsp;</p>")
        expect(normalizeTemplateHtml("<p>\n\t</p>")).toBe("<p>&nbsp;</p>")
    })

    it("preserves paragraphs containing only a line break", () => {
        expect(normalizeTemplateHtml("<p><br></p>")).toBe("<p>&nbsp;</p>")
        expect(normalizeTemplateHtml("<p><br/></p>")).toBe("<p>&nbsp;</p>")
        expect(normalizeTemplateHtml("<p><br /></p>")).toBe("<p>&nbsp;</p>")
        expect(normalizeTemplateHtml("<p> <br /> </p>")).toBe("<p>&nbsp;</p>")
    })

    it("preserves attributes on empty and break-only paragraphs", () => {
        expect(
            normalizeTemplateHtml(
                '<p style="text-align:center"></p><p class="legacy"><br class="ProseMirror-trailingBreak"></p>',
            ),
        ).toBe(
            '<p style="text-align:center">&nbsp;</p><p class="legacy">&nbsp;</p>',
        )
    })

    it("does not modify non-empty paragraphs", () => {
        expect(normalizeTemplateHtml("<p>Hello</p>")).toBe("<p>Hello</p>")
        expect(normalizeTemplateHtml("<p>&nbsp;</p>")).toBe("<p>&nbsp;</p>")
        expect(normalizeTemplateHtml("<p><strong>Hi</strong></p>")).toBe("<p><strong>Hi</strong></p>")
    })
})

describe("prepareTemplateHtmlForVisualEditor", () => {
    it("preserves legacy plain-text blank lines as empty paragraphs", () => {
        expect(
            prepareTemplateHtmlForVisualEditor(
                "Hi there,\r\n\r\nThank you for reaching out.",
            ),
        ).toBe(
            "<p>Hi there,</p><p>&nbsp;</p><p>Thank you for reaching out.</p>",
        )
    })

    it("escapes plain-text markup instead of turning it into editor HTML", () => {
        expect(
            prepareTemplateHtmlForVisualEditor("Use 1 < 2 & keep {{first_name}}"),
        ).toBe("<p>Use 1 &lt; 2 &amp; keep {{first_name}}</p>")
    })

    it("does not rewrite stored HTML merely by opening the editor", () => {
        const html = '<p style="margin:0">Already HTML</p><p></p>'
        expect(prepareTemplateHtmlForVisualEditor(html)).toBe(html)
    })
})
