import { act, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { useIsMobile } from "@/hooks/use-mobile"

type MediaChangeListener = (event: MediaQueryListEvent) => void

let mediaMatches = false
const mediaListeners = new Set<MediaChangeListener>()

function setViewportWidth(width: number) {
    Object.defineProperty(window, "innerWidth", {
        configurable: true,
        value: width,
    })
}

function installMatchMedia(initialMatches: boolean) {
    mediaMatches = initialMatches
    mediaListeners.clear()

    vi.stubGlobal(
        "matchMedia",
        vi.fn((query: string) => ({
            get matches() {
                return mediaMatches
            },
            media: query,
            onchange: null,
            addListener: vi.fn(),
            removeListener: vi.fn(),
            addEventListener: vi.fn((event: string, listener: MediaChangeListener) => {
                if (event === "change") {
                    mediaListeners.add(listener)
                }
            }),
            removeEventListener: vi.fn((event: string, listener: MediaChangeListener) => {
                if (event === "change") {
                    mediaListeners.delete(listener)
                }
            }),
            dispatchEvent: vi.fn(),
        }))
    )
}

function emitMediaChange(matches: boolean) {
    mediaMatches = matches
    const event = { matches, media: "(max-width: 767px)" } as MediaQueryListEvent
    for (const listener of mediaListeners) {
        listener(event)
    }
}

function UseMobileHarness() {
    const isMobile = useIsMobile()

    return <output aria-label="mobile">{String(isMobile)}</output>
}

describe("useIsMobile", () => {
    afterEach(() => {
        vi.unstubAllGlobals()
    })

    it("uses the media query snapshot for the initial mobile value", () => {
        setViewportWidth(1024)
        installMatchMedia(true)

        render(<UseMobileHarness />)

        expect(screen.getByLabelText("mobile")).toHaveTextContent("true")
    })

    it("updates when the media query changes", () => {
        setViewportWidth(1024)
        installMatchMedia(false)
        render(<UseMobileHarness />)

        expect(screen.getByLabelText("mobile")).toHaveTextContent("false")

        act(() => emitMediaChange(true))
        expect(screen.getByLabelText("mobile")).toHaveTextContent("true")

        act(() => emitMediaChange(false))
        expect(screen.getByLabelText("mobile")).toHaveTextContent("false")
    })
})
