import type { PropsWithChildren, ReactNode } from "react"
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"

import { MatchDetailOverviewTabs } from "@/app/(app)/intended-parents/matches/[id]/components/MatchDetailOverviewTabs"

vi.mock("@/components/ui/select", () => ({
    Select: ({ children }: PropsWithChildren) => <div>{children}</div>,
    SelectTrigger: ({ children }: PropsWithChildren) => <div>{children}</div>,
    SelectValue: ({ children }: { children?: ReactNode | ((value: string | null) => ReactNode) }) => (
        <span>{typeof children === "function" ? children("all") : children}</span>
    ),
    SelectContent: ({ children }: PropsWithChildren) => <div>{children}</div>,
    SelectItem: ({ children }: PropsWithChildren<{ value: string }>) => <div>{children}</div>,
}))

describe("MatchDetailOverviewTabs", () => {
    it("uses filename-specific labels for file action buttons", () => {
        render(
            <MatchDetailOverviewTabs
                activeTab="files"
                sourceFilter="all"
                filteredNotes={[]}
                filteredFiles={[
                    {
                        id: "file-1",
                        filename: "agreement.pdf",
                        file_size: 2048,
                        created_at: "2026-01-01T00:00:00Z",
                        source: "surrogate",
                    },
                ]}
                filteredTasks={[]}
                filteredActivity={[]}
                onTabChange={vi.fn()}
                onSourceFilterChange={vi.fn()}
                onAddTask={vi.fn()}
                onAddNote={vi.fn()}
                onUploadFile={vi.fn()}
                onDownloadFile={vi.fn()}
                onDeleteFile={vi.fn()}
                isDownloadPending={false}
                isDeletePending={false}
                formatDate={() => "Jan 1, 2026"}
                formatDateTime={() => "Jan 1, 2026"}
            />,
        )

        expect(screen.getByRole("button", { name: "Download agreement.pdf" })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Delete agreement.pdf" })).toBeInTheDocument()
    })
})
