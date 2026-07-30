import { act, cleanup, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { OfflineBanner } from "@/components/offline-banner"

describe("OfflineBanner", () => {
    let nativeFetch: typeof window.fetch

    beforeEach(() => {
        nativeFetch = window.fetch
        Object.defineProperty(navigator, "onLine", {
            configurable: true,
            value: true,
        })
    })

    afterEach(() => {
        cleanup()
        window.fetch = nativeFetch
        vi.restoreAllMocks()
    })

    it("keeps a stable fetch wrapper across offline/online transitions", async () => {
        let failRequests = true
        const fetchSpy = vi.fn(async () => {
            if (failRequests) {
                throw new TypeError("Failed to fetch")
            }
            return new Response(JSON.stringify({ ok: true }), {
                status: 200,
                headers: { "Content-Type": "application/json" },
            })
        })

        window.fetch = fetchSpy as typeof window.fetch
        render(<OfflineBanner />)

        await waitFor(() => {
            expect(window.fetch).not.toBe(fetchSpy)
        })

        const wrappedFetch = window.fetch

        await act(async () => {
            await expect(window.fetch("/api/test")).rejects.toThrow("Failed to fetch")
        })

        await waitFor(() => {
            expect(screen.getByText("You're offline. Some features may be unavailable.")).toBeInTheDocument()
        })

        // Wrapper should remain stable; swapping wrappers on every state change
        // risks nested/recursive wrappers during remounts.
        expect(window.fetch).toBe(wrappedFetch)

        failRequests = false
        await act(async () => {
            await window.fetch("/api/test")
        })

        await waitFor(() => {
            expect(
                screen.queryByText("You're offline. Some features may be unavailable.")
            ).not.toBeInTheDocument()
        })
        expect(window.fetch).toBe(wrappedFetch)
    })

    it("announces the offline state without exposing the decorative icon", async () => {
        Object.defineProperty(navigator, "onLine", {
            configurable: true,
            value: false,
        })

        const { container } = render(<OfflineBanner />)

        const alert = await screen.findByRole("alert")
        expect(alert).toHaveTextContent("You're offline. Some features may be unavailable.")
        expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true")
    })
})
