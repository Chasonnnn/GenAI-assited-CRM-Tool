import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import IntendedParentDetailLoading from "@/app/(app)/intended-parents/[id]/loading"

describe("intended-parent instant navigation shell", () => {
    it("renders a reusable shell without tenant-specific content", () => {
        render(<IntendedParentDetailLoading />)

        expect(
            screen.getByRole("status", { name: "Loading intended parent details" }),
        ).toBeInTheDocument()
        expect(screen.queryByText("Tenant detail")).not.toBeInTheDocument()
    })
})
