import { act, renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useEmbedFormSessionHandshake } from "@/lib/hooks/use-embed-form-session-handshake"

const mockCreateEmbedFormSession = vi.fn()
let originalParent: PropertyDescriptor | undefined

vi.mock("@/lib/api/forms", () => ({
    createEmbedFormSession: (...args: unknown[]) => mockCreateEmbedFormSession(...args),
}))

describe("useEmbedFormSessionHandshake", () => {
    beforeEach(() => {
        originalParent = Object.getOwnPropertyDescriptor(window, "parent")
        mockCreateEmbedFormSession.mockReset()
        mockCreateEmbedFormSession.mockResolvedValue({
            session_token: "session-token",
            expires_at: new Date(Date.now() + 60_000).toISOString(),
        })
    })

    afterEach(() => {
        if (originalParent) {
            Object.defineProperty(window, "parent", originalParent)
        }
    })

    it("accepts one sanitized init message from the configured parent origin", async () => {
        const postMessage = vi.fn()
        Object.defineProperty(window, "parent", {
            configurable: true,
            value: { postMessage },
        })
        const removeEventListener = vi.spyOn(window, "removeEventListener")

        const { result, unmount } = renderHook(() =>
            useEmbedFormSessionHandshake({
                enabled: true,
                parentOrigin: "https://www.ewisurrogacy.com",
                slug: "lead-form",
            }),
        )

        expect(postMessage).toHaveBeenCalledWith(
            { type: "sf:form:ready" },
            "https://www.ewisurrogacy.com",
        )

        act(() => {
            window.dispatchEvent(
                new MessageEvent("message", {
                    origin: "https://attacker.example",
                    data: { type: "sf:form:init", attribution: { utm_source: "wrong" } },
                }),
            )
            window.dispatchEvent(
                new MessageEvent("message", {
                    origin: "https://www.ewisurrogacy.com",
                    data: {
                        type: "sf:form:init",
                        attribution: {
                            utm_source: "meta",
                            medical_notes: "must not leave the browser",
                        },
                    },
                }),
            )
        })

        await waitFor(() => {
            expect(mockCreateEmbedFormSession).toHaveBeenCalledWith(
                "lead-form",
                "https://www.ewisurrogacy.com",
                { utm_source: "meta" },
            )
        })
        await waitFor(() => expect(result.current.sessionToken).toBe("session-token"))

        act(() => {
            window.dispatchEvent(
                new MessageEvent("message", {
                    origin: "https://www.ewisurrogacy.com",
                    data: { type: "sf:form:init", attribution: { utm_source: "meta" } },
                }),
            )
        })
        expect(mockCreateEmbedFormSession).toHaveBeenCalledTimes(1)

        unmount()

        expect(removeEventListener).toHaveBeenCalledWith("message", expect.any(Function))
        removeEventListener.mockRestore()
    })
})
