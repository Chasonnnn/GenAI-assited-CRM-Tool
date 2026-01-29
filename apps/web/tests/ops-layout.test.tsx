import type { ReactNode } from "react"
import { describe, it, expect, vi, afterEach } from "vitest"
import { render, waitFor } from "@testing-library/react"
import "@testing-library/jest-dom"
import OpsLayout from "../app/ops/layout"

const mockGetPlatformMe = vi.fn()
const mockGetPlatformStats = vi.fn()
const mockReplace = vi.fn()

vi.mock("@/lib/api/platform", () => ({
    getPlatformMe: () => mockGetPlatformMe(),
    getPlatformStats: () => mockGetPlatformStats(),
}))

vi.mock("next/navigation", () => ({
    useRouter: () => ({ replace: mockReplace }),
    usePathname: () => "/ops",
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

describe("OpsLayout", () => {
    afterEach(() => {
        vi.clearAllMocks()
    })

    it("starts stats fetch without waiting for platform me", async () => {
        const pendingMe = new Promise(() => {})
        mockGetPlatformMe.mockReturnValue(pendingMe)
        mockGetPlatformStats.mockResolvedValue({ open_alerts: 2 })

        render(
            <OpsLayout>
                <div>Child</div>
            </OpsLayout>
        )

        await waitFor(() => expect(mockGetPlatformStats).toHaveBeenCalledTimes(1))
    })
})
