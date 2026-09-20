import type { ReactNode } from "react"
import { describe, it, expect, vi, afterEach } from "vitest"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import "@testing-library/jest-dom"
import OpsLayout from "../app/ops/layout"

vi.unmock("@tanstack/react-query")

const mockGetPlatformMe = vi.fn()
const mockGetPlatformStats = vi.fn()
const mockReplace = vi.fn()
const mockPathname = vi.fn(() => '/ops')

vi.mock("@/lib/api/platform", () => ({
    getPlatformMe: () => mockGetPlatformMe(),
    getPlatformStats: () => mockGetPlatformStats(),
}))

vi.mock("next/navigation", () => ({
    useRouter: () => ({ replace: mockReplace }),
    usePathname: () => mockPathname(),
}))

vi.mock("@/components/app-link", () => ({
    __esModule: true,
    default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
        <a href={href} {...props}>{children}</a>
    ),
}))

vi.mock("@/lib/api", () => ({
    __esModule: true,
    default: { post: vi.fn() },
    ApiError: class ApiError extends Error {
        status: number
        constructor(message = "", status = 0) {
            super(message)
            this.status = status
        }
    },
}))

function renderOpsLayout(queryClient: QueryClient) {
    return render(
        <QueryClientProvider client={queryClient}>
            <OpsLayout>
                <div>Child</div>
            </OpsLayout>
        </QueryClientProvider>
    )
}

describe("OpsLayout", () => {
    afterEach(() => {
        vi.clearAllMocks()
        mockPathname.mockReturnValue('/ops')
        sessionStorage.clear()
    })

    it('returns to CLI approval after normal OPS authentication', async () => {
        mockPathname.mockReturnValue('/ops/cli')
        mockGetPlatformMe.mockRejectedValue(new Error('Sign in'))
        mockGetPlatformStats.mockResolvedValue({ open_alerts: 0 })
        const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
        const first = renderOpsLayout(client)
        await waitFor(() => expect(mockReplace).toHaveBeenCalledWith('/ops/login'))
        expect(sessionStorage.getItem('ops_cli_login_pending')).toBe('1')
        first.unmount()
        mockPathname.mockReturnValue('/ops')
        mockGetPlatformMe.mockResolvedValue({ email: 'admin@example.test' })
        renderOpsLayout(new QueryClient({ defaultOptions: { queries: { retry: false } } }))
        await waitFor(() => expect(mockReplace).toHaveBeenCalledWith('/ops/cli'))
        expect(sessionStorage.getItem('ops_cli_login_pending')).toBeNull()
    })

    it("starts stats fetch without waiting for platform me", async () => {
        const pendingMe = new Promise(() => {})
        mockGetPlatformMe.mockReturnValue(pendingMe)
        mockGetPlatformStats.mockResolvedValue({ open_alerts: 2 })
        const queryClient = new QueryClient({
            defaultOptions: { queries: { retry: false } },
        })

        renderOpsLayout(queryClient)

        await waitFor(() => expect(mockGetPlatformStats).toHaveBeenCalledTimes(1))
    })

    it("reuses fresh platform access data when the protected layout remounts", async () => {
        mockGetPlatformMe.mockResolvedValue({
            user_id: "platform-user-1",
            email: "admin@surrogacyforce.com",
            display_name: "Platform Admin",
            is_platform_admin: true,
        })
        mockGetPlatformStats.mockResolvedValue({
            agency_count: 12,
            active_user_count: 34,
            open_alerts: 2,
        })
        const queryClient = new QueryClient({
            defaultOptions: {
                queries: {
                    retry: false,
                    staleTime: 60_000,
                },
            },
        })

        const firstRender = renderOpsLayout(queryClient)
        expect(await screen.findByText("admin@surrogacyforce.com")).toBeInTheDocument()
        firstRender.unmount()

        renderOpsLayout(queryClient)
        expect(await screen.findByText("admin@surrogacyforce.com")).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Log out" })).toBeInTheDocument()

        expect(mockGetPlatformMe).toHaveBeenCalledTimes(1)
        expect(mockGetPlatformStats).toHaveBeenCalledTimes(1)
    })
})
