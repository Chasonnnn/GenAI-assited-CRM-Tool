import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"

import { EmailTemplateHistorySheet } from "@/components/email/EmailTemplateHistorySheet"
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

function renderHistory(
    overrides: Partial<React.ComponentProps<typeof EmailTemplateHistorySheet>> = {},
) {
    return render(
        <EmailTemplateHistorySheet
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

describe("EmailTemplateHistorySheet", () => {
    it("shows friendly saved-version labels without exposing user ids", () => {
        renderHistory()

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
        renderHistory({ onRestore })

        fireEvent.click(screen.getByRole("button", { name: "Restore version 1" }))

        expect(screen.getByRole("heading", { name: "Restore version 1?" })).toBeInTheDocument()
        expect(screen.getByText(/creates a new version/i)).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Restore version" }))

        await waitFor(() => {
            expect(onRestore).toHaveBeenCalledWith(1)
        })
    })

    it("renders loading, error, and empty states", () => {
        const { rerender } = render(
            <EmailTemplateHistorySheet
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
            <EmailTemplateHistorySheet
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
            <EmailTemplateHistorySheet
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
