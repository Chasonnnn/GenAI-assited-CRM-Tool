import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import { PaginationJump } from "@/components/ui/pagination-jump"

describe("PaginationJump", () => {
    it("resets the draft input when the current page changes externally", () => {
        const handlePageChange = vi.fn()
        const { rerender } = render(<PaginationJump page={3} totalPages={12} onPageChange={handlePageChange} />)

        const input = screen.getByLabelText("Page number")
        fireEvent.change(input, { target: { value: "9" } })
        expect(input).toHaveValue(9)

        rerender(<PaginationJump page={4} totalPages={12} onPageChange={handlePageChange} />)

        expect(screen.getByLabelText("Page number")).toHaveValue(4)
    })
})
