import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { TranscriptViewer } from "@/components/surrogates/interviews/TranscriptViewer"
import type { InterviewNoteRead, TipTapDoc } from "@/lib/api/interviews"

describe("TranscriptViewer", () => {
    it("sanitizes raw transcript HTML fallback before rendering", () => {
        const { container } = render(
            <TranscriptViewer
                transcriptHtml={'<img src=x onerror="alert(1)"><p>Safe transcript</p><script>alert("x")</script>'}
                transcriptJson={null}
                notes={[]}
                onAddNote={vi.fn()}
            />,
        )

        expect(screen.getByText("Safe transcript")).toBeInTheDocument()
        expect(container.querySelector("img")).toBeNull()
        expect(container.querySelector("script")).toBeNull()
        expect(container.querySelector("[onerror]")).toBeNull()
    })

    it("preserves anchored note click handling after safe HTML rendering", async () => {
        const onNoteClick = vi.fn()
        const transcriptJson: TipTapDoc = {
            type: "doc",
            content: [
                {
                    type: "paragraph",
                    content: [
                        {
                            type: "text",
                            text: "Anchored transcript text",
                            marks: [{ type: "comment", attrs: { commentId: "comment-1" } }],
                        },
                    ],
                },
            ],
        }
        const notes: InterviewNoteRead[] = [
            {
                id: "note-1",
                content: "Follow up",
                transcript_version: 1,
                comment_id: "comment-1",
                anchor_text: "Anchored transcript text",
                parent_id: null,
                replies: [],
                resolved_at: null,
                resolved_by_user_id: null,
                resolved_by_name: null,
                author_user_id: "user-1",
                author_name: "Case Manager",
                is_own: false,
                created_at: "2026-01-01T00:00:00Z",
                updated_at: "2026-01-01T00:00:00Z",
            },
        ]

        render(
            <TranscriptViewer
                transcriptHtml={null}
                transcriptJson={transcriptJson}
                notes={notes}
                onAddNote={vi.fn()}
                onNoteClick={onNoteClick}
            />,
        )

        fireEvent.click(await screen.findByText("Anchored transcript text"))

        expect(onNoteClick).toHaveBeenCalledWith("note-1")
    })
})
