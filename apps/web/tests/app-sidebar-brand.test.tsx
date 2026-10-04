import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { render, waitFor, within } from "@testing-library/react"
import type { ReactNode } from "react"

import { AppSidebar } from "../components/app-sidebar"
import { getOrgInitials } from "@/lib/org-initials"

const mockUseAuth = vi.fn()

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => mockUseAuth(),
}))

vi.mock("@/lib/hooks/use-permissions", () => ({
    useEffectivePermissions: () => ({ data: { permissions: [] } }),
}))

vi.mock("next/navigation", () => ({
    usePathname: () => "/dashboard",
    useSearchParams: () => ({ get: () => null }),
}))

vi.mock("next/link", () => ({
    default: ({ children, href, prefetch: _prefetch, ...props }: { children: ReactNode; href: string; prefetch?: boolean | null }) => (
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

vi.mock("@/components/ui/dropdown-menu", () => ({
    DropdownMenu: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DropdownMenuTrigger: ({ children, render }: { children: ReactNode; render?: ReactNode }) => <>{render ?? children}</>,
    DropdownMenuContent: () => null,
    DropdownMenuGroup: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DropdownMenuItem: ({ children }: { children?: ReactNode }) => <>{children}</>,
    DropdownMenuLabel: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DropdownMenuSeparator: () => <div />,
}))

/** jsdom never loads images; this stand-in loads every src so Base UI renders the logo. */
class LoadingImage {
    onload: (() => void) | null = null
    onerror: (() => void) | null = null
    complete = false
    naturalWidth = 0
    referrerPolicy = ""
    crossOrigin: string | null = null
    set src(_value: string) {
        queueMicrotask(() => this.onload?.())
    }
}

function renderSidebar(user: Record<string, unknown>) {
    mockUseAuth.mockReturnValue({
        user: {
            user_id: "user-1",
            role: "admin",
            display_name: "Admin User",
            email: "admin@test.com",
            ai_enabled: false,
            ...user,
        },
    })
    return render(
        <AppSidebar>
            <div>content</div>
        </AppSidebar>,
    )
}

function getBrand() {
    const brand = document.querySelector('[data-slot="org-logo-tile"]')?.parentElement
    if (!(brand instanceof HTMLElement)) throw new Error("Brand row not rendered")
    return brand
}

describe("AppSidebar organization brand", () => {
    const originalImage = window.Image

    beforeEach(() => {
        document.cookie = "sidebar_state=true"
    })

    afterEach(() => {
        window.Image = originalImage
    })

    it("shows the org name first and Surrogacy Force second with an initials tile", () => {
        renderSidebar({ org_name: "aster-vale", org_display_name: "Aster & Vale Family", org_logo_url: null })

        const brand = getBrand()
        expect(within(brand).getByText("AV")).toBeInTheDocument()
        const orgName = within(brand).getByText("Aster & Vale Family")
        const product = within(brand).getByText("Surrogacy Force")
        expect(orgName.compareDocumentPosition(product)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
        expect(brand.querySelector("img")).toBeNull()
    })

    it("shows the uploaded logo in the tile", async () => {
        window.Image = LoadingImage as unknown as typeof Image
        renderSidebar({
            org_name: "aster-vale",
            org_display_name: "Aster & Vale Family",
            org_logo_url: "https://cdn.example.test/logo.png",
        })

        await waitFor(() => {
            expect(getBrand().querySelector("img")).toHaveAttribute("src", "https://cdn.example.test/logo.png")
        })
        expect(within(getBrand()).queryByText("AV")).not.toBeInTheDocument()
    })

    it("keeps the same tile and announces the org name when collapsed", () => {
        document.cookie = "sidebar_state=false"
        renderSidebar({ org_name: "aster-vale", org_display_name: "Aster & Vale Family", org_logo_url: null })

        const brand = getBrand()
        expect(within(brand).getByText("AV")).toBeInTheDocument()
        expect(within(brand).getByText("Aster & Vale Family")).toHaveClass("sr-only")
        expect(within(brand).queryByText("Surrogacy Force")).not.toBeInTheDocument()
    })
})

describe("getOrgInitials", () => {
    it("takes the first letters of the first two words and skips symbols", () => {
        expect(getOrgInitials("Aster & Vale Family")).toBe("AV")
        expect(getOrgInitials("everhope")).toBe("E")
        expect(getOrgInitials("  (Bright) Path  ")).toBe("BP")
        expect(getOrgInitials("Élan Surrogacy")).toBe("ÉS")
        expect(getOrgInitials("")).toBe("")
        expect(getOrgInitials(null)).toBe("")
    })
})
