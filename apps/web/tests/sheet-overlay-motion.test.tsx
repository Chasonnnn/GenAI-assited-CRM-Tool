import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog"
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet"

function stateMotionClasses(element: Element | null) {
    expect(element).not.toBeNull()
    return Array.from(element!.classList)
        .filter((name) => /^data-(open|closed|starting-style|ending-style):/.test(name))
        .sort()
}

describe("Sheet overlay motion", () => {
    it("fades the overlay out like the dialog overlay and holds it hidden until the sheet unmounts", () => {
        render(
            <>
                <Sheet open>
                    <SheetContent>
                        <SheetTitle>Sheet</SheetTitle>
                    </SheetContent>
                </Sheet>
                <Dialog open>
                    <DialogContent>
                        <DialogTitle>Dialog</DialogTitle>
                    </DialogContent>
                </Dialog>
            </>
        )
        expect(screen.getByText("Sheet")).toBeInTheDocument()

        const sheetOverlay = document.querySelector('[data-slot="sheet-overlay"]')
        const dialogOverlay = document.querySelector('[data-slot="dialog-overlay"]')

        // The exit keyframe only defines `to`, so an ending-style opacity would make it animate 0 to 0.
        expect(sheetOverlay).not.toHaveClass("data-ending-style:opacity-0")
        // The 100ms overlay fade ends before the 200ms sheet slide, so the overlay keeps its end state.
        expect(sheetOverlay).toHaveClass("data-closed:fill-mode-forwards")
        expect(stateMotionClasses(sheetOverlay).filter((name) => name !== "data-closed:fill-mode-forwards")).toEqual(
            stateMotionClasses(dialogOverlay),
        )
    })
})
