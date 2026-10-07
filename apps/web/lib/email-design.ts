/**
 * React Email editor documents stored beside template HTML (ADR 0010).
 *
 * `body` stays the send artifact. A body without a design opens as one HTML
 * block; while the document is still only that block, saving writes the block's
 * HTML unchanged and stores no design.
 */

import type { EmailBodyDesign } from "@/lib/api/email-templates"

export const HTML_BLOCK_NODE = "htmlBlock"

/** Nodes that carry no email content of their own. */
const CONTAINER_NODES = new Set(["container"])
const IGNORED_NODES = new Set(["globalContent"])

type DesignNode = {
    type?: string
    attrs?: Record<string, unknown>
    content?: DesignNode[]
    text?: string
}

export type EmailBodyValue = {
    body: string
    bodyDesign: EmailBodyDesign | null
}

/**
 * The editor wraps content in one container node. Wrapping before mount keeps
 * that normalization from looking like an edit.
 */
export function wrapEmailDesign(design: EmailBodyDesign): EmailBodyDesign {
    const nodes = ((design as DesignNode).content ?? []) as DesignNode[]
    if (nodes.some((node) => node.type === "container")) return design
    const globals = nodes.filter((node) => node.type !== undefined && IGNORED_NODES.has(node.type))
    const blocks = nodes.filter((node) => !(node.type !== undefined && IGNORED_NODES.has(node.type)))
    return {
        ...design,
        content: [
            ...globals,
            { type: "container", content: blocks.length > 0 ? blocks : [{ type: "paragraph" }] },
        ],
    }
}

export function legacyEmailDesign(body: string): EmailBodyDesign {
    return wrapEmailDesign({
        type: "doc",
        content: body ? [{ type: HTML_BLOCK_NODE, attrs: { html: body } }] : [],
    })
}

export function initialEmailDesign(value: EmailBodyValue): EmailBodyDesign {
    return value.bodyDesign ? wrapEmailDesign(value.bodyDesign) : legacyEmailDesign(value.body)
}

function isEmptyParagraph(node: DesignNode) {
    return node.type === "paragraph" && !(node.content?.length)
}

function contentNodes(nodes: DesignNode[] | undefined): DesignNode[] {
    const result: DesignNode[] = []
    for (const node of nodes ?? []) {
        if (!node.type || IGNORED_NODES.has(node.type) || isEmptyParagraph(node)) continue
        if (CONTAINER_NODES.has(node.type)) {
            result.push(...contentNodes(node.content))
            continue
        }
        result.push(node)
    }
    return result
}

/** Returns the HTML of a document that is only one HTML block, else null. */
export function soleHtmlBlock(design: EmailBodyDesign): string | null {
    const nodes = contentNodes((design as DesignNode).content)
    const [only] = nodes
    if (nodes.length !== 1 || only?.type !== HTML_BLOCK_NODE) return null
    const html = only.attrs?.html
    return typeof html === "string" ? html : ""
}

const REACT_MARKERS = new Set(["$", "/$", "html", "head", "body"])

/**
 * React Email renders a full document. The sanitizer keeps `<title>` text, so
 * only the `<body>` content is stored, without React's stream markers. Body
 * styles (the document background) move to a wrapping `<div>`.
 */
export function extractEmailBodyFragment(documentHtml: string): string {
    const parsed = new DOMParser().parseFromString(documentHtml, "text/html")
    for (const child of Array.from(parsed.body.childNodes)) {
        if (child.nodeType === Node.COMMENT_NODE && REACT_MARKERS.has((child as Comment).data)) {
            child.remove()
        }
    }
    const style = parsed.body.getAttribute("style")
    if (!style) return parsed.body.innerHTML.trim()

    const wrapper = parsed.createElement("div")
    wrapper.setAttribute("style", style)
    wrapper.append(...Array.from(parsed.body.childNodes))
    return wrapper.outerHTML
}
