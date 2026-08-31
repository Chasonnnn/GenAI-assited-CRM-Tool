import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}))

import { TaskItem } from "@/components/appointments/UnifiedCalendar"
import type { TaskListItem } from "@/lib/types/task"

describe("calendar donor task presentation", () => {
    it("renders the donor as a sibling link without swallowing the task action", () => {
        const onClick = vi.fn()
        const task = {
            id: "task-1",
            title: "Call donor",
            donor_id: "donor-1",
            donor_number: "D10001",
            donor_type: "sperm",
            donor_name: "Alex Morgan",
            surrogate_id: null,
            intended_parent_id: null,
            due_time: "09:00:00",
        } as TaskListItem

        render(<TaskItem task={task} onClick={onClick} />)

        const donorLink = screen.getByRole("link", { name: "Sperm Donor D10001" })
        expect(donorLink).toHaveAttribute("href", "/donors/donor-1")
        const taskButton = screen.getByRole("button", { name: /Call donor/ })
        expect(taskButton).not.toContainElement(donorLink)
        fireEvent.click(taskButton)
        expect(onClick).toHaveBeenCalledWith(task)
    })
})
