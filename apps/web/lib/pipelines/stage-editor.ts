import type {
    PipelineDependencyGraph,
    PipelineDraft,
    PipelineEntityType,
    PipelineFeatureConfig,
    PipelineStage,
    PipelineStageRemap,
    StageCapabilityKey,
    StageType,
    StageSemantics,
} from "@/lib/api/pipelines"
import {
    CUSTOM_STAGE_COLOR_PRESETS,
    resolveStageColor,
    shouldAutoRefreshStageColor,
    suggestStageColor,
} from "@/lib/pipeline-stage-colors"
import { createSelectLabelGetter, getSelectLabel } from "@/lib/select-labels"
import { stageDisplayColor } from "@/lib/stage-colors"
import { getStageSemantics, normalizeStageKey } from "@/lib/surrogate-stage-context"

/**
 * Draft model for Settings > Pipelines: types, labels, validation and the pure draft
 * transforms the page's editor hook composes. Presentation lives in components/pipelines.
 */

export type EditableStage = PipelineStage & {
    category: StageType
    semantics: StageSemantics
}

export type StageSemanticInput = {
    stage_key?: string | null
    slug?: string | null
    stage_type?: string | null
    semantics?: Partial<StageSemantics> | null
}

export type PipelineDraftState = {
    name: string
    stages: EditableStage[]
    featureConfig: PipelineFeatureConfig
    remaps: PipelineStageRemap[]
}

export type DeleteStageState = {
    stageKey: string
    targetStageKey: string
}

export type ScopedEditorState<T> = {
    contextKey: string
    value: T
}

export type ImpactArea =
    | "analytics"
    | "campaigns"
    | "integrations"
    | "intelligent_suggestions"
    | "journey"
    | "role_mutation"
    | "role_visibility"
    | "ui_gating"
    | "workflows"

export type BehaviorPreset =
    | "intake"
    | "contacted"
    | "match_candidate"
    | "matched"
    | "pregnancy_milestone"
    | "delivery"
    | "pause"
    | "terminal_lost"
    | "terminal_disqualified"
    | "custom"

export const STAGE_CATEGORIES: StageType[] = [
    "intake",
    "post_approval",
    "paused",
    "terminal",
]

export const CUSTOM_STAGE_CATEGORIES: StageType[] = ["intake", "post_approval"]
export const STAGE_CATEGORY_LABELS: Record<StageType, string> = {
    intake: "Intake",
    post_approval: "Post-approval",
    paused: "Paused",
    terminal: "Terminal",
}
export const getStageCategoryLabel = createSelectLabelGetter(STAGE_CATEGORY_LABELS, {
    emptyLabel: "Select category",
    unknownLabel: "Unknown category",
})
export const STAGE_LABEL_MAX_LENGTH = 100
export const STAGE_SLUG_MAX_LENGTH = 50
export const IMPACT_PREVIEW_ID = "pipeline-impact-preview"
/** Add Custom Stage on the phone list or the desktop toolbar; only one of them is mounted. */
export const ADD_STAGE_BUTTON_ID = "pipeline-add-stage"
export const DEFAULT_CUSTOM_STAGE_COLOR = "#6b7280"
export const RESERVED_CAPABILITY_KEYS = new Set<StageCapabilityKey>([
    "eligible_for_matching",
    "locks_match_state",
    "shows_pregnancy_tracking",
    "requires_delivery_details",
])

export const CAPABILITY_LABELS: Array<{
    key: StageCapabilityKey
    label: string
}> = [
    { key: "counts_as_contacted", label: "Counts as contacted" },
    { key: "eligible_for_matching", label: "Eligible for matching" },
    { key: "locks_match_state", label: "Locks match state" },
    { key: "shows_pregnancy_tracking", label: "Shows pregnancy tracking" },
    { key: "requires_delivery_details", label: "Requires delivery details" },
    { key: "tracks_interview_outcome", label: "Tracks interview outcome" },
]

export const PIPELINE_ENTITY_OPTIONS: Array<{
    value: PipelineEntityType
    label: string
}> = [
    { value: "surrogate", label: "Surrogates" },
    { value: "intended_parent", label: "Intended Parents" },
    { value: "egg_donor", label: "Egg Donors" },
    { value: "sperm_donor", label: "Sperm Donors" },
]

