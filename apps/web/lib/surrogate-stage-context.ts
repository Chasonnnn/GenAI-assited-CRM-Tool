import type { PipelineStage } from "@/lib/api/pipelines"
import type { SurrogateRead } from "@/lib/types/surrogate"

type SurrogateStageContextInput = Pick<
    SurrogateRead,
    | "stage_id"
    | "stage_slug"
    | "stage_type"
    | "paused_from_stage_id"
    | "paused_from_stage_slug"
    | "paused_from_stage_label"
    | "paused_from_stage_type"
>

export interface SurrogateStageContext {
    currentStage: PipelineStage | undefined
    pausedFromStage: PipelineStage | undefined
    effectiveStage: PipelineStage | undefined
    currentStageSlug: string | null
    effectiveStageId: string | null
    effectiveStageSlug: string | null
    effectiveStageType: string | null
    pausedFromStageLabel: string | null
    isOnHold: boolean
}

export function getSurrogateStageContext(
    surrogate: SurrogateStageContextInput | null,
    stageById: Map<string, PipelineStage>
): SurrogateStageContext {
    if (!surrogate) {
        return {
            currentStage: undefined,
            pausedFromStage: undefined,
            effectiveStage: undefined,
            currentStageSlug: null,
            effectiveStageId: null,
            effectiveStageSlug: null,
            effectiveStageType: null,
            pausedFromStageLabel: null,
            isOnHold: false,
        }
    }

    const currentStage = stageById.get(surrogate.stage_id)
    const currentStageSlug = currentStage?.slug ?? surrogate.stage_slug ?? null
    const isOnHold = currentStageSlug === "on_hold"

    const pausedFromStage = surrogate.paused_from_stage_id
        ? stageById.get(surrogate.paused_from_stage_id)
        : undefined

    const effectiveStage = isOnHold ? (pausedFromStage ?? currentStage) : currentStage

    return {
        currentStage,
        pausedFromStage,
        effectiveStage,
        currentStageSlug,
        effectiveStageId:
            effectiveStage?.id ??
            (isOnHold ? surrogate.paused_from_stage_id ?? null : surrogate.stage_id),
        effectiveStageSlug: isOnHold
            ? pausedFromStage?.slug ?? surrogate.paused_from_stage_slug ?? currentStageSlug
            : currentStageSlug,
        effectiveStageType: isOnHold
            ? pausedFromStage?.stage_type ??
                surrogate.paused_from_stage_type ??
                currentStage?.stage_type ??
                surrogate.stage_type ??
                null
            : currentStage?.stage_type ?? surrogate.stage_type ?? null,
        pausedFromStageLabel:
            pausedFromStage?.label ?? surrogate.paused_from_stage_label ?? null,
        isOnHold,
    }
}
