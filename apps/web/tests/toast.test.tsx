import { act, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { toast, Toaster } from "@/components/ui/toast"

describe("Base UI toast adapter", () => {
    afterEach(() => {
        act(() => toast.dismiss())
    })

    it("preserves message, description, type, duration, and action behavior", () => {
        const onUndo = vi.fn()
        render(<Toaster timeout={0} />)

        act(() => {
            toast.success("Stage updated", {
                description: "The surrogate moved to qualified.",
                duration: 10_000,
                action: { label: "Undo", onClick: onUndo },
            })
        })

        const title = screen.getByText("Stage updated")
        expect(title.closest('[data-slot="toast"]')).toHaveAttribute("data-type", "success")
        expect(screen.getByText("The surrogate moved to qualified.")).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Undo" }))
        expect(onUndo).toHaveBeenCalledOnce()
    })
})
