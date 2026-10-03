import type { ReactNode } from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor, fireEvent, within } from "@testing-library/react"

import { NotificationBell } from "@/components/notification-bell"
import type { Notification, NotificationTier } from "@/lib/api/notifications"

const mockPush = vi.fn()
const mockUseNotifications = vi.fn()
const mockUseNotificationCounts = vi.fn()
const mockUseNotificationSocket = vi.fn()
const mockMarkReadMutate = vi.fn()
const mockMarkAllReadMutate = vi.fn()
const mockUseMarkAllRead = vi.fn()
const mockUseBrowserNotifications = vi.fn()
const mockRequestPermission = vi.fn()
const mockToastSuccess = vi.fn()

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: mockPush }),
}))

vi.mock("next/link", () => ({
    default: ({ children, href, ...props }: { children?: ReactNode; href: string }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}))

vi.mock("@/components/ui/sheet", () => ({
    Sheet: ({ children, open }: { children?: ReactNode; open?: boolean }) => (
        <div data-testid="notification-panel" data-open={String(open)}>
            {open ? children : null}
        </div>
    ),
    SheetContent: ({ children }: { children?: ReactNode }) => <div role="dialog">{children}</div>,
    SheetTitle: ({ children }: { children?: ReactNode }) => <h2>{children}</h2>,
}))

vi.mock("@/components/ui/toast", () => ({
    toast: { success: (...args: unknown[]) => mockToastSuccess(...args), error: vi.fn() },
}))

vi.mock("@/lib/hooks/use-notifications", () => ({
    useNotifications: (params: unknown) => mockUseNotifications(params),
    useNotificationCounts: () => mockUseNotificationCounts(),
    useMarkRead: () => ({ mutate: mockMarkReadMutate }),
    useMarkAllRead: () => mockUseMarkAllRead(),
}))

vi.mock("@/lib/hooks/use-notification-socket", () => ({
    useNotificationSocket: () => mockUseNotificationSocket(),
}))

vi.mock("@/lib/hooks/use-browser-notifications", () => ({
    useBrowserNotifications: () => mockUseBrowserNotifications(),
}))

function makeNotification(overrides: Partial<Notification> = {}): Notification {
    return {
        id: "n1",
        type: "workflow_approval_requested",
        tier: "action",
        title: "Approval needed: Send welcome email",
        body: "A workflow action requires your approval",
        entity_type: "task",
        entity_id: "t1",
        read_at: null,
        created_at: new Date().toISOString(),
        ...overrides,
    }
}

function listsByTier(lists: Partial<Record<NotificationTier, unknown>>) {
    mockUseNotifications.mockImplementation((params: { tier: NotificationTier }) =>
        lists[params.tier] ?? { data: { items: [], unread_count: 0 }, isLoading: false }
    )
}

function setCounts(action_count: number, updates_unread: number) {
    mockUseNotificationCounts.mockReturnValue({
        data: { action_count, updates_unread },
        isLoading: false,
    })
}

function openPanel() {
    fireEvent.click(screen.getByRole("button", { name: /^Notifications/ }))
    return screen.getByRole("dialog")
}

describe("NotificationBell", () => {
    beforeEach(() => {
        sessionStorage.clear()
        mockPush.mockReset()
        mockMarkReadMutate.mockReset()
        mockMarkAllReadMutate.mockReset()
        mockRequestPermission.mockReset()
        mockToastSuccess.mockReset()
        mockUseMarkAllRead.mockReturnValue({ mutate: mockMarkAllReadMutate, isPending: false })
        mockUseNotificationSocket.mockReturnValue({ isConnected: false, lastNotification: null })
        mockUseBrowserNotifications.mockReturnValue({
            isSupported: true,
            permission: "denied",
            requestPermission: mockRequestPermission,
            showNotification: vi.fn(),
        })
        setCounts(0, 0)
        listsByTier({})
    })

    it("badges open action items and announces them on the trigger", () => {
        setCounts(3, 5)

        render(<NotificationBell />)

        const trigger = screen.getByRole("button", { name: "Notifications (3 need action)" })
        expect(within(trigger).getByText("3")).toBeInTheDocument()
    })

    it("does not badge a number for unread updates alone", () => {
        setCounts(0, 4)

        render(<NotificationBell />)

        const trigger = screen.getByRole("button", { name: "Notifications (4 unread updates)" })
        expect(within(trigger).queryByText("4")).toBeNull()
    })

    it("fetches panel lists only while the panel is open", () => {
        render(<NotificationBell />)

        expect(mockUseNotifications).not.toHaveBeenCalled()

        openPanel()

        expect(mockUseNotifications).toHaveBeenCalledWith(
            expect.objectContaining({ tier: "action", enabled: true, refetch_interval_ms: 30_000 })
        )
    })

    it("shows open action items and navigates on select", () => {
        setCounts(1, 0)
        listsByTier({
            action: { data: { items: [makeNotification()], unread_count: 1 }, isLoading: false },
        })
        render(<NotificationBell />)

        const panel = openPanel()
        expect(within(panel).getByRole("tab", { name: /Action needed/ })).toHaveAttribute(
            "aria-selected",
            "true"
        )
        expect(within(panel).getByText("Unread")).toBeInTheDocument()
        fireEvent.click(within(panel).getByRole("button", { name: /Approval needed/ }))

        expect(mockMarkReadMutate).toHaveBeenCalledWith("n1")
        expect(mockPush).toHaveBeenCalledWith("/tasks?filter=my_tasks&focus=approvals")
        expect(screen.getByTestId("notification-panel")).toHaveAttribute("data-open", "false")
    })

    it("shows an empty action state", () => {
        render(<NotificationBell />)

        expect(within(openPanel()).getByText("Nothing needs you")).toBeInTheDocument()
    })

    it("shows loading and retryable error states", () => {
        const refetch = vi.fn()
        listsByTier({ action: { data: undefined, isLoading: true } })
        const { unmount } = render(<NotificationBell />)
        expect(within(openPanel()).getByLabelText("Loading notifications")).toBeInTheDocument()
        unmount()

        listsByTier({
            action: { data: undefined, isLoading: false, isError: true, refetch, isFetching: false },
        })
        render(<NotificationBell />)
        fireEvent.click(within(openPanel()).getByRole("button", { name: "Retry" }))
        expect(refetch).toHaveBeenCalled()
    })

    it("marks only updates read from the Updates tab", async () => {
        setCounts(1, 2)
        listsByTier({
            update: {
                data: {
                    items: [
                        makeNotification({
                            id: "u1",
                            type: "surrogate_status_changed",
                            tier: "update",
                            title: "Surrogate #S-1042 moved to Screening",
                        }),
                    ],
                    unread_count: 2,
                },
                isLoading: false,
            },
        })
        render(<NotificationBell />)
        const panel = openPanel()

        expect(within(panel).queryByRole("button", { name: "Mark all read" })).toBeNull()
        fireEvent.click(within(panel).getByRole("tab", { name: /Updates/ }))
        await waitFor(() => {
            expect(within(panel).getByText("Surrogate #S-1042 moved to Screening")).toBeInTheDocument()
        })
        fireEvent.click(within(panel).getByRole("button", { name: "Mark all read" }))

        expect(mockMarkAllReadMutate).toHaveBeenCalledWith("update")
    })

    it("disables mark all read while the request is pending", async () => {
        setCounts(0, 2)
        mockUseMarkAllRead.mockReturnValue({ mutate: mockMarkAllReadMutate, isPending: true })
        render(<NotificationBell />)
        const panel = openPanel()
        fireEvent.click(within(panel).getByRole("tab", { name: /Updates/ }))

        const button = await within(panel).findByRole("button", { name: "Mark all read" })
        expect(button).toBeDisabled()
        expect(button).toHaveAttribute("aria-busy", "true")
    })

    it("rings the bell for a new action item but not for an update", () => {
        mockUseNotificationSocket.mockReturnValue({
            isConnected: true,
            lastNotification: { id: "n9", tier: "action", title: "Approval needed" },
        })
        const { container, rerender } = render(<NotificationBell />)
        expect(container.querySelector("svg.motion-safe\\:animate-bell-ring")).not.toBeNull()

        mockUseNotificationSocket.mockReturnValue({
            isConnected: true,
            lastNotification: { id: "u9", tier: "update", title: "Moved to Screening" },
        })
        rerender(<NotificationBell />)
        expect(container.querySelector("svg.motion-safe\\:animate-bell-ring")).toBeNull()
    })

    it("offers desktop alerts until the browser permission is decided", async () => {
        mockUseBrowserNotifications.mockReturnValue({
            isSupported: true,
            permission: "default",
            requestPermission: mockRequestPermission.mockResolvedValue("granted"),
            showNotification: vi.fn(),
        })
        render(<NotificationBell />)
        const panel = openPanel()

        expect(within(panel).getByText("Desktop alerts are off")).toBeInTheDocument()
        fireEvent.click(within(panel).getByRole("button", { name: "Turn on" }))

        await waitFor(() => expect(mockToastSuccess).toHaveBeenCalledWith("Desktop alerts on"))
    })

    it("hides the desktop alert prompt once permission is decided", () => {
        render(<NotificationBell />)

        expect(within(openPanel()).queryByText("Desktop alerts are off")).toBeNull()
    })

    it("opens once after login when action items exist", async () => {
        sessionStorage.setItem("notification_login_reminder_pending", "1")
        setCounts(3, 0)

        render(<NotificationBell />)

        await waitFor(() => {
            expect(screen.getByTestId("notification-panel")).toHaveAttribute("data-open", "true")
        })
        expect(sessionStorage.getItem("notification_login_reminder_pending")).toBeNull()
        expect(mockMarkReadMutate).not.toHaveBeenCalled()
        expect(mockMarkAllReadMutate).not.toHaveBeenCalled()
    })

    it("consumes the login reminder without opening when only updates are unread", async () => {
        sessionStorage.setItem("notification_login_reminder_pending", "1")
        setCounts(0, 6)

        render(<NotificationBell />)

        await waitFor(() => {
            expect(sessionStorage.getItem("notification_login_reminder_pending")).toBeNull()
        })
        expect(screen.getByTestId("notification-panel")).toHaveAttribute("data-open", "false")
    })

    it("does not open for action items without a fresh login reminder", () => {
        setCounts(3, 0)

        render(<NotificationBell />)

        expect(screen.getByTestId("notification-panel")).toHaveAttribute("data-open", "false")
    })
})
