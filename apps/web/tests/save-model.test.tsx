import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { SaveBar, SaveStatus } from "@/components/ui/save-bar"

function renderSaveBar(props: Partial<React.ComponentProps<typeof SaveBar>> = {}) {
    const handlers = { onSave: vi.fn(), onDiscard: vi.fn() }
    const result = render(<SaveBar dirty {...handlers} {...props} />)
    return { ...result, ...handlers }
}

describe("SaveBar", () => {
    it("renders only an empty live region while the editor is clean", () => {
        renderSaveBar({ dirty: false })

        expect(screen.queryByRole("region", { name: "Unsaved changes" })).not.toBeInTheDocument()
        expect(screen.queryByRole("button")).not.toBeInTheDocument()
        expect(screen.getByRole("status")).toBeEmptyDOMElement()
    })

    it("keeps the same live region mounted so the bar's first appearance is announced", () => {
        const { rerender, onSave, onDiscard } = renderSaveBar({ dirty: false })
        const status = screen.getByRole("status")
        expect(status).toBeEmptyDOMElement()

        rerender(<SaveBar dirty changeCount={2} errorCount={1} onSave={onSave} onDiscard={onDiscard} />)
        expect(screen.getByRole("status")).toBe(status)
        expect(status).toHaveTextContent("2 unsaved changes, 1 error")
        expect(screen.getByRole("region", { name: "Unsaved changes" })).toBeInTheDocument()

        rerender(<SaveBar dirty={false} onSave={onSave} onDiscard={onDiscard} />)
        expect(screen.getByRole("status")).toBe(status)
        expect(status).toBeEmptyDOMElement()
        expect(screen.getAllByRole("status")).toHaveLength(1)
    })

    it("shows the change count with Discard and Save when dirty", () => {
        const { onSave, onDiscard } = renderSaveBar({ changeCount: 3 })

        expect(screen.getByRole("region", { name: "Unsaved changes" })).toHaveClass("sticky", "bottom-0")
        expect(screen.getByRole("status")).toHaveTextContent("3 unsaved changes")

        fireEvent.click(screen.getByRole("button", { name: "Save changes" }))
        fireEvent.click(screen.getByRole("button", { name: "Discard" }))
        expect(onSave).toHaveBeenCalledTimes(1)
        expect(onDiscard).toHaveBeenCalledTimes(1)
    })

    it("uses singular and uncounted labels", () => {
        const { rerender, onSave, onDiscard } = renderSaveBar({ changeCount: 1 })
        expect(screen.getByRole("status")).toHaveTextContent("1 unsaved change")

        rerender(<SaveBar dirty onSave={onSave} onDiscard={onDiscard} />)
        expect(screen.getByRole("status")).toHaveTextContent("Unsaved changes")
    })

    it("disables Save while errors exist and links the error count to the first error", () => {
        const onErrorsClick = vi.fn()
        renderSaveBar({ changeCount: 3, errorCount: 1, onErrorsClick })

        expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled()
        fireEvent.click(screen.getByRole("button", { name: "1 error" }))
        expect(onErrorsClick).toHaveBeenCalledTimes(1)
    })

    it("shows the error count as text without a handler", () => {
        renderSaveBar({ errorCount: 2 })

        expect(screen.getByText("2 errors")).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "2 errors" })).not.toBeInTheDocument()
    })

    it("stays visible and locks both actions while saving", () => {
        renderSaveBar({ dirty: false, saving: true })

        expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled()
        expect(screen.getByRole("button", { name: "Discard" })).toBeDisabled()
    })
})

describe("SaveStatus", () => {
    it("keeps one live region and swaps its content per state", () => {
        const { rerender } = render(<SaveStatus state="idle" />)
        const status = screen.getByRole("status")
        expect(status).toBeEmptyDOMElement()

        rerender(<SaveStatus state="saving" />)
        expect(screen.getByRole("status")).toBe(status)
        expect(status).toHaveTextContent("Saving")

        rerender(<SaveStatus state="saved" />)
        expect(status).toHaveTextContent("Saved")
        expect(status.querySelector(".text-success")).not.toBeNull()

        rerender(<SaveStatus state="error" />)
        expect(status).toHaveTextContent("Not saved")
    })
})
