import { describe, expect, it, vi } from "vitest"
import { renderToString } from "react-dom/server"

import UnassignedSurrogatesPage from "@/app/(app)/surrogates/unassigned/page.client"

const mocks = vi.hoisted(() => ({
    redirect: vi.fn(),
    useAuth: vi.fn(),
    useUnassignedQueue: vi.fn(),
    useClaimSurrogate: vi.fn(),
    trackViewed: vi.fn(),
}))

vi.mock("next/navigation", () => ({
    redirect: (path: string) => mocks.redirect(path),
    useRouter: () => ({
        push: vi.fn(),
        replace: vi.fn(),
    }),
}))

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => mocks.useAuth(),
}))

vi.mock("@/lib/hooks/use-surrogates", () => ({
    useUnassignedQueue: (...args: unknown[]) => mocks.useUnassignedQueue(...args),
}))

vi.mock("@/lib/hooks/use-queues", () => ({
    useClaimSurrogate: () => mocks.useClaimSurrogate(),
}))

vi.mock("@/lib/workflow-metrics", () => ({
    trackUnassignedQueueViewed: () => mocks.trackViewed(),
}))

describe("UnassignedSurrogatesPage", () => {
    it("redirects unauthorized users during initial rendering before queue hooks mount", () => {
        mocks.useAuth.mockReturnValue({
            user: {
                user_id: "case-manager-1",
                role: "case_manager",
            },
        })
        mocks.useUnassignedQueue.mockReturnValue({
            data: null,
            isLoading: false,
            error: null,
            refetch: vi.fn(),
        })
        mocks.useClaimSurrogate.mockReturnValue({
            mutateAsync: vi.fn(),
            isPending: false,
        })

        renderToString(
            <UnassignedSurrogatesPage
                initialPageParam={null}
                initialSearchParams=""
            />
        )

        expect(mocks.redirect).toHaveBeenCalledWith("/surrogates")
        expect(mocks.useUnassignedQueue).not.toHaveBeenCalled()
        expect(mocks.useClaimSurrogate).not.toHaveBeenCalled()
        expect(mocks.trackViewed).not.toHaveBeenCalled()
    })
})
