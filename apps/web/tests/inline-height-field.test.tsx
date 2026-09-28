import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { InlineHeightField } from "@/components/records/RecordProfileFields"

function openOptions() {
    const listbox = screen.getAllByRole("listbox").at(-1)!
    return within(listbox).getAllByRole("option").map((option) => option.textContent)
}

function pick(name: string) {
    const option = screen.getByRole("option", { name })
    fireEvent.mouseMove(option)
    fireEvent.click(option)
}

describe("InlineHeightField selects", () => {
    it("offers no ft/in placeholder rows and keeps inches disabled until feet is chosen", () => {
        render(<InlineHeightField value={null} onSave={vi.fn().mockResolvedValue(undefined)} />)

        fireEvent.click(screen.getByRole("button", { name: "Edit Height" }))
        const inches = screen.getByRole("combobox", { name: "Height inches" })
        expect(inches).toBeDisabled()

        fireEvent.click(screen.getByRole("combobox", { name: "Height feet" }))
        const feetOptions = openOptions()
        expect(feetOptions[0]).toBe("Not provided")
        expect(feetOptions).not.toContain("ft")
        pick("5 ft")

        expect(inches).not.toBeDisabled()
        fireEvent.click(inches)
        const inchOptions = openOptions()
        expect(inchOptions).not.toContain("in")
        expect(inchOptions[0]).toBe("0 in")
    })

    it("clears the whole height when feet is set to Not provided", async () => {
        const onSave = vi.fn().mockResolvedValue(undefined)
        render(<InlineHeightField value={5.5} onSave={onSave} />)

        fireEvent.click(screen.getByRole("button", { name: "Edit Height" }))
        fireEvent.click(screen.getByRole("combobox", { name: "Height feet" }))
        pick("Not provided")

        expect(screen.getByRole("combobox", { name: "Height inches" })).toBeDisabled()
        fireEvent.click(screen.getByRole("button", { name: "Save Height" }))

        await waitFor(() => expect(onSave).toHaveBeenCalledWith(null))
    })
})
