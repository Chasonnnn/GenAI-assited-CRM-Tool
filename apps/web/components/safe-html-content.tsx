"use client"

import * as React from "react"

import { sanitizeHtml } from "@/lib/utils/sanitize"
import { cn } from "@/lib/utils"

type SafeHtmlContentProps = {
    html: string
    className?: string
}

type ParsedHtmlContentProps = SafeHtmlContentProps

const NUMERIC_ATTRIBUTES = new Set([
    "colspan",
    "rowspan",
    "tabindex",
    "width",
    "height",
])

function stripHtml(html: string) {
    return html
        .replace(/<br\s*\/?>/gi, "\n")
        .replace(/<\/p>/gi, "\n")
        .replace(/<[^>]+>/g, " ")
        .replace(/\s+/g, " ")
        .trim()
}

function toCamelCase(value: string) {
    return value.replace(/-([a-z])/g, (_match, letter: string) => letter.toUpperCase())
}

function parseStyleAttribute(styleValue: string): React.CSSProperties {
    const styles: Record<string, string> = {}

    for (const entry of styleValue.split(";")) {
        const declaration = entry.trim()
        if (!declaration) continue

        const [propertyPart = "", ...valueParts] = declaration.split(":")
        if (valueParts.length === 0) continue

        const property = propertyPart.trim()
        const value = valueParts.join(":").trim()
        if (!property || !value) continue

        styles[toCamelCase(property)] = value
    }

    return styles as React.CSSProperties
}

function buildElementProps(element: HTMLElement, key: string): Record<string, unknown> {
    const props: Record<string, unknown> = { key }

    for (const attribute of Array.from(element.attributes)) {
        if (attribute.name.startsWith("aria-") || attribute.name.startsWith("data-")) {
            props[attribute.name] = attribute.value
            continue
        }
        if (attribute.name === "class") {
            props.className = attribute.value
            continue
        }
        if (attribute.name === "style") {
            props.style = parseStyleAttribute(attribute.value)
            continue
        }
        if (attribute.name === "for") {
            props.htmlFor = attribute.value
            continue
        }
        if (attribute.name === "srcset") {
            props.srcSet = attribute.value
            continue
        }
        if (attribute.name === "readonly") {
            props.readOnly = true
            continue
        }
        if (NUMERIC_ATTRIBUTES.has(attribute.name)) {
            const nextValue = Number(attribute.value)
            props[toCamelCase(attribute.name)] = Number.isNaN(nextValue) ? attribute.value : nextValue
            continue
        }
        props[toCamelCase(attribute.name)] = attribute.value
    }

    return props
}

function nodeToReactNode(node: ChildNode, key: string): React.ReactNode {
    if (node.nodeType === Node.TEXT_NODE) {
        return node.textContent
    }

    if (node.nodeType !== Node.ELEMENT_NODE) {
        return null
    }

    const element = node as HTMLElement
    const children = Array.from(element.childNodes).map((child, index) =>
        nodeToReactNode(child, `${key}-${index}`),
    )

    return React.createElement(
        element.tagName.toLowerCase(),
        buildElementProps(element, key),
        ...children,
    )
}

function useParsedHtmlContent(html: string) {
    const isClient = React.useSyncExternalStore(
        () => () => undefined,
        () => true,
        () => false,
    )

    let content: React.ReactNode = null
    if (isClient && typeof window !== "undefined") {
        const parser = new window.DOMParser()
        const document = parser.parseFromString(`<div>${html}</div>`, "text/html")
        const root = document.body.firstElementChild
        if (root) {
            content = Array.from(root.childNodes).map((node, index) =>
                nodeToReactNode(node, `node-${index}`),
            )
        }
    }

    return content ?? stripHtml(html)
}

function ParsedHtmlContent({ html, className }: ParsedHtmlContentProps) {
    const content = useParsedHtmlContent(html)
    return <div className={className}>{content}</div>
}

export function TrustedSanitizedHtmlFragment({ html }: { html: string }) {
    const content = useParsedHtmlContent(html)
    return <>{content}</>
}

export function TrustedSanitizedHtmlContent({ html, className }: ParsedHtmlContentProps) {
    if (className === undefined) {
        return <ParsedHtmlContent html={html} />
    }
    return <ParsedHtmlContent html={html} className={className} />
}

export function SafeHtmlContent({ html, className }: SafeHtmlContentProps) {
    const sanitizedHtml = sanitizeHtml(html)

    return (
        <ParsedHtmlContent
            html={sanitizedHtml}
            className={cn("text-sm whitespace-pre-wrap text-foreground", className)}
        />
    )
}
