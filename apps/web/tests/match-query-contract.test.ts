import { describe, expect, it, vi } from "vitest"

import { matchDetailQueryOptions, matchKeys } from "@/lib/hooks/use-matches"

describe("match detail query contract", () => {
    it("shares one cache key between server hydration and the client hook", async () => {
        const queryFn = vi.fn().mockResolvedValue({ id: "match-1" })
        const options = matchDetailQueryOptions("match-1", queryFn)

        expect(options.queryKey).toEqual(matchKeys.detail("match-1"))
        await expect(options.queryFn?.({} as never)).resolves.toEqual({ id: "match-1" })
        expect(queryFn).toHaveBeenCalledOnce()
    })
})
