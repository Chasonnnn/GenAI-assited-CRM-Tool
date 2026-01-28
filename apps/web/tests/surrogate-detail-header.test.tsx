import { describe, expect, it, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { SurrogateDetailHeader } from "@/components/surrogates/detail/SurrogateDetailHeader"

describe("SurrogateDetailHeader", () => {
    it("renders surrogate number and triggers back", () => {
        const onBack = vi.fn()

        render(
            <SurrogateDetailHeader
                surrogateNumber="S12345"
                statusLabel="New Unread"
                statusColor="#111111"
                isArchived={false}
                onBack={onBack}
            >
                <div>Actions</div>
            </SurrogateDetailHeader>
        )

        expect(screen.getByText("Surrogate #S12345")).toBeInTheDocument()
        expect(screen.getByText("New Unread")).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Back" }))
        expect(onBack).toHaveBeenCalled()
    })
})
