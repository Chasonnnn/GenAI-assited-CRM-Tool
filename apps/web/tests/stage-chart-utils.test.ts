import { describe, it, expect } from "vitest"
import { buildStageChartData, type StageStatus } from "../app/(app)/dashboard/components/stage-chart-utils"

describe("buildStageChartData", () => {
    it("groups low-count stages into Other when too many stages exist", () => {
        const stageColorMap = new Map<string, string>()
        const statusData: StageStatus[] = [
            { status: "Contacted", stage_id: "s1", count: 10, order: 1 },
            { status: "Qualified", stage_id: "s2", count: 8, order: 2 },
            { status: "Interview", stage_id: "s3", count: 5, order: 3 },
            { status: "Submitted", stage_id: "s4", count: 4, order: 4 },
            { status: "Review", stage_id: "s5", count: 3, order: 5 },
            { status: "Ready", stage_id: "s6", count: 2, order: 6 },
            { status: "Match", stage_id: "s7", count: 2, order: 7 },
            { status: "Medical", stage_id: "s8", count: 1, order: 8 },
            { status: "Legal", stage_id: "s9", count: 1, order: 9 },
            { status: "Transfer", stage_id: "s10", count: 1, order: 10 },
        ]

        const result = buildStageChartData(statusData, stageColorMap)
        const other = result.data.find((item) => item.status === "Other")

        expect(other).toBeTruthy()
        expect(other?.count).toBe(7)
        expect(other?.groupedCount).toBe(5)
    })

    it("does not group when stage count stays under the limit", () => {
        const stageColorMap = new Map<string, string>()
        const statusData: StageStatus[] = [
            { status: "Contacted", stage_id: "s1", count: 4, order: 1 },
            { status: "Qualified", stage_id: "s2", count: 3, order: 2 },
            { status: "Interview", stage_id: "s3", count: 2, order: 3 },
            { status: "Submitted", stage_id: "s4", count: 1, order: 4 },
        ]

        const result = buildStageChartData(statusData, stageColorMap)
        expect(result.data.find((item) => item.status === "Other")).toBeUndefined()
        expect(result.data).toHaveLength(4)
    })
})
