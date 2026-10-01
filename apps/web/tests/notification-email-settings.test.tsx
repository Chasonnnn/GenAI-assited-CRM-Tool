import { afterEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"

import NotificationSettingsPage from "../app/(app)/settings/notifications/page"
import type { NotificationSettings } from "@/lib/api/notifications"

const mocks = vi.hoisted(() => ({
    settings: undefined as Record<string, boolean> | undefined,
    isLoading: false,
    isPending: false,
    mutateAsync: vi.fn(),
    toastError: vi.fn(),
}))

vi.mock("@/lib/hooks/use-notifications", () => ({
    useNotificationSettings: () => ({
        data: mocks.settings,
        isLoading: mocks.isLoading,
    }),
    useUpdateNotificationSettings: () => ({
        mutateAsync: mocks.mutateAsync,
        isPending: mocks.isPending,
    }),
}))

vi.mock("@/components/ui/toast", () => ({
    toast: { error: mocks.toastError, success: vi.fn() },
}))

const SETTINGS: NotificationSettings = {
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
    email_workflow_notifications: false,
}

function emailSwitch() {
    return screen.getByRole("switch", { name: "Workflow Notifications email" })
}

describe("Email notification settings", () => {
    afterEach(() => {
        mocks.settings = undefined
        mocks.isLoading = false
        mocks.isPending = false
        mocks.mutateAsync.mockReset()
        mocks.toastError.mockReset()
        vi.unstubAllGlobals()
    })

    it("shows the workflow email toggle off by default", () => {
        mocks.settings = { ...SETTINGS }

        render(<NotificationSettingsPage />)

        expect(screen.getByText("Email Notifications")).toBeInTheDocument()
        expect(emailSwitch()).not.toBeChecked()
        expect(emailSwitch()).not.toHaveAttribute("aria-disabled", "true")
    })

    it("shows the stored email preference", () => {
        mocks.settings = { ...SETTINGS, email_workflow_notifications: true }

        render(<NotificationSettingsPage />)

        expect(emailSwitch()).toBeChecked()
    })

    it("saves only the email preference when toggled", async () => {
        mocks.settings = { ...SETTINGS }
        mocks.mutateAsync.mockResolvedValue({ ...SETTINGS, email_workflow_notifications: true })

        render(<NotificationSettingsPage />)
        fireEvent.click(emailSwitch())

        await waitFor(() =>
            expect(mocks.mutateAsync).toHaveBeenCalledWith({ email_workflow_notifications: true })
        )
        expect(mocks.toastError).not.toHaveBeenCalled()
    })

    it("shows an error toast when saving fails", async () => {
        mocks.settings = { ...SETTINGS }
        mocks.mutateAsync.mockRejectedValue(new Error("network"))

        render(<NotificationSettingsPage />)
        fireEvent.click(emailSwitch())

        await waitFor(() =>
            expect(mocks.toastError).toHaveBeenCalledWith("Failed to update notification settings")
        )
    })

    it("disables the toggle while a save is pending", () => {
        mocks.settings = { ...SETTINGS }
        mocks.isPending = true

        render(<NotificationSettingsPage />)

        expect(emailSwitch()).toHaveAttribute("aria-disabled", "true")
    })

    it("disables the toggle when settings failed to load", () => {
        render(<NotificationSettingsPage />)

        expect(emailSwitch()).toHaveAttribute("aria-disabled", "true")
        expect(emailSwitch()).not.toBeChecked()
    })

    it("hides the toggle while settings load", () => {
        mocks.isLoading = true

        render(<NotificationSettingsPage />)

        expect(screen.queryByText("Email Notifications")).not.toBeInTheDocument()
        expect(screen.queryByRole("switch", { name: "Workflow Notifications email" })).not.toBeInTheDocument()
    })
})
