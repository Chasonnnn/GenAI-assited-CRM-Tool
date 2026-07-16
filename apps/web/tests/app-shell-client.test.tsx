import type { ReactNode } from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { renderToString } from "react-dom/server"

import AppShellClient from "@/components/app-shell-client"

const mocks = vi.hoisted(() => ({
    redirect: vi.fn(),
    replace: vi.fn(),
    useAuth: vi.fn(),
}))

vi.mock("next/navigation", () => ({
    redirect: (path: string) => mocks.redirect(path),
    usePathname: () => "/dashboard",
    useRouter: () => ({ replace: mocks.replace }),
}))

vi.mock("next/dynamic", () => ({
    default: () =>
        function DynamicSidebar({ children }: { children: ReactNode }) {
            return <div data-testid="sidebar">{children}</div>
        },
}))

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => mocks.useAuth(),
}))

vi.mock("@/lib/context/ai-context", () => ({
    AIContextProvider: ({ children }: { children: ReactNode }) => children,
}))

vi.mock("@/components/ai/AIChatDrawerHost", () => ({
    AIChatDrawerHost: () => null,
}))

vi.mock("@/components/ai/AIFloatingButton", () => ({
    AIFloatingButton: () => null,
}))

vi.mock("@/components/offline-banner", () => ({
    OfflineBanner: () => null,
}))

vi.mock("@/components/session-expired-dialog", () => ({
    SessionExpiredDialog: () => null,
}))

describe("AppShellClient", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        document.cookie = "auth_return_to=; max-age=0; path=/"
    })

    it("redirects signed-out users during initial rendering before protected children mount", () => {
        mocks.useAuth.mockReturnValue({
            user: null,
            isLoading: false,
        })

        const html = renderToString(
            <AppShellClient>
                <div>Protected dashboard</div>
            </AppShellClient>
        )

        expect(mocks.redirect).toHaveBeenCalledWith("/login")
        expect(html).not.toContain("Protected dashboard")
    })

    it("redirects MFA-required users during initial rendering before protected children mount", () => {
        mocks.useAuth.mockReturnValue({
            user: {
                user_id: "user-1",
                profile_complete: true,
                mfa_required: true,
                mfa_verified: false,
            },
            isLoading: false,
        })

        const html = renderToString(
            <AppShellClient>
                <div>Protected dashboard</div>
            </AppShellClient>
        )

        expect(mocks.redirect).toHaveBeenCalledWith("/mfa")
        expect(html).not.toContain("Protected dashboard")
    })

    it("preserves the ops return target for MFA-required users", () => {
        document.cookie = "auth_return_to=ops; path=/"
        mocks.useAuth.mockReturnValue({
            user: {
                user_id: "user-1",
                profile_complete: true,
                mfa_required: true,
                mfa_verified: false,
            },
            isLoading: false,
        })

        renderToString(
            <AppShellClient>
                <div>Protected dashboard</div>
            </AppShellClient>
        )

        expect(mocks.redirect).toHaveBeenCalledWith("/mfa?return_to=ops")
    })

    it("redirects incomplete profiles during initial rendering before protected children mount", () => {
        mocks.useAuth.mockReturnValue({
            user: {
                user_id: "user-1",
                profile_complete: false,
                mfa_required: false,
                mfa_verified: false,
            },
            isLoading: false,
        })

        const html = renderToString(
            <AppShellClient>
                <div>Protected dashboard</div>
            </AppShellClient>
        )

        expect(mocks.redirect).toHaveBeenCalledWith("/welcome")
        expect(mocks.replace).not.toHaveBeenCalled()
        expect(html).not.toContain("Protected dashboard")
    })
})