export const IMPACT_LABELS: Record<ImpactArea, string> = {
    analytics: "Analytics and reports",
    campaigns: "Campaign filters",
    integrations: "Integrations",
    intelligent_suggestions: "Intelligent suggestions",
    journey: "Journey milestones",
    role_mutation: "Role mutation rules",
    role_visibility: "Role visibility rules",
    ui_gating: "UI gating and actions",
    workflows: "Workflow references",
}

export const REMAP_REASON_LABELS: Record<string, string> = {
    active_surrogates: "Active surrogates",
    campaigns: "Campaign filters",
    intelligent_suggestions: "Intelligent suggestions",
    integrations: "Integration mappings",
    records: "Records",
    workflows: "Workflow references",
}

export const SUGGESTION_PROFILE_OPTIONS = [
    "",
    "new_unread_followup",
    "contacted_followup",
    "qualified_followup",
    "interview_scheduled_followup",
    "application_submitted_followup",
    "under_review_followup",
    "approved_followup",
    "ready_to_match_followup",
    "matched_followup",
    "medical_clearance_followup",
    "legal_clearance_followup",
    "transfer_cycle_followup",
    "second_hcg_followup",
    "heartbeat_followup",
    "ob_care_followup",
    "anatomy_scan_followup",
]

export function deepClone<T>(value: T): T {
    return structuredClone(value)
}

export function createLocalId(): string {
    return `draft-${Math.random().toString(36).slice(2, 10)}`
}

export function isUuidLike(value: string | undefined): boolean {
    return Boolean(value && /^[0-9a-fA-F-]{36}$/.test(value))
}

export function normalizeIdentifier(value: string): string {
    return value
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9_]/g, "_")
        .replace(/_+/g, "_")
        .replace(/^_+|_+$/g, "")
}

export function ensureUniqueIdentifier(base: string, existing: Set<string>): string {
    const normalizedBase = normalizeIdentifier(base) || "custom_stage"
    let candidate = normalizedBase
    let counter = 2
    while (existing.has(candidate)) {
        candidate = `${normalizedBase}_${counter}`
        counter += 1
    }
    return candidate
}

export function createFallbackFeatureConfig(stages: PipelineStage[]): PipelineFeatureConfig {
    const stageKeys = stages.map((stage) => stage.stage_key)
    return {
        schema_version: 1,
        journey: {
            phases: [],
            milestones: [],
        },
        analytics: {
            funnel_stage_keys: stageKeys.slice(0, 6),
            performance_stage_keys: stageKeys.slice(1, 8),
            qualification_stage_key: stageKeys[2] ?? stageKeys[0] ?? null,
            conversion_stage_key: stageKeys[4] ?? stageKeys.at(-1) ?? null,
        },
        role_visibility: {},
        role_mutation: {},
    }
}

export function getVisibleCapabilityLabels(entityType: PipelineEntityType) {
    if (entityType === "intended_parent") {
        return CAPABILITY_LABELS.filter((capability) =>
            [
                "eligible_for_matching",
                "locks_match_state",
                "requires_delivery_details",
            ].includes(capability.key),
        )
    }
    if (entityType === "egg_donor" || entityType === "sperm_donor") {
        return CAPABILITY_LABELS.filter((capability) =>
            ["counts_as_contacted", "eligible_for_matching", "locks_match_state"].includes(
                capability.key,
            ),
        )
    }
    return CAPABILITY_LABELS
}

export function getEntityRecordLabel(entityType: PipelineEntityType, count: number) {
    if (entityType === "intended_parent") {
        // Includes archived intended parents, which keep their stage.
        return `${count} record${count === 1 ? "" : "s"}`
    }
    if (entityType === "egg_donor") {
        return `${count} active egg donor${count === 1 ? "" : "s"}`
    }
    if (entityType === "sperm_donor") {
        return `${count} active sperm donor${count === 1 ? "" : "s"}`
    }
    return `${count} active surrogate${count === 1 ? "" : "s"}`
}

export function isPipelineEntityType(value: unknown): value is PipelineEntityType {
    return PIPELINE_ENTITY_OPTIONS.some((option) => option.value === value)
}

