import { describe, expect, it, vi } from "vitest"

const mockRedirect = vi.fn()

vi.mock("next/navigation", () => ({
    redirect: (url: string) => mockRedirect(url),
}))

import MatchesRedirectPage from "@/app/(app)/matches/page"

describe("/matches route", () => {
    it("redirects to the Matches list under Intended Parents", () => {
        MatchesRedirectPage()
        expect(mockRedirect).toHaveBeenCalledWith("/intended-parents/matches")
    })
})
