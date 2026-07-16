import { renderHook } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { useDashboardKpiMismatchWarning } from "@/lib/hooks/use-dashboard-kpi-mismatch-warning"

describe("useDashboardKpiMismatchWarning", () => {
    afterEach(() => {
        vi.restoreAllMocks()
    })

    it("warns once for an equivalent mismatch and warns again when the mismatch changes", () => {
        const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined)
        const { rerender } = renderHook(
            ({ distributionTotal, filters }) =>
                useDashboardKpiMismatchWarning({
                    dateParams: { from_date: "2026-01-01" },
                    distributionTotal,
                    enabled: true,
                    filters,
                    kpiTotal: 100,
                }),
            {
                initialProps: {
                    distributionTotal: 60,
                    filters: { assigneeId: "user-1", dateRange: "month" },
                },
            },
        )

        expect(warn).toHaveBeenCalledTimes(1)

        rerender({
            distributionTotal: 60,
            filters: { assigneeId: "user-1", dateRange: "month" },
        })
        expect(warn).toHaveBeenCalledTimes(1)

        rerender({
            distributionTotal: 50,
            filters: { assigneeId: "user-1", dateRange: "month" },
        })
        expect(warn).toHaveBeenCalledTimes(2)
    })
})