export function getIntendedParentStageSemantics(stage: StageSemanticInput | null | undefined): StageSemantics {
    const stageKey = normalizeStageKey(stage?.stage_key ?? stage?.slug ?? null)
    const isMatchedStage = stageKey === "matched" || stageKey === "delivered"

    return {
        capabilities: {
            counts_as_contacted: false,
            eligible_for_matching: stageKey === "ready_to_match",
            locks_match_state: isMatchedStage,
            shows_pregnancy_tracking: false,
            requires_delivery_details: stageKey === "delivered",
            tracks_interview_outcome: false,
        },
        pause_behavior: stageKey === "on_hold" ? "resume_previous_stage" : "none",
        terminal_outcome:
            stageKey === "lost"
                ? "lost"
                : stageKey === "disqualified"
                    ? "disqualified"
                    : "none",
        integration_bucket: "none",
        analytics_bucket: null,
        suggestion_profile_key: null,
        requires_reason_on_enter: stageKey === "on_hold",
    }
}

export function getStageSemanticsForEntity(
    entityType: PipelineEntityType,
    stage: StageSemanticInput | null | undefined,
): StageSemantics {
    if (entityType === "surrogate") {
        return getStageSemantics(stage)
    }
    const base = getIntendedParentStageSemantics(stage)
    const merged = {
        ...base,
        ...stage?.semantics,
        capabilities: {
            ...base.capabilities,
            ...(stage?.semantics?.capabilities ?? {}),
        },
    }
    // Donor and intended parent stage changes never resume a paused-from stage.
    if (
        normalizeStageKey(stage?.stage_key ?? stage?.slug ?? null) === "on_hold" &&
        stage?.semantics?.pause_behavior == null
    ) {
        return { ...merged, pause_behavior: "none" }
    }
    return merged
}

export function normalizeEditableStage(
    stage: PipelineStage,
    entityType: PipelineEntityType,
): EditableStage {
    const category = stage.category ?? stage.stage_type
    return {
        ...stage,
        id: stage.id || stage.stage_key,
        category,
        stage_type: category,
        color: resolveStageColor({
            color: stage.color,
            label: stage.label,
            slug: stage.slug,
            stage_key: stage.stage_key,
            stage_type: category,
            order: stage.order,
            is_locked: stage.is_locked ?? false,
        }),
        is_locked: stage.is_locked ?? false,
        system_role: stage.system_role ?? null,
        lock_reason: stage.lock_reason ?? null,
        locked_fields: stage.locked_fields ?? [],
        semantics: deepClone(getStageSemanticsForEntity(entityType, stage)),
    }
}

export function buildDraft(
    pipeline:
        | {
            name: string
            stages: PipelineStage[]
            feature_config?: PipelineFeatureConfig
        }
        | null
        | undefined,
    entityType: PipelineEntityType,
): PipelineDraftState | null {
    if (!pipeline) return null
    return {
        name: pipeline.name,
        stages: pipeline.stages.map((stage) => normalizeEditableStage(stage, entityType)),
        featureConfig: deepClone(
            pipeline.feature_config ?? createFallbackFeatureConfig(pipeline.stages),
        ),
        remaps: [],
    }
}

export function buildApiDraft(draft: PipelineDraftState): PipelineDraft {
    return {
        name: draft.name,
        stages: draft.stages.map((stage, index) => ({
            ...(isUuidLike(stage.id) ? { id: stage.id } : {}),
            stage_key: stage.stage_key,
            slug: stage.slug,
            label: stage.label,
            color: stage.color,
            order: index + 1,
            category: stage.category,
            is_active: stage.is_active,
            semantics: stage.semantics,
        })),
        feature_config: draft.featureConfig,
        remaps: draft.remaps,
    }
}

export function stringifyDraft(draft: PipelineDraftState): string {
    return JSON.stringify(buildApiDraft(draft))
}

/**
 * The recommended draft carries no lock metadata, so system stages keep the lock state of the
 * current stage with the same stage_key. Without this, Reset to Default unlocks them.
 */
export function withCurrentLockMetadata(stages: PipelineStage[], currentStages: PipelineStage[]): PipelineStage[] {
    const currentByKey = new Map(currentStages.map((stage) => [stage.stage_key, stage]))
    return stages.map((stage) => {
        const current = currentByKey.get(stage.stage_key)
        if (!current) return stage
        const merged: PipelineStage = { ...stage }
        const isLocked = stage.is_locked ?? current.is_locked
        const systemRole = stage.system_role ?? current.system_role
        const lockReason = stage.lock_reason ?? current.lock_reason
        const lockedFields = stage.locked_fields ?? current.locked_fields
        if (isLocked !== undefined) merged.is_locked = isLocked
        if (systemRole !== undefined) merged.system_role = systemRole
        if (lockReason !== undefined) merged.lock_reason = lockReason
        if (lockedFields !== undefined) merged.locked_fields = lockedFields
        return merged
    })
}

