import type { ReactNode } from "react"
import { describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
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
        expect(await screen.findByText("Platform Operations")).toBeInTheDocument()
        await waitFor(() => {
            expect(mockGetPlatformStats).toHaveBeenCalledTimes(1)
            expect(mockListAlerts).toHaveBeenCalledTimes(1)
        })

        firstView.unmount()
        renderDashboard()

        expect(screen.getByText("Platform Operations")).toBeInTheDocument()
        expect(mockGetPlatformStats).toHaveBeenCalledTimes(1)
        expect(mockListAlerts).toHaveBeenCalledTimes(1)
    })
})
