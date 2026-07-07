import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import type { ReactNode } from "react"

vi.mock("@/components/ui/select", () => ({
    Select: ({
        value,
        onValueChange,
        children,
    }: {
        value?: string
        onValueChange: (value: string) => void
        children: ReactNode
    }) => (
        <select value={value ?? ""} onChange={(event) => onValueChange(event.target.value)}>
            {children}
        </select>
    ),
    SelectTrigger: ({ children }: { children: ReactNode }) => <>{children}</>,
    SelectValue: () => null,
    SelectContent: ({ children }: { children: ReactNode }) => <>{children}</>,
    SelectItem: ({ value, children }: { value: string; children: ReactNode }) => (
        <option value={value}>{children}</option>
    ),
}))

import { AddSurrogateTaskDialog } from "@/components/surrogates/AddSurrogateTaskDialog"

function renderDialog(onSubmit = vi.fn().mockResolvedValue(undefined)) {
    const onOpenChange = vi.fn()
    render(
        <AddSurrogateTaskDialog
            open
            onOpenChange={onOpenChange}
            onSubmit={onSubmit}
            isPending={false}
            surrogateName="Alex Chen"
        />
    )
    return { onOpenChange, onSubmit }
}

describe("AddSurrogateTaskDialog", () => {
    it("requires a due date before creating recurring tasks", async () => {
        const { onSubmit } = renderDialog()

        fireEvent.change(screen.getByLabelText("Title *"), {
            target: { value: "Follow up" },
        })
        const repeatSelect = screen.getAllByRole("combobox")[1]
        fireEvent.change(repeatSelect, { target: { value: "weekly" } })
        fireEvent.click(screen.getByRole("button", { name: "Create Task" }))

        expect(await screen.findByText("Recurring tasks require a due date.")).toBeInTheDocument()
        expect(onSubmit).not.toHaveBeenCalled()
    })

    it("submits trimmed task data and closes after creation", async () => {
        const onSubmit = vi.fn().mockResolvedValue(undefined)
        const { onOpenChange } = renderDialog(onSubmit)

        fireEvent.change(screen.getByLabelText("Title *"), {
            target: { value: "  Review records  " },
        })
        fireEvent.change(screen.getByLabelText("Description"), {
            target: { value: "  Check the latest upload.  " },
        })
        fireEvent.change(screen.getByLabelText("Due Date"), {
            target: { value: "2026-08-12" },
        })
        fireEvent.change(screen.getByLabelText("Due Time"), {
            target: { value: "09:30" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Create Task" }))

        await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1))
        expect(onSubmit).toHaveBeenCalledWith({
            title: "Review records",
            task_type: "other",
            recurrence: "none",
            description: "Check the latest upload.",
            due_date: "2026-08-12",
            due_time: "09:30",
        })
        expect(onOpenChange).toHaveBeenCalledWith(false)
    })
})
