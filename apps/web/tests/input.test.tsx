import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { Input } from "@/components/ui/input"

describe("Input", () => {
    it("uses Base UI value-change semantics while preserving native change events", () => {
        const handleChange = vi.fn()
        const handleValueChange = vi.fn()

        render(
            <Input
                aria-label="Job title"
                onChange={handleChange}
                onValueChange={handleValueChange}
            />,
        )

        const input = screen.getByRole("textbox", { name: "Job title" })
        fireEvent.change(input, { target: { value: "Case Manager" } })

        expect(handleChange).toHaveBeenCalledOnce()
        expect(handleValueChange).toHaveBeenCalledWith("Case Manager", expect.any(Object))
        expect(input).toHaveAttribute("data-slot", "input")
    })
})
