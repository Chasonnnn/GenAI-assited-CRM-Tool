import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"

import { SegmentedControl, SegmentedControlItem } from "@/components/ui/segmented-control"

function renderControl(props: { readOnly?: boolean; disabled?: boolean } = {}) {
    const onValueChange = vi.fn()
    render(
        <SegmentedControl aria-label="Mode" value="auto" onValueChange={onValueChange} {...props}>
            <SegmentedControlItem value="auto">Automatically</SegmentedControlItem>
            <SegmentedControlItem value="review">After review</SegmentedControlItem>
            <SegmentedControlItem value="off">Off</SegmentedControlItem>
        </SegmentedControl>,
    )
    return {
        onValueChange,
        selected: screen.getByRole("radio", { name: "Automatically" }),
        review: screen.getByRole("radio", { name: "After review" }),
        off: screen.getByRole("radio", { name: "Off" }),
    }
}

/** Tries a click, Enter, Space and the arrow keys on unselected segments. */
async function tryToChange({ selected, review, off }: ReturnType<typeof renderControl>) {
    fireEvent.click(review)
    fireEvent.keyDown(off, { key: "Enter" })
    fireEvent.keyDown(off, { key: " " })
    fireEvent.keyUp(off, { key: " " })
    selected.focus()
    fireEvent.keyDown(selected, { key: "ArrowRight" })
    fireEvent.keyDown(selected, { key: "ArrowLeft" })
    await new Promise((resolve) => setTimeout(resolve, 0))
}

describe("SegmentedControl", () => {
    it("selects with a click, Enter and Space when editable", async () => {
        const control = renderControl()

        fireEvent.click(control.review)
        expect(control.onValueChange).toHaveBeenLastCalledWith("review", expect.anything())
        fireEvent.keyDown(control.off, { key: "Enter" })
        expect(control.onValueChange).toHaveBeenLastCalledWith("off", expect.anything())
        fireEvent.keyDown(control.review, { key: " " })
        fireEvent.keyUp(control.review, { key: " " })
        await waitFor(() => expect(control.onValueChange).toHaveBeenCalledTimes(3))
    })

    it.each([
        ["readOnly", { readOnly: true }, "aria-readonly"],
        ["disabled", { disabled: true }, "aria-disabled"],
    ] as const)("keeps the selection when %s", async (_name, props, groupAttribute) => {
        const control = renderControl(props)
        expect(screen.getByRole("radiogroup", { name: "Mode" })).toHaveAttribute(groupAttribute, "true")

        await tryToChange(control)

        expect(control.onValueChange).not.toHaveBeenCalled()
        expect(control.selected).toHaveAttribute("aria-checked", "true")
        expect(control.review).toHaveAttribute("aria-checked", "false")
        expect(control.off).toHaveAttribute("aria-checked", "false")
    })
})
