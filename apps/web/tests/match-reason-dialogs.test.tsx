import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { CancelMatchDialog } from "@/components/matches/CancelMatchDialog"
import { DeclineMatchDialog } from "@/components/matches/DeclineMatchDialog"
import { ApiError } from "@/lib/api"

describe("match reasons", () => {
    it.each([
        ["decline", DeclineMatchDialog, "Decline Match"],
        ["cancellation", CancelMatchDialog, "Request Cancellation"],
    ] as const)("requires a trimmed %s reason", async (_, Dialog, label) => {
        const confirm = vi.fn().mockResolvedValue(undefined)
        render(<Dialog open onOpenChange={vi.fn()} onConfirm={confirm} />)
        const button = screen.getByRole("button", { name: label })
        const input = screen.getByRole("textbox")
        expect(button).toBeDisabled()
        fireEvent.change(input, { target: { value: "   " } })
        expect(button).toBeDisabled()
        fireEvent.change(input, { target: { value: "  Family withdrew  " } })
        expect(button).toBeEnabled()
        fireEvent.click(button)
        await waitFor(() => expect(confirm).toHaveBeenCalledWith("Family withdrew"))
    })
})

describe("match reason dialog states", () => {
    it.each([
        ["decline", DeclineMatchDialog, "Declining"],
        ["cancellation", CancelMatchDialog, "Requesting"],
    ] as const)("disables the %s dialog while pending", (_, Dialog, pendingLabel) => {
        render(<Dialog open onOpenChange={vi.fn()} onConfirm={vi.fn()} isPending />)
        expect(screen.getByRole("button", { name: pendingLabel })).toBeDisabled()
        expect(screen.getByRole("button", { name: /^(Cancel|Back)$/ })).toBeDisabled()
    })

    it.each([
        ["decline", DeclineMatchDialog, "Decline Match"],
        ["cancellation", CancelMatchDialog, "Request Cancellation"],
    ] as const)("shows the server detail when the %s request fails and stays open", async (_, Dialog, label) => {
        const onOpenChange = vi.fn()
        const confirm = vi.fn().mockRejectedValue(new ApiError(400, "Bad Request", "Match is no longer under review"))
        render(<Dialog open onOpenChange={onOpenChange} onConfirm={confirm} />)
        fireEvent.change(screen.getByRole("textbox"), { target: { value: "Family withdrew" } })
        fireEvent.click(screen.getByRole("button", { name: label }))
        await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Match is no longer under review"))
        expect(onOpenChange).not.toHaveBeenCalledWith(false)
    })
})
