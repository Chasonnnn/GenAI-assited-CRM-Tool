import { describe, expect, it, vi } from "vitest"
import { render } from "@testing-library/react"

import { Tabs } from "@/components/ui/tabs"
import { SurrogateNotesTab } from "@/components/surrogates/tabs/SurrogateNotesTab"

const richTextEditorSpy = vi.fn()

vi.mock("@/components/rich-text-editor", () => ({
    RichTextEditor: (props: unknown) => {
        richTextEditorSpy(props)
        return <div data-testid="rich-text-editor" />
    },
}))

vi.mock("@/components/FileUploadZone", () => ({
    FileUploadZone: () => <div data-testid="file-upload-zone" />,
}))

describe("SurrogateNotesTab", () => {
    it("enables emoji picker for note composition", () => {
        richTextEditorSpy.mockClear()

        render(
            <Tabs defaultValue="notes">
                <SurrogateNotesTab
                    surrogateId="sur_1"
                    notes={[]}
                    onAddNote={vi.fn()}
                    isSubmitting={false}
                    onDeleteNote={vi.fn()}
                    formatDateTime={() => "now"}
                />
            </Tabs>
        )

        expect(richTextEditorSpy).toHaveBeenCalled()
        const hasEmojiEnabled = richTextEditorSpy.mock.calls.some(
            ([props]) => Boolean((props as { enableEmojiPicker?: boolean }).enableEmojiPicker)
        )
        expect(hasEmojiEnabled).toBe(true)
    })
})
