import { fireEvent, render, screen } from "@testing-library/react"
import { CalendarIcon, HeartHandshakeIcon } from "lucide-react"
import { describe, expect, it, vi } from "vitest"

import { EmptyState } from "@/components/empty-state"
import { Button } from "@/components/ui/button"

describe("EmptyState", () => {
    it("renders a first-run state with a neutral decorative icon and no action", () => {
        const { container } = render(<EmptyState icon={CalendarIcon} title="No past appointments" />)

        expect(screen.getByText("No past appointments")).toBeInTheDocument()
        expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true")
        expect(container.querySelector("[data-slot=empty-state]")).not.toHaveTextContent(/clear filters/i)
        expect(screen.queryByRole("button")).not.toBeInTheDocument()
    })

    it("renders the single create action for a first-run state", () => {
        const onCreate = vi.fn()
        render(
            <EmptyState
                icon={CalendarIcon}
                title="No appointment types"
                action={<Button onClick={onCreate}>New appointment type</Button>}
            />
        )

        fireEvent.click(screen.getByRole("button", { name: "New appointment type" }))
        expect(onCreate).toHaveBeenCalledOnce()
    })

    it("renders Clear filters for a filtered state", () => {
        const onClearFilters = vi.fn()
        render(
            <EmptyState
                icon={HeartHandshakeIcon}
                title="No matches found"
                onClearFilters={onClearFilters}
            />
        )

        fireEvent.click(screen.getByRole("button", { name: "Clear filters" }))
        expect(onClearFilters).toHaveBeenCalledOnce()
        expect(screen.getAllByRole("button")).toHaveLength(1)
    })

    it("keeps a heading when the replaced markup used one", () => {
        const { unmount } = render(<EmptyState icon={CalendarIcon} title="No past appointments" />)
        expect(screen.queryByRole("heading")).not.toBeInTheDocument()
        unmount()

        render(<EmptyState icon={HeartHandshakeIcon} title="No matches found" headingLevel={2} onClearFilters={vi.fn()} />)
        expect(screen.getByRole("heading", { level: 2, name: "No matches found" })).toBeInTheDocument()
    })
})
