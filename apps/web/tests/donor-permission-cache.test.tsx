import {act, renderHook, waitFor} from "@testing-library/react"
import {QueryClient, QueryClientProvider} from "@tanstack/react-query"
import {describe, expect, it, vi} from "vitest"
import type {PropsWithChildren} from "react"
import {useArchiveDonor, useRestoreDonor, useUpdateDonorStatus} from "@/lib/hooks/use-donors"

vi.mock("@/lib/api/donors", () => ({
    updateDonorStatus: vi.fn(async () => ({donor: {id: "donor-1", owner_type: "queue", owner_id: "pool"}, status: "applied"})),
    archiveDonor: vi.fn(async () => ({id: "donor-1", is_archived: true})),
    restoreDonor: vi.fn(async () => ({id: "donor-1", is_archived: false})),
}))

describe("donor approval cache", () => {
    it("refreshes collaborators and record-scope consumers after approval", async () => {
        const client = new QueryClient({defaultOptions: {queries: {retry: false}, mutations: {retry: false}}})
        const keys = [["record-collaborators", "donor", "donor-1"], ["analytics", "donors"], ["campaigns", "preview"]]
        for (const key of keys) client.setQueryData(key, {cached: true})
        const wrapper = ({children}: PropsWithChildren) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
        const {result} = renderHook(() => useUpdateDonorStatus(), {wrapper})
        await act(async () => {await result.current.mutateAsync({id: "donor-1", data: {stage_id: "approved"}})})
        await waitFor(() => {for (const key of keys) expect(client.getQueryState(key)?.isInvalidated).toBe(true)})
        client.clear()
    })

    it.each([useArchiveDonor, useRestoreDonor])("refreshes record-scope consumers after %s", async (useMutation) => {
        const client = new QueryClient({defaultOptions: {queries: {retry: false}, mutations: {retry: false}}})
        const keys = [["analytics", "donors"], ["campaigns", "preview"], ["donors", "profile", "donor-1"]]
        for (const key of keys) client.setQueryData(key, {cached: true})
        const wrapper = ({children}: PropsWithChildren) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
        const {result} = renderHook(useMutation, {wrapper})
        await act(async () => {await result.current.mutateAsync("donor-1")})
        for (const key of keys) expect(client.getQueryState(key)?.isInvalidated).toBe(true)
        client.clear()
    })
})
