import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"

import { EmailTemplateHistoryDialog } from "@/components/email/EmailTemplateHistoryDialog"
import type { EmailTemplateVersion } from "@/lib/api/email-template-history"

const VERSIONS: EmailTemplateVersion[] = [
    {
        id: "version-3",
        version: 3,
        created_by_user_id: "user-1",
        comment: "Updated",
        created_at: "2026-07-23T14:30:00.000Z",
    },
    {
        id: "version-2",
        version: 2,
        created_by_user_id: "user-1",
        comment: "Rollback from v1",
        created_at: "2026-07-22T14:30:00.000Z",
    },
    {
        id: "version-1",
        version: 1,
        created_by_user_id: null,
        comment: "Created",
        created_at: "2026-07-21T14:30:00.000Z",
    },
]

function renderHistoryDialog(
    overrides: Partial<React.ComponentProps<typeof EmailTemplateHistoryDialog>> = {},
) {
    return render(
        <EmailTemplateHistoryDialog
            open
            onOpenChange={vi.fn()}
            templateName="Welcome email"
            currentVersion={3}
            versions={VERSIONS}
            isLoading={false}
            isError={false}
            onRetry={vi.fn()}
            onRestore={vi.fn().mockResolvedValue(undefined)}
            isRestoring={false}
            {...overrides}
        />,
    )
}

describe("EmailTemplateHistoryDialog", () => {
    it("shows friendly saved-version labels without exposing user ids", () => {
        renderHistoryDialog()

        expect(screen.getByRole("heading", { name: "Template history" })).toBeInTheDocument()
        expect(screen.getByText("Version 3")).toBeInTheDocument()
        expect(screen.getByText("Current")).toBeInTheDocument()
        expect(screen.getByText("Template updated")).toBeInTheDocument()
        expect(screen.getByText("Restored from version 1")).toBeInTheDocument()
        expect(screen.getByText("Template created")).toBeInTheDocument()
        expect(screen.queryByText("user-1")).not.toBeInTheDocument()
    })

    it("confirms a restore and explains that history remains append-only", async () => {
        const onRestore = vi.fn().mockResolvedValue(undefined)
        renderHistoryDialog({ onRestore })

        fireEvent.click(screen.getByRole("button", { name: "Restore version 1" }))

        expect(screen.getByRole("heading", { name: "Restore version 1?" })).toBeInTheDocument()
        expect(screen.getByText(/creates a new version/i)).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Restore version" }))

        await waitFor(() => {
            expect(onRestore).toHaveBeenCalledWith(1)
        })
    })

    it("explains draft-safe restoration without implying production changed", async () => {
        const onRestore = vi.fn().mockResolvedValue(undefined)
        renderHistoryDialog({ onRestore, restoreMode: "draft" })

        expect(
            screen.getByText(
                "Review published versions or load one into an isolated draft. Production stays unchanged until you publish.",
            ),
        ).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Restore version 1" }))

        expect(
            screen.getByText(
                "This loads version 1 into your isolated draft. The published template stays unchanged until you publish.",
            ),
        ).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Restore to draft" }))

        await waitFor(() => {
            expect(onRestore).toHaveBeenCalledWith(1)
        })
    })

    it("uses scope-neutral copy when a Studio template has no saved versions", () => {
        renderHistoryDialog({
            versions: [],
            restoreMode: "draft",
        })

        expect(
            screen.getByText(
                "Version history will appear after this template is published.",
            ),
        ).toBeInTheDocument()
        expect(screen.queryByText(/organization template/i)).not.toBeInTheDocument()
    })

    it("renders loading, error, and empty states", () => {
        const { rerender } = render(
            <EmailTemplateHistoryDialog
                open
                onOpenChange={vi.fn()}
                templateName="Welcome email"
                currentVersion={3}
                versions={[]}
                isLoading
                isError={false}
                onRetry={vi.fn()}
                onRestore={vi.fn()}
                isRestoring={false}
            />,
        )

        expect(screen.getByText("Loading version history…")).toBeInTheDocument()

        const onRetry = vi.fn()
        rerender(
            <EmailTemplateHistoryDialog
                open
                onOpenChange={vi.fn()}
                templateName="Welcome email"
                currentVersion={3}
                versions={[]}
                isLoading={false}
                isError
                onRetry={onRetry}
                onRestore={vi.fn()}
                isRestoring={false}
            />,
        )
        expect(screen.getByText("Couldn’t load history")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Try again" }))
        expect(onRetry).toHaveBeenCalledOnce()

        rerender(
            <EmailTemplateHistoryDialog
                open
                onOpenChange={vi.fn()}
                templateName="Welcome email"
                currentVersion={3}
                versions={[]}
                isLoading={false}
                isError={false}
                onRetry={vi.fn()}
                onRestore={vi.fn()}
                isRestoring={false}
            />,
        )
        expect(screen.getByText("No saved versions yet")).toBeInTheDocument()
    })
})
