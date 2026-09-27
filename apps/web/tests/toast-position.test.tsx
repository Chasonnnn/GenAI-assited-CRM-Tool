import * as React from "react"
import { act, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { toast, Toaster } from "@/components/ui/toast"
import { toastClearanceRef } from "@/components/ui/toast-clearance"

type ResizeCallback = () => void

let resizeCallbacks: ResizeCallback[] = []

class CapturingResizeObserver {
    constructor(callback: ResizeCallback) {
        resizeCallbacks.push(callback)
    }
    observe() {}
    unobserve() {}
    disconnect() {}
}

// jsdom has no layout: give an element a height and a viewport position (top edge in px).
function placeElement(element: HTMLElement, box: () => { top: number; height: number }) {
    Object.defineProperty(element, "offsetHeight", { configurable: true, get: () => box().height })
    element.getBoundingClientRect = () => {
        const { top, height } = box()
        return DOMRect.fromRect({ x: 0, y: top, width: 600, height })
    }
}

/** A bar pinned `bottom` px above the viewport bottom, like fixed bottom-6. */
function BottomBar({ height, bottom }: { height: number; bottom: number }) {
    const ref = (element: HTMLDivElement | null) => {
        if (element) placeElement(element, () => ({ top: window.innerHeight - bottom - height, height }))
        return toastClearanceRef(element)
    }
    return <div ref={ref} data-testid="bottom-bar" style={{ position: "fixed", bottom }} />
}

function viewport() {
    const element = document.querySelector<HTMLElement>('[data-slot="toast-viewport"]')
    expect(element).not.toBeNull()
    return element!
}

function showToast(title = "Saved") {
    act(() => {
        toast.success(title)
    })
    const root = screen.getByText(title).closest<HTMLElement>('[data-slot="toast"]')
    expect(root).not.toBeNull()
    return root!
}

describe("Toast viewport position", () => {
    afterEach(() => {
        act(() => toast.dismiss())
        vi.unstubAllGlobals()
        resizeCallbacks = []
    })

    it("anchors toasts to the bottom right with the newest nearest the edge", () => {
        render(<Toaster timeout={0} />)
        showToast("First")

        const element = viewport()
        expect(element).toHaveClass("fixed", "right-4", "bottom-[calc(1rem+var(--toast-clearance))]", "flex-col-reverse")
        expect(element).not.toHaveClass("top-4")
        expect(element.style.getPropertyValue("--toast-clearance")).toBe("0px")
    })

    it("stacks above a registered bottom bar and drops back when it unmounts", () => {
        const { rerender } = render(
            <>
                <Toaster timeout={0} />
                <BottomBar height={56} bottom={24} />
            </>,
        )
        showToast()

        // bottom-6 inset (24px) plus the bar's 56px height.
        expect(viewport().style.getPropertyValue("--toast-clearance")).toBe("80px")

        rerender(<Toaster timeout={0} />)
        expect(viewport().style.getPropertyValue("--toast-clearance")).toBe("0px")
    })

    it("uses the tallest registered element and follows its resizes", () => {
        vi.stubGlobal("ResizeObserver", CapturingResizeObserver)
        let saveBarHeight = 61
        function ResizingSaveBar() {
            const ref = (element: HTMLDivElement | null) => {
                if (element) {
                    placeElement(element, () => ({
                        top: window.innerHeight - saveBarHeight,
                        height: saveBarHeight,
                    }))
                }
                return toastClearanceRef(element)
            }
            return <div ref={ref} style={{ position: "sticky", bottom: "0px" }} />
        }

        render(
            <>
                <Toaster timeout={0} />
                <BottomBar height={56} bottom={24} />
                <ResizingSaveBar />
            </>,
        )
        showToast()
        expect(viewport().style.getPropertyValue("--toast-clearance")).toBe("80px")

        // The save bar wraps to two rows on a narrow screen.
        saveBarHeight = 89
        act(() => {
            for (const callback of resizeCallbacks) callback()
        })
        expect(viewport().style.getPropertyValue("--toast-clearance")).toBe("89px")
    })

    it("ignores registered elements that take no space", () => {
        render(
            <>
                <Toaster timeout={0} />
                <BottomBar height={0} bottom={24} />
            </>,
        )
        showToast()
        expect(viewport().style.getPropertyValue("--toast-clearance")).toBe("0px")
    })

    it("stacks above a sticky bar that sits in the page flow above its stuck position", () => {
        // A short form: the sticky save bar ends 68px above the viewport bottom instead of at it.
        const barTop = window.innerHeight - 128
        function InFlowSaveBar() {
            const ref = (element: HTMLDivElement | null) => {
                if (element) placeElement(element, () => ({ top: barTop, height: 60 }))
                return toastClearanceRef(element)
            }
            return <div ref={ref} style={{ position: "sticky", bottom: "0px" }} />
        }

        render(
            <>
                <Toaster timeout={0} />
                <InFlowSaveBar />
            </>,
        )
        showToast()

        expect(viewport().style.getPropertyValue("--toast-clearance")).toBe("128px")
    })

    it("follows an in-flow bar while the page scrolls and ignores it in the upper half", () => {
        const frames: FrameRequestCallback[] = []
        vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => frames.push(callback))
        vi.stubGlobal("cancelAnimationFrame", () => {})
        const flushFrames = () =>
            act(() => {
                for (const callback of frames.splice(0)) callback(0)
            })
        let barTop = window.innerHeight - 128
        function ScrollingSaveBar() {
            const ref = (element: HTMLDivElement | null) => {
                if (element) placeElement(element, () => ({ top: barTop, height: 60 }))
                return toastClearanceRef(element)
            }
            return (
                <div data-testid="scroller" style={{ overflowY: "auto" }}>
                    <div ref={ref} style={{ position: "sticky", bottom: "0px" }} />
                </div>
            )
        }

        render(
            <>
                <Toaster timeout={0} />
                <ScrollingSaveBar />
            </>,
        )
        showToast()
        expect(viewport().style.getPropertyValue("--toast-clearance")).toBe("128px")

        // Scroll events do not bubble; an inner scroll container must still trigger a re-measure.
        barTop = window.innerHeight - 200
        fireEvent.scroll(screen.getByTestId("scroller"))
        flushFrames()
        expect(viewport().style.getPropertyValue("--toast-clearance")).toBe("200px")

        barTop = Math.floor(window.innerHeight / 2) - 10
        fireEvent.scroll(window)
        flushFrames()
        expect(viewport().style.getPropertyValue("--toast-clearance")).toBe("0px")
    })

    it("dismisses a toast swiped down toward the bottom edge", () => {
        render(<Toaster timeout={0} />)
        const root = showToast("Swipe me")

        act(() => {
            fireEvent.pointerDown(root, { button: 0, pointerId: 1, pointerType: "mouse", clientX: 100, clientY: 100 })
            fireEvent.pointerMove(root, { button: 0, pointerId: 1, pointerType: "mouse", clientX: 100, clientY: 120 })
            fireEvent.pointerMove(root, { button: 0, pointerId: 1, pointerType: "mouse", clientX: 100, clientY: 180 })
            fireEvent.pointerUp(root, { button: 0, pointerId: 1, pointerType: "mouse", clientX: 100, clientY: 180 })
        })

        expect(root).toHaveAttribute("data-swipe-direction", "down")
    })
})
