import { afterEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"

import NotificationSettingsPage from "../app/(app)/settings/notifications/page"

const toastMocks = vi.hoisted(() => ({
    error: vi.fn(),
    success: vi.fn(),
}))

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
            intelligent_suggestion_digest: true,
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

vi.mock("@/components/ui/toast", () => ({
    toast: toastMocks,
}))

function installNotificationApi(
    permission: NotificationPermission,
    requestResult: NotificationPermission = permission
) {
    const requestPermission = vi.fn(async () => requestResult)
    const notificationConstructor = vi.fn()

    Object.defineProperties(notificationConstructor, {
        permission: {
            configurable: true,
            get: () => permission,
        },
        requestPermission: {
            configurable: true,
            value: requestPermission,
        },
    })

    vi.stubGlobal("Notification", notificationConstructor)

    return { notificationConstructor, requestPermission }
}

describe("NotificationSettingsPage", () => {
    afterEach(() => {
        toastMocks.error.mockReset()
        toastMocks.success.mockReset()
        vi.unstubAllGlobals()
    })

    it("shows in-app notification sections including important-change controls", () => {
        render(<NotificationSettingsPage />)

        expect(screen.getByText("In-app Notifications")).toBeInTheDocument()
        expect(screen.getByText("Contact Reminders")).toBeInTheDocument()
        expect(screen.getByText("Intelligent Suggestions Digest")).toBeInTheDocument()
        expect(screen.getByText("Status Change Decisions")).toBeInTheDocument()
        expect(screen.getByText("Approval Timeouts")).toBeInTheDocument()
        expect(screen.getByText("Security Alerts")).toBeInTheDocument()
    })

    it("shows unsupported browser notification state when the browser API is unavailable", () => {
        vi.stubGlobal("Notification", undefined)

        render(<NotificationSettingsPage />)

        expect(screen.getByText("Not Supported")).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /enable notifications/i })).not.toBeInTheDocument()
    })

    it("shows granted browser notification permission immediately", () => {
        installNotificationApi("granted")

        render(<NotificationSettingsPage />)

        expect(screen.getByText("Enabled")).toBeInTheDocument()
        expect(screen.getByText("You'll receive notifications even when the app is in the background.")).toBeInTheDocument()
    })

    it("requests browser notification permission and updates the visible state", async () => {
        const { notificationConstructor, requestPermission } = installNotificationApi("default", "granted")

        render(<NotificationSettingsPage />)
        fireEvent.click(screen.getByRole("button", { name: /enable notifications/i }))

        await waitFor(() => expect(screen.getByText("Enabled")).toBeInTheDocument())
        expect(requestPermission).toHaveBeenCalledTimes(1)
        expect(toastMocks.success).toHaveBeenCalledWith("Browser notifications enabled!")
        expect(notificationConstructor).toHaveBeenCalledWith(
            "Notifications Enabled",
            expect.objectContaining({
                body: "You'll now receive browser notifications for important updates.",
                icon: "/favicon.ico",
            })
        )
    })
})
