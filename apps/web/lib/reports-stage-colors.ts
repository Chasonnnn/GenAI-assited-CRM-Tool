import type { FunnelStage, StatusCount } from "@/lib/api/analytics"
import type { PipelineStage } from "@/lib/api/pipelines"

const chartColors = [
    "#3b82f6",
    "#22c55e",
    "#f59e0b",
    "#a855f7",
    "#06b6d4",
    "#ef4444",
]
const chartFallbackColor = "#3b82f6"

type StageColorIndex = {
    byId: Map<string, string>
    bySlug: Map<string, string>
    byKey: Map<string, string>
    byLabel: Map<string, string>
}

export type StatusChartDatum = {
    status: string
    count: number
    fill: string
}

export type ColoredFunnelStage = FunnelStage & {
    fill: string
}

function buildStageColorIndex(stages: PipelineStage[] | undefined): StageColorIndex {
    const index: StageColorIndex = {
        byId: new Map(),
        bySlug: new Map(),
        byKey: new Map(),
        byLabel: new Map(),
    }

    for (const stage of stages ?? []) {
        if (!stage.is_active || !stage.color) continue
        index.byId.set(stage.id, stage.color)
        index.bySlug.set(stage.slug, stage.color)
        index.byKey.set(stage.stage_key, stage.color)
        index.byLabel.set(stage.label, stage.color)
    }

    return index
}

function resolveStageColor(
    index: StageColorIndex,
    fallbackIndex: number,
    refs: {
        stageId?: string | null
        stageSlug?: string | null
        stageKey?: string | null
        stageLabel?: string | null
    },
): string {
    const {
        stageId,
        stageSlug,
        stageKey,
        stageLabel,
    } = refs
    return (
        (stageId ? index.byId.get(stageId) : undefined) ??
        (stageSlug ? index.bySlug.get(stageSlug) : undefined) ??
        (stageKey ? index.byKey.get(stageKey) : undefined) ??
        (stageLabel ? index.byLabel.get(stageLabel) : undefined) ??
        chartColors[fallbackIndex % chartColors.length] ??
        chartFallbackColor
    )
}

function formatStatusLabel(value: string): string {
    return value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase())
}

export function buildStatusChartData(
    byStatus: StatusCount[] | undefined,
    stages: PipelineStage[] | undefined,
): StatusChartDatum[] {
    const stageColorIndex = buildStageColorIndex(stages)
    return (byStatus ?? []).map((item, index) => ({
        status: formatStatusLabel(item.status),
        count: item.count,
        fill: resolveStageColor(stageColorIndex, index, {
            stageId: item.stage_id,
            stageLabel: item.status,
        }),
    }))
}

export function buildFunnelChartData(
    funnel: FunnelStage[] | undefined,
    stages: PipelineStage[] | undefined,
): ColoredFunnelStage[] {
    const stageColorIndex = buildStageColorIndex(stages)
    return (funnel ?? []).map((item, index) => ({
        ...item,
        fill: resolveStageColor(stageColorIndex, index, {
            stageSlug: item.stage,
            stageKey: item.stage,
            stageLabel: item.label,
        }),
    }))
}
