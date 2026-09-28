import { renderHook } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { ReactNode } from "react"
import { describe, expect, it, vi } from "vitest"
import * as matchesApi from "@/lib/api/matches"
import * as requestsApi from "@/lib/api/status-change-requests"
import { matchKeys, useAcceptMatch } from "@/lib/hooks/use-matches"
import { useApproveStatusChangeRequest, useCancelStatusChangeRequest, useRejectStatusChangeRequest } from "@/lib/hooks/use-status-change-requests"

vi.mock("@/lib/api/matches", async (original) => ({ ...await original<typeof matchesApi>(), acceptMatch: vi.fn() }))
vi.mock("@/lib/api/status-change-requests", async (original) => ({ ...await original<typeof requestsApi>(), approveRequest: vi.fn(), rejectRequest: vi.fn(), cancelRequest: vi.fn() }))

const acceptedMatch = { id: "match1", status: "accepted", allowed_actions: ["request_cancel"], blocked_reasons: {} } as unknown as matchesApi.MatchRead

function makeClient() {
    return new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 60_000 } } })
}

describe("match capability refresh", () => {
    it("refreshes sibling match details after an accept", async () => {
        vi.mocked(matchesApi.acceptMatch).mockResolvedValue({ ...acceptedMatch, id: "match1" })
        const client = makeClient()
        client.setQueryData(matchKeys.detail("match1"), acceptedMatch)
        client.setQueryData(matchKeys.detail("match2"), { ...acceptedMatch, id: "match2", status: "under_review" })
        const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
        const { result } = renderHook(() => useAcceptMatch(), { wrapper })
        await result.current.mutateAsync({ matchId: "match1" })
        expect(client.getQueryState(matchKeys.detail("match2"))?.isInvalidated).toBe(true)
        expect(client.getQueryState(matchKeys.detail("match1"))?.isInvalidated).toBe(false)
    })

    it.each([
        ["approve", () => useApproveStatusChangeRequest(), (hook: { mutateAsync: (value: never) => Promise<unknown> }) => hook.mutateAsync("request1" as never)],
        ["reject", () => useRejectStatusChangeRequest(), (hook: { mutateAsync: (value: never) => Promise<unknown> }) => hook.mutateAsync({ requestId: "request1" } as never)],
        ["cancel", () => useCancelStatusChangeRequest(), (hook: { mutateAsync: (value: never) => Promise<unknown> }) => hook.mutateAsync("request1" as never)],
    ])("invalidates match reads after a status change request %s", async (_, useHook, run) => {
        vi.mocked(requestsApi.approveRequest).mockResolvedValue({} as requestsApi.StatusChangeRequest)
        vi.mocked(requestsApi.rejectRequest).mockResolvedValue({} as requestsApi.StatusChangeRequest)
        vi.mocked(requestsApi.cancelRequest).mockResolvedValue({} as requestsApi.StatusChangeRequest)
        const client = makeClient()
        client.setQueryData(matchKeys.detail("match1"), acceptedMatch)
        const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
        const { result } = renderHook(useHook, { wrapper })
        await run(result.current as never)
        expect(client.getQueryState(matchKeys.detail("match1"))?.isInvalidated).toBe(true)
    })
})
