import type { ReactNode } from "react"
import { assert, beforeEach, describe, expect, it, vi } from "vitest"
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

    beforeEach(() => {
        mockListAlerts.mockReset()
    })

    it("shows a retryable error state instead of the all-clear state when loading fails", async () => {
        mockListAlerts.mockRejectedValueOnce(new Error("boom"))
        mockListAlerts.mockResolvedValueOnce({ items: [], total: 0 })

        renderAlertsPage()

        expect(await screen.findByRole("heading", { name: "Couldn't load alerts" })).toBeInTheDocument()
        expect(screen.queryByRole("heading", { name: "No alerts" })).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: /Try again|Retry/ }))
        expect(await screen.findByRole("heading", { name: "No alerts" })).toBeInTheDocument()
    })

    it("shows a filtered empty state with a clear action and labels the filter trigger", async () => {
        mockListAlerts.mockResolvedValue({ items: [], total: 0 })

        renderAlertsPage()
        expect(await screen.findByRole("heading", { name: "No alerts" })).toBeInTheDocument()

        const statusSelect = screen.getByRole("combobox", { name: "Filter by status" })
        fireEvent.mouseDown(statusSelect)
        const snoozed = await screen.findByRole("option", { name: "Snoozed" })
        fireEvent.mouseMove(snoozed)
        fireEvent.click(snoozed)

        expect(await screen.findByRole("heading", { name: "No matching alerts" })).toBeInTheDocument()
        expect(statusSelect).toHaveTextContent("Snoozed")
        expect(statusSelect).not.toHaveTextContent("snoozed")

        fireEvent.click(screen.getByRole("button", { name: "Clear filters" }))
        expect(await screen.findByRole("heading", { name: "No alerts" })).toBeInTheDocument()
        expect(statusSelect).toHaveTextContent("All statuses")
    })

    it("labels severity and status badges", async () => {
        mockListAlerts.mockResolvedValue({
            items: [
                {
                    id: "a1",
                    organization_id: "org-1",
                    org_name: "Agency One",
                    alert_type: "integration",
                    severity: "warn",
                    status: "acknowledged",
                    title: "Label check",
                    occurrence_count: 1,
                    first_seen_at: "2026-07-16T00:00:00Z",
                    last_seen_at: "2026-07-16T00:00:00Z",
                },
            ],
            total: 1,
        })

        renderAlertsPage()

        expect(await screen.findByText("Label check")).toBeInTheDocument()
        expect(screen.getByText("Warning")).toBeInTheDocument()
        expect(screen.getByText("Acknowledged")).toBeInTheDocument()
        expect(screen.queryByText("warn")).not.toBeInTheDocument()
    })

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
        assert.isDefined(statusSelect)
        assert.isDefined(severitySelect)

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
        assert.isDefined(severitySelect)
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
