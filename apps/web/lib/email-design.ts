/**
 * React Email editor documents stored beside template HTML (ADR 0010).
 *
 * `body` stays the send artifact. A body without a design opens as one HTML
 * block; while the document is still only that block, saving writes the block's
 * HTML unchanged and stores no design.
 */

import type { EmailBodyDesign, EmailLayout, EmailTemplateScope } from "@/lib/api/email-templates"

export const HTML_BLOCK_NODE = "htmlBlock"

/**
 * The text style sends wrap around fragment bodies (email_composition_service._wrap_body_html).
 * Fragment renders and HTML conversion use it so the editor shows what recipients get.
 */
export const EMAIL_BODY_STYLE =
    "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Apple Color Emoji','Segoe UI Emoji','Noto Color Emoji',Arial,sans-serif;" +
    "font-size:16px;line-height:24px;color:#111827;"

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

const FULL_DOCUMENT = /<!doctype|<html\b|<body\b/i

/** A full HTML document controls its own frame, so sends give it no layout. */
export function isFullEmailDocument(body: string): boolean {
    return FULL_DOCUMENT.test(body)
}

const ORG_LOGO_VARIABLE = /\{\{\s*org_logo_url\s*\}\}/

/** A body that places the org logo keeps its own placement; the layout shows none. */
export function placesOrgLogo(body: string): boolean {
    return ORG_LOGO_VARIABLE.test(body)
}

export const EMAIL_PAGE_BACKGROUND = "#f4f4f5"

/** Mirrors app.core.email_layout: org templates default to Card, personal templates to Plain. */
export function defaultEmailLayout(scope: EmailTemplateScope): EmailLayout {
    return {
        kind: scope === "org" ? "card" : "plain",
        show_logo: true,
        logo_position: "center",
        accent_color: null,
        page_background: EMAIL_PAGE_BACKGROUND,
    }
}

export function resolveEmailLayout(layout: EmailLayout | null | undefined, scope: EmailTemplateScope): EmailLayout {
    return layout ?? defaultEmailLayout(scope)
}
