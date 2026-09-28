import * as React from "react"
import { act, render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { SelectionPopover } from "@/components/surrogates/interviews/SelectionPopover"

function SelectionPopoverHost() {
    const containerRef = React.useRef<HTMLDivElement>(null)

    return (
        <div>
            <div ref={containerRef}>Transcript text</div>
            <SelectionPopover containerRef={containerRef} onAddComment={() => undefined} />
        </div>
    )
}

async function showPopover() {
    render(<SelectionPopoverHost />)
    const textNode = screen.getByText("Transcript text").firstChild
    expect(textNode).not.toBeNull()

    const range = document.createRange()
    range.setStart(textNode!, 0)
    range.setEnd(textNode!, "Transcript".length)
    Object.defineProperty(range, "getClientRects", {
        value: () => [
            {
                left: 20,
                top: 40,
                width: 100,
                height: 20,
                right: 120,
                bottom: 60,
                x: 20,
                y: 40,
                toJSON: () => ({}),
            },
        ],
    })

    const selection = window.getSelection()
    selection?.removeAllRanges()
    selection?.addRange(range)
    act(() => {
        document.dispatchEvent(new Event("selectionchange"))
    })

    const button = await screen.findByRole("button", { name: /add comment/i })
    return button.parentElement!
}

describe("SelectionPopover position", () => {
    it("centers over the selection with one translate that the enter animation does not replace", async () => {
        const popover = await showPopover()

        expect(popover.style.left).toBe("70px")
        expect(popover.style.top).toBe("32px")
        // The enter keyframe animates transform, so positioning must live on the translate property.
        expect(popover.style.transform).toBe("")
        expect(popover.className).not.toMatch(/(^|\s)transform(\s|$)/)
        expect(popover).toHaveClass("-translate-x-1/2", "-translate-y-full", "animate-in")
    })
})
