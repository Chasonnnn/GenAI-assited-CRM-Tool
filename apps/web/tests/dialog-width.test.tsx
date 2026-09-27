import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogContent,
    DialogFooter,
    DialogTitle,
} from "@/components/ui/dialog"

import {
    classTokens,
    scanJsxElements,
    SOURCE_SCAN_TIMEOUT_MS,
} from "./fixtures/jsx-class-scan"

function renderDialog(props: React.ComponentProps<typeof DialogContent>) {
    render(
        <Dialog open>
            <DialogContent {...props}>
                <DialogTitle>Edit surrogate</DialogTitle>
            </DialogContent>
        </Dialog>,
    )
    return screen.getByRole("dialog")
}

describe("DialogContent width", () => {
    it("defaults to the md width with a mobile gutter and no breakpoint-only max width", () => {
        const dialog = renderDialog({})

        expect(dialog).toHaveAttribute("data-size", "md")
        expect(dialog).toHaveClass("max-w-md", "w-[calc(100%-2rem)]")
        expect(dialog.className).not.toMatch(/(^|\s)sm:max-w-/)
    })

    it("applies the size prop as the only named max width", () => {
        const dialog = renderDialog({ size: "2xl" })

        expect(dialog).toHaveAttribute("data-size", "2xl")
        expect(dialog).toHaveClass("max-w-2xl")
        expect(dialog).not.toHaveClass("max-w-md")
    })

    it("lets an unprefixed className max width replace the default at every breakpoint", () => {
        const dialog = renderDialog({ className: "max-w-2xl max-h-[90vh]" })

        expect(dialog).toHaveClass("max-w-2xl", "max-h-[90vh]")
        expect(dialog).not.toHaveClass("max-w-md")
        expect(dialog.className).not.toMatch(/(^|\s)sm:max-w-md/)
    })

    it("keeps a larger-breakpoint className width on top of the size", () => {
        const dialog = renderDialog({ size: "xl", className: "lg:max-w-2xl" })

        expect(dialog).toHaveAttribute("data-size", "xl")
        expect(dialog).toHaveClass("max-w-xl", "lg:max-w-2xl")
    })

    it("keeps a custom width class in place of the gutter width", () => {
        const dialog = renderDialog({ className: "w-[95vw]" })

        expect(dialog).toHaveClass("w-[95vw]")
        expect(dialog).not.toHaveClass("w-[calc(100%-2rem)]")
    })
})

describe("DialogFooter start slot", () => {
    it("renders start actions before Cancel/Save in their own group", () => {
        render(
            <Dialog open>
                <DialogContent>
                    <DialogTitle>Edit task</DialogTitle>
                    <DialogFooter start={<Button variant="destructive-ghost">Delete task</Button>}>
                        <Button variant="outline">Cancel</Button>
                        <Button>Save changes</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>,
        )

        const deleteButton = screen.getByRole("button", { name: "Delete task" })
        const startGroup = deleteButton.parentElement
        expect(startGroup).toHaveAttribute("data-slot", "dialog-footer-start")
        expect(startGroup).toHaveClass("sm:mr-auto")

        const footerButtons = Array.from(
            startGroup?.parentElement?.querySelectorAll("button") ?? [],
        ).map((button) => button.textContent)
        expect(footerButtons).toEqual(["Delete task", "Cancel", "Save changes"])
    })

    it("renders no start group when start is not set", () => {
        render(
            <Dialog open>
                <DialogContent>
                    <DialogTitle>Edit task</DialogTitle>
                    <DialogFooter>
                        <Button>Save changes</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>,
        )

        expect(document.querySelector('[data-slot="dialog-footer-start"]')).toBeNull()
    })
})

// A named max-w-* or sm:max-w-* on DialogContent duplicates the size prop. Arbitrary values
// (max-w-[640px]) and widths at md or larger breakpoints (lg:max-w-2xl on top of a size) stay allowed.
const NAMED_BASE_MAX_WIDTH = /^(sm:)?!?max-w-(xs|sm|md|lg|xl|[2-7]xl)!?$/

describe("DialogContent width policy", () => {
    it("uses the size prop instead of a named max-w or sm:max-w class", () => {
        const offenders = scanJsxElements(["DialogContent"]).filter(({ attributes }) => {
            const className = attributes.className
            if (typeof className !== "string") return false
            return classTokens(className).some((token) => NAMED_BASE_MAX_WIDTH.test(token))
        })

        expect(offenders.map(({ file, line }) => `${file}:${line}`)).toEqual([])
    }, SOURCE_SCAN_TIMEOUT_MS)
})
