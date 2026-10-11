import { Editor, type Extensions, type JSONContent } from "@tiptap/react"
import { composeReactEmail, isDocumentVisuallyEmpty } from "@react-email/editor/core"

import { createEmailDesignExtensions } from "@/components/email/design/extensions"
import type { EmailBodyDesign } from "@/lib/api/email-templates"
import {
    EMAIL_BODY_STYLE,
    extractEmailBodyFragment,
    soleHtmlBlock,
    type EmailBodyValue,
} from "@/lib/email-design"

/**
 * Compile the editor document to the stored send HTML. A document that is only
 * one HTML block saves that HTML unchanged and stores no design (ADR 0010).
 */
export async function compileEmailDesign(editor: Editor): Promise<EmailBodyValue> {
    const design = editor.getJSON() as EmailBodyDesign
    const legacyHtml = soleHtmlBlock(design)
    if (legacyHtml !== null) return { body: legacyHtml, bodyDesign: null }
    if (isDocumentVisuallyEmpty(editor.state.doc)) return { body: "", bodyDesign: null }

    const { unformattedHtml } = await composeReactEmail({ editor })
    return { body: extractEmailBodyFragment(unformattedHtml), bodyDesign: design }
}

export type ConvertedEmailHtml = EmailBodyValue & {
    /** Block content to put in place of the HTML block. */
    blocks: JSONContent[]
    warnings: string[]
}

function containerChildren(design: JSONContent): JSONContent[] {
    return (design.content ?? []).flatMap((node) =>
        node.type === "container" ? (node.content ?? []) : [node],
    )
}

/** Keep the sent text style explicit so the editor theme does not restyle imported HTML. */
function prepareHtmlForConversion(html: string) {
    const document = new DOMParser().parseFromString(html, "text/html")
    const warnings: string[] = []
    if (document.querySelector('style, link[rel="stylesheet"]')) {
        warnings.push("Stylesheet rules may change. Keep HTML to preserve the original formatting.")
    }
    if (Array.from(document.images).some((img) => img.style.display !== "block" || img.hasAttribute("style"))) {
        warnings.push("Image layout or styling may change when images become blocks.")
    }
    if (document.querySelector("font")) {
        warnings.push("Legacy font formatting may change. Keep HTML to preserve it.")
    }

    const textStyle = "font-family:inherit;font-size:inherit;line-height:inherit;color:inherit;"
    const defaults: Record<string, string> = {
        p: `${textStyle}font-weight:inherit;margin:1em 0;padding:0;`,
        a: "color:#0000ee;text-decoration:underline;",
        blockquote: `${textStyle}margin:1em 40px;padding:0;border:0;`,
        ul: `${textStyle}margin:1em 0;padding:0 0 0 40px;`,
        ol: `${textStyle}margin:1em 0;padding:0 0 0 40px;`,
        li: `${textStyle}margin:0;padding:0;`,
    }
    for (const [index, size] of ["2em", "1.5em", "1.17em", "1em", ".83em", ".67em"].entries()) {
        const margin = [".67em", ".83em", "1em", "1.33em", "1.67em", "2.33em"][index]
        defaults[`h${index + 1}`] = `${textStyle}font-size:${size};font-weight:bold;margin:${margin} 0;padding:0;`
    }
    for (const element of document.body.querySelectorAll<HTMLElement>(Object.keys(defaults).join(","))) {
        const authored = Array.from(element.style, (property) => ({
            property,
            value: element.style.getPropertyValue(property),
            priority: element.style.getPropertyPriority(property),
        }))
        element.style.cssText = defaults[element.localName] ?? ""
        for (const { property, value, priority } of authored) {
            element.style.setProperty(property, value, priority)
        }
        // React merges theme and inline style objects; shorthands can otherwise override
        // an author's earlier longhand property when that merged object is serialized.
        const spacing: string[] = []
        for (const property of ["margin", "padding"]) {
            const sides = ["top", "right", "bottom", "left"].map((side) => `${property}-${side}`)
            for (const side of sides) {
                const value = element.style.getPropertyValue(side)
                if (value) spacing.push(`${side}:${value};`)
            }
            element.style.removeProperty(property)
        }
        element.setAttribute("style", element.style.cssText + spacing.join(""))
    }
    for (const img of document.images) {
        const href = img.closest("a")?.getAttribute("href")
        if (href) img.setAttribute("href", href)
    }
    const wrapper = document.createElement("div")
    wrapper.setAttribute("style", `${EMAIL_BODY_STYLE}${document.body.getAttribute("style") ?? ""}`)
    wrapper.append(...Array.from(document.body.childNodes))
    return { html: wrapper.outerHTML, warnings, hasImages: wrapper.querySelector("img") !== null }
}

/** Parse with the same extensions as the editor, including image serialization. */
export async function convertHtmlToDesign(
    html: string,
    extensions: Extensions = createEmailDesignExtensions(),
): Promise<ConvertedEmailHtml> {
    const prepared = prepareHtmlForConversion(html)
    if (prepared.hasImages && !extensions.some((extension) => extension.name === "image")) {
        throw new Error("Image conversion requires the editor image extension")
    }
    // Extensions hold an editor reference; previewing must not rebind the live editor's instances.
    const editor = new Editor({
        extensions: extensions.map((extension) => extension.configure()),
        content: prepared.html,
    })
    try {
        const compiled = await compileEmailDesign(editor)
        return { ...compiled, blocks: containerChildren(editor.getJSON()), warnings: prepared.warnings }
    } finally {
        editor.destroy()
    }
}
