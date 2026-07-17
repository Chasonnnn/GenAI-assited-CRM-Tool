import type { ReactNode } from "react"
import { describe, expect, it, vi } from "vitest"
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

import OpsAlertsPage from "../app/ops/alerts/page.client"

const mockListAlerts = vi.fn()
const mockAcknowledgeAlert = vi.fn()
const mockResolveAlert = vi.fn()

vi.unmock("@tanstack/react-query")

vi.mock("@/lib/api/platform", () => ({
    listAlerts: (...args: unknown[]) => mockListAlerts(...args),
    acknowledgeAlert: (...args: unknown[]) => mockAcknowledgeAlert(...args),
    resolveAlert: (...args: unknown[]) => mockResolveAlert(...args),
}))

vi.mock("@/components/app-link", () => ({
    __esModule: true,
    default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}))

describe("OpsAlertsPage filters", () => {
    const renderAlertsPage = () => {
        const queryClient = new QueryClient({
            defaultOptions: { queries: { retry: false } },
        })
        return render(
            <QueryClientProvider client={queryClient}>
                <OpsAlertsPage />
            </QueryClientProvider>
        )
    }

    it("matches backend-supported alert enums", async () => {
        mockListAlerts.mockResolvedValue({
            items: [],
            total: 0,
        })

        renderAlertsPage()

        await waitFor(() => expect(mockListAlerts).toHaveBeenCalledTimes(1))

        const selects = screen.getAllByRole("combobox")
        expect(selects.length).toBeGreaterThanOrEqual(2)

        const statusSelect = selects[0]
        const severitySelect = selects[1]

        fireEvent.mouseDown(severitySelect)
        await screen.findByRole("option", { name: "Warning" })
        expect(screen.queryByText("Info")).not.toBeInTheDocument()

        fireEvent.keyDown(severitySelect, { key: "Escape" })

        fireEvent.mouseDown(statusSelect)
        expect(await screen.findByRole("option", { name: "Snoozed" })).toBeInTheDocument()
    })

    it("keeps filtered alerts visible when the older request finishes last", async () => {
        let resolveInitial: (value: unknown) => void = () => undefined
        let resolveWarning: (value: unknown) => void = () => undefined
        const initialRequest = new Promise((resolve) => {
            resolveInitial = resolve
        })
        const warningRequest = new Promise((resolve) => {
            resolveWarning = resolve
        })
        mockListAlerts.mockImplementation((filters?: { severity?: string }) =>
            filters?.severity === "warn" ? warningRequest : initialRequest
        )
        renderAlertsPage()

        const severitySelect = screen.getAllByRole("combobox")[1]
        fireEvent.mouseDown(severitySelect)
        const warningOption = await screen.findByRole("option", { name: "Warning" })
        fireEvent.mouseMove(warningOption)
        fireEvent.click(warningOption)

        await act(async () => {
            resolveWarning({
                items: [
                    {
                        id: "warning-alert",
                        organization_id: "org-warning",
                        org_name: "Warning Agency",
                        alert_type: "integration",
                        severity: "warn",
                        status: "open",
                        title: "Warning filter result",
                        occurrence_count: 1,
                        first_seen_at: "2026-07-16T00:00:00Z",
                        last_seen_at: "2026-07-16T00:00:00Z",
                    },
                ],
                total: 1,
            })
        })
        expect(await screen.findByText("Warning filter result")).toBeInTheDocument()

        await act(async () => {
            resolveInitial({
                items: [
                    {
                        id: "old-alert",
                        organization_id: "org-old",
                        org_name: "Old Agency",
                        alert_type: "system",
                        severity: "critical",
                        status: "open",
                        title: "Older unfiltered result",
                        occurrence_count: 1,
                        first_seen_at: "2026-07-15T00:00:00Z",
                        last_seen_at: "2026-07-15T00:00:00Z",
                    },
                ],
                total: 1,
            })
            await Promise.resolve()
        })

        expect(screen.getByText("Warning filter result")).toBeInTheDocument()
        expect(screen.queryByText("Older unfiltered result")).not.toBeInTheDocument()
    })
})
