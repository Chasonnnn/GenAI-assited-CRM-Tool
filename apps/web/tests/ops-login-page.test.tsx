import type { ReactNode } from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import OpsLoginPage from "@/app/ops/login/page"
import OpsLoginPageClient from "@/app/ops/login/page.client"

vi.mock("@/components/app-link", () => ({
    __esModule: true,
    default: ({
        href,
        children,
        fallbackMode,
        ...props
    }: {
        href: string
        children: ReactNode
        fallbackMode?: string
    }) => (
        <a href={href} data-fallback-mode={fallbackMode} {...props}>
            {children}
        </a>
    ),
}))

const assignLocation = vi.mocked(window.location.assign)

describe("OpsLoginPageClient", () => {
    beforeEach(() => {
        assignLocation.mockClear()
        window.sessionStorage.clear()
    })

    it("explains a missing platform role and links back to the app", () => {
        render(<OpsLoginPageClient errorCode="not_platform_admin" />)

        expect(screen.getByRole("alert")).toHaveTextContent("This account does not have platform access.")
        const backLink = screen.getByRole("link", { name: "Back to app" })
        expect(backLink).toHaveAttribute("href", "/dashboard")
        // A client-side navigation keeps the ops AuthProvider state (no user) and redirects to /login.
        expect(backLink).toHaveAttribute("data-fallback-mode", "reload")
        expect(screen.getByRole("button", { name: /sign in with google/i })).toBeEnabled()
    })

    it("reads the error code from the route search params, not window.location", async () => {
        // The layout redirects with router.replace, so window.location still shows /ops here.
        const page = await OpsLoginPage({ searchParams: Promise.resolve({ error: "not_platform_admin" }) })
        render(page)

        expect(screen.getByRole("alert")).toHaveTextContent("This account does not have platform access.")
        expect(screen.getByRole("link", { name: "Back to app" })).toBeInTheDocument()
    })

    it("shows a generic message for an unknown error code", async () => {
        const page = await OpsLoginPage({ searchParams: Promise.resolve({ error: ["unexpected", "other"] }) })
        render(page)

        expect(screen.getByRole("alert")).toHaveTextContent("An error occurred.")
        expect(screen.queryByRole("link", { name: "Back to app" })).not.toBeInTheDocument()
    })

    it("uses the default button variant without color overrides", () => {
        render(<OpsLoginPageClient />)

        const button = screen.getByRole("button", { name: /sign in with google/i })
        expect(button.className).not.toMatch(/\bbg-stone|\btext-stone|dark:bg-/)
        expect(screen.queryByRole("link", { name: "Back to app" })).not.toBeInTheDocument()
        expect(screen.queryByRole("alert")).not.toBeInTheDocument()
    })

    it("stores the ops return target and shows redirecting feedback", () => {
        render(<OpsLoginPageClient />)

        const button = screen.getByRole("button", { name: /sign in with google/i })
        fireEvent.click(button)

        expect(button).toBeDisabled()
        expect(button).toHaveTextContent("Signing In...")
        expect(window.sessionStorage.getItem("auth_return_to")).toBe("ops")
        expect(assignLocation).toHaveBeenCalledWith(
            expect.stringContaining("/auth/google/login?return_to=ops"),
        )
    })
})
