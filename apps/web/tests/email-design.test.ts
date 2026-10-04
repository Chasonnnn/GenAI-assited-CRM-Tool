import { Editor, type JSONContent } from "@tiptap/react"
import { afterEach, describe, expect, it } from "vitest"

import { compileEmailDesign, convertHtmlToDesign } from "@/components/email/design/compile"
import { createEmailDesignExtensions } from "@/components/email/design/extensions"
import type { EmailBodyDesign } from "@/lib/api/email-templates"
import {
    extractEmailBodyFragment,
    initialEmailDesign,
    legacyEmailDesign,
    soleHtmlBlock,
} from "@/lib/email-design"

const editors: Editor[] = []

function editorFor(content: EmailBodyDesign | string) {
    const editor = new Editor({ extensions: createEmailDesignExtensions(), content: content as JSONContent | string })
    editors.push(editor)
    return editor
}

afterEach(() => {
    for (const editor of editors.splice(0)) editor.destroy()
})

const LEGACY_BODIES = [
    '<table role="presentation" cellpadding="0"><tr><td style="color:#555">Hi {{first_name}} — 保留</td></tr></table>\r\n',
    "Hello {{first_name}},\n\nPlain text body.\n",
    '<p>Hi</p><!-- note --><style>.x{color:red}</style><div class="x">{{org_name}}</div>',
]

describe("legacy bodies", () => {
    it.each(LEGACY_BODIES)("save byte-identical while untouched: %#", async (body) => {
        const editor = editorFor(legacyEmailDesign(body))

        await expect(compileEmailDesign(editor)).resolves.toEqual({ body, bodyDesign: null })
    })

    it("save the edited HTML of a sole HTML block without a design", async () => {
        const editor = editorFor(legacyEmailDesign("<p>Old</p>"))
        editor.commands.command(({ tr, state }) => {
            state.doc.descendants((node, pos) => {
                if (node.type.name === "htmlBlock") {
                    tr.setNodeMarkup(pos, undefined, { html: "<p>New {{first_name}}</p>" })
                }
            })
            return true
        })

        await expect(compileEmailDesign(editor)).resolves.toEqual({
            body: "<p>New {{first_name}}</p>",
            bodyDesign: null,
        })
    })

    it("compile with blocks once content is added beside the HTML block", async () => {
        const editor = editorFor(legacyEmailDesign("<p>Legacy {{first_name}}</p>"))
        editor.commands.insertContentAt(editor.state.doc.content.size - 1, {
            type: "paragraph",
            content: [{ type: "text", text: "Added" }],
        })

        const compiled = await compileEmailDesign(editor)

        expect(compiled.bodyDesign).not.toBeNull()
        expect(compiled.body).toContain("<p>Legacy {{first_name}}</p>")
        expect(compiled.body).toContain("Added")
    })

    it("open stored designs and fall back to a wrapped legacy block", () => {
        const design: EmailBodyDesign = {
            type: "doc",
            content: [{ type: "globalContent" }, { type: "paragraph" }],
        }
        expect(initialEmailDesign({ body: "<p>x</p>", bodyDesign: design })).toEqual({
            type: "doc",
            content: [{ type: "globalContent" }, { type: "container", content: [{ type: "paragraph" }] }],
        })
        expect(initialEmailDesign({ body: "<p>x</p>", bodyDesign: null })).toEqual({
            type: "doc",
            content: [{ type: "container", content: [{ type: "htmlBlock", attrs: { html: "<p>x</p>" } }] }],
        })
        expect(legacyEmailDesign("")).toEqual({
            type: "doc",
            content: [{ type: "container", content: [{ type: "paragraph" }] }],
        })
    })
})

describe("compileEmailDesign", () => {
    it("stores the body fragment with variables intact", async () => {
        const editor = editorFor({
            type: "doc",
            content: [
                { type: "paragraph", content: [{ type: "text", text: "Hi {{first_name}}" }] },
                {
                    type: "button",
                    attrs: { href: "{{appointment_link}}" },
                    content: [{ type: "text", text: "Book" }],
                },
            ],
        })

        const { body, bodyDesign } = await compileEmailDesign(editor)

        expect(bodyDesign?.type).toBe("doc")
        expect(body).toContain("Hi {{first_name}}")
        expect(body).toContain('href="{{appointment_link}}"')
        expect(body).not.toMatch(/<!doctype|<html|<head|<title|<!--body-->|<!--\/\$-->/i)
        expect(body.startsWith('<div style="background-color:#ffffff">')).toBe(true)
    })

    it("returns an empty body for an empty document", async () => {
        const editor = editorFor({ type: "doc", content: [] })

        await expect(compileEmailDesign(editor)).resolves.toEqual({ body: "", bodyDesign: null })
    })
})

describe("convertHtmlToDesign", () => {
    it("parses tables, links, and variables into blocks", async () => {
        const converted = await convertHtmlToDesign(
            '<h1>Title</h1><table role="presentation"><tr><td style="padding:8px"><a href="{{form_link}}">Apply</a></td></tr></table>',
            createEmailDesignExtensions(),
        )

        const types: string[] = []
        const convertedEditor = editorFor({ type: "doc", content: converted.blocks })
        convertedEditor.state.doc.descendants((node) => { types.push(node.type.name) })
        expect(types).toContain("heading")
        expect(types).toContain("table")
        expect(types).not.toContain("htmlBlock")
        expect(converted.body).toContain('href="{{form_link}}"')
        expect(converted.bodyDesign).not.toBeNull()
    })
})

describe("helpers", () => {
    it("ignores theme data and empty paragraphs around a sole HTML block", () => {
        expect(
            soleHtmlBlock({
                type: "doc",
                content: [
                    { type: "globalContent", attrs: {} },
                    {
                        type: "container",
                        content: [
                            { type: "htmlBlock", attrs: { html: "<p>x</p>" } },
                            { type: "paragraph" },
                        ],
                    },
                ],
            }),
        ).toBe("<p>x</p>")
        expect(
            soleHtmlBlock({
                type: "doc",
                content: [
                    { type: "htmlBlock", attrs: { html: "<p>x</p>" } },
                    { type: "paragraph", content: [{ type: "text", text: "y" }] },
                ],
            }),
        ).toBeNull()
    })

    it("strips React stream markers and keeps body styles", () => {
        expect(
            extractEmailBodyFragment(
                '<!DOCTYPE html><html><head><title>T</title></head><body style="background-color:#f4f4f5"><!--$--><!--html--><!--head--><!--body--><p>Hi</p><!--/$--></body></html>',
            ),
        ).toBe('<div style="background-color:#f4f4f5"><p>Hi</p></div>')
        expect(extractEmailBodyFragment("<html><body><p>Hi</p></body></html>")).toBe("<p>Hi</p>")
    })

    it("highlights variable tokens without changing the text", () => {
        const editor = editorFor({
            type: "doc",
            content: [{ type: "paragraph", content: [{ type: "text", text: "Hi {{ first_name }}!" }] }],
        })

        const tokens = editor.view.dom.querySelectorAll(".email-variable-token")
        expect(Array.from(tokens, (token) => token.textContent)).toEqual(["{{ first_name }}"])
    })
})
