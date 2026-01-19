"use client"

export interface StageStatus {
    status: string
    stage_id: string | null
    count: number
    order: number | null
}

export interface StageChartDatum {
    status: string
    stage_id: string | null
    count: number
    percent: number
    fill: string
    groupedCount?: number
    groupedStages?: string[]
}

export interface StageChartBuildResult {
    data: StageChartDatum[]
    total: number
}

const DEFAULT_MAX_VISIBLE_STAGES = 8
const DEFAULT_LOW_COUNT_THRESHOLD = 2
const MIN_GROUPED_STAGES = 2
const OTHER_COLOR = "#94a3b8"

const getItemKey = (item: StageStatus) => item.stage_id ?? item.status

export function buildStageChartData(
    statusData: StageStatus[] | undefined,
    stageColorMap: Map<string, string>,
    options?: {
        maxVisibleStages?: number
        lowCountThreshold?: number
    }
): StageChartBuildResult {
    if (!Array.isArray(statusData)) {
        return { data: [], total: 0 }
    }

    const maxVisibleStages = options?.maxVisibleStages ?? DEFAULT_MAX_VISIBLE_STAGES
    const lowCountThreshold = options?.lowCountThreshold ?? DEFAULT_LOW_COUNT_THRESHOLD

    const sorted = [...statusData].sort((a, b) => {
        const orderA = a.order ?? 999
        const orderB = b.order ?? 999
        return orderA - orderB
    })

    const total = sorted.reduce((sum, item) => sum + item.count, 0)

    if (sorted.length <= maxVisibleStages) {
        return {
            data: sorted.map((item) => ({
                status: item.status,
                stage_id: item.stage_id,
                count: item.count,
                percent: total > 0 ? Math.round((item.count / total) * 100) : 0,
                fill: (item.stage_id && stageColorMap.get(item.stage_id)) || "#6b7280",
            })),
            total,
        }
    }

    let groupedItems: StageStatus[] = []
    let remaining = sorted

    const lowCountItems = sorted.filter((item) => item.count <= lowCountThreshold)
    if (lowCountItems.length >= MIN_GROUPED_STAGES) {
        const lowCountKeys = new Set(lowCountItems.map(getItemKey))
        groupedItems = lowCountItems
        remaining = sorted.filter((item) => !lowCountKeys.has(getItemKey(item)))
    }

    const maxRemaining = Math.max(maxVisibleStages - 1, 1)
    if (remaining.length > maxRemaining) {
        const overflowCount = remaining.length - maxRemaining
        const overflowItems = [...remaining]
            .sort((a, b) => a.count - b.count)
            .slice(0, overflowCount)
        const overflowKeys = new Set(overflowItems.map(getItemKey))
        groupedItems = [...groupedItems, ...overflowItems]
        remaining = remaining.filter((item) => !overflowKeys.has(getItemKey(item)))
    }

    if (remaining.length === 0) {
        remaining = sorted.slice(0, maxRemaining)
        groupedItems = sorted.slice(maxRemaining)
    }

    if (groupedItems.length === 0 || remaining.length === 0) {
        return {
            data: sorted.map((item) => ({
                status: item.status,
                stage_id: item.stage_id,
                count: item.count,
                percent: total > 0 ? Math.round((item.count / total) * 100) : 0,
                fill: (item.stage_id && stageColorMap.get(item.stage_id)) || "#6b7280",
            })),
            total,
        }
    }

    const data: StageChartDatum[] = remaining.map((item) => ({
        status: item.status,
        stage_id: item.stage_id,
        count: item.count,
        percent: total > 0 ? Math.round((item.count / total) * 100) : 0,
        fill: (item.stage_id && stageColorMap.get(item.stage_id)) || "#6b7280",
    }))

    const groupedCount = groupedItems.reduce((sum, item) => sum + item.count, 0)
    if (groupedCount > 0) {
        data.push({
            status: "Other",
            stage_id: null,
            count: groupedCount,
            percent: total > 0 ? Math.round((groupedCount / total) * 100) : 0,
            fill: OTHER_COLOR,
            groupedCount: groupedItems.length,
            groupedStages: groupedItems.map((item) => item.status),
        })
    }

    return { data, total }
}
