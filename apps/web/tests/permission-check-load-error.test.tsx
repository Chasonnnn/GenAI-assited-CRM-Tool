import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import type { PermissionCheck } from "@/lib/hooks/use-permission-check"

// A failed permissions lookup (500, network) is not a denial: gated pages render a
// retryable load error, not "Permission required".

const permissionState = vi.hoisted(() => ({
    check: null as PermissionCheck | null,
    emailQueries: 0,
}))

vi.mock("@/lib/hooks/use-permission-check", () => ({
    usePermissionCheck: () => permissionState.check,
}))

vi.mock("next/navigation", () => ({
    useParams: () => ({ id: "surrogate-1" }),
}))

vi.mock("next/link", () => ({
    default: ({ children, href, ...props }: React.ComponentProps<"a">) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}))

vi.mock("@/components/app-link", () => ({
    default: ({ children, href, ...props }: React.ComponentProps<"a">) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}))

vi.mock("@/lib/hooks/use-surrogate-emails", () => {
    const query = (options?: { enabled?: boolean }) => {
        if (options?.enabled) permissionState.emailQueries += 1
        return { data: undefined, isLoading: false, isError: false }
    }
    return {
        useSurrogateEmails: (_id: string, options?: { enabled?: boolean }) => query(options),
        useSurrogateEmailContacts: (_id: string, options?: { enabled?: boolean }) => query(options),
        useCreateSurrogateEmailContact: () => ({ mutateAsync: vi.fn(), isPending: false }),
        useDeactivateSurrogateEmailContact: () => ({ mutateAsync: vi.fn(), isPending: false }),
    }
})

vi.mock("next/dynamic", () => ({
    __esModule: true,
    default: () => () => null,
}))

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => ({ user: { user_id: "user-1", role: "admin", ai_enabled: false }, isLoading: false }),
}))

vi.mock("@/lib/context/ai-context", () => ({
    useSetAIContext: () => {},
}))

vi.mock("@/components/page-header", () => ({
    PageHeader: ({ title }: { title: string }) => <h1>{title}</h1>,
}))

import SurrogateEmailsPage from "@/app/(app)/surrogates/[id]/emails/page"
import ReportsPage from "@/app/(app)/reports/page"

function failedLookup(retry = vi.fn()): PermissionCheck {
    return { isLoading: false, isError: true, retry, isRetrying: false, can: () => false }
}

describe("permission lookup failures on gated pages", () => {
    beforeEach(() => {
        permissionState.emailQueries = 0
    })

    it("surrogate emails shows a retryable load error, not the denied state", () => {
        const retry = vi.fn()
        permissionState.check = failedLookup(retry)

        render(<SurrogateEmailsPage />)

        expect(screen.getByRole("heading", { level: 2, name: "Couldn't load permissions" })).toBeInTheDocument()
        expect(screen.queryByText("No access to emails")).not.toBeInTheDocument()
        expect(permissionState.emailQueries).toBe(0)

        fireEvent.click(screen.getByRole("button", { name: "Try again" }))
        expect(retry).toHaveBeenCalledOnce()
    })

    it("surrogate emails still shows the denied state when the lookup succeeds without the permission", () => {
        permissionState.check = {
            isLoading: false,
            isError: false,
            retry: vi.fn(),
            isRetrying: false,
            can: () => false,
        }

        render(<SurrogateEmailsPage />)

        expect(screen.getByText("No access to emails")).toBeInTheDocument()
        expect(screen.queryByText("Couldn't load permissions")).not.toBeInTheDocument()
    })

    it("reports shows a retryable load error under its header, not the denied state", () => {
        const retry = vi.fn()
        permissionState.check = failedLookup(retry)

        render(<ReportsPage />)

        expect(screen.getByRole("heading", { level: 1, name: "Reports" })).toBeInTheDocument()
        expect(screen.getByRole("heading", { level: 2, name: "Couldn't load permissions" })).toBeInTheDocument()
        expect(screen.queryByText("Permission required")).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Try again" }))
        expect(retry).toHaveBeenCalledOnce()
    })
})
