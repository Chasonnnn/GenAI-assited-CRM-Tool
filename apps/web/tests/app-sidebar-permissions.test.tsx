import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import type { ReactNode } from "react"

import { AppSidebar } from "../components/app-sidebar"

const mockUseAuth = vi.fn()
const mockUseEffectivePermissions = vi.fn()

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => mockUseAuth(),
}))

vi.mock("@/lib/hooks/use-permissions", () => ({
    useEffectivePermissions: () => mockUseEffectivePermissions(),
}))

vi.mock("next/navigation", () => ({
    usePathname: () => "/settings/team",
    useSearchParams: () => ({
        get: () => null,
    }),
}))

vi.mock("next/link", () => ({
    default: ({
        children,
        href,
        prefetch: _prefetch,
        ...props
    }: {
        children: ReactNode
        href: string
        prefetch?: boolean
    }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}))

vi.mock("@/hooks/use-mobile", () => ({
    useIsMobile: () => false,
}))

vi.mock("@/components/search-command", () => ({
    useSearchHotkey: () => {},
    SearchCommandDialog: () => null,
}))

vi.mock("@/components/notification-bell", () => ({
    NotificationBell: () => null,
}))

vi.mock("@/components/theme-toggle", () => ({
    ThemeToggle: () => null,
}))

vi.mock("@/components/ui/avatar", () => ({
    Avatar: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    AvatarImage: () => null,
    AvatarFallback: ({ children }: { children: ReactNode }) => <span>{children}</span>,
}))

vi.mock("@/components/ui/button", () => ({
    Button: ({
        children,
        render,
        ...props
    }: {
        children?: ReactNode
        render?: ReactNode
    }) => (render ? render : <button type="button" {...props}>{children}</button>),
}))

vi.mock("@/components/ui/dropdown-menu", () => ({
    DropdownMenu: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DropdownMenuTrigger: ({
        children,
        render,
    }: {
        children: ReactNode
        render?: ReactNode
    }) => <>{render ?? children}</>,
    DropdownMenuContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DropdownMenuGroup: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DropdownMenuItem: ({ children, render }: { children?: ReactNode; render?: ReactNode }) => (
        <>{render ?? children}</>
    ),
    DropdownMenuLabel: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DropdownMenuSeparator: () => <div />,
}))

describe("AppSidebar permission visibility", () => {
    beforeEach(() => {
        mockUseAuth.mockReturnValue({
            user: {
                user_id: "user-1",
                role: "admin",
                display_name: "Admin User",
                email: "admin@test.com",
                org_name: "Org",
                org_display_name: "Org",
                ai_enabled: false,
            },
        })
    })

    it("hides Team settings when manage_team permission is missing", async () => {
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: ["view_audit_log"] },
        })

        render(
            <AppSidebar>
                <div>content</div>
            </AppSidebar>
        )

        await waitFor(() => {
            expect(screen.getByText("General")).toBeInTheDocument()
        })
        expect(screen.queryByText("Team")).not.toBeInTheDocument()
        expect(screen.getByText("Audit Log")).toBeInTheDocument()
    })

    it("shows Team settings when manage_team permission exists", async () => {
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: ["manage_team", "view_audit_log"] },
        })

        render(
            <AppSidebar>
                <div>content</div>
            </AppSidebar>
        )

        await waitFor(() => {
            expect(screen.getByText("Team")).toBeInTheDocument()
        })
    })

    it("hides Tickets for non-developers even when view_tickets permission exists", async () => {
        mockUseAuth.mockReturnValue({
            user: {
                user_id: "user-1",
                role: "admin",
                display_name: "Admin User",
                email: "admin@test.com",
                org_name: "Org",
                org_display_name: "Org",
                ai_enabled: false,
            },
        })
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: ["view_tickets", "manage_team"] },
        })

        render(
            <AppSidebar>
                <div>content</div>
            </AppSidebar>
        )

        await waitFor(() => {
            expect(screen.getByText("Dashboard")).toBeInTheDocument()
        })
        expect(screen.queryByText("Tickets")).not.toBeInTheDocument()
    })

    it("shows Tickets for developer role", async () => {
        mockUseAuth.mockReturnValue({
            user: {
                user_id: "user-dev",
                role: "developer",
                display_name: "Dev User",
                email: "dev@test.com",
                org_name: "Org",
                org_display_name: "Org",
                ai_enabled: false,
            },
        })
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: [] },
        })

        render(
            <AppSidebar>
                <div>content</div>
            </AppSidebar>
        )

        await waitFor(() => {
            expect(screen.getByText("Tickets")).toBeInTheDocument()
        })
    })

    it("shows Integrations settings for case managers without manage_integrations permission", async () => {
        mockUseAuth.mockReturnValue({
            user: {
                user_id: "user-2",
                role: "case_manager",
                display_name: "Case Manager User",
                email: "cm@test.com",
                org_name: "Org",
                org_display_name: "Org",
                ai_enabled: false,
            },
        })
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: ["view_audit_log"] },
        })

        render(
            <AppSidebar>
                <div>content</div>
            </AppSidebar>
        )

        await waitFor(() => {
            expect(screen.getByText("Integrations")).toBeInTheDocument()
        })
    })

    it("exposes accessible labels and expanded state for navigation and user menu", async () => {
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: ["manage_team", "view_audit_log"] },
        })

        render(
            <AppSidebar>
                <div>content</div>
            </AppSidebar>
        )

        await waitFor(() => {
            expect(screen.getByRole("button", { name: "Tasks & Scheduling" })).toBeInTheDocument()
        })

        expect(screen.getByRole("button", { name: "Tasks & Scheduling" })).toHaveAttribute(
            "aria-expanded",
            "false"
        )
        expect(screen.getByRole("button", { name: "Automation" })).toHaveAttribute(
            "aria-expanded",
            "false"
        )
        expect(screen.getByRole("button", { name: "Settings" })).toHaveAttribute(
            "aria-expanded",
            "true"
        )
        expect(screen.getByLabelText("User menu")).toBeInTheDocument()
    })

    it("hides the visual Navigation heading when collapsed but keeps nav aria-label", async () => {
        document.cookie = "sidebar_state=false"
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: ["manage_team", "view_audit_log"] },
        })

        render(
            <AppSidebar>
                <div>content</div>
            </AppSidebar>
        )

        await waitFor(() => {
            expect(screen.getByRole("navigation", { name: "Navigation" })).toBeInTheDocument()
        })
        expect(screen.queryByText("Navigation")).not.toBeInTheDocument()
    })
})
