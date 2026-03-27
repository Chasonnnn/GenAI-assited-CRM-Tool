import type { PipelineStage } from "@/lib/api/pipelines"
import { getStageSemantics, normalizeStageKey } from "@/lib/surrogate-stage-context"

type MatchCandidateStageRef = {
    stage_id?: string | null
    stage_key?: string | null
    stage_slug?: string | null
}

function findPipelineStageForCandidate(
    candidate: MatchCandidateStageRef,
    stages: PipelineStage[],
): PipelineStage | undefined {
    const normalizedStageKey = normalizeStageKey(candidate.stage_key ?? candidate.stage_slug ?? null)
    return stages.find((stage) => {
        if (candidate.stage_id && stage.id === candidate.stage_id) return true
        if (normalizedStageKey && stage.stage_key === normalizedStageKey) return true
        if (candidate.stage_slug && stage.slug === candidate.stage_slug) return true
        return false
    })
}

export function getEligibleForMatchingStages(stages: PipelineStage[] | undefined | null): PipelineStage[] {
    return (stages ?? []).filter((stage) => getStageSemantics(stage).capabilities.eligible_for_matching)
}

export function getEligibleForMatchingStageLabel(stages: PipelineStage[] | undefined | null): string {
    return getEligibleForMatchingStages(stages)[0]?.label ?? "Ready to Match"
}

export function isEligibleForMatchingCandidate(
    candidate: MatchCandidateStageRef,
    stages: PipelineStage[] | undefined | null,
): boolean {
    const matchedStage = findPipelineStageForCandidate(candidate, stages ?? [])
    if (matchedStage) {
        return getStageSemantics(matchedStage).capabilities.eligible_for_matching
    }
    return getStageSemantics({
        stage_key: candidate.stage_key,
        stage_slug: candidate.stage_slug,
    }).capabilities.eligible_for_matching
}
