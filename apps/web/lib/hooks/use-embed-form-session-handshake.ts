"use client"

import { useEffect, useReducer, useRef } from "react"

import { createEmbedFormSession } from "@/lib/api/forms"

type ParentMessage = {
    type: string
    attribution?: Record<string, unknown>
}

type EmbedSessionState = {
    token: string | null
    error: string | null
}

type EmbedSessionAction =
    | { type: "created"; token: string }
    | { type: "failed" }

type UseEmbedFormSessionHandshakeOptions = {
    enabled: boolean
    parentOrigin: string | null
    slug: string
}

const ALLOWED_ATTRIBUTION_KEYS = new Set([
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ad_id",
    "adset_id",
    "campaign_id",
    "fbclid",
    "fbc",
    "fbp",
    "referrer",
    "landing_url",
])

const initialEmbedSessionState: EmbedSessionState = {
    token: null,
    error: null,
}

function embedSessionReducer(
    state: EmbedSessionState,
    action: EmbedSessionAction,
): EmbedSessionState {
    switch (action.type) {
        case "created":
            return { token: action.token, error: null }
        case "failed":
            return {
                ...state,
                error: "This form is not available for this website.",
            }
        default:
            return state
    }
}

function sanitizeAttribution(
    payload: Record<string, unknown> | undefined,
): Record<string, unknown> {
    const sanitized: Record<string, unknown> = {}
    for (const [key, value] of Object.entries(payload || {})) {
        if (!ALLOWED_ATTRIBUTION_KEYS.has(key)) continue
        if (value === null || value === undefined) continue
        sanitized[key] = String(value).slice(0, 1000)
    }
    return sanitized
}

function postReadyToParent(parentOrigin: string) {
    if (window.parent === window) return
    window.parent.postMessage({ type: "sf:form:ready" }, parentOrigin)
}

export function useEmbedFormSessionHandshake({
    enabled,
    parentOrigin,
    slug,
}: UseEmbedFormSessionHandshakeOptions) {
    const [{ token, error }, dispatch] = useReducer(
        embedSessionReducer,
        initialEmbedSessionState,
    )
    const sessionTokenRef = useRef<string | null>(null)
    const sessionRequestPendingRef = useRef(false)

    useEffect(() => {
        if (!enabled || !parentOrigin) return

        let active = true
        const ensureSession = (attribution: Record<string, unknown>) => {
            if (sessionTokenRef.current || sessionRequestPendingRef.current) return
            sessionRequestPendingRef.current = true

            void (async () => {
                try {
                    const session = await createEmbedFormSession(
                        slug,
                        parentOrigin,
                        attribution,
                    )
                    if (active) {
                        sessionTokenRef.current = session.session_token
                        dispatch({ type: "created", token: session.session_token })
                    }
                } catch {
                    if (active) {
                        dispatch({ type: "failed" })
                    }
                }
                sessionRequestPendingRef.current = false
            })()
        }
        const onMessage = (event: MessageEvent<ParentMessage>) => {
            if (event.origin !== parentOrigin) return
            if (!event.data || event.data.type !== "sf:form:init") return
            ensureSession(sanitizeAttribution(event.data.attribution))
        }

        window.addEventListener("message", onMessage)
        postReadyToParent(parentOrigin)
        const fallback = window.setTimeout(() => {
            ensureSession({})
        }, 1000)

        return () => {
            active = false
            window.removeEventListener("message", onMessage)
            window.clearTimeout(fallback)
        }
    }, [enabled, parentOrigin, slug])

    return {
        sessionToken: token,
        sessionError: error,
    }
}
