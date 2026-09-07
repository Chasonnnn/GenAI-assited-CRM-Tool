import type { PropsWithChildren, ReactNode } from "react"
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

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
    const historyProps = {
        activeTab: "notes" as const, sourceFilter: "all" as const,
        filteredNotes: [{ id: "legacy-note", content: "Retained participant history", created_at: "2026-01-01T00:00:00Z", source: "surrogate" as const, scope: "record" as const }],
        filteredFiles: [], filteredTasks: [], filteredActivity: [],
        onTabChange: vi.fn(), onSourceFilterChange: vi.fn(), onDownloadFile: vi.fn(), onDeleteFile: vi.fn(),
        isDownloadPending: false, isDeletePending: false,
        formatDate: () => "Jan 1, 2026", formatDateTime: () => "Jan 1, 2026",
    }

    it("attributes participant history without assigning it to the match", () => {
        render(<MatchDetailOverviewTabs {...historyProps} />)
        expect(screen.getByText("Surrogate record")).toBeInTheDocument()
        expect(screen.getByText("Retained participant history")).toBeInTheDocument()
    })

    it("retains loading, empty and retry states for historical work", () => {
        const retry = vi.fn()
        const view = render(<MatchDetailOverviewTabs {...historyProps} isLoading />)
        expect(screen.queryByText("Retained participant history")).not.toBeInTheDocument()
        view.rerender(<MatchDetailOverviewTabs {...historyProps} filteredNotes={[]} />)
        expect(screen.getByText("No notes yet")).toBeInTheDocument()
        view.rerender(<MatchDetailOverviewTabs {...historyProps} error="History unavailable" onRetry={retry} />)
        expect(screen.getByRole("alert")).toHaveTextContent("History unavailable")
        fireEvent.click(screen.getByRole("button", { name: "Retry" }))
        expect(retry).toHaveBeenCalledOnce()
    })

    it("sanitizes note HTML before rendering match notes", () => {
        const { container } = render(
            <MatchDetailOverviewTabs
                activeTab="notes"
                sourceFilter="all"
                filteredNotes={[
                    {
                        id: "note-xss",
                        content: '<img src=x onerror="alert(1)"><p>Safe match note</p><script>alert("x")</script>',
                        created_at: "2026-01-01T00:00:00Z",
                        source: "match",
                    },
                ]}
                filteredFiles={[]}
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

        expect(screen.getByText("Safe match note")).toBeInTheDocument()
        expect(container.querySelector("img")).toBeNull()
        expect(container.querySelector("script")).toBeNull()
        expect(container.querySelector("[onerror]")).toBeNull()
    })

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
