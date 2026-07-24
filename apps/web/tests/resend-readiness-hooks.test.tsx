import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import {
    getEmailOperationsLiveReadiness,
    requestEmailOperationsReadinessCheck,
} from "@/lib/api/email-operations"
import {
    getPlatformEmailReadiness,
    getPlatformEmailStatus,
    requestPlatformEmailReadinessCheck,
} from "@/lib/api/platform"
import {
    emailOperationsKeys,
    useEmailOperationsLiveReadiness,
    useRequestEmailOperationsReadinessCheck,
} from "@/lib/hooks/use-email-operations"
import {
    platformEmailKeys,
    usePlatformEmailReadiness,
    usePlatformEmailStatus,
    useRequestPlatformEmailReadinessCheck,
} from "@/lib/hooks/use-platform-email"
import type {
    ResendReadinessCheckStatus,
    ResendReadinessEnvelope,
} from "@/lib/types/resend-readiness"

vi.unmock("@tanstack/react-query")

vi.mock("@/lib/api/email-operations", async (importOriginal) => {
    const actual = await importOriginal<typeof import("@/lib/api/email-operations")>()
    return {
        ...actual,
        getEmailOperationsLiveReadiness: vi.fn(),
        requestEmailOperationsReadinessCheck: vi.fn(),
    }
})

vi.mock("@/lib/api/platform", async (importOriginal) => {
    const actual = await importOriginal<typeof import("@/lib/api/platform")>()
    return {
        ...actual,
        getPlatformEmailReadiness: vi.fn(),
        getPlatformEmailStatus: vi.fn(),
        requestPlatformEmailReadinessCheck: vi.fn(),
    }
})

function readinessEnvelope(
    checkStatus: ResendReadinessCheckStatus,
): ResendReadinessEnvelope {
    return {
        check_status: checkStatus,
        last_snapshot: {
            freshness: "fresh",
            probe_status: "succeeded",
            overall_status: "ready",
            domain_status: "ready",
            webhook_status: "ready",
            sending_status: "ready",
            delivery_tracking_status: "ready",
            engagement_tracking_status: "ready",
            verified_domain_count: 1,
            enabled_webhook_count: 1,
            issue_codes: [],
            checked_at: "2026-07-23T20:00:00Z",
            last_success_at: "2026-07-23T20:00:00Z",
        },
    }
}

function wrapperFor(queryClient: QueryClient) {
    return function Wrapper({ children }: { children: ReactNode }) {
        return (
            <QueryClientProvider client={queryClient}>
                {children}
            </QueryClientProvider>
        )
    }
}

function createQueryClient() {
    return new QueryClient({
        defaultOptions: {
            queries: { retry: false },
            mutations: { retry: false },
        },
    })
}

