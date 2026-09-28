import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"

import { WorkflowStatsCards } from "@/app/(app)/automation/components/workflow-stats-cards"
import type { WorkflowStats } from "@/lib/api/workflows"

function stats(successRate: number): WorkflowStats {
    return {
        total_workflows: 3,
        enabled_workflows: 2,
        total_executions_24h: 0,
        success_rate_24h: successRate,
        by_trigger_type: {},
    }
}

describe("WorkflowStatsCards", () => {
    it("renders a zero success rate without a stray 0", () => {
        render(<WorkflowStatsCards stats={stats(0)} isLoading={false} />)

        const rate = screen.getByText("0.0%")
        expect(rate.parentElement).toHaveTextContent(/^0\.0%$/)
        expect(screen.queryByText("Good")).not.toBeInTheDocument()
    })

    it("marks a success rate above 95% as good", () => {
        render(<WorkflowStatsCards stats={stats(98)} isLoading={false} />)

        expect(screen.getByText("98.0%")).toBeInTheDocument()
        expect(screen.getByText("Good")).toBeInTheDocument()
    })
})
