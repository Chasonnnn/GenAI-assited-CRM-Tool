"use client"

import * as React from "react"

import { sanitizeHtml } from "@/lib/utils/sanitize"
import { cn } from "@/lib/utils"

type SafeHtmlContentProps = {
    html: string
    className?: string
}

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

    for (const declaration of styleValue.split(";").map((entry) => entry.trim()).filter(Boolean)) {
        const separatorIndex = declaration.indexOf(":")
        if (separatorIndex === -1) continue

        const property = declaration.slice(0, separatorIndex).trim()
        const value = declaration.slice(separatorIndex + 1).trim()
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

export function SafeHtmlContent({ html, className }: SafeHtmlContentProps) {
    const sanitizedHtml = React.useMemo(() => sanitizeHtml(html), [html])
    const [isMounted, setIsMounted] = React.useState(false)

    React.useEffect(() => {
        setIsMounted(true)
    }, [])

    const content = React.useMemo(() => {
        if (!isMounted || typeof window === "undefined") {
            return null
        }

        const parser = new window.DOMParser()
        const document = parser.parseFromString(`<div>${sanitizedHtml}</div>`, "text/html")
        const root = document.body.firstElementChild
        if (!root) return null

        return Array.from(root.childNodes).map((node, index) => nodeToReactNode(node, `node-${index}`))
    }, [isMounted, sanitizedHtml])

    if (!isMounted || !content) {
        return (
            <div className={cn("text-sm whitespace-pre-wrap text-foreground", className)}>
                {stripHtml(sanitizedHtml)}
            </div>
        )
    }

    return <div className={className}>{content}</div>
}
