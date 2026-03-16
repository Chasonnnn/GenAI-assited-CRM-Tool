import type { PipelineStage } from "@/lib/api/pipelines"
import type { SurrogateRead } from "@/lib/types/surrogate"

const LEGACY_STAGE_KEY_ALIASES: Record<string, string> = {
    qualified: "pre_qualified",
}

type StageSemanticRef = {
    stage_key?: string | null | undefined
    slug?: string | null | undefined
    stage_slug?: string | null | undefined
}

type SurrogateStageContextInput = Pick<
    SurrogateRead,
    | "stage_id"
    | "stage_key"
    | "stage_slug"
    | "stage_type"
    | "paused_from_stage_id"
    | "paused_from_stage_key"
    | "paused_from_stage_slug"
    | "paused_from_stage_label"
    | "paused_from_stage_type"
>

export interface SurrogateStageContext {
    currentStage: PipelineStage | undefined
    pausedFromStage: PipelineStage | undefined
    effectiveStage: PipelineStage | undefined
    currentStageKey: string | null
    currentStageSlug: string | null
    effectiveStageId: string | null
    effectiveStageKey: string | null
    effectiveStageSlug: string | null
    effectiveStageType: string | null
    pausedFromStageLabel: string | null
    isOnHold: boolean
}

export function normalizeStageKey(value: string | null | undefined): string | null {
    const normalized = value?.trim().toLowerCase() ?? ""
    if (!normalized) return null
    return LEGACY_STAGE_KEY_ALIASES[normalized] ?? normalized
}

export function getStageSemanticKey(stage: StageSemanticRef | null | undefined): string | null {
    if (!stage) return null
    return normalizeStageKey(stage.stage_key ?? stage.slug ?? stage.stage_slug ?? null)
}

export function stageMatchesKey(
    stage: StageSemanticRef | null | undefined,
    targetStageKey: string | null | undefined
): boolean {
    const normalizedTarget = normalizeStageKey(targetStageKey)
    if (!normalizedTarget) return false
    return getStageSemanticKey(stage) === normalizedTarget
}

export function isTerminalStage(stage: StageSemanticRef | null | undefined): boolean {
    const stageKey = getStageSemanticKey(stage)
    return stageKey === "lost" || stageKey === "disqualified"
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
            currentStageKey: null,
            currentStageSlug: null,
            effectiveStageId: null,
            effectiveStageKey: null,
            effectiveStageSlug: null,
            effectiveStageType: null,
            pausedFromStageLabel: null,
            isOnHold: false,
        }
    }

    const currentStage = stageById.get(surrogate.stage_id)
    const currentStageKey = getStageSemanticKey(
        currentStage ?? { stage_key: surrogate.stage_key, stage_slug: surrogate.stage_slug }
    )
    const currentStageSlug = currentStage?.slug ?? surrogate.stage_slug ?? null
    const isOnHold = currentStageKey === "on_hold"

    const pausedFromStage = surrogate.paused_from_stage_id
        ? stageById.get(surrogate.paused_from_stage_id)
        : undefined
    const pausedFromStageKey = getStageSemanticKey(
        pausedFromStage ??
            {
                stage_key: surrogate.paused_from_stage_key,
                stage_slug: surrogate.paused_from_stage_slug,
            }
    )

    const effectiveStage = isOnHold ? (pausedFromStage ?? currentStage) : currentStage
    const effectiveStageKey = isOnHold ? (pausedFromStageKey ?? currentStageKey) : currentStageKey

    return {
        currentStage,
        pausedFromStage,
        effectiveStage,
        currentStageKey,
        currentStageSlug,
        effectiveStageId:
            effectiveStage?.id ??
            (isOnHold ? surrogate.paused_from_stage_id ?? null : surrogate.stage_id),
        effectiveStageKey,
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
