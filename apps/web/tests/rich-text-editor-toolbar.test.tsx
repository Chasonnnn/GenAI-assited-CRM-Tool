import { Editor } from "@tiptap/react"
import StarterKit from "@tiptap/starter-kit"
import TextAlign from "@tiptap/extension-text-align"
import { act, render, screen, within } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { RichTextEditorToolbar } from "@/components/rich-text-editor-toolbar"

const editors: Editor[] = []

afterEach(() => {
    for (const editor of editors.splice(0)) editor.destroy()
})

function createEditor() {
    const editor = new Editor({
        extensions: [StarterKit, TextAlign.configure({ types: ["paragraph"] })],
        content: "<p><strong>Bold text</strong> plain text</p>",
    })
    editors.push(editor)
    return editor
}

function renderToolbar(editor = createEditor()) {
    return render(
        <RichTextEditorToolbar
            editor={editor}
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
    it("updates formatting, alignment, and history controls when the editor changes", () => {
        const editor = createEditor()
        renderToolbar(editor)

        act(() => { editor.commands.setTextSelection(2) })
        expect(screen.getByRole("button", { name: "Bold" })).toHaveAttribute("aria-pressed", "true")

        act(() => { editor.commands.setTextSelection(13) })
        expect(screen.getByRole("button", { name: "Bold" })).toHaveAttribute("aria-pressed", "false")

        act(() => { editor.commands.setTextAlign("center") })
        expect(screen.getByRole("button", { name: "Align Center" })).toHaveAttribute("aria-pressed", "true")
        expect(screen.getByRole("button", { name: "Undo" })).toBeEnabled()

        act(() => { editor.commands.undo() })
        expect(screen.getByRole("button", { name: "Align Center" })).toHaveAttribute("aria-pressed", "false")
        expect(screen.getByRole("button", { name: "Redo" })).toBeEnabled()

        act(() => { editor.commands.redo() })
        expect(screen.getByRole("button", { name: "Align Center" })).toHaveAttribute("aria-pressed", "true")
        expect(screen.getByRole("button", { name: "Redo" })).toBeDisabled()
    })

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
