import { renderHook } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { useSyncRichTextEditorContent } from "@/lib/hooks/use-sync-rich-text-editor-content"

describe("useSyncRichTextEditorContent", () => {
    it("updates external editor content once and ignores matching rerenders", () => {
        let currentHtml = "<p>Original</p>"
        const setContent = vi.fn((nextHtml: string) => {
            currentHtml = nextHtml
        })
        const editor = {
            getHTML: () => currentHtml,
            commands: { setContent },
        }

        const view = renderHook(
            ({ content }) => useSyncRichTextEditorContent(editor, content),
            { initialProps: { content: "<p>Original</p>" } }
        )

        expect(setContent).not.toHaveBeenCalled()

        view.rerender({ content: "<p>Updated externally</p>" })
        expect(setContent).toHaveBeenCalledTimes(1)
        expect(setContent).toHaveBeenCalledWith("<p>Updated externally</p>")

        view.rerender({ content: "<p>Updated externally</p>" })
        expect(setContent).toHaveBeenCalledTimes(1)
    })
})
