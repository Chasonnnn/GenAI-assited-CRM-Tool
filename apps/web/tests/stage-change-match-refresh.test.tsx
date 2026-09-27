import { renderHook } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { ReactNode } from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import * as surrogatesApi from "@/lib/api/surrogates"
import * as intendedParentsApi from "@/lib/api/intended-parents"
import * as donorsApi from "@/lib/api/donors"
import { matchKeys } from "@/lib/queries/matches"
import { useApplySurrogateMassEditStage, useBulkChangeStage, useChangeSurrogateStatus } from "@/lib/hooks/use-surrogates"
import { useUpdateIntendedParentStatus } from "@/lib/hooks/use-intended-parents"
import { useUpdateDonorStatus } from "@/lib/hooks/use-donors"

vi.mock("@/lib/api/surrogates", async (original) => ({ ...await original<typeof surrogatesApi>(), changeSurrogateStatus: vi.fn(), bulkChangeStage: vi.fn(), applySurrogateMassEditStage: vi.fn() }))
vi.mock("@/lib/api/intended-parents", async (original) => ({ ...await original<typeof intendedParentsApi>(), updateIntendedParentStatus: vi.fn() }))
vi.mock("@/lib/api/donors", async (original) => ({ ...await original<typeof donorsApi>(), updateDonorStatus: vi.fn() }))

type Mutation = { mutateAsync: (value: never) => Promise<unknown> }

async function runAndReadMatchState(useHook: () => unknown, variables: unknown) {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 60_000 } } })
    client.setQueryData(matchKeys.detail("match1"), { id: "match1" })
    const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
    const { result } = renderHook(useHook, { wrapper })
    await (result.current as Mutation).mutateAsync(variables as never)
    return client.getQueryState(matchKeys.detail("match1"))?.isInvalidated
}

describe("stage changes refresh match capabilities", () => {
    beforeEach(() => {
        vi.mocked(surrogatesApi.changeSurrogateStatus).mockResolvedValue({ status: "applied" } as never)
        vi.mocked(surrogatesApi.bulkChangeStage).mockResolvedValue({} as never)
        vi.mocked(surrogatesApi.applySurrogateMassEditStage).mockResolvedValue({} as never)
        vi.mocked(intendedParentsApi.updateIntendedParentStatus).mockResolvedValue({ status: "applied" } as never)
        vi.mocked(donorsApi.updateDonorStatus).mockResolvedValue({} as never)
    })

    it("invalidates match reads after a surrogate stage change", async () => {
        expect(await runAndReadMatchState(useChangeSurrogateStatus, { surrogateId: "s1", data: { stage_id: "stage1" } })).toBe(true)
    })

    it("invalidates match reads after a bulk surrogate stage change", async () => {
        expect(await runAndReadMatchState(useBulkChangeStage, { surrogate_ids: ["s1"], stage_id: "stage1" })).toBe(true)
    })

    it("invalidates match reads after a mass surrogate stage change", async () => {
        expect(await runAndReadMatchState(useApplySurrogateMassEditStage, {})).toBe(true)
    })

    it("invalidates match reads after an intended parent stage change", async () => {
        expect(await runAndReadMatchState(useUpdateIntendedParentStatus, { id: "ip1", data: { stage_id: "stage1" } })).toBe(true)
    })

    it("invalidates match reads after a donor stage change", async () => {
        expect(await runAndReadMatchState(useUpdateDonorStatus, { id: "d1", data: { stage_id: "stage1" } })).toBe(true)
    })
})
