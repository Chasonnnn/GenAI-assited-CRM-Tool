import * as React from "react"
import { render } from "@testing-library/react"
import { describe, expect, it, vi, afterEach } from "vitest"

import { SelectionPopover } from "@/components/surrogates/interviews/SelectionPopover"

function SelectionPopoverHost({
    onSelectionStateChange,
}: {
    onSelectionStateChange: (active: boolean) => void
}) {
    const containerRef = React.useRef<HTMLDivElement>(null)

    return (
        <div>
            <div ref={containerRef}>Transcript text</div>
            <SelectionPopover
                containerRef={containerRef}
                onAddComment={vi.fn()}
                onSelectionStateChange={onSelectionStateChange}
            />
        </div>
    )
}

describe("SelectionPopover document listeners", () => {
    afterEach(() => {
        vi.restoreAllMocks()
    })

    it("keeps document listeners stable when parent callbacks change", () => {
        const addListenerSpy = vi.spyOn(document, "addEventListener")
        const removeListenerSpy = vi.spyOn(document, "removeEventListener")

        const { rerender } = render(
            <SelectionPopoverHost onSelectionStateChange={() => undefined} />
        )

        const initialSelectionListeners = addListenerSpy.mock.calls.filter(
            ([event]) => event === "selectionchange"
        ).length
        const initialMouseDownListeners = addListenerSpy.mock.calls.filter(
            ([event]) => event === "mousedown"
        ).length
        const initialMouseUpListeners = addListenerSpy.mock.calls.filter(
            ([event]) => event === "mouseup"
        ).length

        rerender(<SelectionPopoverHost onSelectionStateChange={() => undefined} />)

        expect(
            addListenerSpy.mock.calls.filter(([event]) => event === "selectionchange")
        ).toHaveLength(initialSelectionListeners)
        expect(
            addListenerSpy.mock.calls.filter(([event]) => event === "mousedown")
        ).toHaveLength(initialMouseDownListeners)
        expect(
            addListenerSpy.mock.calls.filter(([event]) => event === "mouseup")
        ).toHaveLength(initialMouseUpListeners)
        expect(removeListenerSpy).not.toHaveBeenCalledWith(
            "selectionchange",
            expect.any(Function)
        )
    })
})
