import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { TeamPerformanceTable } from "@/components/reports/TeamPerformanceTable"

describe("TeamPerformanceTable", () => {
    it("renders a separate On-Hold column alongside Lost", () => {
        render(
            <TeamPerformanceTable
                data={[
                    {
                        user_id: "u1",
                        user_name: "Alex Case Manager",
                        total_surrogates: 12,
                        archived_count: 1,
                        contacted: 8,
                        pre_qualified: 6,
                        ready_to_match: 4,
                        matched: 2,
                        application_submitted: 5,
                        on_hold: 3,
                        lost: 1,
                        conversion_rate: 41,
                        avg_days_to_match: 12.4,
                        avg_days_to_application_submitted: 9.5,
                    },
                ]}
                unassigned={{
                    total_surrogates: 2,
                    archived_count: 0,
                    contacted: 1,
                    pre_qualified: 0,
                    ready_to_match: 0,
                    matched: 0,
                    application_submitted: 0,
                    on_hold: 1,
                    lost: 0,
                }}
            />
        )

        expect(screen.getByRole("button", { name: /On-Hold/i })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: /Lost/i })).toBeInTheDocument()
        expect(screen.getAllByText("3")).toHaveLength(1)
        expect(screen.getAllByText("1")).toHaveLength(3)
    })
})
