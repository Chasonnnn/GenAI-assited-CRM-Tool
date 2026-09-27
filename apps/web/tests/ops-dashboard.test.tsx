import type { ReactNode } from "react"
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

import OpsDashboard from "../app/ops/page.client"

const mockGetPlatformStats = vi.fn()
const mockListAlerts = vi.fn()

vi.unmock("@tanstack/react-query")

vi.mock("@/lib/api/platform", () => ({
    getPlatformStats: () => mockGetPlatformStats(),
    listAlerts: (...args: unknown[]) => mockListAlerts(...args),
}))

vi.mock("@/components/app-link", () => ({
    __esModule: true,
    default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}))

describe("OpsDashboard", () => {
    it("reuses fresh dashboard data when the page remounts", async () => {
        mockGetPlatformStats.mockResolvedValue({
            agency_count: 12,
            active_user_count: 34,
            open_alerts: 2,
        })
        mockListAlerts.mockResolvedValue({ items: [], total: 0 })
        const queryClient = new QueryClient({
            defaultOptions: { queries: { retry: false } },
        })
        const renderDashboard = () =>
            render(
                <QueryClientProvider client={queryClient}>
                    <OpsDashboard />
                </QueryClientProvider>
            )

        const firstView = renderDashboard()
        expect(await screen.findByRole("link", { name: /Agencies\s*12/ })).toBeInTheDocument()
        await waitFor(() => {
            expect(mockGetPlatformStats).toHaveBeenCalledTimes(1)
            expect(mockListAlerts).toHaveBeenCalledTimes(1)
        })

        firstView.unmount()
        renderDashboard()

        expect(screen.getByRole("link", { name: /Agencies\s*12/ })).toBeInTheDocument()
        expect(mockGetPlatformStats).toHaveBeenCalledTimes(1)
        expect(mockListAlerts).toHaveBeenCalledTimes(1)
    })

    const renderFresh = () =>
        render(
            <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
                <OpsDashboard />
            </QueryClientProvider>
        )

    it("uses a Dashboard page header with one Create Agency action and linked stat cards", async () => {
        mockGetPlatformStats.mockReset()
        mockListAlerts.mockReset()
        mockGetPlatformStats.mockResolvedValue({ agency_count: 3, active_user_count: 7, open_alerts: 1 })
        mockListAlerts.mockResolvedValue({
            items: [
                {
                    id: "alert-1",
                    organization_id: "org-1",
                    org_name: "Agency One",
                    alert_type: "integration",
                    severity: "critical",
                    status: "open",
                    title: "Calendar sync failing",
                    occurrence_count: 1,
                    first_seen_at: "2026-07-16T00:00:00Z",
                    last_seen_at: "2026-07-16T00:00:00Z",
                },
            ],
            total: 1,
        })

        renderFresh()

        expect(await screen.findByRole("heading", { level: 1, name: "Dashboard" })).toBeInTheDocument()
        await screen.findByText("Calendar sync failing")
        const createLinks = screen.getAllByRole("link", { name: /Create Agency/ })
        expect(createLinks).toHaveLength(1)
        expect(createLinks[0]).toHaveAttribute("href", "/ops/agencies/new")
        expect(screen.getByRole("link", { name: /Agencies\s*3/ })).toHaveAttribute("href", "/ops/agencies")
        expect(screen.getByRole("link", { name: /Open Alerts\s*1/ })).toHaveAttribute("href", "/ops/alerts")
        expect(screen.queryByRole("link", { name: "View All Agencies" })).not.toBeInTheDocument()
        expect(screen.queryByRole("link", { name: "Alert Inbox" })).not.toBeInTheDocument()

        expect(await screen.findByText("Agency One · Critical")).toBeInTheDocument()
        expect(screen.getByText("Open")).toBeInTheDocument()
        expect(screen.queryByText(/CRITICAL/)).not.toBeInTheDocument()
    })

    it("shows a retryable load error without reloading the page", async () => {
        mockGetPlatformStats.mockReset()
        mockListAlerts.mockReset()
        mockGetPlatformStats.mockRejectedValueOnce(new Error("boom"))
        mockGetPlatformStats.mockResolvedValue({ agency_count: 2, active_user_count: 0, open_alerts: 0 })
        mockListAlerts.mockResolvedValue({ items: [], total: 0 })

        renderFresh()

        expect(await screen.findByRole("heading", { name: "Couldn't load dashboard" })).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Try again" }))

        expect(await screen.findByRole("link", { name: /Agencies\s*2/ })).toBeInTheDocument()
        expect(screen.getByRole("heading", { name: "No open alerts" })).toBeInTheDocument()
        expect(window.location.reload).not.toHaveBeenCalled()
    })
})
