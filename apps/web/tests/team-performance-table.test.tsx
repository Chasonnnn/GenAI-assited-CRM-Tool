import { describe, expect, it } from "vitest"
import { render, screen, within } from "@testing-library/react"
import { TeamPerformanceTable } from "@/components/reports/TeamPerformanceTable"

describe("TeamPerformanceTable", () => {
    const columns = [
        { stage_key: "contacted", label: "Contacted", color: "#10B981", order: 1 },
        { stage_key: "on_hold", label: "On-Hold", color: "#6B7280", order: 2 },
        { stage_key: "lost", label: "Lost", color: "#EF4444", order: 3 },
    ]

    it("renders dynamic stage columns from the analytics response", () => {
        render(
            <TeamPerformanceTable
                columns={columns}
                data={[
                    {
                        user_id: "u1",
                        user_name: "Alex Case Manager",
                        total_surrogates: 12,
                        archived_count: 1,
                        stage_counts: {
                            contacted: 8,
                            on_hold: 3,
                            lost: 1,
                        },
                        conversion_rate: 41,
                        avg_days_to_match: 12.4,
                        avg_days_to_conversion: 9.5,
                    },
                ]}
                unassigned={{
                    total_surrogates: 2,
                    archived_count: 0,
                    stage_counts: {
                        contacted: 1,
                        on_hold: 1,
                        lost: 0,
                    },
                }}
            />
        )

        expect(screen.getByRole("button", { name: /On-Hold/i })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: /Lost/i })).toBeInTheDocument()
        const table = screen.getByRole("table")
        expect(within(table).getAllByText("3")).toHaveLength(1)
        expect(within(table).getAllByText("1")).toHaveLength(3)
    })

    it("renders a mobile-friendly summary view for each team member", () => {
        render(
            <TeamPerformanceTable
                columns={columns}
                data={[
                    {
                        user_id: "u1",
                        user_name: "Alex Case Manager",
                        total_surrogates: 12,
                        archived_count: 1,
                        stage_counts: {
                            contacted: 8,
                            on_hold: 3,
                            lost: 1,
                        },
                        conversion_rate: 41,
                        avg_days_to_match: 12.4,
                        avg_days_to_conversion: 9.5,
                    },
                ]}
                unassigned={{
                    total_surrogates: 2,
                    archived_count: 0,
                    stage_counts: {
                        contacted: 1,
                        on_hold: 1,
                        lost: 0,
                    },
                }}
            />,
        )

        expect(
            screen.getByLabelText("Team performance mobile summary"),
        ).toBeInTheDocument()
        expect(
            screen.getByLabelText("Performance summary for Alex Case Manager"),
        ).toBeInTheDocument()
        expect(
            screen.getByLabelText("Performance summary for Unassigned"),
        ).toBeInTheDocument()
        const alexSummary = screen.getByLabelText("Performance summary for Alex Case Manager")
        expect(within(alexSummary).getByText("Match conversion")).toBeInTheDocument()
        expect(within(alexSummary).getAllByText("41%")).toHaveLength(2)
    })
})
