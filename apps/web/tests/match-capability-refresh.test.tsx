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

const acceptedMatch: matchesApi.MatchRead = {
    id: "match1", match_number: "M10001", surrogate_id: "surrogate1", intended_parent_id: "ip1",
    status: "accepted", allowed_actions: ["request_cancel"], blocked_reasons: {},
    pending_cancellation_request_id: null, accept_eligibility_warnings: [], surrogate_has_accepted_match: true,
    proposed_by_user_id: "user1", proposed_at: "2026-09-30T00:00:00Z", reviewed_by_user_id: null,
    reviewed_at: null, notes: null, decline_reason: null, created_at: "2026-09-30T00:00:00Z",
    updated_at: "2026-09-30T00:00:00Z", surrogate_number: "S10001", surrogate_name: "Sample Surrogate",
    ip_name: "Sample Parent", ip_number: "IP10001", surrogate_stage_id: null,
    surrogate_stage_slug: null, surrogate_stage_label: null,
}

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

    it.each(["approve", "reject", "cancel"] as const)("invalidates match reads after a status change request %s", async (action) => {
        const request: requestsApi.StatusChangeRequest = {
            id: "request1", organization_id: "org1", entity_type: "match", entity_id: "match1",
            target_stage_id: null, target_status: "cancelled", effective_at: "2026-09-30T00:00:00Z",
            reason: "Cancellation requested", requested_by_user_id: "user1", requested_at: "2026-09-30T00:00:00Z",
            status: "pending", approved_by_user_id: null, approved_at: null,
            rejected_by_user_id: null, rejected_at: null, cancelled_by_user_id: null, cancelled_at: null,
        }
        vi.mocked(requestsApi.approveRequest).mockResolvedValue({ ...request, status: "approved" })
        vi.mocked(requestsApi.rejectRequest).mockResolvedValue({ ...request, status: "rejected" })
        vi.mocked(requestsApi.cancelRequest).mockResolvedValue({ ...request, status: "cancelled" })
        const client = makeClient()
        client.setQueryData(matchKeys.detail("match1"), acceptedMatch)
        const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
        if (action === "approve") {
            const { result } = renderHook(() => useApproveStatusChangeRequest(), { wrapper })
            await result.current.mutateAsync("request1")
        } else if (action === "reject") {
            const { result } = renderHook(() => useRejectStatusChangeRequest(), { wrapper })
            await result.current.mutateAsync({ requestId: "request1" })
        } else {
            const { result } = renderHook(() => useCancelStatusChangeRequest(), { wrapper })
            await result.current.mutateAsync("request1")
        }
        expect(client.getQueryState(matchKeys.detail("match1"))?.isInvalidated).toBe(true)
    })
})