export type StageFieldErrors = { label?: string; slug?: string }

/** Client checks for the fields the API rejects with a 422, keyed by stage id. */
export function getDraftStageErrors(stages: EditableStage[]): Record<string, StageFieldErrors> {
    const slugCounts = new Map<string, number>()
    for (const stage of stages) {
        if (stage.slug) slugCounts.set(stage.slug, (slugCounts.get(stage.slug) ?? 0) + 1)
    }
    const errors: Record<string, StageFieldErrors> = {}
    for (const stage of stages) {
        if (stage.is_locked) continue
        const stageErrors: StageFieldErrors = {}
        if (!stage.label.trim()) stageErrors.label = "Enter a stage label."
        if (!stage.slug) {
            stageErrors.slug = "Enter a slug."
        } else if ((slugCounts.get(stage.slug) ?? 0) > 1) {
            stageErrors.slug = "Another stage uses this slug."
        }
        if (stageErrors.label || stageErrors.slug) errors[stage.id] = stageErrors
    }
    return errors
}

export function countStageErrors(errors: Record<string, StageFieldErrors>): number {
    return Object.values(errors).reduce(
        (total, stageErrors) => total + (stageErrors.label ? 1 : 0) + (stageErrors.slug ? 1 : 0),
        0,
    )
}

export function getStageEditFingerprint(stage: EditableStage): string {
    return JSON.stringify([
        stage.slug,
        stage.label,
        stage.color,
        stage.category,
        stage.is_active,
        stage.semantics,
    ])
}

/** Added, removed and edited stages, plus one each for stage order, journey/analytics config and name. */
export function countDraftChanges(baseline: PipelineDraftState | null, draft: PipelineDraftState | null): number {
    if (!baseline || !draft) return 0
    const baselineByKey = new Map(baseline.stages.map((stage) => [stage.stage_key, stage]))
    const draftKeys = new Set(draft.stages.map((stage) => stage.stage_key))
    let count = 0
    for (const stage of draft.stages) {
        const baselineStage = baselineByKey.get(stage.stage_key)
        if (!baselineStage || getStageEditFingerprint(baselineStage) !== getStageEditFingerprint(stage)) {
            count += 1
        }
    }
    for (const stage of baseline.stages) {
        if (!draftKeys.has(stage.stage_key)) count += 1
    }
    const sharedOrder = (stages: EditableStage[], keys: Set<string>) =>
        stages.filter((stage) => keys.has(stage.stage_key)).map((stage) => stage.stage_key).join("|")
    const baselineKeys = new Set(baselineByKey.keys())
    if (sharedOrder(baseline.stages, draftKeys) !== sharedOrder(draft.stages, baselineKeys)) count += 1
    if (JSON.stringify(baseline.featureConfig) !== JSON.stringify(draft.featureConfig)) count += 1
    if (baseline.name !== draft.name) count += 1
    return count
}

export function getBehaviorPreset(
    stage: EditableStage,
    entityType: PipelineEntityType,
): BehaviorPreset {
    const semantics = stage.semantics
    if (entityType !== "intended_parent") {
        if (semantics.pause_behavior === "resume_previous_stage") return "pause"
        if (stage.category === "paused" && semantics.requires_reason_on_enter) return "pause"
    }
    if (semantics.terminal_outcome === "lost") return "terminal_lost"
    if (semantics.terminal_outcome === "disqualified") return "terminal_disqualified"
    if (semantics.capabilities.requires_delivery_details) return "delivery"
    if (semantics.capabilities.eligible_for_matching) return "match_candidate"
    if (semantics.capabilities.locks_match_state) return "matched"
    if (entityType === "surrogate" && semantics.capabilities.shows_pregnancy_tracking) {
        return "pregnancy_milestone"
    }
    if (entityType === "surrogate" && semantics.capabilities.counts_as_contacted) {
        return "contacted"
    }
    return stage.category === "intake" ? "intake" : "custom"
}

