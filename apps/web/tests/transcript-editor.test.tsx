import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterAll, beforeAll, describe, expect, it } from "vitest"

import { TranscriptEditor } from "@/components/surrogates/interviews/TranscriptEditor"
import type { TipTapDoc } from "@/lib/api/interviews"

const content: TipTapDoc = {
    type: "doc",
    content: [{ type: "paragraph", content: [{ type: "text", text: "Transcript body" }] }],
}

const rangeGeometry = {
    getClientRects: Object.getOwnPropertyDescriptor(Range.prototype, "getClientRects"),
    getBoundingClientRect: Object.getOwnPropertyDescriptor(Range.prototype, "getBoundingClientRect"),
}

// JSDOM has no layout geometry; ProseMirror reads it when toolbar actions focus the editor.
beforeAll(() => {
    Object.defineProperties(Range.prototype, {
        getClientRects: { configurable: true, value: () => [new DOMRect()] },
        getBoundingClientRect: { configurable: true, value: () => new DOMRect() },
    })
})

afterAll(() => {
    for (const [name, descriptor] of Object.entries(rangeGeometry)) {
        if (descriptor) Object.defineProperty(Range.prototype, name, descriptor)
        else Reflect.deleteProperty(Range.prototype, name)
    }
})

describe("TranscriptEditor", () => {
    it("keeps heading and history controls synchronized with editing", async () => {
        render(<TranscriptEditor content={content} />)
        const heading = await screen.findByRole("button", { name: "Heading 1" })
        expect(heading).toHaveAttribute("aria-pressed", "false")

        fireEvent.click(heading)
        await waitFor(() => {
            expect(screen.getByRole("heading", { name: "Transcript body" })).toBeInTheDocument()
            expect(heading).toHaveAttribute("aria-pressed", "true")
            expect(screen.getByRole("button", { name: "Undo" })).toBeEnabled()
        })

        fireEvent.click(screen.getByRole("button", { name: "Undo" }))
        await waitFor(() => {
            expect(screen.queryByRole("heading", { name: "Transcript body" })).not.toBeInTheDocument()
            expect(heading).toHaveAttribute("aria-pressed", "false")
            expect(screen.getByRole("button", { name: "Redo" })).toBeEnabled()
        })

        fireEvent.click(screen.getByRole("button", { name: "Redo" }))
        await waitFor(() => {
            expect(heading).toHaveAttribute("aria-pressed", "true")
            expect(screen.getByRole("button", { name: "Redo" })).toBeDisabled()
        })
    })

    it("shows read-only content without editing controls", async () => {
        render(<TranscriptEditor content={content} readOnly />)
        expect(await screen.findByText("Transcript body")).toBeInTheDocument()
        expect(screen.queryByRole("button")).not.toBeInTheDocument()
        expect(screen.getByText("Transcript body").closest("[contenteditable]"))
            .toHaveAttribute("contenteditable", "false")
    })
})
