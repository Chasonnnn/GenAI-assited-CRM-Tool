import { Extension, type Extensions } from "@tiptap/react"
import Placeholder from "@tiptap/extension-placeholder"
import { Plugin, PluginKey } from "@tiptap/pm/state"
import { Decoration, DecorationSet } from "@tiptap/pm/view"
import type { Node as ProseMirrorNode } from "@tiptap/pm/model"
import { StarterKit } from "@react-email/editor/extensions"
import { EmailTheming } from "@react-email/editor/plugins"

import { HtmlBlock, type HtmlBlockOptions } from "@/components/email/design/html-block"

const VARIABLE_TOKEN = /\{\{\s*[a-zA-Z0-9_]+\s*\}\}/g

function variableDecorations(doc: ProseMirrorNode) {
    const decorations: Decoration[] = []
    doc.descendants((node, pos) => {
        if (!node.isText || !node.text) return
        for (const match of node.text.matchAll(VARIABLE_TOKEN)) {
            const from = pos + (match.index ?? 0)
            decorations.push(
                Decoration.inline(from, from + match[0].length, {
                    class: "email-variable-token",
                }),
            )
        }
    })
    return DecorationSet.create(doc, decorations)
}

/** Highlights `{{variable}}` tokens; the text itself stays plain so it renders unchanged. */
const VariableTokens = Extension.create({
    name: "variableTokens",
    addProseMirrorPlugins() {
        return [
            new Plugin({
                key: new PluginKey("variableTokens"),
                state: {
                    init: (_, state) => variableDecorations(state.doc),
                    apply: (tr, previous) =>
                        tr.docChanged ? variableDecorations(tr.doc) : previous,
                },
                props: {
                    decorations(state) {
                        return this.getState(state)
                    },
                },
            }),
        ]
    },
})

export function createEmailDesignExtensions(
    htmlBlock: Partial<HtmlBlockOptions> = {},
): Extensions {
    return [
        StarterKit.configure(),
        Placeholder.configure({
            placeholder: ({ node }) =>
                node.type.name === "heading" ? `Heading ${node.attrs.level}` : "Press '/' for blocks",
            includeChildren: true,
        }),
        EmailTheming.configure({ theme: "basic" }),
        HtmlBlock.configure(htmlBlock),
        VariableTokens,
    ]
}
