import { render, screen } from "@testing-library/react"
import { renderToStaticMarkup } from "react-dom/server"
import { describe, it, expect, vi } from "vitest"

import RootLayout from "@/app/layout"
import AppLayout from "@/app/(app)/layout"
import MfaLayout from "@/app/mfa/layout"
import AuthLayout from "@/app/auth/layout"

vi.mock("@/lib/auth-context", () => ({
    AuthProvider: ({ children }: { children: React.ReactNode }) => (
        <div data-testid="auth-provider">{children}</div>
    ),
}))

vi.mock("@/components/app-shell-client", () => ({
    default: ({ children }: { children: React.ReactNode }) => (
        <div data-testid="app-shell">{children}</div>
    ),
}))

vi.mock("@/lib/query-provider", () => ({
    QueryProvider: ({ children }: { children: React.ReactNode }) => (
        <div data-testid="query-provider">{children}</div>
    ),
}))

vi.mock("@/components/theme-provider", () => ({
    ThemeProvider: ({ children }: { children: React.ReactNode }) => (
        <div data-testid="theme-provider">{children}</div>
    ),
}))

vi.mock("@/components/ui/sonner", () => ({
    Toaster: () => <div data-testid="toaster" />,
}))

vi.mock("next/font/google", () => ({
    Noto_Sans: () => ({ variable: "font-noto-sans" }),
}))

describe("layout auth provider placement", () => {
    it("does not wrap root layout with AuthProvider", () => {
        const markup = renderToStaticMarkup(
            <RootLayout>
                <div>child</div>
            </RootLayout>,
        )

        expect(markup).not.toContain("data-testid=\"auth-provider\"")
    })

    it("wraps app layout with AuthProvider", () => {
        render(
            <AppLayout>
                <div>child</div>
            </AppLayout>,
        )

        expect(screen.getByTestId("auth-provider")).toBeInTheDocument()
    })

    it("wraps mfa layout with AuthProvider", () => {
        render(
            <MfaLayout>
                <div>child</div>
            </MfaLayout>,
        )

        expect(screen.getByTestId("auth-provider")).toBeInTheDocument()
    })

    it("wraps auth layout with AuthProvider", () => {
        render(
            <AuthLayout>
                <div>child</div>
            </AuthLayout>,
        )

        expect(screen.getByTestId("auth-provider")).toBeInTheDocument()
    })
})
