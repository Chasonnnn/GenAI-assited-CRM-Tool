import { beforeEach, describe, expect, it, vi } from "vitest"
import { renderToString } from "react-dom/server"
import { fireEvent, render, screen } from "@testing-library/react"

import UnassignedSurrogatesPage from "@/app/(app)/surrogates/unassigned/page.client"
import { stageBadgeStyle } from "@/lib/stage-colors"

const mocks = vi.hoisted(() => ({
    redirect: vi.fn(),
    useAuth: vi.fn(),
    useUnassignedQueue: vi.fn(),
    useClaimSurrogate: vi.fn(),
    trackViewed: vi.fn(),
}))

vi.mock("next/navigation", () => ({
    redirect: (path: string) => mocks.redirect(path),
    useRouter: () => ({
        push: vi.fn(),
        replace: vi.fn(),
    }),
}))

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => mocks.useAuth(),
}))

vi.mock("@/lib/hooks/use-surrogates", () => ({
    useUnassignedQueue: (...args: unknown[]) => mocks.useUnassignedQueue(...args),
}))

vi.mock("@/lib/hooks/use-queues", () => ({
    useClaimSurrogate: () => mocks.useClaimSurrogate(),
}))

vi.mock("@/lib/hooks/use-pipelines", () => ({
    useDefaultPipeline: () => ({
        data: { stages: [{ id: "stage-new", label: "New Unread", color: "#3B82F6" }] },
    }),
}))

vi.mock("@/lib/workflow-metrics", () => ({
    trackUnassignedQueueViewed: () => mocks.trackViewed(),
}))

describe("UnassignedSurrogatesPage", () => {
    it("redirects unauthorized users during initial rendering before queue hooks mount", () => {
        mocks.useAuth.mockReturnValue({
            user: {
                user_id: "case-manager-1",
                role: "case_manager",
            },
        })
        mocks.useUnassignedQueue.mockReturnValue({
            data: null,
            isLoading: false,
            error: null,
            refetch: vi.fn(),
        })
        mocks.useClaimSurrogate.mockReturnValue({
            mutateAsync: vi.fn(),
            isPending: false,
        })

        renderToString(
            <UnassignedSurrogatesPage
                initialPageParam={null}
                initialSearchParams=""
            />
        )

        expect(mocks.redirect).toHaveBeenCalledWith("/surrogates")
        expect(mocks.useUnassignedQueue).not.toHaveBeenCalled()
        expect(mocks.useClaimSurrogate).not.toHaveBeenCalled()
        expect(mocks.trackViewed).not.toHaveBeenCalled()
    })

    describe("as admin", () => {
        beforeEach(() => {
            mocks.useAuth.mockReturnValue({ user: { user_id: "admin-1", role: "admin" } })
            mocks.useClaimSurrogate.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
        })

        function renderPage(pageParam: string | null = null) {
            return render(
                <UnassignedSurrogatesPage initialPageParam={pageParam} initialSearchParams="" />
            )
        }

        it("renders the shared page header without a count or subtitle", () => {
            mocks.useUnassignedQueue.mockReturnValue({
                data: {
                    items: [
                        {
                            id: "s-1",
                            surrogate_number: "S10152",
                            full_name: "QA Surrogate",
                            stage_id: "stage-new",
                            status_label: "New Unread",
                            source: "agency",
                            state: null,
                            created_at: "2026-09-01T12:00:00Z",
                        },
                    ],
                    total: 1,
                    pages: 1,
                },
                isLoading: false,
                isRefetching: false,
                error: null,
                refetch: vi.fn(),
            })

            const { container } = renderPage()

            expect(screen.getByRole("heading", { level: 1, name: "Unassigned Queue" })).toBeInTheDocument()
            expect(container.querySelector('[data-slot="page-header-count"]')).toBeNull()
            expect(screen.queryByText("Claim a surrogate to start working the case.")).not.toBeInTheDocument()
            expect(screen.getByText("#S10152")).toBeInTheDocument()
            expect(screen.getByText("Agency")).toBeInTheDocument()
            expect(screen.queryByText("agency")).not.toBeInTheDocument()
            const stageBadge = screen.getByText("New Unread")
            expect(stageBadge).toHaveStyle({ ...stageBadgeStyle("#3B82F6"), color: "#FFFFFF" })
            expect(stageBadgeStyle("#3B82F6").backgroundColor).not.toBe("#3B82F6")
        })

        it("shows the empty state without a first-page button on page 1", () => {
            mocks.useUnassignedQueue.mockReturnValue({
                data: { items: [], total: 0, pages: 0 },
                isLoading: false,
                isRefetching: false,
                error: null,
                refetch: vi.fn(),
            })

            renderPage()

            expect(screen.getByText("No unassigned surrogates")).toBeInTheDocument()
            expect(screen.queryByRole("button", { name: /first page/i })).not.toBeInTheDocument()
        })

        it("offers the first page when a later page is empty", () => {
            mocks.useUnassignedQueue.mockReturnValue({
                data: { items: [], total: 3, pages: 1 },
                isLoading: false,
                isRefetching: false,
                error: null,
                refetch: vi.fn(),
            })

            renderPage("4")

            expect(screen.getByRole("button", { name: "First page" })).toBeInTheDocument()
        })

        it("shows a retryable load error without the raw message", () => {
            const refetch = vi.fn()
            mocks.useUnassignedQueue.mockReturnValue({
                data: undefined,
                isLoading: false,
                isRefetching: false,
                error: new Error("psycopg OperationalError: connection refused"),
                refetch,
            })

            renderPage()

            expect(screen.getByText("Couldn't load unassigned surrogates")).toBeInTheDocument()
            expect(screen.queryByText(/psycopg/)).not.toBeInTheDocument()
            fireEvent.click(screen.getByRole("button", { name: "Try again" }))
            expect(refetch).toHaveBeenCalled()
        })
    })
})
