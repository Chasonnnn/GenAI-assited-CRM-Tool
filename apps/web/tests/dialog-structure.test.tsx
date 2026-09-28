import { render, screen, within } from "@testing-library/react"
import { CalendarIcon } from "lucide-react"
import { describe, expect, it } from "vitest"

import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogBody,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogStatusBar,
    DialogTitle,
} from "@/components/ui/dialog"

function slot(root: HTMLElement, name: string) {
    return root.querySelector<HTMLElement>(`[data-slot="${name}"]`)
}

function renderSectionedDialog() {
    render(
        <Dialog open>
            <DialogContent layout="sectioned" size="2xl">
                <DialogHeader icon={<CalendarIcon />} status={<Badge>Connected</Badge>}>
                    <DialogTitle>Google Calendar &amp; Meet</DialogTitle>
                    <DialogDescription>scheduling-admin@example.test</DialogDescription>
                </DialogHeader>
                <DialogStatusBar>
                    <span>Last sync 4 minutes ago</span>
                    <Button variant="ghost" size="sm">Sync now</Button>
                </DialogStatusBar>
                <DialogBody>
                    <p>Calendars</p>
                </DialogBody>
                <DialogFooter start={<Button variant="destructive-ghost">Disconnect…</Button>}>
                    <Button variant="outline">Cancel</Button>
                    <Button>Save changes</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>,
    )
    return screen.getByRole("dialog")
}

describe("DialogContent sectioned layout", () => {
    it("caps the height and lets only the body scroll between a fixed header and footer", () => {
        const dialog = renderSectionedDialog()

        expect(dialog).toHaveAttribute("data-layout", "sectioned")
        expect(dialog).toHaveClass("flex", "flex-col", "overflow-hidden", "p-0", "max-h-[calc(100dvh-2rem)]", "max-w-2xl")
        expect(dialog).not.toHaveClass("grid", "p-6", "overflow-y-auto")

        const header = slot(dialog, "dialog-header")
        const statusBar = slot(dialog, "dialog-status-bar")
        const body = slot(dialog, "dialog-body")
        const footer = slot(dialog, "dialog-footer")

        expect(header).toHaveClass("shrink-0", "border-b", "pr-14")
        expect(statusBar).toHaveClass("shrink-0", "border-b", "bg-muted/50")
        expect(body).toHaveClass("min-h-0", "flex-1", "overflow-y-auto", "px-6")
        expect(footer).toHaveClass("shrink-0", "border-t", "px-6")

        const sections = Array.from(dialog.children)
            .map((child) => child.getAttribute("data-slot"))
            .filter((name) => name !== "dialog-close")
        expect(sections).toEqual(["dialog-header", "dialog-status-bar", "dialog-body", "dialog-footer"])
    })

    it("renders the identity row: decorative icon tile, title with one detail line, one status", () => {
        const dialog = renderSectionedDialog()

        expect(screen.getByRole("dialog", { name: "Google Calendar & Meet" })).toHaveAccessibleDescription(
            "scheduling-admin@example.test",
        )

        const header = slot(dialog, "dialog-header") as HTMLElement
        expect(header).toHaveClass("flex-row", "items-center")
        expect(slot(header, "dialog-header-icon")).toHaveAttribute("aria-hidden", "true")
        expect(within(slot(header, "dialog-header-status") as HTMLElement).getByText("Connected")).toBeInTheDocument()
        const [iconTile, titleColumn, statusSlot] = Array.from(header.children)
        expect(iconTile).toHaveAttribute("data-slot", "dialog-header-icon")
        expect(within(titleColumn as HTMLElement).getByText("Google Calendar & Meet")).toBeInTheDocument()
        expect(within(titleColumn as HTMLElement).getByText("scheduling-admin@example.test")).toBeInTheDocument()
        expect(statusSlot).toHaveAttribute("data-slot", "dialog-header-status")
    })

    it("keeps Disconnect apart on the left of Cancel and Save", () => {
        const dialog = renderSectionedDialog()

        const footer = slot(dialog, "dialog-footer") as HTMLElement
        expect(within(footer).getAllByRole("button").map((button) => button.textContent)).toEqual([
            "Disconnect…",
            "Cancel",
            "Save changes",
        ])
        expect(slot(footer, "dialog-footer-start")).toHaveClass("sm:mr-auto")
    })

    it("uses the close-button clearance without the right padding when the close button is hidden", () => {
        render(
            <Dialog open>
                <DialogContent layout="sectioned" showCloseButton={false}>
                    <DialogHeader>
                        <DialogTitle>Appointment type</DialogTitle>
                    </DialogHeader>
                </DialogContent>
            </Dialog>,
        )

        const header = slot(screen.getByRole("dialog"), "dialog-header")
        expect(header).toHaveClass("pr-6")
        expect(header).not.toHaveClass("pr-14")
    })
})