export function buildPresetSemantics(
    stage: EditableStage,
    preset: BehaviorPreset,
    entityType: PipelineEntityType,
): StageSemantics {
    const base = deepClone(getStageSemanticsForEntity(entityType, stage))
    const reset: StageSemantics = {
        ...base,
        capabilities: {
            counts_as_contacted: false,
            eligible_for_matching: false,
            locks_match_state: false,
            shows_pregnancy_tracking: false,
            requires_delivery_details: false,
            tracks_interview_outcome: false,
        },
        pause_behavior: "none",
        terminal_outcome: "none",
        integration_bucket: entityType === "surrogate" ? "none" : "none",
        analytics_bucket: null,
        suggestion_profile_key: null,
        requires_reason_on_enter: false,
    }

    if (entityType !== "surrogate") {
        switch (preset) {
            case "intake":
                return reset
            case "contacted":
                return {
                    ...reset,
                    capabilities: {
                        ...reset.capabilities,
                        counts_as_contacted: true,
                    },
                }
            case "match_candidate":
                return {
                    ...reset,
                    capabilities: {
                        ...reset.capabilities,
                        eligible_for_matching: true,
                    },
                }
            case "matched":
                return {
                    ...reset,
                    capabilities: {
                        ...reset.capabilities,
                        locks_match_state: true,
                    },
                }
            case "delivery":
                if (entityType !== "intended_parent") return deepClone(stage.semantics)
                return {
                    ...reset,
                    capabilities: {
                        ...reset.capabilities,
                        locks_match_state: true,
                        requires_delivery_details: true,
                    },
                }
            case "pause":
                return {
                    ...reset,
                    requires_reason_on_enter: true,
                }
            case "terminal_lost":
                return {
                    ...reset,
                    terminal_outcome: "lost",
                }
            case "terminal_disqualified":
                return {
                    ...reset,
                    terminal_outcome: "disqualified",
                }
            case "custom":
            default:
                return deepClone(stage.semantics)
        }
    }

    switch (preset) {
        case "intake":
            return {
                ...reset,
                integration_bucket: "intake",
            }
        case "contacted":
            return {
                ...reset,
                integration_bucket: "qualified",
                capabilities: {
                    ...reset.capabilities,
                    counts_as_contacted: true,
                },
            }
        case "match_candidate":
            return {
                ...reset,
                integration_bucket: "converted",
                capabilities: {
                    ...reset.capabilities,
                    eligible_for_matching: true,
                },
            }
        case "matched":
            return {
                ...reset,
                integration_bucket: "converted",
                capabilities: {
                    ...reset.capabilities,
                    locks_match_state: true,
                },
            }
        case "pregnancy_milestone":
            return {
                ...reset,
                integration_bucket: "converted",
                capabilities: {
                    ...reset.capabilities,
                    locks_match_state: true,
                    shows_pregnancy_tracking: true,
                },
            }
        case "delivery":
            return {
                ...reset,
                integration_bucket: "converted",
                capabilities: {
                    ...reset.capabilities,
                    locks_match_state: true,
                    shows_pregnancy_tracking: true,
                    requires_delivery_details: true,
                },
            }
        case "pause":
            return {
                ...reset,
                pause_behavior: "resume_previous_stage",
                requires_reason_on_enter: true,
            }
        case "terminal_lost":
            return {
                ...reset,
                terminal_outcome: "lost",
                integration_bucket: "lost",
            }
        case "terminal_disqualified":
            return {
                ...reset,
                terminal_outcome: "disqualified",
                integration_bucket: "not_qualified",
            }
        case "custom":
        default:
            return deepClone(stage.semantics)
    }
}

const BEHAVIOR_PRESET_LABELS: Record<BehaviorPreset, string> = {
    intake: "Intake",
    contacted: "Contacted",
    match_candidate: "Match candidate",
    matched: "Matched",
    pregnancy_milestone: "Pregnancy milestone",
    delivery: "Delivery",
    pause: "Pause",
    terminal_lost: "Terminal lost",
    terminal_disqualified: "Terminal disqualified",
    custom: "Custom",
}

/** One label per preset for the select trigger, its items and the stage table's Behavior cell. */
export function getBehaviorPresetLabel(preset: BehaviorPreset, entityType: PipelineEntityType): string {
    if (entityType === "intended_parent") {
        if (preset === "match_candidate") return "Ready to match"
        if (preset === "delivery") return "Delivered"
    }
    if ((entityType === "egg_donor" || entityType === "sperm_donor") && preset === "match_candidate") {
        return "Available to match"
    }
    return BEHAVIOR_PRESET_LABELS[preset]
}

