"use client"

import { EmailNode } from "@react-email/editor/core"
import {
    NodeViewWrapper,
    ReactNodeViewRenderer,
    type NodeViewProps,
} from "@tiptap/react"

import { EmailHtmlFrame } from "@/components/email/design/email-html-frame"
import { Button } from "@/components/ui/button"
import { HTML_BLOCK_NODE } from "@/lib/email-design"

export type HtmlBlockTarget = {
    pos: number
    html: string
}

export type HtmlBlockOptions = {
    onEdit: ((target: HtmlBlockTarget) => void) | null
    onConvert: ((target: HtmlBlockTarget) => void) | null
}

function HtmlBlockView({ node, getPos, extension, selected }: NodeViewProps) {
    const html = String(node.attrs.html ?? "")
    const options = extension.options as HtmlBlockOptions
    const target = (): HtmlBlockTarget | null => {
        const pos = getPos()
        return typeof pos === "number" ? { pos, html } : null
    }

    return (
        <NodeViewWrapper
            data-html-block-view=""
            contentEditable={false}
            className={
                selected
                    ? "my-1 overflow-hidden rounded-sm outline-2 outline-primary"
                    : "my-1 overflow-hidden rounded-sm outline-1 outline-dashed outline-border"
            }
        >
            <div className="flex flex-wrap items-center gap-1 border-b border-border bg-muted/60 px-2 py-1 text-xs">
                <span className="font-mono text-muted-foreground">HTML</span>
                <span className="flex-1" />
                {options.onEdit ? (
                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 px-2 text-xs"
                        onClick={() => {
                            const current = target()
                            if (current) options.onEdit?.(current)
                        }}
                    >
                        Edit HTML
                    </Button>
                ) : null}
                {options.onConvert ? (
                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 px-2 text-xs"
                        onClick={() => {
                            const current = target()
                            if (current) options.onConvert?.(current)
                        }}
                    >
                        Convert to blocks
                    </Button>
                ) : null}
            </div>
            <EmailHtmlFrame html={html} title="HTML block" autoHeight />
        </NodeViewWrapper>
    )
}

/**
 * Raw email HTML kept as one block. Existing templates open as this block so
 * their HTML is saved unchanged until someone converts or edits it (ADR 0006).
 */
export const HtmlBlock = EmailNode.create<HtmlBlockOptions>({
    name: HTML_BLOCK_NODE,
    group: "block",
    atom: true,
    selectable: true,
    draggable: true,

    addOptions() {
        return { onEdit: null, onConvert: null }
    },

    addAttributes() {
        return {
            html: {
                default: "",
                parseHTML: (element) => element.getAttribute("data-html") ?? "",
                renderHTML: (attributes) => ({ "data-html": attributes.html }),
            },
        }
    },

    parseHTML() {
        return [{ tag: "div[data-html-block]", priority: 1000 }]
    },

    renderHTML({ HTMLAttributes }) {
        // The node-* class marks editor content so pasting keeps data-html.
        return ["div", { ...HTMLAttributes, "data-html-block": "", class: "node-htmlBlock" }]
    },

    addNodeView() {
        return ReactNodeViewRenderer(HtmlBlockView)
    },

    renderToReactEmail({ node }) {
        return <div dangerouslySetInnerHTML={{ __html: String(node.attrs?.html ?? "") }} />
    },
})
