import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import NotificationsPage from "../app/(app)/notifications/page"

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn() }),
}))

vi.mock("@/lib/hooks/use-notifications", () => ({
    useNotifications: () => ({ data: { unread_count: 0, items: [] }, isLoading: false }),
    useMarkRead: () => ({ mutate: vi.fn(), isPending: false }),
    useMarkAllRead: () => ({ mutate: vi.fn(), isPending: false }),
}))

vi.mock("@/lib/hooks/use-tasks", () => ({
    useTasks: () => ({
        data: { items: [{ id: "task1", title: "Overdue task", due_date: "2020-01-01" }] },
        isLoading: false,
    }),
}))

vi.mock("@/lib/hooks/use-notification-socket", () => ({
    useNotificationSocket: () => ({ isConnected: true, lastNotification: null, unreadCount: null }),
}))

describe("NotificationsPage overdue toggle", () => {
    it("rotates one chevron with the collapsible trigger state", () => {
        render(<NotificationsPage />)

        expect(screen.getByText("Overdue task")).toBeInTheDocument()
        const trigger = document.querySelector<HTMLElement>('[data-slot="collapsible-trigger"]')
        expect(trigger).not.toBeNull()
        expect(trigger).toHaveAttribute("data-panel-open")
        expect(trigger!.querySelectorAll("svg")).toHaveLength(1)

        const icon = trigger!.querySelector("svg")
        expect(icon).toHaveClass(
            "lucide-chevron-down",
            "group-data-panel-open/overdue-trigger:rotate-180",
            "transition-transform",
        )

        fireEvent.click(trigger!)

        expect(trigger).not.toHaveAttribute("data-panel-open")
        expect(screen.queryByText("Overdue task")).not.toBeInTheDocument()
        expect(trigger!.querySelectorAll("svg")).toHaveLength(1)
        expect(trigger!.querySelector("svg")).toBe(icon)
    })
})
