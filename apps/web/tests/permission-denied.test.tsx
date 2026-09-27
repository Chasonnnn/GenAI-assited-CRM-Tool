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

import { LoadErrorState, PermissionDeniedState, QueryErrorState } from "@/components/error-state"
import { getNonRoleForbiddenReason, getQueryErrorKind, isPermissionError } from "@/lib/error-utils"
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

    it.each([
        ["AI is not enabled", "AI is off for this organization"],
        ["AI is not enabled for this organization", "AI is off for this organization"],
        ["AI features are not enabled for this organization", "AI is off for this organization"],
        ["AI consent not accepted", "AI consent required"],
        [
            "AI consent not accepted. An admin must accept the data processing consent before using AI.",
            "AI consent required",
        ],
        ["AI consent has not been accepted for this organization", "AI consent required"],
        ["Organization is scheduled for deletion", "Organization scheduled for deletion"],
        ["Session invalid for this domain", "Wrong organization address"],
        ["MFA verification required", "Verification required"],
        ["No organization membership", "No active membership"],
        ["Membership inactive", "No active membership"],
    ])("shows product copy, not role copy, for the non-role 403 %j", (detail, title) => {
        render(
            <QueryErrorState
                error={new ApiError(403, "Forbidden", detail)}
                onRetry={vi.fn()}
                title="Couldn't load surrogate"
                forbidden={{
                    title: "No access to this surrogate",
                    description: "Ask an admin or the case owner for access.",
                    secondaryHref: "/surrogates",
                    secondaryLabel: "Back to Surrogates",
                }}
            />
        )

        expect(screen.getByText(title)).toBeInTheDocument()
        expect(screen.queryByText("No access to this surrogate")).not.toBeInTheDocument()
        expect(screen.queryByText(/update your role|case owner/)).not.toBeInTheDocument()
        expect(screen.queryByText(detail)).not.toBeInTheDocument()
        expect(screen.getByRole("link", { name: "Back to Surrogates" })).toHaveAttribute("href", "/surrogates")
        expect(getNonRoleForbiddenReason(new ApiError(403, "Forbidden", detail))).not.toBeNull()
    })

    it("keeps role copy for permission denials and never renders their server detail", () => {
        render(
            <QueryErrorState
                error={new ApiError(403, "Forbidden", "You don't have access to this surrogate")}
                onRetry={vi.fn()}
                title="Couldn't load surrogate"
            />
        )

        expect(screen.getByText("Permission required")).toBeInTheDocument()
        expect(screen.getByText("Ask an admin to update your role.")).toBeInTheDocument()
        expect(screen.queryByText(/have access to this surrogate/)).not.toBeInTheDocument()
    })

    it("matches only exact 403 details", () => {
        expect(getNonRoleForbiddenReason(new ApiError(403, "Forbidden", "Missing permission: use_ai"))).toBeNull()
        expect(getNonRoleForbiddenReason(new ApiError(403, "Forbidden", "AI is not enabled yet"))).toBeNull()
        expect(getNonRoleForbiddenReason(new ApiError(500, "Error", "AI is not enabled"))).toBeNull()
        expect(getNonRoleForbiddenReason(new Error("AI is not enabled"))).toBeNull()
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

    it("stays loading until effective permissions arrive, then reports a failed lookup as an error", () => {
        mocks.useAuth.mockReturnValue({ user: { user_id: "u1", role: "case_manager" }, isLoading: false })
        mocks.useEffectivePermissions.mockReturnValue({ data: undefined, isLoading: true })

        const { result, rerender } = renderHook(() => usePermissionCheck())
        expect(result.current.isLoading).toBe(true)
        expect(result.current.isError).toBe(false)

        const refetch = vi.fn().mockResolvedValue(undefined)
        mocks.useEffectivePermissions.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            isFetching: false,
            error: new ApiError(500, "Internal Server Error"),
            refetch,
        })
        rerender()
        expect(result.current.isLoading).toBe(false)
        expect(result.current.isError).toBe(true)
        expect(result.current.isRetrying).toBe(false)
        expect(result.current.can("manage_team")).toBe(false)

        result.current.retry()
        expect(refetch).toHaveBeenCalledOnce()
    })

    it("denies without an error state when the lookup itself is forbidden", () => {
        mocks.useAuth.mockReturnValue({ user: { user_id: "u1", role: "intake" }, isLoading: false })
        mocks.useEffectivePermissions.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            error: new ApiError(403, "Forbidden", "No organization membership"),
            refetch: vi.fn(),
        })

        const { result } = renderHook(() => usePermissionCheck())

        expect(result.current.isError).toBe(false)
        expect(result.current.can("view_surrogates")).toBe(false)
    })

    it("keeps the last permissions when a background refetch fails", () => {
        mocks.useAuth.mockReturnValue({ user: { user_id: "u1", role: "intake" }, isLoading: false })
        mocks.useEffectivePermissions.mockReturnValue({
            data: { permissions: ["view_surrogates"] },
            isLoading: false,
            isError: true,
            error: new Error("Network error"),
            refetch: vi.fn(),
        })

        const { result } = renderHook(() => usePermissionCheck())

        expect(result.current.isError).toBe(false)
        expect(result.current.can("view_surrogates")).toBe(true)
    })

    it("lets a page render a retryable load error instead of the denied state", () => {
        const refetch = vi.fn().mockResolvedValue(undefined)
        mocks.useAuth.mockReturnValue({ user: { user_id: "u1", role: "admin" }, isLoading: false })
        mocks.useEffectivePermissions.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            isFetching: false,
            error: new TypeError("Failed to fetch"),
            refetch,
        })

        function GatedPage() {
            const { isLoading, isError, retry, isRetrying, can } = usePermissionCheck()
            if (isLoading) return <p>Loading</p>
            if (isError) {
                return <LoadErrorState title="Couldn't load permissions" onRetry={retry} isRetrying={isRetrying} />
            }
            if (!can("manage_team")) return <PermissionDeniedState description="Ask an admin to update your role." />
            return <p>Team</p>
        }

        render(<GatedPage />)

        expect(screen.getByText("Couldn't load permissions")).toBeInTheDocument()
        expect(screen.queryByText("Permission required")).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Try again" }))
        expect(refetch).toHaveBeenCalledOnce()
    })

    it("grants developers every permission without waiting for the lookup", () => {
        mocks.useAuth.mockReturnValue({ user: { user_id: "dev", role: "developer" }, isLoading: false })
        mocks.useEffectivePermissions.mockReturnValue({ data: undefined, isLoading: true })

        const { result } = renderHook(() => usePermissionCheck())

        expect(result.current.isLoading).toBe(false)
        expect(result.current.can("manage_ops")).toBe(true)
    })

    it("uses the loaded list for developers, which omits AI keys under policy v2 when AI is off", () => {
        mocks.useAuth.mockReturnValue({ user: { user_id: "dev", role: "developer" }, isLoading: false })
        mocks.useEffectivePermissions.mockReturnValue({
            data: { permissions: ["manage_ops", "create_surrogates"], policy_version: 2 },
            isLoading: false,
        })

        const { result } = renderHook(() => usePermissionCheck())

        expect(result.current.can("manage_ops")).toBe(true)
        expect(result.current.can("use_ai_assistant")).toBe(false)
    })

    it("exposes the policy version so callers can pick per-version keys", () => {
        mocks.useAuth.mockReturnValue({ user: { user_id: "u1", role: "case_manager" }, isLoading: false })
        mocks.useEffectivePermissions.mockReturnValue({
            data: { permissions: ["edit_intended_parents"], policy_version: 1 },
            isLoading: false,
        })

        const { result, rerender } = renderHook(() => usePermissionCheck())
        const createKey = () =>
            result.current.policyVersion === 2 ? "create_intended_parents" : "edit_intended_parents"

        expect(result.current.policyVersion).toBe(1)
        expect(result.current.can(createKey())).toBe(true)

        mocks.useEffectivePermissions.mockReturnValue({
            data: { permissions: ["edit_intended_parents"], policy_version: 2 },
            isLoading: false,
        })
        rerender()

        expect(result.current.policyVersion).toBe(2)
        expect(result.current.can(createKey())).toBe(false)
    })

    it("leaves the policy version undefined until the lookup loads", () => {
        mocks.useAuth.mockReturnValue({ user: { user_id: "u1", role: "admin" }, isLoading: false })
        mocks.useEffectivePermissions.mockReturnValue({ data: undefined, isLoading: true })

        const { result } = renderHook(() => usePermissionCheck())

        expect(result.current.policyVersion).toBeUndefined()
        expect(result.current.can("view_surrogates")).toBe(false)
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