describe("Resend readiness hooks", () => {
    beforeEach(() => {
        vi.mocked(getEmailOperationsLiveReadiness).mockReset()
        vi.mocked(requestEmailOperationsReadinessCheck).mockReset()
        vi.mocked(getPlatformEmailReadiness).mockReset()
        vi.mocked(getPlatformEmailStatus).mockReset()
        vi.mocked(requestPlatformEmailReadinessCheck).mockReset()
    })

    afterEach(() => {
        vi.useRealTimers()
    })

    it("polls organization readiness every five seconds only while a check is active", async () => {
        vi.useFakeTimers({ shouldAdvanceTime: true })
        vi.mocked(getEmailOperationsLiveReadiness)
            .mockResolvedValueOnce(readinessEnvelope("queued"))
            .mockResolvedValue(readinessEnvelope("idle"))
        const queryClient = createQueryClient()

        renderHook(() => useEmailOperationsLiveReadiness(), {
            wrapper: wrapperFor(queryClient),
        })

        await waitFor(() => {
            expect(getEmailOperationsLiveReadiness).toHaveBeenCalledTimes(1)
        })
        expect(
            queryClient.getQueryCache().find({
                queryKey: emailOperationsKeys.liveReadiness(),
            })?.options.refetchIntervalInBackground,
        ).toBe(false)

        await vi.advanceTimersByTimeAsync(5_000)
        await waitFor(() => {
            expect(getEmailOperationsLiveReadiness).toHaveBeenCalledTimes(2)
        })

        await vi.advanceTimersByTimeAsync(10_000)
        expect(getEmailOperationsLiveReadiness).toHaveBeenCalledTimes(2)
    })

    it("does not fetch platform readiness until its surface is enabled", async () => {
        vi.mocked(getPlatformEmailReadiness).mockResolvedValue(
            readinessEnvelope("idle"),
        )
        const queryClient = createQueryClient()
        const view = renderHook(
            ({ enabled }) => usePlatformEmailReadiness({ enabled }),
            {
                initialProps: { enabled: false },
                wrapper: wrapperFor(queryClient),
            },
        )

        await Promise.resolve()
        expect(getPlatformEmailReadiness).not.toHaveBeenCalled()

        view.rerender({ enabled: true })
        await waitFor(() => {
            expect(getPlatformEmailReadiness).toHaveBeenCalledTimes(1)
        })
    })

    it("stops platform polling when its queued check becomes idle", async () => {
        vi.useFakeTimers({ shouldAdvanceTime: true })
        vi.mocked(getPlatformEmailReadiness)
            .mockResolvedValueOnce(readinessEnvelope("running"))
            .mockResolvedValue(readinessEnvelope("idle"))
        const queryClient = createQueryClient()

        renderHook(() => usePlatformEmailReadiness(), {
            wrapper: wrapperFor(queryClient),
        })
        await waitFor(() => {
            expect(getPlatformEmailReadiness).toHaveBeenCalledTimes(1)
        })
        expect(
            queryClient.getQueryCache().find({
                queryKey: platformEmailKeys.readiness(),
            })?.options.refetchIntervalInBackground,
        ).toBe(false)

        await vi.advanceTimersByTimeAsync(5_000)
        await waitFor(() => {
            expect(getPlatformEmailReadiness).toHaveBeenCalledTimes(2)
        })
        await vi.advanceTimersByTimeAsync(10_000)

        expect(getPlatformEmailReadiness).toHaveBeenCalledTimes(2)
    })

    it("reuses fresh platform sender status across remounts", async () => {
        vi.mocked(getPlatformEmailStatus).mockResolvedValue({
            configured: true,
            from_email: "notifications@example.com",
            provider: "resend",
        })
        const queryClient = createQueryClient()
        const wrapper = wrapperFor(queryClient)

        const firstView = renderHook(() => usePlatformEmailStatus(), { wrapper })
        await waitFor(() => {
            expect(getPlatformEmailStatus).toHaveBeenCalledTimes(1)
        })
        firstView.unmount()

        renderHook(() => usePlatformEmailStatus(), { wrapper })
        await Promise.resolve()
        expect(getPlatformEmailStatus).toHaveBeenCalledTimes(1)
    })

    it("queues one organization check and invalidates only organization live readiness", async () => {
        const queued = readinessEnvelope("queued")
        vi.mocked(requestEmailOperationsReadinessCheck).mockResolvedValue(queued)
        const queryClient = createQueryClient()
        queryClient.setQueryData(
            emailOperationsKeys.liveReadiness(),
            readinessEnvelope("idle"),
        )
        queryClient.setQueryData(
            platformEmailKeys.readiness(),
            readinessEnvelope("idle"),
        )
        const view = renderHook(
            () => useRequestEmailOperationsReadinessCheck(),
            { wrapper: wrapperFor(queryClient) },
        )

        await act(async () => {
            await view.result.current.mutateAsync()
        })

        expect(requestEmailOperationsReadinessCheck).toHaveBeenCalledTimes(1)
        expect(
            queryClient.getQueryState(emailOperationsKeys.liveReadiness())
                ?.isInvalidated,
        ).toBe(true)
        expect(
            queryClient.getQueryState(platformEmailKeys.readiness())?.isInvalidated,
        ).toBe(false)
    })

    it("queues one platform check and invalidates only platform live readiness", async () => {
        const queued = readinessEnvelope("queued")
        vi.mocked(requestPlatformEmailReadinessCheck).mockResolvedValue(queued)
        const queryClient = createQueryClient()
        queryClient.setQueryData(
            emailOperationsKeys.liveReadiness(),
            readinessEnvelope("idle"),
        )
        queryClient.setQueryData(
            platformEmailKeys.readiness(),
            readinessEnvelope("idle"),
        )
        const view = renderHook(
            () => useRequestPlatformEmailReadinessCheck(),
            { wrapper: wrapperFor(queryClient) },
        )

        await act(async () => {
            await view.result.current.mutateAsync()
        })

        expect(requestPlatformEmailReadinessCheck).toHaveBeenCalledTimes(1)
        expect(
            queryClient.getQueryState(platformEmailKeys.readiness())?.isInvalidated,
        ).toBe(true)
        expect(
            queryClient.getQueryState(emailOperationsKeys.liveReadiness())
                ?.isInvalidated,
        ).toBe(false)
    })
})