function getSelectablePresets(stage: EditableStage, entityType: PipelineEntityType): BehaviorPreset[] {
    if (!stage.is_locked) {
        if (stage.category === "intake") {
            if (entityType === "intended_parent") return ["intake", "custom"]
            return ["intake", "contacted", "custom"]
        }
        return ["custom"]
    }
    if (stage.category === "paused") {
        if (entityType === "intended_parent") return ["custom"]
        return ["pause", "custom"]
    }
    if (stage.category === "terminal") {
        return ["terminal_lost", "terminal_disqualified", "custom"]
    }
    if (entityType === "intended_parent" && stage.category === "post_approval") {
        return ["match_candidate", "matched", "delivery", "custom"]
    }
    if (
        (entityType === "egg_donor" || entityType === "sperm_donor") &&
        stage.category === "post_approval"
    ) {
        return ["match_candidate", "matched", "custom"]
    }
    if (stage.category === "post_approval") {
        return ["match_candidate", "matched", "pregnancy_milestone", "delivery", "custom"]
    }
    if (entityType === "intended_parent") return ["intake", "custom"]
    return ["intake", "contacted", "custom"]
}

export function getPresetOptions(
    stage: EditableStage,
    entityType: PipelineEntityType,
): Array<{ value: BehaviorPreset; label: string }> {
    const presets = getSelectablePresets(stage, entityType)
    // Unlocked platform stages keep seeded lifecycle semantics they cannot select (Medical
    // Clearance Passed reads as Matched). List the current preset so the trigger names it
    // instead of "Unknown option".
    const current = getBehaviorPreset(stage, entityType)
    if (!presets.includes(current)) {
        presets.splice(Math.max(presets.indexOf("custom"), 0), 0, current)
    }
    return presets.map((value) => ({ value, label: getBehaviorPresetLabel(value, entityType) }))
}

export function remapStageKeys(values: string[], removedStageKey: string, targetStageKey?: string): string[] {
    const remapped: string[] = []
    for (const value of values) {
        const nextValue = value === removedStageKey ? targetStageKey : value
        if (nextValue) {
            remapped.push(nextValue)
        }
    }
    return Array.from(new Set(remapped))
}

export function applyLocalFeatureConfigRemap(
    featureConfig: PipelineFeatureConfig,
    removedStageKey: string,
    targetStageKey?: string,
): PipelineFeatureConfig {
    const next = deepClone(featureConfig)
    next.journey.milestones = next.journey.milestones.map((milestone) => ({
        ...milestone,
        mapped_stage_keys: remapStageKeys(
            milestone.mapped_stage_keys,
            removedStageKey,
            targetStageKey,
        ),
    }))
    next.analytics.funnel_stage_keys = remapStageKeys(
        next.analytics.funnel_stage_keys,
        removedStageKey,
        targetStageKey,
    )
    next.analytics.performance_stage_keys = remapStageKeys(
        next.analytics.performance_stage_keys,
        removedStageKey,
        targetStageKey,
    )
    if (next.analytics.qualification_stage_key === removedStageKey) {
        next.analytics.qualification_stage_key = targetStageKey ?? null
    }
    if (next.analytics.conversion_stage_key === removedStageKey) {
        next.analytics.conversion_stage_key = targetStageKey ?? null
    }
    for (const rule of Object.values(next.role_visibility)) {
        rule.stage_keys = remapStageKeys(rule.stage_keys, removedStageKey, targetStageKey)
    }
    for (const rule of Object.values(next.role_mutation)) {
        rule.stage_keys = remapStageKeys(rule.stage_keys, removedStageKey, targetStageKey)
    }
    return next
}

