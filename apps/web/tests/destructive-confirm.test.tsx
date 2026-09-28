import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const toastMocks = vi.hoisted(() => ({
    success: vi.fn(() => "toast-id"),
    error: vi.fn(() => "toast-id"),
    dismiss: vi.fn(),
}))

vi.mock("@/components/ui/toast", () => ({
    toast: toastMocks,
}))

import { Button } from "@/components/ui/button"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { showUndoToast } from "@/components/ui/undo-toast"
import { ApiError } from "@/lib/api"

function deferred() {
    let resolve!: () => void
    let reject!: (reason: unknown) => void
    const promise = new Promise<void>((res, rej) => {
        resolve = res
        reject = rej
    })
    return { promise, resolve, reject }
}

function openFromTrigger(onConfirm: () => void | Promise<unknown>, onOpenChange = vi.fn()) {
    render(
        <ConfirmDialog
            trigger={<Button variant="destructive-ghost">Archive</Button>}
            title="Archive S10152?"
            description="The record leaves active lists."
            confirmLabel="Archive"
            onConfirm={onConfirm}
            onOpenChange={onOpenChange}
        />,
    )
    fireEvent.click(screen.getByRole("button", { name: "Archive" }))
    return screen.getByRole("alertdialog")
}

describe("ConfirmDialog", () => {
    beforeEach(() => {
        toastMocks.success.mockClear()
        toastMocks.error.mockClear()
    })

    it("opens from its trigger with the title, consequence and a destructive action", async () => {
        const dialog = openFromTrigger(vi.fn())

        expect(dialog).toHaveAccessibleName("Archive S10152?")
        expect(screen.getByText("The record leaves active lists.")).toBeInTheDocument()
        const confirm = screen.getAllByRole("button", { name: "Archive" }).at(-1)
        expect(confirm).toHaveClass("bg-destructive")
        await waitFor(() => {
            expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus()
        })
    })

    it("closes after a synchronous confirm", async () => {
        const onConfirm = vi.fn()
        const onOpenChange = vi.fn()
        openFromTrigger(onConfirm, onOpenChange)

        fireEvent.click(screen.getAllByRole("button", { name: "Archive" }).at(-1)!)

        expect(onConfirm).toHaveBeenCalledTimes(1)
        expect(onOpenChange).toHaveBeenLastCalledWith(false)
        await waitFor(() => {
            expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()
        })
    })

    it("closes on Escape when nothing is running", async () => {
        const onOpenChange = vi.fn()
        openFromTrigger(vi.fn(), onOpenChange)

        fireEvent.keyDown(screen.getByRole("alertdialog"), { key: "Escape" })

        expect(onOpenChange).toHaveBeenLastCalledWith(false)
        await waitFor(() => {
            expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()
        })
    })

    it("stays open and blocks dismissal while a promise runs, then closes when it resolves", async () => {
        const pending = deferred()
        openFromTrigger(() => pending.promise)

        const confirm = screen.getAllByRole("button", { name: "Archive" }).at(-1)!
        fireEvent.click(confirm)

        expect(confirm).toBeDisabled()
        expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled()
        fireEvent.keyDown(screen.getByRole("alertdialog"), { key: "Escape" })
        expect(screen.getByRole("alertdialog")).toBeInTheDocument()

        await act(async () => {
            pending.resolve()
            await pending.promise
        })

        await waitFor(() => {
            expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()
        })
    })

    it("shows the fallback inline and stays open when the server fails", async () => {
        const pending = deferred()
        openFromTrigger(() => pending.promise)

        fireEvent.click(screen.getAllByRole("button", { name: "Archive" }).at(-1)!)
        await act(async () => {
            pending.reject(new ApiError(500, "Internal Server Error"))
            await pending.promise.catch(() => undefined)
        })

        expect(await screen.findByRole("alert")).toHaveTextContent(
            "Couldn't complete this action. Try again.",
        )
        expect(screen.getByRole("alertdialog")).toBeInTheDocument()
        expect(screen.getAllByRole("button", { name: "Archive" }).at(-1)).toBeEnabled()
    })

    it("shows an API detail message for a client error", async () => {
        const pending = deferred()
        openFromTrigger(() => pending.promise)

        fireEvent.click(screen.getAllByRole("button", { name: "Archive" }).at(-1)!)
        await act(async () => {
            pending.reject(new ApiError(409, "Conflict", "Surrogate is already archived"))
            await pending.promise.catch(() => undefined)
        })

        expect(await screen.findByRole("alert")).toHaveTextContent("Surrogate is already archived")
    })

    it("uses the default variant for non-destructive commits and supports controlled open", () => {
        const onOpenChange = vi.fn()
        render(
            <ConfirmDialog
                open
                onOpenChange={onOpenChange}
                title="Send to 151 recipients now?"
                confirmLabel="Send to 151"
                confirmVariant="default"
                onConfirm={vi.fn()}
            />,
        )

        const confirm = screen.getByRole("button", { name: "Send to 151" })
        expect(confirm.className).toMatch(/bg-\[linear-gradient/)

        fireEvent.click(screen.getByRole("button", { name: "Cancel" }))
        expect(onOpenChange).toHaveBeenCalledWith(false)
    })

    it("clears the previous error when a controlled dialog opens again", async () => {
        const pending = deferred()
        const props = {
            title: "Delete Intake?",
            confirmLabel: "Delete",
            onConfirm: () => pending.promise,
        }
        const { rerender } = render(<ConfirmDialog open {...props} />)

        fireEvent.click(screen.getByRole("button", { name: "Delete" }))
        await act(async () => {
            pending.reject(new ApiError(500, "Internal Server Error"))
            await pending.promise.catch(() => undefined)
        })
        expect(await screen.findByRole("alert")).toBeInTheDocument()

        // The parent closes and reopens the dialog for another record without onOpenChange.
        rerender(<ConfirmDialog open={false} {...props} />)
        await waitFor(() => {
            expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()
        })
        rerender(<ConfirmDialog open {...props} title="Delete Screening?" />)

        expect(await screen.findByRole("alertdialog", { name: "Delete Screening?" })).toBeInTheDocument()
        expect(screen.queryByRole("alert")).not.toBeInTheDocument()
    })

    it("keeps the confirm button disabled while confirmDisabled is set", () => {
        render(
            <ConfirmDialog
                open
                title="Delete now?"
                confirmLabel="Delete now"
                confirmDisabled
                onConfirm={vi.fn()}
            />,
        )

        expect(screen.getByRole("button", { name: "Delete now" })).toBeDisabled()
    })
})

describe("showUndoToast", () => {
    beforeEach(() => {
        toastMocks.success.mockClear()
        toastMocks.error.mockClear()
        toastMocks.dismiss.mockClear()
    })

    function undoAction() {
        const [, options] = toastMocks.success.mock.calls.at(-1) as unknown as [
            string,
            { action: { label: string; onClick: () => void }; duration: number },
        ]
        return options
    }

    it("shows a success toast with an Undo action", () => {
        const onUndo = vi.fn()
        showUndoToast("Surrogate S10152 archived", onUndo)

        const options = undoAction()
        expect(toastMocks.success).toHaveBeenCalledWith("Surrogate S10152 archived", expect.any(Object))
        expect(options.action.label).toBe("Undo")
        expect(options.duration).toBeGreaterThanOrEqual(5_000)
    })

    it("closes the toast on Undo and runs the handler once", async () => {
        const onUndo = vi.fn().mockResolvedValue(undefined)
        showUndoToast("Surrogate S10152 archived", onUndo)

        const { onClick } = undoAction().action
        onClick()
        onClick()

        expect(toastMocks.dismiss).toHaveBeenCalledWith("toast-id")
        await waitFor(() => {
            expect(onUndo).toHaveBeenCalledTimes(1)
        })
        expect(toastMocks.error).not.toHaveBeenCalled()
    })

    it("runs the undo handler and reports a failed undo", async () => {
        const onUndo = vi.fn().mockRejectedValue(new ApiError(500, "Internal Server Error"))
        showUndoToast("Task completed", onUndo)

        undoAction().action.onClick()

        await waitFor(() => {
            expect(toastMocks.error).toHaveBeenCalledWith("Couldn't undo. Try again.")
        })
        expect(onUndo).toHaveBeenCalledTimes(1)
    })
})
