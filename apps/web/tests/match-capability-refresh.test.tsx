import { fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { ReactNode } from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import * as matchesApi from "@/lib/api/matches"
import * as requestsApi from "@/lib/api/status-change-requests"
import { MatchActionControls } from "@/components/matches/MatchActionControls"
import { MatchAttemptDialog } from "@/components/matches/MatchAttemptDialog"
import { matchKeys, useAcceptMatch, useMatch } from "@/lib/hooks/use-matches"
import { useApproveStatusChangeRequest, useCancelStatusChangeRequest, useRejectStatusChangeRequest } from "@/lib/hooks/use-status-change-requests"

vi.mock("@/lib/api/matches", async (original) => ({ ...await original<typeof matchesApi>(), getMatch: vi.fn(), updateMatchAttempt: vi.fn(), listMatchAttempts: vi.fn(), acceptMatch: vi.fn() }))
vi.mock("@/lib/api/status-change-requests", async (original) => ({ ...await original<typeof requestsApi>(), approveRequest: vi.fn(), rejectRequest: vi.fn(), cancelRequest: vi.fn() }))

const openAttempt: matchesApi.MatchAttempt = { id: "attempt1", match_id: "match1", sequence: 1, attempt_type: "embryo_transfer", status: "in_progress", started_at: "2026-09-01", ended_at: null, outcome: null }
const blockedReason = "Finish or cancel open attempts before completing the match"
const acceptedMatch = { id: "match1", status: "accepted", allowed_actions: ["request_cancel"], blocked_reasons: { complete: blockedReason } } as unknown as matchesApi.MatchRead

function makeClient() {
    return new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 60_000 } } })
}

function Harness() {
    const { data } = useMatch("match1")
    if (!data) return null
    return <>
        <MatchActionControls match={data} pending={{}} onAction={vi.fn()} />
        <MatchAttemptDialog matchId="match1" kind="surrogate" attempt={openAttempt} onClose={vi.fn()} />
    </>
}

describe("match capability refresh", () => {
    beforeEach(() => {
        vi.mocked(matchesApi.getMatch).mockReset()
        vi.mocked(matchesApi.updateMatchAttempt).mockReset().mockResolvedValue({ ...openAttempt, status: "completed", ended_at: "2026-09-20" })
        vi.mocked(matchesApi.listMatchAttempts).mockReset().mockResolvedValue([])
    })

    it("re-reads allowed actions after the last open attempt is closed", async () => {
        vi.mocked(matchesApi.getMatch)
            .mockResolvedValueOnce(acceptedMatch)
            .mockResolvedValue({ ...acceptedMatch, allowed_actions: ["complete", "request_cancel"], blocked_reasons: {} })
        const client = makeClient()
        const invalidate = vi.spyOn(client, "invalidateQueries")
        render(<QueryClientProvider client={client}><Harness /></QueryClientProvider>)
        const blocked = await screen.findByRole("button", { name: "Complete Match", hidden: true })
        expect(blocked).toHaveAttribute("aria-disabled", "true")
        expect(blocked).toHaveAccessibleDescription(blockedReason)

        fireEvent.click(screen.getByRole("combobox", { name: "Status" }))
        const completed = await screen.findByRole("option", { name: "Completed" })
        fireEvent.mouseMove(completed)
        fireEvent.click(completed)
        fireEvent.change(screen.getByLabelText("End Date"), { target: { value: "2026-09-20" } })
        fireEvent.click(screen.getByRole("button", { name: "Save Attempt" }))

        await waitFor(() => expect(matchesApi.updateMatchAttempt).toHaveBeenCalledWith("match1", "attempt1", expect.objectContaining({ status: "completed" })))
        await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: matchKeys.detail("match1") }))
        await waitFor(() => expect(screen.getByRole("button", { name: "Complete Match", hidden: true })).toBeEnabled())
        expect(screen.getByRole("button", { name: "Complete Match", hidden: true })).not.toHaveAttribute("aria-disabled", "true")
        expect(matchesApi.getMatch).toHaveBeenCalledTimes(2)
    })

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