export function buildNewStage(
    draft: PipelineDraftState,
    entityType: PipelineEntityType,
    insertIndex: number,
): EditableStage {
    const existingKeys = new Set(draft.stages.map((stage) => stage.stage_key))
    const existingSlugs = new Set(draft.stages.map((stage) => stage.slug))
    const stageKey = ensureUniqueIdentifier("custom_stage", existingKeys)
    const slug = ensureUniqueIdentifier(stageKey, existingSlugs)
    const previousStage = draft.stages[insertIndex - 1]
    const nextStage = draft.stages[insertIndex]
    const category: StageType =
        previousStage?.stage_type === "post_approval" || nextStage?.stage_type === "post_approval"
            ? "post_approval"
            : "intake"
    const presetPalette = CUSTOM_STAGE_COLOR_PRESETS[category]
    let categoryStageCount = 0
    for (let index = 0; index < insertIndex; index += 1) {
        if (draft.stages[index]?.stage_type === category) {
            categoryStageCount += 1
        }
    }
    const presetIndex = categoryStageCount % presetPalette.length
    // Presets are display colors; compare neighbors (possibly stored before darkening) the same way.
    const neighborColors = new Set<string>()
    for (const color of [previousStage?.color, nextStage?.color]) {
        if (color) {
            neighborColors.add(stageDisplayColor(color).toLowerCase())
        }
    }
    const presetColor =
        presetPalette.find(
            (color, offset) =>
                offset >= presetIndex
                && !neighborColors.has(color.toLowerCase()),
        )
        ?? presetPalette.find((color) => !neighborColors.has(color.toLowerCase()))
        ?? presetPalette[presetIndex]
        ?? DEFAULT_CUSTOM_STAGE_COLOR
    const base: EditableStage = {
        id: createLocalId(),
        stage_key: stageKey,
        slug,
        label: "New Stage",
        color: presetColor,
        order: draft.stages.length + 1,
        category,
        stage_type: category,
        is_active: true,
        is_locked: false,
        system_role: null,
        lock_reason: null,
        locked_fields: [],
        semantics: getStageSemanticsForEntity(entityType, {
            stage_key: stageKey,
            slug,
            stage_type: category,
        }),
    }
    return base
}

export function withAutoStageColor(current: EditableStage, next: EditableStage): EditableStage {
    if (!shouldAutoRefreshStageColor(current)) {
        return next
    }
    return {
        ...next,
        color: suggestStageColor({
            color: next.color,
            label: next.label,
            slug: next.slug,
            stage_key: next.stage_key,
            stage_type: next.stage_type,
            order: next.order,
            is_locked: next.is_locked ?? false,
        }),
    }
}

export function buildDuplicateStage(source: EditableStage, draft: PipelineDraftState): EditableStage {
    const existingKeys = new Set(draft.stages.map((stage) => stage.stage_key))
    const existingSlugs = new Set(draft.stages.map((stage) => stage.slug))
    const stageKey = ensureUniqueIdentifier(`${source.stage_key}_copy`, existingKeys)
    const slug = ensureUniqueIdentifier(`${source.slug}_copy`, existingSlugs)
    return {
        ...deepClone(source),
        id: createLocalId(),
        stage_key: stageKey,
        slug,
        label: `${source.label} Copy`,
        order: draft.stages.length + 1,
        is_locked: false,
        system_role: null,
        lock_reason: null,
        locked_fields: [],
    }
}

export function getDefaultStageInsertIndex(stages: EditableStage[]): number {
    for (let index = stages.length - 1; index >= 0; index -= 1) {
        if (!stages[index]?.is_locked) {
            return index + 1
        }
    }
    return Math.max(stages.length - 1, 0)
}

export function getDependencyByStageKey(
    dependencyGraph: PipelineDependencyGraph | null | undefined,
    stageKey: string,
) {
    return dependencyGraph?.stages.find((stage) => stage.stage_key === stageKey)
}

export function getDeleteRequirements(
    dependencyGraph: PipelineDependencyGraph | null | undefined,
    stageKey: string,
    entityType: PipelineEntityType,
): string[] {
    const dependency = getDependencyByStageKey(dependencyGraph, stageKey)
    if (!dependency) return []
    const requirements: string[] = []
    if (dependency.surrogate_count > 0) {
        requirements.push(getEntityRecordLabel(entityType, dependency.surrogate_count))
    }
    if (dependency.intelligent_suggestion_rules.length > 0) {
        requirements.push("intelligent suggestions")
    }
    if (dependency.integration_refs.length > 0) {
        requirements.push("integration mappings")
    }
    if (dependency.campaign_refs.length > 0) {
        requirements.push("campaign filters")
    }
    if (dependency.workflow_refs.length > 0) {
        requirements.push("workflow references")
    }
    return requirements
}

export function getActiveRemapTargetStages(stages: EditableStage[], stageKey: string): EditableStage[] {
    return stages
        .filter((candidate) => candidate.is_active && candidate.stage_key !== stageKey)
        .sort((left, right) => left.order - right.order)
}

export function getDefaultRemapTargetStageKey(stages: EditableStage[], stageKey: string): string {
    const orderedStages = stages
        .filter((stage) => stage.is_active)
        .sort((left, right) => left.order - right.order)
    const stageIndex = orderedStages.findIndex((stage) => stage.stage_key === stageKey)
    if (stageIndex < 0) return ""
    const previousStages = orderedStages.slice(0, stageIndex).reverse()
    return (
        orderedStages.slice(stageIndex + 1).find((stage) => stage.stage_key !== stageKey)?.stage_key
        ?? previousStages.find((stage) => stage.stage_key !== stageKey)?.stage_key
        ?? ""
    )
}

