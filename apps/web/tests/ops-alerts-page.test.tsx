import type { ReactNode } from "react"
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"

import OpsAlertsPage from "../app/ops/alerts/page"

const mockListAlerts = vi.fn()
const mockAcknowledgeAlert = vi.fn()
const mockResolveAlert = vi.fn()

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
    it("matches backend-supported alert enums", async () => {
        mockListAlerts.mockResolvedValue({
            items: [],
            total: 0,
        })

        render(<OpsAlertsPage />)

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
})
