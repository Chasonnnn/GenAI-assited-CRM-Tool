import { describe, expect, it } from "vitest"
import { normalizeTemplateHtml } from "@/lib/email-template-html"

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

    it("does not modify non-empty paragraphs", () => {
        expect(normalizeTemplateHtml("<p>Hello</p>")).toBe("<p>Hello</p>")
        expect(normalizeTemplateHtml("<p>&nbsp;</p>")).toBe("<p>&nbsp;</p>")
        expect(normalizeTemplateHtml("<p><strong>Hi</strong></p>")).toBe("<p><strong>Hi</strong></p>")
    })
})