export type PipelineSelectOption = {
    value: string
    label: string
    disabled?: boolean
}

export const EMPTY_SELECT_SENTINEL = "__empty_select_value__"

export function normalizeSelectValue(value: string | null | undefined): string {
    return value && value.length > 0 ? value : EMPTY_SELECT_SENTINEL
}

export function denormalizeSelectValue(value: string | null | undefined): string {
    return !value || value === EMPTY_SELECT_SENTINEL ? "" : value
}

export function getPipelineSelectLabel(options: PipelineSelectOption[], value: string | null, fieldLabel: string): string {
    return getSelectLabel(denormalizeSelectValue(value), options, {
        emptyLabel: options.find((option) => option.value === "")?.label ?? fieldLabel,
        unknownLabel: "Unknown option",
    })
}

/** Every selectable category plus the stage's current one, so the trigger never renders blank. */
export function getStageCategoryOptions(stage: EditableStage): PipelineSelectOption[] {
    const selectable = stage.is_locked ? STAGE_CATEGORIES : CUSTOM_STAGE_CATEGORIES
    const categories = STAGE_CATEGORIES.filter(
        (category) => selectable.includes(category) || category === stage.category,
    )
    return categories.map((category) => ({
        value: category,
        label: getStageCategoryLabel(category),
        disabled: !selectable.includes(category),
    }))
}

/** Header for the stage table's record count column. */
export function getEntityCountColumnLabel(entityType: PipelineEntityType): string {
    if (entityType === "intended_parent") return "Records"
    if (entityType === "egg_donor") return "Egg donors"
    if (entityType === "sperm_donor") return "Sperm donors"
    return "Surrogates"
}

/** Moves one stage from `fromIndex` to `toIndex` and renumbers `order`. Locked stages may be passed. */
export function moveStageInList(stages: EditableStage[], fromIndex: number, toIndex: number): EditableStage[] {
    if (fromIndex === toIndex || toIndex < 0 || toIndex >= stages.length) return stages
    const next = [...stages]
    const [moved] = next.splice(fromIndex, 1)
    if (!moved) return stages
    next.splice(toIndex, 0, moved)
    return next.map((stage, index) => ({ ...stage, order: index + 1 }))
}

/** Journey milestone slugs that map this stage, in milestone order. */
export function getStageMilestoneSlugs(featureConfig: PipelineFeatureConfig, stageKey: string): string[] {
    return featureConfig.journey.milestones
        .filter((milestone) => milestone.mapped_stage_keys.includes(stageKey))
        .map((milestone) => milestone.slug)
}

/** One label helper for journey milestone values: the drawer select, its trigger and the table cell. */
export function createMilestoneLabelGetter(featureConfig: PipelineFeatureConfig) {
    return createSelectLabelGetter(
        featureConfig.journey.milestones.map((milestone) => ({ value: milestone.slug, label: milestone.label })),
        { emptyLabel: "None", unknownLabel: "Unknown milestone" },
    )
}

export function withStageMilestones(
    featureConfig: PipelineFeatureConfig,
    stageKey: string,
    milestoneSlugs: readonly string[],
): PipelineFeatureConfig {
    const selected = new Set(milestoneSlugs)
    const next = deepClone(featureConfig)
    next.journey.milestones = next.journey.milestones.map((milestone) => {
        const keys = milestone.mapped_stage_keys.filter((key) => key !== stageKey)
        return {
            ...milestone,
            mapped_stage_keys: selected.has(milestone.slug) ? [...keys, stageKey] : keys,
        }
    })
    return next
}

/** Adds or removes a stage from the analytics funnel, keeping funnel keys in active stage order. */
export function withStageFunnel(
    featureConfig: PipelineFeatureConfig,
    stages: readonly EditableStage[],
    stageKey: string,
    included: boolean,
): PipelineFeatureConfig {
    const next = deepClone(featureConfig)
    const keys = new Set(next.analytics.funnel_stage_keys)
    if (included) keys.add(stageKey)
    else keys.delete(stageKey)
    next.analytics.funnel_stage_keys = stages
        .filter((stage) => stage.is_active && keys.has(stage.stage_key))
        .map((stage) => stage.stage_key)
    return next
}
