import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"
import type { ReactNode } from "react"

import { AppSidebar } from "@/components/app-sidebar"

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
    usePathname: () => "/dashboard",
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

function transitionProperties(element: Element) {
    const token = Array.from(element.classList).find((name) => name.startsWith("transition-["))
    return token ? token.slice("transition-[".length, -1).split(",") : []
}

describe("AppSidebar mobile motion", () => {
    it("transitions the translate property that slides the mobile sidebar", () => {
        const view = render(
            <AppSidebar>
                <div>content</div>
            </AppSidebar>
        )
        const sidebar = view.container.querySelector("aside")
        expect(sidebar).toHaveClass("-translate-x-full")

        fireEvent.click(screen.getByRole("button", { name: "Toggle sidebar" }))

        expect(sidebar).toHaveClass("translate-x-0")
        expect(transitionProperties(sidebar!)).toContain("translate")
    })

    it("fades the mobile backdrop in when it mounts", () => {
        render(
            <AppSidebar>
                <div>content</div>
            </AppSidebar>
        )

        fireEvent.click(screen.getByRole("button", { name: "Toggle sidebar" }))

        expect(screen.getByRole("button", { name: "Close sidebar overlay" })).toHaveClass(
            "animate-in",
            "fade-in-0",
        )
    })

    it("closes on Escape from the trigger or inside the sidebar and returns focus to the trigger", () => {
        const view = render(
            <AppSidebar>
                <div>content</div>
            </AppSidebar>
        )
        const sidebar = view.container.querySelector("aside")!
        const trigger = screen.getByRole("button", { name: "Toggle sidebar" })

        fireEvent.click(trigger)
        trigger.focus()
        fireEvent.keyDown(trigger, { key: "Escape" })
        expect(sidebar).toHaveClass("-translate-x-full")
        expect(screen.queryByRole("button", { name: "Close sidebar overlay" })).not.toBeInTheDocument()

        fireEvent.click(trigger)
        const link = sidebar.querySelector("a[href]") as HTMLElement
        link.focus()
        fireEvent.keyDown(link, { key: "Escape" })
        expect(sidebar).toHaveClass("-translate-x-full")
        expect(trigger).toHaveFocus()
    })

    it("leaves the sidebar open when Escape comes from an open menu", () => {
        const view = render(
            <AppSidebar>
                <div role="menu" tabIndex={-1} data-testid="menu" />
            </AppSidebar>
        )
        const sidebar = view.container.querySelector("aside")!

        fireEvent.click(screen.getByRole("button", { name: "Toggle sidebar" }))
        fireEvent.keyDown(screen.getByTestId("menu"), { key: "Escape" })

        expect(sidebar).toHaveClass("translate-x-0")
    })
})
