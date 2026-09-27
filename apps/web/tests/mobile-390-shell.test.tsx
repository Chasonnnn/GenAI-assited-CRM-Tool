import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"
import type { ReactNode } from "react"

import { AppSidebar } from "@/components/app-sidebar"

const mockNavigationState = vi.hoisted(() => ({ pathname: "/dashboard" }))

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => ({
        user: {
            user_id: "user-1",
            role: "admin",
            display_name: "Admin User",
            email: "admin@test.com",
            org_name: "Org",
            org_display_name: "Org",
            ai_enabled: false,
        },
    }),
}))

vi.mock("@/lib/hooks/use-permissions", () => ({
    useEffectivePermissions: () => ({ data: { permissions: [] } }),
}))

vi.mock("next/navigation", () => ({
    usePathname: () => mockNavigationState.pathname,
    useSearchParams: () => ({ get: () => null }),
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
        prefetch?: boolean | null
    }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}))

vi.mock("@/hooks/use-mobile", () => ({
    useIsMobile: () => true,
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

function renderShell() {
    return render(
        <AppSidebar>
            <div>content</div>
        </AppSidebar>
    )
}

describe("App shell at 390px", () => {
    it("closes the mobile sidebar when the route changes", () => {
        mockNavigationState.pathname = "/dashboard"
        const view = renderShell()
        const sidebar = view.container.querySelector("aside")

        fireEvent.click(screen.getByRole("button", { name: "Toggle sidebar" }))
        expect(sidebar).toHaveClass("translate-x-0")
        expect(screen.getByRole("button", { name: "Close sidebar overlay" })).toBeInTheDocument()

        mockNavigationState.pathname = "/surrogates"
        view.rerender(
            <AppSidebar>
                <div>content</div>
            </AppSidebar>
        )

        expect(sidebar).toHaveClass("-translate-x-full")
        expect(screen.queryByRole("button", { name: "Close sidebar overlay" })).not.toBeInTheDocument()
    })

    it("keeps the mobile sidebar open while the route stays the same", () => {
        mockNavigationState.pathname = "/dashboard"
        const view = renderShell()
        const sidebar = view.container.querySelector("aside")

        fireEvent.click(screen.getByRole("button", { name: "Toggle sidebar" }))
        view.rerender(
            <AppSidebar>
                <div>other content</div>
            </AppSidebar>
        )

        expect(sidebar).toHaveClass("translate-x-0")
    })

    it("closes the mobile sidebar when a tapped link keeps the same pathname", () => {
        // /settings?tab=email-signature -> General (/settings): the pathname does not change.
        mockNavigationState.pathname = "/settings"
        const view = renderShell()
        const sidebar = view.container.querySelector("aside")

        fireEvent.click(screen.getByRole("button", { name: "Toggle sidebar" }))
        expect(sidebar).toHaveClass("translate-x-0")

        const general = screen.getByRole("link", { name: "General" })
        general.addEventListener("click", (event) => event.preventDefault())
        fireEvent.click(general)

        expect(sidebar).toHaveClass("-translate-x-full")
        expect(screen.queryByRole("button", { name: "Close sidebar overlay" })).not.toBeInTheDocument()
    })

    it("keeps the section for the new route expanded after closing", () => {
        mockNavigationState.pathname = "/dashboard"
        const view = renderShell()

        fireEvent.click(screen.getByRole("button", { name: "Toggle sidebar" }))
        mockNavigationState.pathname = "/automation/campaigns"
        view.rerender(
            <AppSidebar>
                <div>content</div>
            </AppSidebar>
        )

        expect(screen.getByRole("link", { name: "Campaigns" })).toBeInTheDocument()
    })
})
