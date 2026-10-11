"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import DOMPurify from "dompurify"

import { EMAIL_BODY_STYLE } from "@/lib/email-design"
import { cn } from "@/lib/utils"

const PREVIEW_CSP =
    "default-src 'none'; style-src 'unsafe-inline'; img-src https: data:; base-uri 'none'; form-action 'none'"

function isDocument(html: string) {
    return /^\s*(<!doctype|<html[\s>])/i.test(html)
}

/** Sanitized email HTML in a script-free iframe document; fragments get the sent body style. */
export function buildEmailFrameDocument(html: string): string {
    if (isDocument(html)) {
        return DOMPurify.sanitize(html, { WHOLE_DOCUMENT: true, FORBID_TAGS: ["form"] })
    }
    const body = DOMPurify.sanitize(html, { FORBID_TAGS: ["form"] })
    return `<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="${PREVIEW_CSP}"><meta name="viewport" content="width=device-width, initial-scale=1"></head><body style="margin:0;${EMAIL_BODY_STYLE}">${body}</body></html>`
}

type EmailHtmlFrameProps = {
    html: string
    title: string
    className?: string
    /** Grow to the content height instead of scrolling inside the frame. */
    autoHeight?: boolean
    minHeight?: number
}

/**
 * The frame has no `allow-scripts`, so nothing in the email runs. Same-origin
 * access only lets the parent measure the content height.
 */
export function EmailHtmlFrame({
    html,
    title,
    className,
    autoHeight = false,
    minHeight = 48,
}: EmailHtmlFrameProps) {
    const frameRef = useRef<HTMLIFrameElement>(null)
    const [height, setHeight] = useState(minHeight)
    const observerRef = useRef<ResizeObserver | null>(null)

    const measure = useCallback(() => {
        const root = frameRef.current?.contentDocument?.documentElement
        if (root) setHeight(Math.max(minHeight, root.scrollHeight))
    }, [minHeight])

    useEffect(() => () => observerRef.current?.disconnect(), [])

    const handleLoad = () => {
        if (!autoHeight) return
        measure()
        observerRef.current?.disconnect()
        const body = frameRef.current?.contentDocument?.body
        if (body && typeof ResizeObserver !== "undefined") {
            observerRef.current = new ResizeObserver(measure)
            observerRef.current.observe(body)
        }
    }

    return (
        <iframe
            ref={frameRef}
            title={title}
            sandbox="allow-same-origin"
            referrerPolicy="no-referrer"
            srcDoc={buildEmailFrameDocument(html)}
            onLoad={handleLoad}
            className={cn("block w-full border-0 bg-white", className)}
            style={autoHeight ? { height } : undefined}
        />
    )
}
