import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { MetaSpendDashboard } from "@/components/reports/MetaSpendDashboard"

vi.mock("next/dynamic", () => ({
    default: () => ({
        kind,
        data,
    }: {
        kind: string
        data: Array<{ date?: string }>
    }) => kind === "trend" ? (
        <div data-testid="meta-spend-trend-dates">
            {data.map((point) => point.date).join(",")}
        </div>
    ) : null,
}))

vi.mock("@/lib/hooks/use-analytics", () => ({
    useMetaAdAccounts: () => ({ data: [], isLoading: false }),
    useSpendTotals: () => ({ data: null, isLoading: false, isError: false }),
    useSpendByCampaign: () => ({ data: [], isLoading: false, isError: false }),
    useSpendByBreakdown: () => ({ data: [], isLoading: false, isError: false }),
    useSpendTrend: () => ({
        data: [{
            date: "2026-08-29",
            spend: 100,
            impressions: 1000,
            clicks: 50,
            leads: 2,
            cost_per_lead: 50,
        }],
        isLoading: false,
        isError: false,
    }),
    useMetaPlatformBreakdown: () => ({ data: [], isLoading: false, isError: false }),
    useMetaAdPerformance: () => ({
        data: [
            {
                ad_id: "ad-1",
                ad_name: "Donor Ad",
                lead_count: 2,
                converted_count: 1,
                surrogate_count: 0,
                egg_donor_count: 1,
                sperm_donor_count: 0,
                conversion_rate: 50,
            },
        ],
        isLoading: false,
        isError: false,
    }),
    useFormPerformance: () => ({
        data: [
            {
                form_external_id: "form-egg",
                form_name: "Egg Donor Form",
                mapping_status: "mapped",
                lead_kind: "egg_donor",
                lead_count: 2,
                converted_count: 1,
                surrogate_count: 0,
                egg_donor_count: 1,
                sperm_donor_count: 0,
                qualified_count: 0,
                conversion_rate: 50,
                qualified_rate: 0,
            },
        ],
        isLoading: false,
        isError: false,
    }),
}))

describe("MetaSpendDashboard donor breakdown", () => {
    it("labels donor forms and keeps conversion types separate", () => {
        render(<MetaSpendDashboard dateParams={{}} />)

        const row = screen.getByText("Egg Donor Form").closest("tr")
        expect(row).not.toBeNull()
        expect(row).toHaveTextContent("Egg Donor")
        expect(row).toHaveTextContent("mapped")
        expect(
            Array.from(row?.querySelectorAll("td") ?? [], (cell) => cell.textContent),
        ).toEqual([
            "Egg Donor Form",
            "Egg Donor",
            "mapped",
            "2",
            "1",
            "0",
            "1",
            "0",
            "50.0%",
        ])
        expect(screen.getByTestId("meta-spend-trend-dates")).toHaveTextContent("Aug 29")
    })
})
