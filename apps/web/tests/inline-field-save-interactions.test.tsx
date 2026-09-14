import { act, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { InlineEditField } from "@/components/inline-edit-field"

afterEach(() => vi.useRealTimers())

function edit(onSave: (value: string) => Promise<void>) {
    render(<InlineEditField value="Original" label="Name" onSave={onSave} />)
    fireEvent.click(screen.getByRole("button", { name: "Edit Name" }))
    const input = screen.getByRole("textbox", { name: "Name" })
    fireEvent.change(input, { target: { value: "Updated" } })
    return input
}

describe("InlineEditField save interactions", () => {
    it("saves once when focus moves to the Save button", async () => {
        vi.useFakeTimers()
        const onSave = vi.fn().mockResolvedValue(undefined)
        const input = edit(onSave)
        const save = screen.getByRole("button", { name: "Save Name" })
        fireEvent.blur(input, { relatedTarget: save })
        fireEvent.click(save)
        await act(() => vi.advanceTimersByTimeAsync(250))
        expect(onSave).toHaveBeenCalledTimes(1)
        expect(onSave).toHaveBeenCalledWith("Updated")
    })

    it("does not save when focus moves to Cancel", async () => {
        vi.useFakeTimers()
        const onSave = vi.fn().mockResolvedValue(undefined)
        const input = edit(onSave)
        const cancel = screen.getByRole("button", { name: "Cancel Name" })
        fireEvent.blur(input, { relatedTarget: cancel })
        fireEvent.click(cancel)
        await act(() => vi.advanceTimersByTimeAsync(250))
        expect(onSave).not.toHaveBeenCalled()
        expect(screen.getByRole("button", { name: "Edit Name" })).toHaveTextContent("Original")
    })

    it("saves when focus leaves the field and allows retry after failure", async () => {
        vi.useFakeTimers()
        const onSave = vi.fn().mockRejectedValueOnce(new Error("Save unavailable")).mockResolvedValue(undefined)
        const input = edit(onSave)
        fireEvent.blur(input, { relatedTarget: document.body })
        await act(() => vi.advanceTimersByTimeAsync(250))
        expect(onSave).toHaveBeenCalledTimes(1)
        expect(screen.getByText("Save unavailable")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Save Name" }))
        await act(() => vi.advanceTimersByTimeAsync(250))
        expect(onSave).toHaveBeenCalledTimes(2)
        expect(screen.getByRole("button", { name: "Edit Name" })).toBeInTheDocument()
    })
})
