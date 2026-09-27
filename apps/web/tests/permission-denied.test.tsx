import { fireEvent, render, renderHook, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ApiError } from "@/lib/api"

const mocks = vi.hoisted(() => ({
    useAuth: vi.fn(),
    useEffectivePermissions: vi.fn(),
}))

vi.mock("@/components/app-link", () => ({
    default: ({ children, href, ...props }: React.ComponentProps<"a">) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}))

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => mocks.useAuth(),
}))

vi.mock("@/lib/hooks/use-permissions", () => ({
    useEffectivePermissions: (userId: string | null) => mocks.useEffectivePermissions(userId),
}))

import { PermissionDeniedState, QueryErrorState } from "@/components/error-state"
import { getQueryErrorKind, isPermissionError } from "@/lib/error-utils"
import { usePermissionCheck } from "@/lib/hooks/use-permission-check"

describe("PermissionDeniedState", () => {
    it("explains the denial and links back without a retry by default", () => {
        const { container } = render(
            <PermissionDeniedState
                description="Compliance settings need the Manage compliance permission. Ask an admin to update your role."
                secondaryHref="/settings"
                secondaryLabel="Back to Settings"
            />
        )

        expect(screen.getByText("Permission required")).toBeInTheDocument()
        expect(screen.getByText(/Manage compliance permission/)).toBeInTheDocument()
        expect(screen.getByRole("link", { name: "Back to Settings" })).toHaveAttribute("href", "/settings")
        expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument()

        const icon = container.querySelector("svg")
        expect(icon).toHaveAttribute("aria-hidden", "true")
        expect(icon).toHaveClass("text-warning")
    })
})

describe("QueryErrorState on a 403", () => {
    it("renders the denied state instead of a load error or empty data", () => {
        render(
            <QueryErrorState
                error={new ApiError(403, "Forbidden", "Missing permission: manage_forms")}
                onRetry={vi.fn()}
                title="Couldn't load forms"
                forbidden={{
                    title: "No access to Form Builder",
                    description: "Form Builder needs the Manage forms permission.",
                    secondaryHref: "/dashboard",
                }}
            />
        )

        expect(screen.getByText("No access to Form Builder")).toBeInTheDocument()
        expect(screen.queryByText("Couldn't load forms")).not.toBeInTheDocument()
        expect(screen.queryByText(/manage_forms/)).not.toBeInTheDocument()
    })

    it("falls back to a generic denied state without forbidden copy", () => {
        render(
            <QueryErrorState
                error={new ApiError(403, "Forbidden")}
                onRetry={vi.fn()}
                title="Couldn't load members"
            />
        )

        expect(screen.getByText("Permission required")).toBeInTheDocument()
        expect(screen.getByText("Ask an admin to update your role.")).toBeInTheDocument()
    })

    it("classifies 403 as forbidden", () => {
        expect(isPermissionError(new ApiError(403, "Forbidden"))).toBe(true)
        expect(getQueryErrorKind(new ApiError(403, "Forbidden"))).toBe("forbidden")
        expect(isPermissionError(new Error("403"))).toBe(false)
    })
})

describe("usePermissionCheck", () => {
    beforeEach(() => {
        mocks.useAuth.mockReset()
        mocks.useEffectivePermissions.mockReset()
    })

    it("allows only the permissions the viewer holds", () => {
        mocks.useAuth.mockReturnValue({ user: { user_id: "u1", role: "intake" }, isLoading: false })
        mocks.useEffectivePermissions.mockReturnValue({
            data: { permissions: ["view_surrogates"] },
            isLoading: false,
        })

        const { result } = renderHook(() => usePermissionCheck())

        expect(mocks.useEffectivePermissions).toHaveBeenCalledWith("u1")
        expect(result.current.isLoading).toBe(false)
        expect(result.current.can("view_surrogates")).toBe(true)
        expect(result.current.can("manage_compliance")).toBe(false)
    })

    it("stays loading until effective permissions arrive, then denies on a failed lookup", () => {
        mocks.useAuth.mockReturnValue({ user: { user_id: "u1", role: "case_manager" }, isLoading: false })
        mocks.useEffectivePermissions.mockReturnValue({ data: undefined, isLoading: true })

        const { result, rerender } = renderHook(() => usePermissionCheck())
        expect(result.current.isLoading).toBe(true)

        mocks.useEffectivePermissions.mockReturnValue({ data: undefined, isLoading: false, isError: true })
        rerender()
        expect(result.current.isLoading).toBe(false)
        expect(result.current.can("manage_team")).toBe(false)
    })

    it("grants developers every permission without waiting for the lookup", () => {
        mocks.useAuth.mockReturnValue({ user: { user_id: "dev", role: "developer" }, isLoading: false })
        mocks.useEffectivePermissions.mockReturnValue({ data: undefined, isLoading: true })

        const { result } = renderHook(() => usePermissionCheck())

        expect(result.current.isLoading).toBe(false)
        expect(result.current.can("manage_ops")).toBe(true)
    })
})

describe("PermissionDeniedState actions", () => {
    it("keeps the optional retry for callers that pass onRetry", () => {
        const onRetry = vi.fn()
        render(<PermissionDeniedState description="Ask an admin for access." onRetry={onRetry} />)

        fireEvent.click(screen.getByRole("button", { name: "Try again" }))
        expect(onRetry).toHaveBeenCalledOnce()
    })
})
