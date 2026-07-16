import { render, screen } from "@testing-library/react"
import { useRef } from "react"
import { describe, expect, it, vi } from "vitest"

import { useFocusWhen } from "@/lib/hooks/use-focus-when"

function FocusHarness({ active, select = false }: { active: boolean; select?: boolean }) {
    const inputRef = useRef<HTMLInputElement>(null)
    useFocusWhen(inputRef, active, { select })
    return <input ref={inputRef} aria-label="Draft" defaultValue="Draft value" />
}

describe("useFocusWhen", () => {
    it("focuses only when active becomes true", () => {
        const view = render(<FocusHarness active={false} />)
        const input = screen.getByRole("textbox", { name: "Draft" })

        expect(input).not.toHaveFocus()
        view.rerender(<FocusHarness active />)
        expect(input).toHaveFocus()
    })

    it("optionally selects the focused input text", () => {
        const selectSpy = vi.spyOn(HTMLInputElement.prototype, "select")

        render(<FocusHarness active select />)

        expect(selectSpy).toHaveBeenCalledTimes(1)
    })
})
