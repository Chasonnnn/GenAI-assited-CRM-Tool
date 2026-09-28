import type { CSSProperties } from "react"

import type { PipelineStage } from "@/lib/api/pipelines"
import { stageBadgeStyle } from "@/lib/stage-colors"

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

/** The donor's configured stage color, for dots and stage badges. */
export function getDonorStageColor(
    stages: PipelineStage[] | null | undefined,
    donor: { stage_id?: string | null; stage_key?: string | null },
): string {
    const stage = (stages ?? []).find(
        (candidate) =>
            candidate.id === donor.stage_id || candidate.stage_key === donor.stage_key,
    )
    return normalizeColor(stage?.color)
}

export function getDonorStageStyle(
    stages: PipelineStage[] | null | undefined,
    donor: { stage_id?: string | null; stage_key?: string | null },
): CSSProperties {
    return stageBadgeStyle(getDonorStageColor(stages, donor))
}
