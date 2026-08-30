import type { CSSProperties } from "react"

import type { PipelineStage } from "@/lib/api/pipelines"

function normalizeColor(color: string | null | undefined): string {
    return /^#[0-9A-Fa-f]{6}$/.test(color ?? "") ? String(color) : "#6B7280"
}

export function getActiveDonorStages(stages: PipelineStage[] | null | undefined): PipelineStage[] {
    return (stages ?? [])
        .filter((stage) => stage.is_active)
        .toSorted((left, right) => left.order - right.order)
}

export function getDonorStageLabel(
    stages: PipelineStage[] | null | undefined,
    donor: { stage_id?: string | null; stage_key?: string | null; status_label?: string | null },
): string {
    const stage = (stages ?? []).find(
        (candidate) =>
            candidate.id === donor.stage_id || candidate.stage_key === donor.stage_key,
    )
    return stage?.label ?? donor.status_label ?? "Stage unavailable"
}

export function getDonorStageStyle(
    stages: PipelineStage[] | null | undefined,
    donor: { stage_id?: string | null; stage_key?: string | null },
): CSSProperties {
    const stage = (stages ?? []).find(
        (candidate) =>
            candidate.id === donor.stage_id || candidate.stage_key === donor.stage_key,
    )
    const color = normalizeColor(stage?.color)
    return {
        borderColor: `${color}33`,
        backgroundColor: `${color}14`,
        color,
    }
}
