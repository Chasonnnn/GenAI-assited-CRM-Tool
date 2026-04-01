import type { PipelineStage, PipelineStageRemap, StageCapabilities, StageSemantics, StageType } from "@/lib/api/pipelines"

type ResettableStage = Pick<
    PipelineStage,
    "stage_key" | "order" | "stage_type" | "category" | "is_active" | "semantics"
>

function getStageCategory(stage: ResettableStage): StageType {
    return stage.category ?? stage.stage_type
}

function normalizeStageSemantics(
    semantics: StageSemantics | null | undefined,
): StageSemantics | null {
    if (!semantics) return null
    return {
        capabilities: {
            counts_as_contacted: Boolean(semantics.capabilities?.counts_as_contacted),
            eligible_for_matching: Boolean(semantics.capabilities?.eligible_for_matching),
            locks_match_state: Boolean(semantics.capabilities?.locks_match_state),
            shows_pregnancy_tracking: Boolean(semantics.capabilities?.shows_pregnancy_tracking),
            requires_delivery_details: Boolean(semantics.capabilities?.requires_delivery_details),
            tracks_interview_outcome: Boolean(semantics.capabilities?.tracks_interview_outcome),
        },
        pause_behavior: semantics.pause_behavior ?? "none",
        terminal_outcome: semantics.terminal_outcome ?? "none",
        integration_bucket: semantics.integration_bucket ?? "none",
        analytics_bucket: semantics.analytics_bucket ?? null,
        suggestion_profile_key: semantics.suggestion_profile_key ?? null,
        requires_reason_on_enter: Boolean(semantics.requires_reason_on_enter),
    }
}

function getSemanticsFingerprint(semantics: StageSemantics | null | undefined): string | null {
    const normalized = normalizeStageSemantics(semantics)
    return normalized ? JSON.stringify(normalized) : null
}

function getCapabilityMatchCount(
    source: StageCapabilities | undefined,
    target: StageCapabilities | undefined,
): number {
    if (!source || !target) return 0
    return [
        "counts_as_contacted",
        "eligible_for_matching",
        "locks_match_state",
        "shows_pregnancy_tracking",
        "requires_delivery_details",
        "tracks_interview_outcome",
    ].reduce((total, key) => {
        return total + (source[key as keyof StageCapabilities] === target[key as keyof StageCapabilities] ? 1 : 0)
    }, 0)
}

function getRemapCandidateScore(source: ResettableStage, target: ResettableStage): number {
    const sourceSemantics = normalizeStageSemantics(source.semantics)
    const targetSemantics = normalizeStageSemantics(target.semantics)
    const sourceFingerprint = getSemanticsFingerprint(sourceSemantics)
    const targetFingerprint = getSemanticsFingerprint(targetSemantics)
    const orderDistance = Math.abs((source.order ?? 0) - (target.order ?? 0))

    let score = 0

    if (getStageCategory(source) === getStageCategory(target)) {
        score += 40
    }
    if (sourceFingerprint && sourceFingerprint === targetFingerprint) {
        score += 200
    }
    if (
        sourceSemantics?.suggestion_profile_key
        && sourceSemantics.suggestion_profile_key === targetSemantics?.suggestion_profile_key
    ) {
        score += 80
    }
    if (
        sourceSemantics?.analytics_bucket
        && sourceSemantics.analytics_bucket === targetSemantics?.analytics_bucket
    ) {
        score += 70
    }
    if (sourceSemantics?.integration_bucket === targetSemantics?.integration_bucket) {
        score += 25
    }
    if (sourceSemantics?.pause_behavior === targetSemantics?.pause_behavior) {
        score += 10
    }
    if (sourceSemantics?.terminal_outcome === targetSemantics?.terminal_outcome) {
        score += 10
    }

    score += getCapabilityMatchCount(sourceSemantics?.capabilities, targetSemantics?.capabilities) * 5
    score += Math.max(0, 30 - orderDistance * 5)

    return score
}

function pickRemapTarget(
    source: ResettableStage,
    candidates: ResettableStage[],
): string | null {
    const ranked = candidates
        .filter((candidate) => candidate.stage_key)
        .map((candidate) => ({
            stage_key: candidate.stage_key,
            score: getRemapCandidateScore(source, candidate),
            orderDistance: Math.abs((source.order ?? 0) - (candidate.order ?? 0)),
        }))
        .sort((left, right) => {
            if (right.score !== left.score) return right.score - left.score
            if (left.orderDistance !== right.orderDistance) {
                return left.orderDistance - right.orderDistance
            }
            return left.stage_key.localeCompare(right.stage_key)
        })

    const best = ranked[0]
    return best && best.score > 0 ? best.stage_key : null
}

export function buildRecommendedDraftRemaps(
    currentStages: ResettableStage[],
    recommendedStages: ResettableStage[],
): PipelineStageRemap[] {
    const activeRecommendedStages = recommendedStages.filter((stage) => stage.is_active !== false && stage.stage_key)
    const recommendedStageKeys = new Set(activeRecommendedStages.map((stage) => stage.stage_key))
    const remaps: PipelineStageRemap[] = []

    for (const stage of currentStages) {
        if (stage.is_active === false || !stage.stage_key || recommendedStageKeys.has(stage.stage_key)) {
            continue
        }
        const targetStageKey = pickRemapTarget(stage, activeRecommendedStages)
        if (!targetStageKey) continue
        remaps.push({
            removed_stage_key: stage.stage_key,
            target_stage_key: targetStageKey,
        })
    }

    return remaps
}
