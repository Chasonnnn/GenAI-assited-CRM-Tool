import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { CancelMatchDialog } from "@/components/matches/CancelMatchDialog"
import { DeclineMatchDialog } from "@/components/matches/DeclineMatchDialog"

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
