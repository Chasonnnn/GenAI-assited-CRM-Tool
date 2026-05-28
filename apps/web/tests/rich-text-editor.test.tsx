import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { createRef } from "react"

import { RichTextEditor, type RichTextEditorHandle } from "@/components/rich-text-editor"

const mockEmojiPickerProps = vi.fn()

const chain = {
    focus: vi.fn(() => chain),
    toggleBold: vi.fn(() => chain),
    toggleItalic: vi.fn(() => chain),
    toggleUnderline: vi.fn(() => chain),
    toggleBulletList: vi.fn(() => chain),
    toggleOrderedList: vi.fn(() => chain),
    extendMarkRange: vi.fn(() => chain),
    unsetLink: vi.fn(() => chain),
    setLink: vi.fn(() => chain),
    setImage: vi.fn(() => chain),
    setTextAlign: vi.fn(() => chain),
    undo: vi.fn(() => chain),
    redo: vi.fn(() => chain),
    insertContent: vi.fn(() => chain),
    run: vi.fn(() => true),
}

const mockEditor = {
    chain: vi.fn(() => chain),
    isActive: vi.fn(() => false),
    can: vi.fn(() => ({ undo: () => false, redo: () => false })),
    commands: {
        setContent: vi.fn(),
        clearContent: vi.fn(),
    },
    getHTML: vi.fn(() => "<p>hello</p>"),
    getAttributes: vi.fn(() => ({ href: "" })),
}

vi.mock("@tiptap/react", () => ({
    useEditor: () => mockEditor,
    EditorContent: () => <div data-testid="editor-content" />,
}))

vi.mock("@tiptap/starter-kit", () => ({
    default: { configure: () => ({}) },
}))

vi.mock("@tiptap/extension-placeholder", () => ({
    default: { configure: () => ({}) },
}))

vi.mock("@tiptap/extension-text-align", () => ({
    default: { configure: () => ({}) },
}))

vi.mock("@tiptap/extension-image", () => ({
    default: { configure: () => ({}) },
}))

vi.mock("emoji-picker-react", () => ({
    default: (props: Record<string, unknown>) => {
        mockEmojiPickerProps(props)
        return (
            <div data-testid="emoji-picker">
                <button
                    type="button"
                    aria-label="pick-emoji"
                    onClick={() =>
                        (props as { onEmojiClick?: (data: { emoji: string }) => void }).onEmojiClick?.({
                            emoji: "🚀",
                        })
                    }
                >
                    🚀
                </button>
            </div>
        )
    },
    EmojiStyle: { NATIVE: "native" },
    SuggestionMode: { FREQUENT: "frequent", RECENT: "recent" },
}))

describe("RichTextEditor", () => {
    beforeEach(() => {
        mockEmojiPickerProps.mockClear()
        chain.insertContent.mockClear()
    })

    it("shows an emoji insert control when enabled", async () => {
        render(<RichTextEditor content="<p>hello</p>" enableEmojiPicker />)

        await waitFor(() => {
            expect(screen.getByLabelText("Bold")).toBeInTheDocument()
        })

        expect(screen.getByLabelText("Insert Emoji")).toBeInTheDocument()
    })

    it("does not show emoji control by default", async () => {
        render(<RichTextEditor content="<p>hello</p>" />)

        await waitFor(() => {
            expect(screen.getByLabelText("Bold")).toBeInTheDocument()
        })

        expect(screen.queryByLabelText("Insert Emoji")).not.toBeInTheDocument()
    })

    it("labels undo and redo toolbar buttons", async () => {
        render(<RichTextEditor content="<p>hello</p>" />)

        await waitFor(() => {
            expect(screen.getByLabelText("Bold")).toBeInTheDocument()
        })

        expect(screen.getByRole("button", { name: "Undo" })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Redo" })).toBeInTheDocument()
    })

    it("inserts selected emoji into the editor", async () => {
        render(<RichTextEditor content="<p>hello</p>" enableEmojiPicker />)

        await waitFor(() => {
            expect(screen.getByLabelText("Insert Emoji")).toBeInTheDocument()
        })

        fireEvent.click(screen.getByLabelText("Insert Emoji"))
        fireEvent.click(screen.getByRole("button", { name: "pick-emoji" }))

        expect(chain.insertContent).toHaveBeenCalledWith("🚀")
    })

    it("renders the full emoji picker with frequent suggestions by default", async () => {
        render(<RichTextEditor content="<p>hello</p>" enableEmojiPicker />)

        await waitFor(() => {
            expect(screen.getByLabelText("Insert Emoji")).toBeInTheDocument()
        })

        fireEvent.click(screen.getByLabelText("Insert Emoji"))

        expect(screen.getByTestId("emoji-picker")).toBeInTheDocument()
        const hasFrequentMode = mockEmojiPickerProps.mock.calls.some(
            ([props]) =>
                (props as { suggestedEmojisMode?: string }).suggestedEmojisMode === "frequent" &&
                (props as { emojiStyle?: string }).emojiStyle === "native"
        )
        expect(hasFrequentMode).toBe(true)
    })

    it("can switch suggested mode to recent", async () => {
        render(<RichTextEditor content="<p>hello</p>" enableEmojiPicker />)

        await waitFor(() => {
            expect(screen.getByLabelText("Insert Emoji")).toBeInTheDocument()
        })

        fireEvent.click(screen.getByLabelText("Insert Emoji"))
        fireEvent.click(screen.getByRole("button", { name: "Recent" }))

        const hasRecentMode = mockEmojiPickerProps.mock.calls.some(
            ([props]) => (props as { suggestedEmojisMode?: string }).suggestedEmojisMode === "recent"
        )
        expect(hasRecentMode).toBe(true)
    })

    it("exposes imperative insertion through the React 19 ref prop", async () => {
        const editorRef = createRef<RichTextEditorHandle>()

        render(<RichTextEditor ref={editorRef} content="<p>hello</p>" />)

        await waitFor(() => {
            expect(screen.getByLabelText("Bold")).toBeInTheDocument()
        })

        editorRef.current?.insertText("follow-up")

        expect(chain.insertContent).toHaveBeenCalledWith("follow-up")
    })
})
