import { act, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { toast, Toaster } from "@/components/ui/toast"

function transitionProperties(element: Element) {
    const token = Array.from(element.classList).find((name) => name.startsWith("transition-["))
    return token ? token.slice("transition-[".length, -1).split(",") : []
}

function renderToast() {
    render(<Toaster timeout={0} />)
    act(() => {
        toast("Stage updated")
    })
    const root = screen.getByText("Stage updated").closest('[data-slot="toast"]')
    expect(root).not.toBeNull()
    return root!
}

describe("Toast motion", () => {
    afterEach(() => {
        act(() => toast.dismiss())
    })

    it("transitions the translate offset used by its enter and exit styles", () => {
        const root = renderToast()

        expect(root).toHaveClass(
            "data-starting-style:translate-x-6",
            "data-ending-style:translate-x-6",
            "duration-200",
            "ease-smooth-out",
        )
        expect(transitionProperties(root)).toEqual(expect.arrayContaining(["translate", "opacity"]))
    })

    it("positions the toast from the Base UI swipe movement so a released swipe does not snap back", () => {
        const root = renderToast()

        expect((root as HTMLElement).style.getPropertyValue("--toast-swipe-movement-x")).toBe("0px")
        expect(root).toHaveClass("transform-[translateX(var(--toast-swipe-movement-x))]")
        expect(transitionProperties(root)).toContain("transform")
    })
})
