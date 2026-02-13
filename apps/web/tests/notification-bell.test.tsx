import type { ButtonHTMLAttributes, ReactNode } from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"

import { NotificationBell } from "@/components/notification-bell"

const mockPush = vi.fn()
const mockUseNotifications = vi.fn()
const mockUseUnreadCount = vi.fn()
const mockUseNotificationSocket = vi.fn()
const mockMarkReadMutate = vi.fn()
const mockMarkAllReadMutate = vi.fn()

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: mockPush }),
}))

vi.mock("@/components/ui/dropdown-menu", () => ({
    DropdownMenu: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DropdownMenuTrigger: ({
        children,
        ...props
    }: { children?: ReactNode } & ButtonHTMLAttributes<HTMLButtonElement>) => (
        <button type="button" {...props}>
            {children}
        </button>
    ),
    DropdownMenuContent: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DropdownMenuItem: ({
        children,
        ...props
    }: { children?: ReactNode } & ButtonHTMLAttributes<HTMLButtonElement>) => (
        <button type="button" {...props}>
            {children}
        </button>
    ),
    DropdownMenuSeparator: () => <hr />,
}))

vi.mock("@/components/ui/scroll-area", () => ({
    ScrollArea: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
}))

vi.mock("@/lib/hooks/use-notifications", () => ({
    useNotifications: (params: unknown) => mockUseNotifications(params),
    useUnreadCount: () => mockUseUnreadCount(),
    useMarkRead: () => ({ mutate: mockMarkReadMutate }),
    useMarkAllRead: () => ({ mutate: mockMarkAllReadMutate }),
}))

vi.mock("@/lib/hooks/use-notification-socket", () => ({
    useNotificationSocket: () => mockUseNotificationSocket(),
}))

vi.mock("@/lib/hooks/use-browser-notifications", () => ({
    useBrowserNotifications: () => ({
        permission: "denied",
        showNotification: vi.fn(),
    }),
}))

describe("NotificationBell", () => {
    beforeEach(() => {
        mockPush.mockReset()
        mockMarkReadMutate.mockReset()
        mockMarkAllReadMutate.mockReset()
        mockUseNotificationSocket.mockReturnValue({
            lastNotification: null,
            unreadCount: null,
        })
        mockUseUnreadCount.mockReturnValue({ data: { count: 0 }, isLoading: false })
        mockUseNotifications.mockReturnValue({
            data: { items: [], unread_count: 0 },
            isLoading: false,
        })
    })

    it("announces unread count in the trigger aria-label", () => {
        mockUseUnreadCount.mockReturnValue({ data: { count: 3 }, isLoading: false })

        render(<NotificationBell />)

        expect(screen.getByRole("button", { name: "Notifications (3 unread)" })).toBeInTheDocument()
    })

    it("announces no unread messages in the trigger aria-label", () => {
        render(<NotificationBell />)

        expect(
            screen.getByRole("button", { name: "Notifications (no unread messages)" })
        ).toBeInTheDocument()
    })

    it("renders loading state while notifications are being fetched", () => {
        mockUseNotifications.mockReturnValue({
            data: undefined,
            isLoading: true,
        })

        render(<NotificationBell />)

        expect(screen.getByLabelText("Loading notifications")).toBeInTheDocument()
    })

    it("exposes unread state to screen readers in list items", () => {
        mockUseNotifications.mockReturnValue({
            data: {
                unread_count: 1,
                items: [
                    {
                        id: "n1",
                        type: "surrogate_assigned",
                        title: "Surrogate assigned",
                        body: "A surrogate was assigned.",
                        entity_type: "surrogate",
                        entity_id: "s1",
                        read_at: null,
                        created_at: new Date().toISOString(),
                    },
                ],
            },
            isLoading: false,
        })
        mockUseUnreadCount.mockReturnValue({ data: { count: 1 }, isLoading: false })

        render(<NotificationBell />)

        expect(screen.getByText("Unread")).toBeInTheDocument()
    })
})
