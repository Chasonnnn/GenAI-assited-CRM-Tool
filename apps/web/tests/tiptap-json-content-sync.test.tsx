import { renderHook } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { useSyncTipTapJsonContent } from "@/lib/hooks/use-sync-tiptap-json-content"
import type { TipTapDoc } from "@/lib/api/interviews"

describe("useSyncTipTapJsonContent", () => {
    it("clears stale editor content for null input and ignores equivalent rerenders", () => {
        let currentContent: TipTapDoc = {
            type: "doc",
            content: [
                {
                    type: "paragraph",
                    content: [{ type: "text", text: "Stale transcript" }],
                },
            ],
        }
        const setContent = vi.fn((nextContent: TipTapDoc) => {
            currentContent = nextContent
        })
        const editor = {
            getJSON: () => currentContent,
            commands: { setContent },
        }

        const view = renderHook(
            ({ content }) => useSyncTipTapJsonContent(editor, content),
            {
                initialProps: {
                    content: currentContent as TipTapDoc | null,
                },
            }
        )

        expect(setContent).not.toHaveBeenCalled()

        view.rerender({ content: null })
        expect(setContent).toHaveBeenCalledTimes(1)
        expect(setContent).toHaveBeenCalledWith({
            type: "doc",
            content: [],
        })

        view.rerender({ content: null })
        expect(setContent).toHaveBeenCalledTimes(1)
    })
})
