import type {
    PipelineFeatureConfig,
    PipelineStage,
    RoleStageRule,
    StageCapabilityKey,
    StageSemantics,
} from "@/lib/api/pipelines"
import type { SurrogateRead } from "@/lib/types/surrogate"

const LEGACY_STAGE_KEY_ALIASES: Record<string, string> = {
    qualified: "pre_qualified",
}

type StageSemanticRef = {
    stage_key?: string | null | undefined
    slug?: string | null | undefined
    stage_slug?: string | null | undefined
    stage_type?: string | null | undefined
    semantics?: Partial<StageSemantics> | null | undefined
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

function defaultStageSemantics(
    stageKey: string | null,
    stageType: string | null | undefined
): StageSemantics {
    const normalizedKey = normalizeStageKey(stageKey)
    return {
        capabilities: {
            counts_as_contacted: !!normalizedKey && [
                "contacted",
                "pre_qualified",
                "interview_scheduled",
                "application_submitted",
                "pending_docusign",
                "under_review",
                "approved",
            ].includes(normalizedKey),
            eligible_for_matching: normalizedKey === "ready_to_match",
            locks_match_state: !!normalizedKey && [
                "matched",
                "medical_clearance_passed",
                "legal_clearance_passed",
                "transfer_cycle",
                "second_hcg_confirmed",
                "heartbeat_confirmed",
                "life_insurance_application_started",
                "ob_care_established",
                "pbo_process_started",
                "anatomy_scanned",
                "delivered",
            ].includes(normalizedKey),
            shows_pregnancy_tracking: !!normalizedKey && [
                "heartbeat_confirmed",
                "life_insurance_application_started",
                "ob_care_established",
                "pbo_process_started",
                "anatomy_scanned",
                "delivered",
            ].includes(normalizedKey),
            requires_delivery_details: normalizedKey === "delivered",
            tracks_interview_outcome: !!normalizedKey && [
                "interview_scheduled",
                "under_review",
                "approved",
            ].includes(normalizedKey),
        },
        pause_behavior: normalizedKey === "on_hold" ? "resume_previous_stage" : "none",
        terminal_outcome:
            normalizedKey === "lost" ? "lost" : normalizedKey === "disqualified" ? "disqualified" : "none",
        integration_bucket:
            normalizedKey === "lost"
                ? "lost"
                : normalizedKey === "disqualified"
                    ? "not_qualified"
                    : normalizedKey && [
                        "ready_to_match",
                        "matched",
                        "medical_clearance_passed",
                        "legal_clearance_passed",
                        "transfer_cycle",
                        "second_hcg_confirmed",
                        "heartbeat_confirmed",
                        "life_insurance_application_started",
                        "ob_care_established",
                        "pbo_process_started",
                        "anatomy_scanned",
                        "delivered",
                    ].includes(normalizedKey)
                    ? "converted"
                    : normalizedKey && [
                        "pre_qualified",
                        "interview_scheduled",
                        "application_submitted",
                        "pending_docusign",
                        "under_review",
                        "approved",
                    ].includes(normalizedKey)
                        ? "qualified"
                        : normalizedKey && ["new_unread", "contacted"].includes(normalizedKey)
                            ? "intake"
                            : "none",
        analytics_bucket: normalizedKey ?? (stageType === "paused" ? "on_hold" : null),
        suggestion_profile_key: null,
        requires_reason_on_enter: normalizedKey === "on_hold",
    }
}

export function getStageSemantics(stage: StageSemanticRef | null | undefined): StageSemantics {
    const stageKey = getStageSemanticKey(stage)
    const base = defaultStageSemantics(stageKey, stage?.stage_type)
    return {
        ...base,
        ...stage?.semantics,
        capabilities: {
            ...base.capabilities,
            ...(stage?.semantics?.capabilities ?? {}),
        },
    }
}

export function stageHasCapability(
    stage: StageSemanticRef | null | undefined,
    capability: StageCapabilityKey
): boolean {
    return Boolean(getStageSemantics(stage).capabilities[capability])
}

export function stageRequiresReasonOnEnter(stage: StageSemanticRef | null | undefined): boolean {
    return getStageSemantics(stage).requires_reason_on_enter
}

export function stageUsesPauseBehavior(stage: StageSemanticRef | null | undefined): boolean {
    return getStageSemantics(stage).pause_behavior === "resume_previous_stage"
}

export function roleRuleMatchesStage(stage: PipelineStage, rule: RoleStageRule | undefined): boolean {
    if (!rule) return false
    const semanticKey = getStageSemanticKey(stage)
    if (stage.stage_type && rule.stage_types.includes(stage.stage_type)) return true
    if (semanticKey && rule.stage_keys.includes(semanticKey)) return true
    return rule.capabilities.some((capability) => stageHasCapability(stage, capability))
}

export function canRoleAccessStage(
    role: string | null | undefined,
    stage: PipelineStage,
    featureConfig: PipelineFeatureConfig | null | undefined,
    mutation = false
): boolean {
    if (!role || !featureConfig) return true
    const rules = mutation ? featureConfig.role_mutation : featureConfig.role_visibility
    return roleRuleMatchesStage(stage, rules[role])
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
    return getStageSemantics(stage).terminal_outcome !== "none"
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
    const isOnHold = getStageSemantics(
        currentStage ?? { stage_key: surrogate.stage_key, stage_slug: surrogate.stage_slug }
    ).pause_behavior === "resume_previous_stage"

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
