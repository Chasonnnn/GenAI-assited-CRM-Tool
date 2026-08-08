import { act, cleanup, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const { mockUseOffline } = vi.hoisted(() => ({
    mockUseOffline: vi.fn(() => false),
}))

vi.mock("next/offline", () => ({
    useOffline: mockUseOffline,
}))

import { OfflineBanner } from "@/components/offline-banner"

describe("OfflineBanner", () => {
    let nativeFetch: typeof window.fetch

    beforeEach(() => {
        nativeFetch = window.fetch
        mockUseOffline.mockReturnValue(false)
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

    it("uses Next's connectivity signal without replacing the global fetch function", () => {
        const fetchSpy = vi.fn()
        window.fetch = fetchSpy as typeof window.fetch
        mockUseOffline.mockReturnValue(true)

        render(<OfflineBanner />)

        expect(window.fetch).toBe(fetchSpy)
        expect(screen.getByRole("alert")).toHaveTextContent(
            "You're offline. Some features may be unavailable.",
        )
    })

    it("retains browser event detection when the experimental Next flag is off", async () => {
        render(<OfflineBanner />)
        expect(screen.queryByRole("alert")).not.toBeInTheDocument()

        Object.defineProperty(navigator, "onLine", {
            configurable: true,
            value: false,
        })
        act(() => window.dispatchEvent(new Event("offline")))

        expect(await screen.findByRole("alert")).toHaveTextContent(
            "You're offline. Some features may be unavailable.",
        )

        Object.defineProperty(navigator, "onLine", {
            configurable: true,
            value: true,
        })
        act(() => window.dispatchEvent(new Event("online")))

        await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument())
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
