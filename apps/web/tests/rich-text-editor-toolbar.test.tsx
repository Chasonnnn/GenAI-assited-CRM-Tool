import type { Editor } from "@tiptap/react"
import { render, screen, within } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { RichTextEditorToolbar } from "@/components/rich-text-editor-toolbar"

function createEditor(): Editor {
    return {
        isActive: () => false,
        can: () => ({ undo: () => false, redo: () => false }),
        getAttributes: () => ({}),
    } as unknown as Editor
}

function renderToolbar() {
    return render(
        <RichTextEditorToolbar
            editor={createEditor()}
            enableImages
            enableEmojiPicker={false}
            emojiOpen={false}
            onEmojiOpenChange={() => {}}
            onInsertEmoji={() => {}}
            onSubmit={undefined}
            submitLabel="Submit"
            isSubmitting={false}
        />,
    )
}

describe("RichTextEditorToolbar", () => {
    it("sizes every control as the same 32px square", () => {
        renderToolbar()

        for (const name of ["Bold", "Bullet List", "Add Link", "Insert Image", "Align Left", "Undo", "Redo"]) {
            expect(screen.getByRole("button", { name })).toHaveClass("size-8", "p-0")
        }
    })

    it("wraps whole groups, each led by its own divider, so no divider ends a row", () => {
        const { container } = renderToolbar()

        const groups = screen.getAllByRole("group")
        expect(groups.map((group) => group.getAttribute("aria-label"))).toEqual([
            "Text style",
            "Lists",
            "Insert",
            "Alignment",
            "History",
        ])
        for (const group of groups) {
            expect(group.firstElementChild).toHaveAttribute("aria-hidden", "true")
            expect(group.lastElementChild).not.toHaveAttribute("aria-hidden")
        }
        expect(within(groups[4]!).getByRole("button", { name: "Undo" })).toBeInTheDocument()

        const row = groups[0]!.parentElement!
        expect(row).toHaveClass("flex-wrap", "-ml-[13px]")
        expect(Array.from(row.children).every((child) => child.getAttribute("role") === "group")).toBe(true)
        expect(container.firstElementChild).toHaveClass("overflow-hidden")
    })
})
