import React from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"

import { TranscriptPane } from "@/components/surrogates/interviews/InterviewComments/TranscriptPane"
import { ListItem } from "@/components/surrogates/interviews/InterviewTab/ListItem"
import { LatestUpdatesCard } from "@/components/surrogates/LatestUpdatesCard"

const mockUseInterviewComments = vi.fn()

vi.mock("@/components/surrogates/interviews/SelectionPopover", () => ({
    SelectionPopover: () => null,
}))

vi.mock("@/components/surrogates/interviews/InterviewComments/hooks/useInteractionClasses", () => ({
    useInteractionClasses: () => undefined,
}))

vi.mock("@/components/surrogates/interviews/InterviewComments/context", () => ({
    useInterviewComments: () => mockUseInterviewComments(),
}))

vi.mock("@/lib/hooks/use-surrogates", () => ({
    useSurrogateHistory: () => ({ data: [] }),
}))

describe("Surrogate interview accessibility labels", () => {
    beforeEach(() => {
        mockUseInterviewComments.mockReturnValue({
            transcriptRef: React.createRef<HTMLDivElement>(),
            transcriptHtml: "<p>Transcript body</p>",
            canEdit: true,
            newComment: { type: "none" },
            isSelectingRef: { current: false },
            interaction: {
                hoveredCommentId: null,
                focusedCommentId: null,
            },
            setHoveredCommentId: vi.fn(),
            setFocusedCommentId: vi.fn(),
            startPendingComment: vi.fn(),
        })
    })

    it("adds an aria-label to the interview transcript pane", () => {
        render(<TranscriptPane />)
        expect(screen.getByRole("button", { name: "Interview Transcript" })).toBeInTheDocument()
    })

    it("adds a descriptive aria-label to interview list rows", () => {
        render(
            <ListItem
                interview={{
                    id: "int-1",
                    interview_type: "video",
                    conducted_at: "2026-02-10T12:00:00Z",
                    conducted_by_user_id: "user-1",
                    conducted_by_name: "Case Manager",
                    duration_minutes: 30,
                    status: "completed",
                    has_transcript: true,
                    transcript_version: 1,
                    notes_count: 1,
                    attachments_count: 1,
                    created_at: "2026-02-10T12:30:00Z",
                }}
                isSelected={false}
                onClick={() => undefined}
            />,
        )

        expect(
            screen.getByRole("button", { name: /Video interview on/ }),
        ).toBeInTheDocument()
    })

    it("adds an aria-label to latest attachment download actions", () => {
        render(
            <LatestUpdatesCard
                surrogateId="sur-1"
                notes={[]}
                attachments={[
                    {
                        id: "att-1",
                        filename: "report.csv",
                        content_type: "text/csv",
                        file_size: 256,
                        scan_status: "clean",
                        quarantined: false,
                        uploaded_by_user_id: "user-1",
                        created_at: "2026-02-10T10:00:00Z",
                    },
                ]}
            />,
        )

        expect(screen.getByRole("button", { name: "Download report.csv" })).toBeInTheDocument()
    })
})
