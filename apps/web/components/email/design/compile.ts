import { Editor, type JSONContent } from "@tiptap/react"
import { composeReactEmail, isDocumentVisuallyEmpty } from "@react-email/editor/core"

import { createEmailDesignExtensions } from "@/components/email/design/extensions"
import type { EmailBodyDesign } from "@/lib/api/email-templates"
import {
    extractEmailBodyFragment,
    soleHtmlBlock,
    type EmailBodyValue,
} from "@/lib/email-design"

/**
 * Compile the editor document to the stored send HTML. A document that is only
 * one HTML block saves that HTML unchanged and stores no design (ADR 0006).
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
}

function containerChildren(design: JSONContent): JSONContent[] {
    return (design.content ?? []).flatMap((node) =>
        node.type === "container" ? (node.content ?? []) : [node],
    )
}

/** Parse raw HTML into editor blocks with a headless editor. */
export async function convertHtmlToDesign(html: string): Promise<ConvertedEmailHtml> {
    const editor = new Editor({ extensions: createEmailDesignExtensions(), content: html })
    try {
        const compiled = await compileEmailDesign(editor)
        return { ...compiled, blocks: containerChildren(editor.getJSON()) }
    } finally {
        editor.destroy()
    }
}