describe("DialogContent default layout", () => {
    it("scrolls the whole dialog when it is taller than the viewport", () => {
        render(
            <Dialog open>
                <DialogContent>
                    <DialogTitle>New appointment type</DialogTitle>
                </DialogContent>
            </Dialog>,
        )

        const dialog = screen.getByRole("dialog")
        expect(dialog).toHaveAttribute("data-layout", "default")
        expect(dialog).toHaveClass("grid", "p-6", "max-h-[calc(100dvh-2rem)]", "overflow-y-auto")
    })

    it("keeps header content clear of the close button", () => {
        render(
            <Dialog open>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>AI Configuration</DialogTitle>
                        <Badge>Disabled</Badge>
                    </DialogHeader>
                </DialogContent>
            </Dialog>,
        )

        expect(slot(screen.getByRole("dialog"), "dialog-header")).toHaveClass("pr-8")
    })

    it("lets a call-site padding replace the clearance", () => {
        render(
            <Dialog open>
                <DialogContent>
                    <DialogHeader className="pr-12">
                        <DialogTitle>Appointment details</DialogTitle>
                    </DialogHeader>
                </DialogContent>
            </Dialog>,
        )

        const header = slot(screen.getByRole("dialog"), "dialog-header")
        expect(header).toHaveClass("pr-12")
        expect(header).not.toHaveClass("pr-8")
    })

    it("drops the clearance when the close button is hidden", () => {
        render(
            <Dialog open>
                <DialogContent showCloseButton={false}>
                    <DialogHeader>
                        <DialogTitle>Manage appointment</DialogTitle>
                    </DialogHeader>
                </DialogContent>
            </Dialog>,
        )

        expect(slot(screen.getByRole("dialog"), "dialog-header")?.className).not.toMatch(/(^|\s)pr-/)
    })

    it("adds no padding to DialogBody or DialogFooter outside the sectioned layout", () => {
        render(
            <Dialog open>
                <DialogContent>
                    <DialogTitle>Edit task</DialogTitle>
                    <DialogBody>Body</DialogBody>
                    <DialogFooter>
                        <Button>Save</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>,
        )

        const dialog = screen.getByRole("dialog")
        expect(slot(dialog, "dialog-body")).not.toHaveClass("overflow-y-auto", "px-6")
        expect(slot(dialog, "dialog-footer")).not.toHaveClass("border-t", "px-6")
    })
})

describe("nested confirm over a dialog", () => {
    it("dims the parent dialog while the nested confirm is open", () => {
        render(
            <Dialog open>
                <DialogContent>
                    <DialogTitle>Edit task</DialogTitle>
                    <AlertDialog open>
                        <AlertDialogContent>
                            <AlertDialogTitle>Delete task?</AlertDialogTitle>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction variant="destructive">Delete</AlertDialogAction>
                        </AlertDialogContent>
                    </AlertDialog>
                </DialogContent>
            </Dialog>,
        )

        // The parent is inert while the confirm is open, so it is not in the accessibility tree.
        const parent = document.body.querySelector('[data-slot="dialog-content"]')
        expect(parent).toHaveAttribute("data-nested-dialog-open")
        expect(parent).toHaveClass("data-nested-dialog-open:brightness-50")
    })
})
