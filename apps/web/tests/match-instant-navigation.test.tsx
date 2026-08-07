import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import MatchDetailLoading from "@/app/(app)/intended-parents/matches/[id]/loading"
import MatchesLoading from "@/app/(app)/intended-parents/matches/loading"

describe("match instant navigation shells", () => {
    it("renders a tenant-neutral matches shell", () => {
        render(<MatchesLoading />)

        expect(
            screen.getByRole("status", { name: "Loading matches" }),
        ).toBeInTheDocument()
        expect(screen.queryByText("Tenant match")).not.toBeInTheDocument()
    })

    it("renders a tenant-neutral match-detail shell", () => {
        render(<MatchDetailLoading />)

        expect(
            screen.getByRole("status", { name: "Loading match details" }),
        ).toBeInTheDocument()
        expect(screen.queryByText("Tenant match")).not.toBeInTheDocument()
    })
})
