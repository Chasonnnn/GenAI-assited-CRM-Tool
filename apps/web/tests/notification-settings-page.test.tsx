import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"

import NotificationSettingsPage from "../app/(app)/settings/notifications/page"

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => ({
        user: {
            email: "case-manager@example.com",
        },
    }),
}))

vi.mock("@/lib/hooks/use-notifications", () => ({
    useNotificationSettings: () => ({
        data: {
            surrogate_assigned: true,
            surrogate_status_changed: true,
            surrogate_claim_available: true,
            task_assigned: true,
            workflow_approvals: true,
            task_reminders: true,
            appointments: true,
            contact_reminder: true,
            status_change_decisions: true,
            approval_timeouts: true,
            security_alerts: true,
        },
        isLoading: false,
    }),
    useUpdateNotificationSettings: () => ({
        mutateAsync: vi.fn(),
        isPending: false,
    }),
}))

describe("NotificationSettingsPage", () => {
    it("shows in-app notification sections including important-change controls", () => {
        render(<NotificationSettingsPage />)

        expect(screen.getByText("In-app Notifications")).toBeInTheDocument()
        expect(screen.getByText("Contact Reminders")).toBeInTheDocument()
        expect(screen.getByText("Status Change Decisions")).toBeInTheDocument()
        expect(screen.getByText("Approval Timeouts")).toBeInTheDocument()
        expect(screen.getByText("Security Alerts")).toBeInTheDocument()
    })
})
