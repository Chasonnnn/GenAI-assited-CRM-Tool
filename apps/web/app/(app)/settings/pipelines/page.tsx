"use client"

import { useCallback, useRef, useState } from "react"
import { EmptyState } from "@/components/empty-state"
import { QueryErrorState } from "@/components/error-state"
import { PageHeader } from "@/components/page-header"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { SaveBar } from "@/components/ui/save-bar"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import {
    ChevronDownIcon,
    ChevronUpIcon,
    CheckIcon,
    CopyIcon,
    GripVerticalIcon,
    HistoryIcon,
    InfoIcon,
    Loader2Icon,
    PlusIcon,
    RotateCcwIcon,
    SparklesIcon,
    TriangleAlertIcon,
    Trash2Icon,
    WorkflowIcon,
} from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { focusFirstInvalid } from "@/lib/forms/use-form-validation"
import { formatRelativeTime } from "@/lib/formatters"
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value"
import { createSelectLabelGetter, getSelectLabel, humanizeSelectKey } from "@/lib/select-labels"
import { SettingsPageGate } from "../settings-page-gate"
import {
    CUSTOM_STAGE_COLOR_PRESETS,
    resolveStageColor,
    shouldAutoRefreshStageColor,
    suggestStageColor,
} from "@/lib/pipeline-stage-colors"
import type {
    PipelineChangePreview,
    PipelineDependencyGraph,
    PipelineDraft,
    PipelineEntityType,
    PipelineFeatureConfig,
    PipelineRequiredRemap,
    PipelineStageDependency,
    PipelineStage,
    PipelineStageRemap,
    StageCapabilityKey,
    StageType,
    StageSemantics,
} from "@/lib/api/pipelines"
import {
    useApplyPipelineDraft,
    usePipeline,
    usePipelineChangePreview,
    usePipelineDependencyGraph,
    usePipelines,
    usePipelineVersions,
    useRecommendedPipelineDraft,
    useRollbackPipeline,
} from "@/lib/hooks/use-pipelines"
import { getStageSemantics, normalizeStageKey } from "@/lib/surrogate-stage-context"
import { buildRecommendedDraftRemaps } from "@/lib/pipeline-reset-remaps"

type EditableStage = PipelineStage & {
    category: StageType
    semantics: StageSemantics
}

type StageSemanticInput = {
    stage_key?: string | null
    slug?: string | null
    stage_type?: string | null
    semantics?: Partial<StageSemantics> | null
}

type PipelineDraftState = {
    name: string
    stages: EditableStage[]
    featureConfig: PipelineFeatureConfig
    remaps: PipelineStageRemap[]
}

type DeleteStageState = {
    stageKey: string
    targetStageKey: string
}

type ScopedEditorState<T> = {
    contextKey: string
    value: T
}

type ImpactArea =
    | "analytics"
    | "campaigns"
    | "integrations"
    | "intelligent_suggestions"
    | "journey"
    | "role_mutation"
    | "role_visibility"
    | "ui_gating"
    | "workflows"

type BehaviorPreset =
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

const STAGE_CATEGORIES: StageType[] = [
    "intake",
    "post_approval",
    "paused",
    "terminal",
]

const CUSTOM_STAGE_CATEGORIES: StageType[] = ["intake", "post_approval"]
const STAGE_CATEGORY_LABELS: Record<StageType, string> = {
    intake: "Intake",
    post_approval: "Post-approval",
    paused: "Paused",
    terminal: "Terminal",
}
const getStageCategoryLabel = createSelectLabelGetter(STAGE_CATEGORY_LABELS, {
    emptyLabel: "Select category",
    unknownLabel: "Unknown category",
})
const STAGE_LABEL_MAX_LENGTH = 100
const STAGE_SLUG_MAX_LENGTH = 50
const IMPACT_PREVIEW_ID = "pipeline-impact-preview"
const DEFAULT_CUSTOM_STAGE_COLOR = "#6b7280"
const RESERVED_CAPABILITY_KEYS = new Set<StageCapabilityKey>([
    "eligible_for_matching",
    "locks_match_state",
    "shows_pregnancy_tracking",
    "requires_delivery_details",
])

const CAPABILITY_LABELS: Array<{
    key: StageCapabilityKey
    label: string
    description: string
}> = [
    {
        key: "counts_as_contacted",
        label: "Counts as contacted",
        description: "Enables contact-based workflow and unreached gating.",
    },
    {
        key: "eligible_for_matching",
        label: "Eligible for matching",
        description: "Allows match-related actions and surfaced match entry points.",
    },
    {
        key: "locks_match_state",
        label: "Locks match state",
        description: "Treat this stage as post-match for journey and related UI.",
    },
    {
        key: "shows_pregnancy_tracking",
        label: "Shows pregnancy tracking",
        description: "Displays pregnancy tracking and related detail modules.",
    },
    {
        key: "requires_delivery_details",
        label: "Requires delivery details",
        description: "Prompts for delivery metadata when entering this stage.",
    },
    {
        key: "tracks_interview_outcome",
        label: "Tracks interview outcome",
        description: "Enables interview-outcome actions and reminders.",
    },
]

const PIPELINE_ENTITY_OPTIONS: Array<{
    value: PipelineEntityType
    label: string
}> = [
    { value: "surrogate", label: "Surrogates" },
    { value: "intended_parent", label: "Intended Parents" },
    { value: "egg_donor", label: "Egg Donors" },
    { value: "sperm_donor", label: "Sperm Donors" },
]

const IMPACT_LABELS: Record<ImpactArea, string> = {
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

const REMAP_REASON_LABELS: Record<string, string> = {
    active_surrogates: "Active surrogates",
    campaigns: "Campaign filters",
    intelligent_suggestions: "Intelligent suggestions",
    integrations: "Integration mappings",
    records: "Records",
    workflows: "Workflow references",
}

const SUGGESTION_PROFILE_OPTIONS = [
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

function deepClone<T>(value: T): T {
    return structuredClone(value)
}

function createLocalId(): string {
    return `draft-${Math.random().toString(36).slice(2, 10)}`
}

function isUuidLike(value: string | undefined): boolean {
    return Boolean(value && /^[0-9a-fA-F-]{36}$/.test(value))
}

function normalizeIdentifier(value: string): string {
    return value
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9_]/g, "_")
        .replace(/_+/g, "_")
        .replace(/^_+|_+$/g, "")
}

function ensureUniqueIdentifier(base: string, existing: Set<string>): string {
    const normalizedBase = normalizeIdentifier(base) || "custom_stage"
    let candidate = normalizedBase
    let counter = 2
    while (existing.has(candidate)) {
        candidate = `${normalizedBase}_${counter}`
        counter += 1
    }
    return candidate
}

function createFallbackFeatureConfig(stages: PipelineStage[]): PipelineFeatureConfig {
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

function getVisibleCapabilityLabels(entityType: PipelineEntityType) {
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

function getEntityRecordLabel(entityType: PipelineEntityType, count: number) {
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

function isPipelineEntityType(value: unknown): value is PipelineEntityType {
    return PIPELINE_ENTITY_OPTIONS.some((option) => option.value === value)
}

function getIntendedParentStageSemantics(stage: StageSemanticInput | null | undefined): StageSemantics {
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

function getStageSemanticsForEntity(
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
    if (
        (entityType === "egg_donor" || entityType === "sperm_donor") &&
        normalizeStageKey(stage?.stage_key ?? stage?.slug ?? null) === "on_hold" &&
        stage?.semantics?.pause_behavior == null
    ) {
        return { ...merged, pause_behavior: "none" }
    }
    return merged
}

function normalizeEditableStage(
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

function buildDraft(
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

function buildApiDraft(draft: PipelineDraftState): PipelineDraft {
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

function stringifyDraft(draft: PipelineDraftState): string {
    return JSON.stringify(buildApiDraft(draft))
}

/**
 * The recommended draft carries no lock metadata, so system stages keep the lock state of the
 * current stage with the same stage_key. Without this, Reset to Default unlocks them.
 */
function withCurrentLockMetadata(stages: PipelineStage[], currentStages: PipelineStage[]): PipelineStage[] {
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

type StageFieldErrors = { label?: string; slug?: string }

/** Client checks for the fields the API rejects with a 422, keyed by stage id. */
function getDraftStageErrors(stages: EditableStage[]): Record<string, StageFieldErrors> {
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

function countStageErrors(errors: Record<string, StageFieldErrors>): number {
    return Object.values(errors).reduce(
        (total, stageErrors) => total + (stageErrors.label ? 1 : 0) + (stageErrors.slug ? 1 : 0),
        0,
    )
}

function getStageEditFingerprint(stage: EditableStage): string {
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
function countDraftChanges(baseline: PipelineDraftState | null, draft: PipelineDraftState | null): number {
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

function getBehaviorPreset(
    stage: EditableStage,
    entityType: PipelineEntityType,
): BehaviorPreset {
    const semantics = stage.semantics
    if (semantics.pause_behavior === "resume_previous_stage") return "pause"
    if (stage.category === "paused" && semantics.requires_reason_on_enter) return "pause"
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

function buildPresetSemantics(
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
                    pause_behavior:
                        entityType === "egg_donor" || entityType === "sperm_donor"
                            ? "none"
                            : "resume_previous_stage",
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

function getPresetOptions(
    stage: EditableStage,
    entityType: PipelineEntityType,
): Array<{ value: BehaviorPreset; label: string }> {
    if (!stage.is_locked) {
        if (stage.category === "intake") {
            if (entityType === "intended_parent") {
                return [
                    { value: "intake", label: "Intake" },
                    { value: "custom", label: "Custom" },
                ]
            }
            return [
                { value: "intake", label: "Intake" },
                { value: "contacted", label: "Contacted" },
                { value: "custom", label: "Custom" },
            ]
        }
        return [{ value: "custom", label: "Custom" }]
    }
    if (stage.category === "paused") {
        return [
            { value: "pause", label: "Pause" },
            { value: "custom", label: "Custom" },
        ]
    }
    if (stage.category === "terminal") {
        return [
            { value: "terminal_lost", label: "Terminal lost" },
            { value: "terminal_disqualified", label: "Terminal disqualified" },
            { value: "custom", label: "Custom" },
        ]
    }
    if (entityType === "intended_parent" && stage.category === "post_approval") {
        return [
            { value: "match_candidate", label: "Ready to match" },
            { value: "matched", label: "Matched" },
            { value: "delivery", label: "Delivered" },
            { value: "custom", label: "Custom" },
        ]
    }
    if (
        (entityType === "egg_donor" || entityType === "sperm_donor") &&
        stage.category === "post_approval"
    ) {
        return [
            { value: "match_candidate", label: "Available to match" },
            { value: "matched", label: "Matched" },
            { value: "custom", label: "Custom" },
        ]
    }
    if (stage.category === "post_approval") {
        return [
            { value: "match_candidate", label: "Match candidate" },
            { value: "matched", label: "Matched" },
            { value: "pregnancy_milestone", label: "Pregnancy milestone" },
            { value: "delivery", label: "Delivery" },
            { value: "custom", label: "Custom" },
        ]
    }
    if (entityType === "intended_parent") {
        return [
            { value: "intake", label: "Intake" },
            { value: "custom", label: "Custom" },
        ]
    }
    if (entityType === "egg_donor" || entityType === "sperm_donor") {
        return [
            { value: "intake", label: "Intake" },
            { value: "contacted", label: "Contacted" },
            { value: "custom", label: "Custom" },
        ]
    }
    return [
        { value: "intake", label: "Intake" },
        { value: "contacted", label: "Contacted" },
        { value: "custom", label: "Custom" },
    ]
}

function remapStageKeys(values: string[], removedStageKey: string, targetStageKey?: string): string[] {
    const remapped: string[] = []
    for (const value of values) {
        const nextValue = value === removedStageKey ? targetStageKey : value
        if (nextValue) {
            remapped.push(nextValue)
        }
    }
    return Array.from(new Set(remapped))
}

function applyLocalFeatureConfigRemap(
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

function buildNewStage(
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
    const neighborColors = new Set<string>()
    for (const color of [previousStage?.color, nextStage?.color]) {
        if (color) {
            neighborColors.add(color.toLowerCase())
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

function withAutoStageColor(current: EditableStage, next: EditableStage): EditableStage {
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

function buildDuplicateStage(source: EditableStage, draft: PipelineDraftState): EditableStage {
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

function getDefaultStageInsertIndex(stages: EditableStage[]): number {
    for (let index = stages.length - 1; index >= 0; index -= 1) {
        if (!stages[index]?.is_locked) {
            return index + 1
        }
    }
    return Math.max(stages.length - 1, 0)
}

function getDependencyByStageKey(
    dependencyGraph: PipelineDependencyGraph | null | undefined,
    stageKey: string,
) {
    return dependencyGraph?.stages.find((stage) => stage.stage_key === stageKey)
}

function getDeleteRequirements(
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

function getActiveRemapTargetStages(stages: EditableStage[], stageKey: string): EditableStage[] {
    return stages
        .filter((candidate) => candidate.is_active && candidate.stage_key !== stageKey)
        .sort((left, right) => left.order - right.order)
}

function getDefaultRemapTargetStageKey(stages: EditableStage[], stageKey: string): string {
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

function VersionHistory({
    pipeline,
    entityType,
    onRollback,
    canRollback,
}: {
    pipeline: { id: string; current_version: number; created_at: string; updated_at: string }
    entityType: PipelineEntityType
    onRollback: (version: number) => void
    canRollback: boolean
}) {
    const {
        data: versions,
        isLoading,
        isError,
        error,
        refetch,
        isFetching,
    } = usePipelineVersions(pipeline.id, entityType)

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-8" role="status" aria-label="Loading">
                <Loader2Icon className="size-5 animate-spin text-muted-foreground" aria-hidden="true" />
            </div>
        )
    }

    if (isError) {
        return (
            <QueryErrorState
                error={error}
                onRetry={() => void refetch()}
                isRetrying={isFetching}
                title="Couldn't load version history"
                headingLevel={3}
            />
        )
    }

    if (!versions?.length) {
        // Pipelines created before snapshots existed have no stored versions; list the current one.
        const isInitial = pipeline.current_version <= 1
        return (
            <div className="rounded-lg border bg-accent/30 p-3">
                <div className="mb-1 flex items-center gap-2">
                    <Badge className="text-xs">v{pipeline.current_version}</Badge>
                    <span className="text-xs font-medium">{isInitial ? "Initial version" : "Current"}</span>
                </div>
                <p className="text-xs text-muted-foreground">
                    {formatRelativeTime(isInitial ? pipeline.created_at : pipeline.updated_at, "Unknown")}
                </p>
            </div>
        )
    }

    return (
        <div className="space-y-2">
            {versions.map((version, index) => (
                <div
                    key={version.id}
                    className={`rounded-lg border p-3 ${index === 0 ? "bg-accent/30" : ""}`}
                >
                    <div className="mb-1 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Badge variant={index === 0 ? "default" : "outline"} className="text-xs">
                                v{version.version}
                            </Badge>
                            {index === 0 ? (
                                <span className="flex items-center gap-1 text-xs text-success">
                                    <CheckIcon className="size-3" aria-hidden="true" />
                                    Current
                                </span>
                            ) : null}
                        </div>
                        {index > 0 && canRollback ? (
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => onRollback(version.version)}
                                className="h-7 text-xs"
                            >
                                <RotateCcwIcon className="mr-1 size-3" aria-hidden="true" />
                                Restore
                            </Button>
                        ) : null}
                    </div>
                    <p className="text-xs text-muted-foreground">
                        {formatRelativeTime(version.created_at, "Unknown")}
                    </p>
                    {version.comment ? <p className="mt-1 text-xs italic">{version.comment}</p> : null}
                </div>
            ))}
        </div>
    )
}

type StageChangeHandler = (updater: (stage: EditableStage) => EditableStage) => void
type PipelineSelectOption = {
    value: string
    label: string
    disabled?: boolean
}

const EMPTY_SELECT_SENTINEL = "__empty_select_value__"

function normalizeSelectValue(value: string | null | undefined): string {
    return value && value.length > 0 ? value : EMPTY_SELECT_SENTINEL
}

function denormalizeSelectValue(value: string | null | undefined): string {
    return !value || value === EMPTY_SELECT_SENTINEL ? "" : value
}

function getPipelineSelectLabel(options: PipelineSelectOption[], value: string | null, fieldLabel: string): string {
    return getSelectLabel(denormalizeSelectValue(value), options, {
        emptyLabel: options.find((option) => option.value === "")?.label ?? fieldLabel,
        unknownLabel: "Unknown option",
    })
}

function PipelineSelectField({
    id,
    label,
    ariaLabel,
    value,
    options,
    onValueChange,
    disabled = false,
    srOnlyLabel = false,
}: {
    id: string
    label: string
    ariaLabel?: string
    value: string | null | undefined
    options: PipelineSelectOption[]
    onValueChange: (value: string) => void
    disabled?: boolean
    srOnlyLabel?: boolean
}) {
    return (
        <div className={srOnlyLabel ? "text-sm" : "space-y-2 text-sm"}>
            <Label htmlFor={id} className={srOnlyLabel ? "sr-only" : "font-medium"}>
                {label}
            </Label>
            <Select
                value={normalizeSelectValue(value)}
                onValueChange={(nextValue) => onValueChange(denormalizeSelectValue(nextValue))}
                disabled={disabled}
            >
                <SelectTrigger id={id} aria-label={ariaLabel ?? label} className="h-9 w-full">
                    <SelectValue placeholder={label}>
                        {(nextValue: string | null) => getPipelineSelectLabel(options, nextValue, label)}
                    </SelectValue>
                </SelectTrigger>
                <SelectContent>
                    {options.map((option) => (
                        <SelectItem
                            key={normalizeSelectValue(option.value)}
                            value={normalizeSelectValue(option.value)}
                            disabled={option.disabled}
                        >
                            {option.label}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
        </div>
    )
}

function StageDependencyBadges({
    dependency,
    entityType,
}: {
    dependency: PipelineStageDependency
    entityType: PipelineEntityType
}) {
    return (
        <div className="mt-3 flex flex-wrap gap-2">
            {dependency.surrogate_count > 0 ? (
                <Badge variant="outline">
                    {getEntityRecordLabel(entityType, dependency.surrogate_count)}
                </Badge>
            ) : null}
            {entityType === "surrogate" && dependency.journey_milestone_slugs.length > 0 ? (
                <Badge variant="outline">
                    Journey: {dependency.journey_milestone_slugs.join(", ")}
                </Badge>
            ) : null}
            {entityType === "surrogate" && dependency.analytics_funnel ? (
                <Badge variant="outline">Analytics funnel</Badge>
            ) : null}
            {entityType === "surrogate" && dependency.integration_refs.length > 0 ? (
                <Badge variant="outline">
                    Integrations: {dependency.integration_refs.join(", ")}
                </Badge>
            ) : null}
            {dependency.campaign_refs.length > 0 ? (
                <Badge variant="outline">Campaigns: {dependency.campaign_refs.length}</Badge>
            ) : null}
            {dependency.workflow_refs.length > 0 ? (
                <Badge variant="outline">Workflows: {dependency.workflow_refs.length}</Badge>
            ) : null}
        </div>
    )
}

/** Every selectable category plus the stage's current one, so the trigger never renders blank. */
function getStageCategoryOptions(stage: EditableStage): PipelineSelectOption[] {
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

function StageSummaryFields({
    stage,
    index,
    errors,
    isExpanded,
    autoFocusLabel,
    onStageChange,
    onToggleDetails,
    onDuplicateStage,
    onRequestDeleteStage,
}: {
    stage: EditableStage
    index: number
    errors: StageFieldErrors | undefined
    isExpanded: boolean
    autoFocusLabel: boolean
    onStageChange: StageChangeHandler
    onToggleDetails: () => void
    onDuplicateStage: () => void
    onRequestDeleteStage: () => void
}) {
    const labelErrorId = `stage-label-error-${stage.id}`
    const slugErrorId = `stage-slug-error-${stage.id}`
    const focusNewStageLabel = useCallback((node: HTMLInputElement | null) => {
        if (!node) return
        node.scrollIntoView?.({ block: "center" })
        node.focus({ preventScroll: true })
        node.select()
    }, [])

    return (
        <div className="flex flex-col gap-3 md:flex-row md:items-start">
            <div className="flex min-w-0 flex-1 items-start gap-3">
                <div className="flex h-9 shrink-0 items-center gap-3">
                    {stage.is_locked ? (
                        <div className="size-4" aria-hidden="true" />
                    ) : (
                        <GripVerticalIcon
                            className="size-4 cursor-grab text-muted-foreground"
                            aria-hidden="true"
                        />
                    )}
                    <input
                        id={`stage-color-${stage.id}`}
                        name={`stage-color-${stage.id}`}
                        type="color"
                        value={stage.color}
                        disabled={stage.is_locked}
                        onChange={(event) =>
                            onStageChange((current) => ({
                                ...current,
                                color: event.target.value,
                            }))
                        }
                        className="size-9 cursor-pointer rounded border disabled:cursor-not-allowed"
                        aria-label={`Stage ${index + 1} color`}
                    />
                </div>
                <div className="min-w-0 flex-1 space-y-1">
                    <Input
                        id={`stage-label-${stage.id}`}
                        ref={autoFocusLabel ? focusNewStageLabel : undefined}
                        value={stage.label}
                        disabled={stage.is_locked}
                        maxLength={STAGE_LABEL_MAX_LENGTH}
                        onChange={(event) =>
                            onStageChange((current) =>
                                withAutoStageColor(current, {
                                    ...current,
                                    label: event.target.value,
                                }),
                            )
                        }
                        placeholder="Label"
                        aria-label={`Stage ${index + 1} label`}
                        aria-invalid={errors?.label ? true : undefined}
                        aria-describedby={errors?.label ? labelErrorId : undefined}
                        className="h-9"
                    />
                    {errors?.label ? (
                        <p id={labelErrorId} className="text-xs text-destructive">
                            {errors.label}
                        </p>
                    ) : null}
                    <Input
                        value={stage.slug}
                        disabled={stage.is_locked}
                        maxLength={STAGE_SLUG_MAX_LENGTH}
                        onChange={(event) =>
                            onStageChange((current) => {
                                const slug = normalizeIdentifier(event.target.value)
                                return withAutoStageColor(current, {
                                    ...current,
                                    slug,
                                    stage_key: isUuidLike(current.id) ? current.stage_key : slug || current.stage_key,
                                })
                            })
                        }
                        placeholder="slug"
                        aria-label="Stage slug"
                        aria-invalid={errors?.slug ? true : undefined}
                        aria-describedby={errors?.slug ? slugErrorId : undefined}
                        className="h-7 border-transparent bg-transparent px-2 font-mono text-xs text-muted-foreground shadow-none hover:border-input focus-visible:border-ring focus-visible:text-foreground aria-invalid:border-destructive disabled:opacity-100 dark:bg-transparent"
                    />
                    {errors?.slug ? (
                        <p id={slugErrorId} className="text-xs text-destructive">
                            {errors.slug}
                        </p>
                    ) : null}
                </div>
            </div>
            <div className="flex items-center gap-2 md:shrink-0">
                <div className="min-w-0 flex-1 md:w-44 md:flex-none">
                    <PipelineSelectField
                        id={`stage-category-${stage.id}`}
                        label="Stage category"
                        ariaLabel="Stage category"
                        value={stage.category}
                        options={getStageCategoryOptions(stage)}
                        disabled={Boolean(stage.is_locked)}
                        srOnlyLabel
                        onValueChange={(value) =>
                            onStageChange((current) =>
                                withAutoStageColor(current, {
                                    ...current,
                                    category: value as StageType,
                                    stage_type: value as StageType,
                                }),
                            )
                        }
                    />
                </div>
                {/* Below sm the order badge hides (list position shows order) so the category keeps its width. */}
                <div className="grid min-h-9 shrink-0 grid-cols-[92px] items-center justify-end gap-2 overflow-hidden rounded-md border bg-muted/30 px-2 py-1 text-xs sm:grid-cols-[44px_108px]">
                    <div
                        data-testid={`stage-order-slot-${stage.id}`}
                        className="hidden items-center justify-center sm:flex"
                    >
                        <Badge variant="outline" className="shrink-0 tabular-nums">
                            #{index + 1}
                        </Badge>
                    </div>
                    <div
                        data-testid={`stage-action-rail-${stage.id}`}
                        className="grid grid-cols-[28px_28px_28px] items-center justify-items-center gap-1 sm:grid-cols-[32px_32px_32px]"
                    >
                        {stage.is_locked ? (
                            <Badge
                                variant="secondary"
                                className="col-span-2 w-full shrink-0"
                                aria-label="System stage"
                            >
                                Locked
                            </Badge>
                        ) : (
                            <>
                                <Button
                                    type="button"
                                    variant="ghost"
                                    size="icon-sm"
                                    className="size-7 shrink-0 sm:size-8"
                                    onClick={onDuplicateStage}
                                    aria-label={`Duplicate ${stage.label}`}
                                >
                                    <CopyIcon className="size-4" aria-hidden="true" />
                                </Button>
                                <Button
                                    type="button"
                                    variant="ghost"
                                    size="icon-sm"
                                    className="size-7 shrink-0 sm:size-8"
                                    onClick={onRequestDeleteStage}
                                    aria-label={`Remove ${stage.label}`}
                                >
                                    <Trash2Icon className="size-4" aria-hidden="true" />
                                </Button>
                            </>
                        )}
                        <Button
                            type="button"
                            variant="ghost"
                            size="icon-sm"
                            className="col-start-3 size-7 shrink-0 sm:size-8"
                            onClick={onToggleDetails}
                            aria-expanded={isExpanded}
                            aria-controls={`stage-details-${stage.id}`}
                            aria-label={`${isExpanded ? "Hide" : "Edit"} details for ${stage.label}`}
                            title={isExpanded ? "Hide details" : "Edit details"}
                        >
                            {isExpanded ? (
                                <ChevronUpIcon className="size-4" aria-hidden="true" />
                            ) : (
                                <ChevronDownIcon className="size-4" aria-hidden="true" />
                            )}
                        </Button>
                    </div>
                </div>
            </div>
        </div>
    )
}

function StageSemanticsFields({
    entityType,
    stage,
    onStageChange,
}: {
    entityType: PipelineEntityType
    stage: EditableStage
    onStageChange: StageChangeHandler
}) {
    const updateSemantics = (updater: (semantics: StageSemantics) => StageSemantics) => {
        onStageChange((current) => ({
            ...current,
            semantics: updater(current.semantics),
        }))
    }
    const behaviorPresetOptions = getPresetOptions(stage, entityType)
    const integrationBucketOptions: PipelineSelectOption[] = [
        { value: "none", label: "Not tracked" },
        { value: "intake", label: "Intake" },
        { value: "qualified", label: "Qualified" },
        { value: "converted", label: "Converted" },
        { value: "lost", label: "Lost" },
        { value: "not_qualified", label: "Not qualified" },
    ]
    const pauseBehaviorOptions: PipelineSelectOption[] = [
        { value: "none", label: "None" },
        { value: "resume_previous_stage", label: "Resume previous stage" },
    ]
    const terminalOutcomeOptions: PipelineSelectOption[] = [
        { value: "none", label: "None" },
        { value: "lost", label: "Lost" },
        { value: "disqualified", label: "Disqualified" },
    ]
    const suggestionProfileOptions: PipelineSelectOption[] = SUGGESTION_PROFILE_OPTIONS.map((option) => ({
        value: option,
        label: option ? humanizeSelectKey(option) ?? "Unknown profile" : "None",
    }))

    return (
        <div className="grid gap-4 lg:grid-cols-2">
            <PipelineSelectField
                id={`behavior-preset-${stage.id}`}
                label="Behavior preset"
                ariaLabel={`Behavior preset for ${stage.label}`}
                value={getBehaviorPreset(stage, entityType)}
                options={behaviorPresetOptions}
                disabled={Boolean(stage.is_locked)}
                onValueChange={(value) => {
                    const preset = value as BehaviorPreset
                    onStageChange((current) => ({
                        ...current,
                        semantics: buildPresetSemantics(current, preset, entityType),
                    }))
                }}
            />
            {entityType === "surrogate" ? (
                <PipelineSelectField
                    id={`integration-bucket-${stage.id}`}
                    label="Integration bucket"
                    ariaLabel={`Integration bucket for ${stage.label}`}
                    value={stage.semantics.integration_bucket}
                    options={integrationBucketOptions}
                    disabled={Boolean(stage.is_locked)}
                    onValueChange={(value) =>
                        updateSemantics((semantics) => ({
                            ...semantics,
                            integration_bucket: value as StageSemantics["integration_bucket"],
                        }))
                    }
                />
            ) : null}
            <PipelineSelectField
                id={`pause-behavior-${stage.id}`}
                label="Pause behavior"
                ariaLabel={`Pause behavior for ${stage.label}`}
                value={stage.semantics.pause_behavior}
                options={pauseBehaviorOptions}
                disabled
                onValueChange={(value) =>
                    updateSemantics((semantics) => ({
                        ...semantics,
                        pause_behavior: value as StageSemantics["pause_behavior"],
                    }))
                }
            />
            <PipelineSelectField
                id={`terminal-outcome-${stage.id}`}
                label="Terminal outcome"
                ariaLabel={`Terminal outcome for ${stage.label}`}
                value={stage.semantics.terminal_outcome}
                options={terminalOutcomeOptions}
                disabled
                onValueChange={(value) =>
                    updateSemantics((semantics) => ({
                        ...semantics,
                        terminal_outcome: value as StageSemantics["terminal_outcome"],
                    }))
                }
            />
            {entityType === "surrogate" ? (
                <>
                    <PipelineSelectField
                        id={`suggestion-profile-${stage.id}`}
                        label="Suggestion profile"
                        ariaLabel={`Suggestion profile for ${stage.label}`}
                        value={stage.semantics.suggestion_profile_key}
                        options={suggestionProfileOptions}
                        disabled={Boolean(stage.is_locked)}
                        onValueChange={(value) =>
                            updateSemantics((semantics) => ({
                                ...semantics,
                                suggestion_profile_key: value || null,
                            }))
                        }
                    />
                    <label className="space-y-2 text-sm" htmlFor={`analytics-bucket-${stage.id}`}>
                        <span className="font-medium">Analytics bucket</span>
                        <Input
                            id={`analytics-bucket-${stage.id}`}
                            value={stage.semantics.analytics_bucket ?? ""}
                            disabled={stage.is_locked}
                            onChange={(event) =>
                                updateSemantics((semantics) => ({
                                    ...semantics,
                                    analytics_bucket: event.target.value.trim() || null,
                                }))
                            }
                            placeholder="analytics bucket"
                            className="h-9"
                            aria-label={`Analytics bucket for ${stage.label}`}
                        />
                    </label>
                </>
            ) : null}
        </div>
    )
}

function StageCapabilitiesEditor({
    entityType,
    stage,
    onStageChange,
}: {
    entityType: PipelineEntityType
    stage: EditableStage
    onStageChange: StageChangeHandler
}) {
    const updateSemantics = (updater: (semantics: StageSemantics) => StageSemantics) => {
        onStageChange((current) => ({
            ...current,
            semantics: updater(current.semantics),
        }))
    }

    return (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {getVisibleCapabilityLabels(entityType).map((capability) => (
                <label
                    key={capability.key}
                    className="flex items-start gap-3 rounded-lg border bg-muted/20 p-3 text-sm"
                >
                    <Checkbox
                        checked={stage.semantics.capabilities[capability.key]}
                        disabled={stage.is_locked || RESERVED_CAPABILITY_KEYS.has(capability.key)}
                        onCheckedChange={(checked) =>
                            updateSemantics((semantics) => ({
                                ...semantics,
                                capabilities: {
                                    ...semantics.capabilities,
                                    [capability.key]: checked,
                                },
                            }))
                        }
                        aria-label={capability.label}
                        className="mt-1"
                    />
                    <span className="space-y-1">
                        <span className="block font-medium">{capability.label}</span>
                        <span className="block text-xs text-muted-foreground">
                            {capability.description}
                        </span>
                    </span>
                </label>
            ))}
            <label className="flex items-start gap-3 rounded-lg border bg-muted/20 p-3 text-sm">
                <Checkbox
                    checked={stage.semantics.requires_reason_on_enter}
                    disabled={stage.is_locked}
                    onCheckedChange={(checked) =>
                        updateSemantics((semantics) => ({
                            ...semantics,
                            requires_reason_on_enter: checked,
                        }))
                    }
                    aria-label="Require reason on enter"
                    className="mt-1"
                />
                <span className="space-y-1">
                    <span className="block font-medium">Require reason on enter</span>
                    <span className="block text-xs text-muted-foreground">
                        Prompts users for a reason when moving into this stage.
                    </span>
                </span>
            </label>
        </div>
    )
}

function StageDetailsPanel({
    entityType,
    stage,
    onStageChange,
}: {
    entityType: PipelineEntityType
    stage: EditableStage
    onStageChange: StageChangeHandler
}) {
    return (
        <div id={`stage-details-${stage.id}`} className="mt-4 space-y-4">
            {stage.is_locked ? (
                <p className="text-sm text-muted-foreground">
                    Locked because platform workflows depend on it. Existing org-specific label,
                    color, and ordering are frozen as-is.
                </p>
            ) : null}
            <label htmlFor={`stage-key-${stage.id}`} className="space-y-2 text-sm">
                <span className="font-medium">Stage key</span>
                <Input
                    id={`stage-key-${stage.id}`}
                    value={stage.stage_key}
                    readOnly
                    disabled
                    className="h-9 bg-muted font-mono text-xs"
                    title="Stage key is immutable after creation"
                    aria-label="Stage key"
                />
            </label>
            <StageSemanticsFields
                entityType={entityType}
                stage={stage}
                onStageChange={onStageChange}
            />
            <StageCapabilitiesEditor
                entityType={entityType}
                stage={stage}
                onStageChange={onStageChange}
            />
        </div>
    )
}

function StageCard({
    entityType,
    stage,
    index,
    errors,
    dependency,
    isExpanded,
    isDragging,
    autoFocusLabel,
    onStageChange,
    onToggleDetails,
    onDuplicateStage,
    onRequestDeleteStage,
    onDragStart,
    onDragOver,
    onDragEnd,
}: {
    entityType: PipelineEntityType
    stage: EditableStage
    index: number
    errors: StageFieldErrors | undefined
    dependency: PipelineStageDependency | undefined
    isExpanded: boolean
    isDragging: boolean
    autoFocusLabel: boolean
    onStageChange: StageChangeHandler
    onToggleDetails: () => void
    onDuplicateStage: () => void
    onRequestDeleteStage: () => void
    onDragStart: () => void
    onDragOver: (event: React.DragEvent) => void
    onDragEnd: () => void
}) {
    return (
        <div
            draggable={!stage.is_locked}
            onDragStart={() => !stage.is_locked && onDragStart()}
            onDragOver={onDragOver}
            onDragEnd={onDragEnd}
            className={`rounded-xl border bg-card p-4 ${errors ? "border-destructive/50" : ""} ${isDragging ? "opacity-60" : ""}`}
        >
            <StageSummaryFields
                stage={stage}
                index={index}
                errors={errors}
                isExpanded={isExpanded}
                autoFocusLabel={autoFocusLabel}
                onStageChange={onStageChange}
                onToggleDetails={onToggleDetails}
                onDuplicateStage={onDuplicateStage}
                onRequestDeleteStage={onRequestDeleteStage}
            />
            {dependency && isExpanded ? (
                <StageDependencyBadges dependency={dependency} entityType={entityType} />
            ) : null}
            {isExpanded ? (
                <StageDetailsPanel
                    entityType={entityType}
                    stage={stage}
                    onStageChange={onStageChange}
                />
            ) : null}
        </div>
    )
}

function StageEditor({
    entityType,
    stages,
    stageErrors,
    focusStageId,
    dependencyGraph,
    onChange,
    onDuplicateStage,
    onRequestDeleteStage,
}: {
    entityType: PipelineEntityType
    stages: EditableStage[]
    stageErrors: Record<string, StageFieldErrors>
    focusStageId: string | null
    dependencyGraph: PipelineDependencyGraph | null | undefined
    onChange: (stages: EditableStage[]) => void
    onDuplicateStage: (stageKey: string) => void
    onRequestDeleteStage: (stageKey: string) => void
}) {
    const [dragIndex, setDragIndex] = useState<number | null>(null)
    const [expandedStageKeys, setExpandedStageKeys] = useState<Record<string, boolean>>({})

    const updateStage = (index: number, updater: (stage: EditableStage) => EditableStage) => {
        const next = [...stages]
        const current = next[index]
        if (!current) return
        next[index] = updater(current)
        onChange(next.map((stage, currentIndex) => ({ ...stage, order: currentIndex + 1 })))
    }

    const handleDragStart = (index: number) => {
        setDragIndex(index)
    }

    const handleDragOver = (event: React.DragEvent, targetIndex: number) => {
        event.preventDefault()
        if (dragIndex === null || dragIndex === targetIndex) return

        const next = [...stages]
        const [removed] = next.splice(dragIndex, 1)
        if (!removed) return
        next.splice(targetIndex, 0, removed)
        onChange(next.map((stage, index) => ({ ...stage, order: index + 1 })))
        setDragIndex(targetIndex)
    }

    const handleDragEnd = () => {
        setDragIndex(null)
    }

    const toggleStageDetails = (stageKey: string) => {
        setExpandedStageKeys((current) => ({
            ...current,
            [stageKey]: !current[stageKey],
        }))
    }

    return (
        <div className="space-y-4">
            {stages.map((stage, index) => {
                const dependency = getDependencyByStageKey(dependencyGraph, stage.stage_key)
                const isExpanded = expandedStageKeys[stage.stage_key] ?? false
                return (
                    <StageCard
                        key={stage.id}
                        entityType={entityType}
                        stage={stage}
                        index={index}
                        errors={stageErrors[stage.id]}
                        dependency={dependency}
                        isExpanded={isExpanded}
                        isDragging={dragIndex === index}
                        autoFocusLabel={stage.id === focusStageId}
                        onStageChange={(updater) => updateStage(index, updater)}
                        onToggleDetails={() => toggleStageDetails(stage.stage_key)}
                        onDuplicateStage={() => onDuplicateStage(stage.stage_key)}
                        onRequestDeleteStage={() => onRequestDeleteStage(stage.stage_key)}
                        onDragStart={() => handleDragStart(index)}
                        onDragOver={(event) => handleDragOver(event, index)}
                        onDragEnd={handleDragEnd}
                    />
                )
            })}

            <Alert>
                <InfoIcon className="size-4" aria-hidden="true" />
                <AlertDescription>
                    System stages are locked. Custom stages can be inserted between existing stages,
                    stage keys stay immutable, and downstream behaviors resolve from stage
                    semantics and stage key instead of the slug.
                </AlertDescription>
            </Alert>
        </div>
    )
}

function JourneyMilestonesEditor({
    stages,
    featureConfig,
    onChange,
}: {
    stages: EditableStage[]
    featureConfig: PipelineFeatureConfig
    onChange: (featureConfig: PipelineFeatureConfig) => void
}) {
    const [expandedMilestones, setExpandedMilestones] = useState<Record<string, boolean>>({})

    const stageOptions = stages.map((stage) => ({
        stageKey: stage.stage_key,
        label: stage.label,
    }))

    return (
        <div className="space-y-4">
            {featureConfig.journey.milestones.map((milestone, milestoneIndex) => {
                const isExpanded = expandedMilestones[milestone.slug] ?? false
                const mappedStageKeys = new Set(milestone.mapped_stage_keys)
                const mappedLabels: string[] = []
                for (const stage of stageOptions) {
                    if (mappedStageKeys.has(stage.stageKey)) {
                        mappedLabels.push(stage.label)
                    }
                }

                return (
                    <div key={milestone.slug} className="rounded-xl border p-4">
                        <div className="space-y-1">
                            <p className="font-medium">{milestone.label}</p>
                            <p className="text-sm text-muted-foreground">{milestone.description}</p>
                        </div>
                        <div className="mt-3 flex items-center justify-between gap-3">
                            <div className="flex min-w-0 flex-wrap gap-2">
                                <Badge variant="outline">
                                    {milestone.mapped_stage_keys.length} mapped stage
                                    {milestone.mapped_stage_keys.length === 1 ? "" : "s"}
                                </Badge>
                                {mappedLabels.length > 0 ? (
                                    <Badge variant="outline" className="max-w-full">
                                        <span className="truncate">{mappedLabels.slice(0, 2).join(", ")}</span>
                                        {mappedLabels.length > 2 ? <span>+{mappedLabels.length - 2}</span> : null}
                                    </Badge>
                                ) : (
                                    <Badge variant="outline">No stages selected</Badge>
                                )}
                            </div>
                            <div className="shrink-0">
                                <Button
                                    type="button"
                                    variant="ghost"
                                    size="icon-sm"
                                    onClick={() =>
                                        setExpandedMilestones((current) => ({
                                            ...current,
                                            [milestone.slug]: !current[milestone.slug],
                                        }))
                                    }
                                    aria-expanded={isExpanded}
                                    aria-controls={`journey-milestone-${milestone.slug}`}
                                    aria-label={`${isExpanded ? "Hide" : "Edit"} details for ${milestone.label}`}
                                    title={isExpanded ? "Hide details" : "Edit details"}
                                >
                                    {isExpanded ? (
                                        <ChevronUpIcon className="size-4" aria-hidden="true" />
                                    ) : (
                                        <ChevronDownIcon className="size-4" aria-hidden="true" />
                                    )}
                                </Button>
                            </div>
                        </div>
                        {isExpanded ? (
                            <div
                                id={`journey-milestone-${milestone.slug}`}
                                className="mt-3 grid gap-2 md:grid-cols-2"
                            >
                                {stageOptions.map((stage) => {
                                    const checked = milestone.mapped_stage_keys.includes(stage.stageKey)
                                    return (
                                        <label
                                            key={`${milestone.slug}-${stage.stageKey}`}
                                            className="flex items-center gap-3 rounded-md border bg-muted/20 px-3 py-2 text-sm"
                                        >
                                            <Checkbox
                                                checked={checked}
                                                onCheckedChange={(nextChecked) => {
                                                    const next = deepClone(featureConfig)
                                                    const nextMilestone = next.journey.milestones[milestoneIndex]
                                                    if (!nextMilestone) return
                                                    const nextKeys = new Set(nextMilestone.mapped_stage_keys)
                                                    if (nextChecked) {
                                                        nextKeys.add(stage.stageKey)
                                                    } else {
                                                        nextKeys.delete(stage.stageKey)
                                                    }
                                                    nextMilestone.mapped_stage_keys = Array.from(nextKeys)
                                                    onChange(next)
                                                }}
                                                aria-label={`${milestone.label} includes ${stage.label}`}
                                            />
                                            <span>{stage.label}</span>
                                        </label>
                                    )
                                })}
                            </div>
                        ) : null}
                    </div>
                )
            })}
        </div>
    )
}

function AnalyticsFunnelEditor({
    stages,
    featureConfig,
    onChange,
}: {
    stages: EditableStage[]
    featureConfig: PipelineFeatureConfig
    onChange: (featureConfig: PipelineFeatureConfig) => void
}) {
    const [isExpanded, setIsExpanded] = useState(false)
    const funnelStageKeys = new Set(featureConfig.analytics.funnel_stage_keys)
    const activeStages: EditableStage[] = []
    const selectedLabels: string[] = []
    for (const stage of stages) {
        if (!stage.is_active) continue
        activeStages.push(stage)
        if (funnelStageKeys.has(stage.stage_key)) {
            selectedLabels.push(stage.label)
        }
    }

    return (
        <div className="rounded-xl border p-4">
            <div className="flex items-center justify-between gap-3">
                <div className="flex flex-wrap gap-2">
                    <Badge variant="outline">
                        {featureConfig.analytics.funnel_stage_keys.length} funnel stage
                        {featureConfig.analytics.funnel_stage_keys.length === 1 ? "" : "s"}
                    </Badge>
                    {selectedLabels.length > 0 ? (
                        <Badge variant="outline">
                            {selectedLabels.slice(0, 2).join(", ")}
                            {selectedLabels.length > 2 ? ` +${selectedLabels.length - 2}` : ""}
                        </Badge>
                    ) : (
                        <Badge variant="outline">No stages selected</Badge>
                    )}
                </div>
                <div className="shrink-0">
                    <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => setIsExpanded((current) => !current)}
                        aria-expanded={isExpanded}
                        aria-controls="analytics-funnel-details"
                        aria-label={`${isExpanded ? "Hide" : "Edit"} details for analytics funnel`}
                        title={isExpanded ? "Hide details" : "Edit details"}
                    >
                        {isExpanded ? (
                            <ChevronUpIcon className="size-4" aria-hidden="true" />
                        ) : (
                            <ChevronDownIcon className="size-4" aria-hidden="true" />
                        )}
                    </Button>
                </div>
            </div>
            {isExpanded ? (
                <div id="analytics-funnel-details" className="mt-3 grid gap-2 md:grid-cols-2">
                    {activeStages.map((stage) => (
                        <label
                            key={stage.id}
                            className="flex items-center gap-3 rounded-md border bg-muted/20 px-3 py-2 text-sm"
                        >
                            <Checkbox
                                checked={funnelStageKeys.has(stage.stage_key)}
                                onCheckedChange={(checked) => {
                                    const next = deepClone(featureConfig)
                                    const nextKeys = new Set(next.analytics.funnel_stage_keys)
                                    if (checked) {
                                        nextKeys.add(stage.stage_key)
                                    } else {
                                        nextKeys.delete(stage.stage_key)
                                    }
                                    const nextFunnelStageKeys: string[] = []
                                    for (const activeStage of activeStages) {
                                        if (nextKeys.has(activeStage.stage_key)) {
                                            nextFunnelStageKeys.push(activeStage.stage_key)
                                        }
                                    }
                                    next.analytics.funnel_stage_keys = nextFunnelStageKeys
                                    onChange(next)
                                }}
                                aria-label={`Include ${stage.label} in analytics funnel`}
                            />
                            <span>{stage.label}</span>
                        </label>
                    ))}
                </div>
            ) : null}
        </div>
    )
}

function DeleteStageDialog({
    entityType,
    stage,
    stages,
    dependencyGraph,
    open,
    state,
    onOpenChange,
    onStateChange,
    onConfirm,
}: {
    entityType: PipelineEntityType
    stage: EditableStage | undefined
    stages: EditableStage[]
    dependencyGraph: PipelineDependencyGraph | null | undefined
    open: boolean
    state: DeleteStageState | null
    onOpenChange: (open: boolean) => void
    onStateChange: (state: DeleteStageState) => void
    onConfirm: () => void
}) {
    if (!stage || !state) return null
    const dependency = getDependencyByStageKey(dependencyGraph, stage.stage_key)
    const requirements = getDeleteRequirements(dependencyGraph, stage.stage_key, entityType)
    const requiresRemap = requirements.length > 0
    const targetOptions = getActiveRemapTargetStages(stages, stage.stage_key)
    const remapTargetOptions: PipelineSelectOption[] = [
        ...(requiresRemap ? [] : [{ value: "", label: "No remap" }]),
        ...targetOptions.map((targetStage) => ({
            value: targetStage.stage_key,
            label: targetStage.label,
        })),
    ]

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent size="lg">
                <DialogHeader>
                    <DialogTitle>Remove {stage.label}?</DialogTitle>
                    <DialogDescription>
                        Remove this stage from the draft
                        {requiresRemap
                            ? " and remap existing "
                            : " and optionally remap existing "}
                        {entityType === "surrogate" ? "surrogates" : "records"} and connected
                        feature references to another stage.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4">
                    {requirements.length > 0 ? (
                        <Alert>
                            <InfoIcon className="size-4" aria-hidden="true" />
                            <AlertDescription>
                                This stage currently has: {requirements.join(", ")}.
                            </AlertDescription>
                        </Alert>
                    ) : null}
                    {requiresRemap ? (
                        <Alert>
                            <InfoIcon className="size-4" aria-hidden="true" />
                            <AlertDescription>
                                A remap target is required before this stage can be removed.
                            </AlertDescription>
                        </Alert>
                    ) : null}
                    {entityType === "surrogate" && dependency?.journey_milestone_slugs.length ? (
                        <Alert>
                            <InfoIcon className="size-4" aria-hidden="true" />
                            <AlertDescription>
                                Journey references in: {dependency.journey_milestone_slugs.join(", ")}.
                                Saving will remap or clear those draft references automatically.
                            </AlertDescription>
                        </Alert>
                    ) : null}

                    <PipelineSelectField
                        id={`remap-target-${stage.id}`}
                        label="Remap target stage"
                        ariaLabel="Remap target stage"
                        value={state.targetStageKey}
                        options={remapTargetOptions}
                        onValueChange={(value) =>
                            onStateChange({
                                ...state,
                                targetStageKey: value,
                            })
                        }
                    />
                </div>

                <DialogFooter>
                    <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                        Cancel
                    </Button>
                    <Button
                        type="button"
                        onClick={onConfirm}
                        disabled={requiresRemap && !state.targetStageKey}
                    >
                        Confirm Removal
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

function PipelineEditorCard({
    entityType,
    pipelineName,
    isResetPending,
    stages,
    stageErrors,
    focusStageId,
    dependencyGraph,
    onResetToRecommended,
    onStagesChange,
    onAddStage,
    onDuplicateStage,
    onRequestDeleteStage,
}: {
    entityType: PipelineEntityType
    pipelineName: string
    isResetPending: boolean
    stages: EditableStage[]
    stageErrors: Record<string, StageFieldErrors>
    focusStageId: string | null
    dependencyGraph: PipelineDependencyGraph | null
    onResetToRecommended: () => void
    onStagesChange: (stages: EditableStage[]) => void
    onAddStage: () => void
    onDuplicateStage: (stageKey: string) => void
    onRequestDeleteStage: (stageKey: string) => void
}) {
    return (
        <Card>
            <CardHeader>
                <div className="flex flex-wrap items-center justify-between gap-4">
                    <CardTitle className="text-lg">{pipelineName}</CardTitle>
                    <div className="flex flex-wrap gap-2">
                        <Button type="button" onClick={onAddStage}>
                            <PlusIcon className="mr-2 size-4" aria-hidden="true" />
                            Add Custom Stage
                        </Button>
                        <Button
                            type="button"
                            variant="outline"
                            onClick={onResetToRecommended}
                            disabled={isResetPending}
                        >
                            {isResetPending ? (
                                <Loader2Icon className="mr-2 size-4 animate-spin" aria-hidden="true" />
                            ) : (
                                <SparklesIcon className="mr-2 size-4" aria-hidden="true" />
                            )}
                            Reset to Default
                        </Button>
                    </div>
                </div>
            </CardHeader>
            <CardContent>
                <StageEditor
                    entityType={entityType}
                    stages={stages}
                    stageErrors={stageErrors}
                    focusStageId={focusStageId}
                    dependencyGraph={dependencyGraph}
                    onChange={onStagesChange}
                    onDuplicateStage={onDuplicateStage}
                    onRequestDeleteStage={onRequestDeleteStage}
                />
            </CardContent>
        </Card>
    )
}

function SurrogatePipelineSections({
    stages,
    featureConfig,
    onFeatureConfigChange,
}: {
    stages: EditableStage[]
    featureConfig: PipelineFeatureConfig
    onFeatureConfigChange: (featureConfig: PipelineFeatureConfig) => void
}) {
    return (
        <>
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Journey Mapping</CardTitle>
                    <CardDescription>
                        Milestone membership drives the journey timeline, exports, and
                        completion state from live pipeline config.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <JourneyMilestonesEditor
                        stages={stages}
                        featureConfig={featureConfig}
                        onChange={onFeatureConfigChange}
                    />
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Analytics Funnel</CardTitle>
                    <CardDescription>
                        Choose which live stages participate in analytics funnel reporting and
                        preserve the pipeline order in the response.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <AnalyticsFunnelEditor
                        stages={stages}
                        featureConfig={featureConfig}
                        onChange={onFeatureConfigChange}
                    />
                </CardContent>
            </Card>
        </>
    )
}

function ImpactPreviewCard({
    isLoading,
    impactAreas,
    safeAutoFixes,
    requiredRemaps,
    validationErrors,
    blockingIssues,
}: {
    isLoading: boolean
    impactAreas: ImpactArea[]
    safeAutoFixes: string[]
    requiredRemaps: PipelineRequiredRemap[]
    validationErrors: string[]
    blockingIssues: string[]
}) {
    return (
        <Card id={IMPACT_PREVIEW_ID} tabIndex={-1} className="outline-none">
            <CardHeader>
                <CardTitle className="text-base">Impact Preview</CardTitle>
                <CardDescription>
                    Server-validated preview of the pipeline-connected areas that will refresh or
                    change when this draft is saved.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                {isLoading ? (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
                        Refreshing preview
                    </div>
                ) : impactAreas.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                        {impactAreas.map((area) => (
                            <Badge key={area} variant="outline">
                                {IMPACT_LABELS[area]}
                            </Badge>
                        ))}
                    </div>
                ) : (
                    <p className="text-sm text-muted-foreground">No downstream impact detected yet.</p>
                )}

                {safeAutoFixes.length > 0 ? (
                    <Alert>
                        <InfoIcon className="size-4" aria-hidden="true" />
                        <AlertDescription>{safeAutoFixes.join(" ")}</AlertDescription>
                    </Alert>
                ) : null}

                {requiredRemaps.length > 0 ? (
                    <Alert variant="destructive">
                        <TriangleAlertIcon className="size-4" aria-hidden="true" />
                        <AlertDescription>
                            <div className="space-y-2">
                                <p className="font-medium">These removals still need a remap target:</p>
                                <ul className="list-disc space-y-1 pl-5">
                                    {requiredRemaps.map((item) => (
                                        <li key={item.stage_key}>
                                            {item.label}:{" "}
                                            {item.reasons
                                                .map((reason) => REMAP_REASON_LABELS[reason] ?? reason)
                                                .join(", ")}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        </AlertDescription>
                    </Alert>
                ) : null}

                {validationErrors.length > 0 || blockingIssues.length > 0 ? (
                    <Alert variant="destructive">
                        <TriangleAlertIcon className="size-4" aria-hidden="true" />
                        <AlertDescription>
                            <div className="space-y-2">
                                <p className="font-medium">Fix these guarded invariants before saving:</p>
                                <ul className="list-disc space-y-1 pl-5">
                                    {[...validationErrors, ...blockingIssues].map((error) => (
                                        <li key={error}>{error}</li>
                                    ))}
                                </ul>
                            </div>
                        </AlertDescription>
                    </Alert>
                ) : null}
            </CardContent>
        </Card>
    )
}

function PipelineEntityToggle({
    entityType,
    onEntityTypeChange,
}: {
    entityType: PipelineEntityType
    onEntityTypeChange: (entityType: PipelineEntityType) => void
}) {
    return (
        // The explicit viewport cap (not max-w-full) keeps the header actions from growing past a
        // 390px screen; the segments scroll instead.
        <div className="max-w-[calc(100vw-3rem)] overflow-x-auto p-0.5">
            <ToggleGroup
                aria-label="Entity"
                variant="outline"
                spacing={0}
                value={[entityType]}
                onValueChange={(next) => {
                    const nextValue = Array.isArray(next) ? next[0] : next
                    if (isPipelineEntityType(nextValue)) onEntityTypeChange(nextValue)
                }}
            >
                {PIPELINE_ENTITY_OPTIONS.map((option) => (
                    <ToggleGroupItem
                        key={option.value}
                        value={option.value}
                        className="h-9 bg-background text-muted-foreground aria-pressed:bg-muted aria-pressed:text-foreground"
                    >
                        {option.label}
                    </ToggleGroupItem>
                ))}
            </ToggleGroup>
        </div>
    )
}

function VersionHistorySheet({
    open,
    onOpenChange,
    pipeline,
    entityType,
    onRollback,
    canRollback,
}: {
    open: boolean
    onOpenChange: (open: boolean) => void
    pipeline: { id: string; current_version: number; created_at: string; updated_at: string }
    entityType: PipelineEntityType
    onRollback: (version: number) => void
    canRollback: boolean
}) {
    return (
        <Sheet open={open} onOpenChange={onOpenChange}>
            <SheetContent side="right" className="w-full sm:max-w-md">
                <SheetHeader className="border-b pr-14">
                    <SheetTitle>Version history</SheetTitle>
                </SheetHeader>
                {/* The popup mounts only while open, so versions load when the sheet opens. */}
                <div className="flex-1 overflow-y-auto p-6">
                    <VersionHistory
                        pipeline={pipeline}
                        entityType={entityType}
                        onRollback={onRollback}
                        canRollback={canRollback}
                    />
                </div>
            </SheetContent>
        </Sheet>
    )
}

function usePipelineSettingsEditor() {
    const { user } = useAuth()
    const isDeveloper = user?.role === "developer"
    const [entityType, setEntityType] = useState<PipelineEntityType>("surrogate")

    const pipelinesQuery = usePipelines(entityType)
    const { data: pipelines, isLoading: pipelinesLoading } = pipelinesQuery
    const defaultPipeline = pipelines?.find((pipeline) => pipeline.is_default)
    const pipelineQuery = usePipeline(
        defaultPipeline?.id || null,
        entityType,
    )
    const { data: pipeline, isLoading: pipelineLoading } = pipelineQuery
    const loadErrorQuery = pipelinesQuery.isError
        ? pipelinesQuery
        : pipelineQuery.isError
            ? pipelineQuery
            : null
    const [focusStageId, setFocusStageId] = useState<string | null>(null)
    const dependencyGraphQuery = usePipelineDependencyGraph(defaultPipeline?.id || null, entityType)
    const applyDraft = useApplyPipelineDraft()
    const rollbackPipeline = useRollbackPipeline()
    const recommendedDraft = useRecommendedPipelineDraft(defaultPipeline?.id || null, entityType)
    const editorContextKey = `${entityType}:${defaultPipeline?.id ?? "none"}:${pipeline?.current_version ?? 0}`

    const [draftOverride, setDraftOverride] = useState<ScopedEditorState<PipelineDraftState> | null>(null)
    const [deleteStageOverride, setDeleteStageOverride] = useState<ScopedEditorState<DeleteStageState> | null>(null)

    const isLoading = pipelinesLoading || pipelineLoading
    const baselineDraft = buildDraft(pipeline, entityType)
    const scopedDraft = draftOverride?.contextKey === editorContextKey ? draftOverride : null
    const debouncedScopedDraft = useDebouncedValue(scopedDraft, 1200)
    const draft = scopedDraft?.value ?? null
    const debouncedDraft = debouncedScopedDraft?.contextKey === editorContextKey ? debouncedScopedDraft.value : null
    const deleteStageState =
        deleteStageOverride?.contextKey === editorContextKey ? deleteStageOverride.value : null
    const currentDraft = draft ?? baselineDraft
    const baselineDraftFingerprint = baselineDraft ? stringifyDraft(baselineDraft) : null
    const debouncedDraftFingerprint = debouncedDraft ? stringifyDraft(debouncedDraft) : null
    const draftIsDebounced = scopedDraft === debouncedScopedDraft
    const hasChanges = scopedDraft
        ? !draftIsDebounced || debouncedDraftFingerprint !== baselineDraftFingerprint
        : false
    const changeCount = countDraftChanges(baselineDraft, draft)
    const stageErrors = draft ? getDraftStageErrors(draft.stages) : {}
    const stageErrorCount = countStageErrors(stageErrors)
    // Drafts that fail the API's field rules would only return a 422; show inline errors instead.
    const debouncedDraftHasErrors = debouncedDraft
        ? countStageErrors(getDraftStageErrors(debouncedDraft.stages)) > 0
        : false
    const previewDraftPayload = !debouncedDraft
        || debouncedDraftFingerprint === baselineDraftFingerprint
        || debouncedDraftHasErrors
        ? null
        : {
            ...buildApiDraft(debouncedDraft),
            ...(pipeline?.current_version
                ? { expected_version: pipeline.current_version }
                : {}),
        }
    const previewDraftFingerprint = previewDraftPayload ? JSON.stringify(previewDraftPayload) : ""
    const previewQuery = usePipelineChangePreview(
        defaultPipeline?.id || null,
        previewDraftPayload,
        entityType,
        previewDraftFingerprint,
    )
    const preview: PipelineChangePreview | null = previewDraftPayload ? previewQuery.data ?? null : null
    const dependencyGraph = preview?.dependency_graph ?? dependencyGraphQuery.data ?? null

    const currentStages = currentDraft?.stages ?? []
    const currentFeatureConfig = currentDraft?.featureConfig
    const setScopedDraft = (value: PipelineDraftState | null) => {
        setDraftOverride(value ? { contextKey: editorContextKey, value } : null)
    }
    const setScopedDeleteStageState = (value: DeleteStageState | null) => {
        setDeleteStageOverride(value ? { contextKey: editorContextKey, value } : null)
    }

    const updateDraft = (updater: (current: PipelineDraftState) => PipelineDraftState) => {
        setDraftOverride((previous) => {
            const scopedPrevious =
                previous?.contextKey === editorContextKey ? previous.value : null
            const base = scopedPrevious
                ?? baselineDraft
                ?? {
                    name: pipeline?.name ?? "Default Pipeline",
                    stages: [],
                    featureConfig: createFallbackFeatureConfig([]),
                    remaps: [],
                }
            return {
                contextKey: editorContextKey,
                value: updater(deepClone(base)),
            }
        })
    }

    const updateDraftStages = (stages: EditableStage[]) => {
        updateDraft((current) => ({
            ...current,
            stages: stages.map((stage, index) => ({ ...stage, order: index + 1 })),
        }))
    }

    const updateDraftFeatureConfig = (featureConfig: PipelineFeatureConfig) => {
        updateDraft((current) => ({
            ...current,
            featureConfig,
        }))
    }

    const handleAddStage = () => {
        if (!currentDraft) return
        const insertIndex = getDefaultStageInsertIndex(currentDraft.stages)
        const newStage = buildNewStage(currentDraft, entityType, insertIndex)
        updateDraft((current) => {
            const nextStages = [...current.stages]
            nextStages.splice(insertIndex, 0, newStage)
            return {
                ...current,
                stages: nextStages.map((stage, index) => ({ ...stage, order: index + 1 })),
            }
        })
        // The new row's label input scrolls into view and takes focus when it mounts.
        setFocusStageId(newStage.id)
    }

    const handleDuplicateStage = (stageKey: string) => {
        if (!currentDraft) return
        const sourceIndex = currentDraft.stages.findIndex((stage) => stage.stage_key === stageKey)
        const source = currentDraft.stages[sourceIndex]
        if (!source || source.is_locked) return
        updateDraft((current) => {
            const nextStages = [...current.stages]
            nextStages.splice(sourceIndex + 1, 0, buildDuplicateStage(source, current))
            return {
                ...current,
                stages: nextStages.map((stage, index) => ({ ...stage, order: index + 1 })),
            }
        })
    }

    const handleRequestDeleteStage = (stageKey: string) => {
        const stage = currentStages.find((item) => item.stage_key === stageKey)
        if (!stage || stage.is_locked) return
        const requiresRemap = getDeleteRequirements(
            dependencyGraph,
            stageKey,
            entityType,
        ).length > 0
        setScopedDeleteStageState({
            stageKey,
            targetStageKey: requiresRemap
                ? getDefaultRemapTargetStageKey(currentStages, stageKey)
                : "",
        })
    }

    const handleConfirmDeleteStage = () => {
        if (!deleteStageState) return
        const removedStageKey = deleteStageState.stageKey
        const targetStageKey = deleteStageState.targetStageKey || undefined
        updateDraft((current) => {
            const nextStages: EditableStage[] = []
            for (const stage of current.stages) {
                if (stage.stage_key === removedStageKey) continue
                nextStages.push({ ...stage, order: nextStages.length + 1 })
            }

            return {
                ...current,
                stages: nextStages,
                featureConfig: applyLocalFeatureConfigRemap(
                    current.featureConfig,
                    removedStageKey,
                    targetStageKey,
                ),
                remaps: [
                    ...current.remaps.filter((item) => item.removed_stage_key !== removedStageKey),
                    ...(targetStageKey
                        ? [
                              {
                                  removed_stage_key: removedStageKey,
                                  target_stage_key: targetStageKey,
                              },
                          ]
                        : []),
                ],
            }
        })
        setScopedDeleteStageState(null)
    }

    const handleReset = () => {
        setScopedDraft(null)
        setScopedDeleteStageState(null)
    }

    const handleResetToRecommended = async () => {
        if (!pipeline) return
        const { data: recommended } = await recommendedDraft.refetch()
        if (!recommended) return

        const nextDraft = buildDraft(
            {
                name: recommended.name,
                stages: withCurrentLockMetadata(recommended.stages as PipelineStage[], pipeline.stages),
                feature_config: recommended.feature_config,
            },
            entityType,
        )
        if (!nextDraft) return
        nextDraft.remaps = buildRecommendedDraftRemaps(pipeline.stages, nextDraft.stages)
        setScopedDraft(nextDraft)
    }

    const handleSave = async () => {
        if (!pipeline || !currentDraft) return
        if (stageErrorCount > 0) return
        if (previewQuery.isLoading) return
        if (preview && (preview.validation_errors.length > 0 || preview.blocking_issues.length > 0)) {
            return
        }

        try {
            await applyDraft.mutateAsync({
                id: pipeline.id,
                data: {
                    ...buildApiDraft(currentDraft),
                    expected_version: pipeline.current_version,
                    comment: "Applied pipeline draft",
                },
                entityType,
            })
            setScopedDraft(null)
            setScopedDeleteStageState(null)
        } catch {
            // Hook toasts surface the error.
        }
    }

    const handleRollback = async (version: number) => {
        if (!pipeline) return
        try {
            await rollbackPipeline.mutateAsync({ id: pipeline.id, version, entityType })
            setScopedDraft(null)
            setScopedDeleteStageState(null)
        } catch {
            // Hook toasts surface the error.
        }
    }

    const selectedDeleteStage = deleteStageState
        ? currentStages.find((stage) => stage.stage_key === deleteStageState.stageKey)
        : undefined
    const impactAreas = (preview?.impact_areas ?? []) as ImpactArea[]
    const validationErrors = preview?.validation_errors ?? []
    const blockingIssues = preview?.blocking_issues ?? []
    const requiredRemaps = preview?.required_remaps ?? []
    const showSurrogateEditors = entityType === "surrogate"

    return {
        entityType,
        setEntityType,
        isDeveloper,
        isLoading,
        loadErrorQuery,
        pipeline,
        currentStages,
        currentFeatureConfig,
        dependencyGraph,
        deleteStageState,
        selectedDeleteStage,
        impactAreas,
        validationErrors,
        blockingIssues,
        requiredRemaps,
        safeAutoFixes: preview?.safe_auto_fixes ?? [],
        showSurrogateEditors,
        hasChanges,
        changeCount,
        stageErrors,
        stageErrorCount,
        focusStageId,
        isResetPending: recommendedDraft.isFetching,
        isSaving: applyDraft.isPending,
        isPreviewLoading: previewQuery.isLoading,
        setDeleteStageState: setScopedDeleteStageState,
        handleAddStage,
        handleDuplicateStage,
        handleRequestDeleteStage,
        handleConfirmDeleteStage,
        handleDeleteStageDialogOpenChange: (open: boolean) => {
            if (!open) setScopedDeleteStageState(null)
        },
        handleReset,
        handleResetToRecommended,
        handleRollback,
        handleSave,
        updateDraftFeatureConfig,
        updateDraftStages,
    }
}

export default function PipelinesSettingsPage() {
    return (
        <SettingsPageGate
            title="Pipelines"
            permission="manage_pipelines"
            deniedDescription="Pipeline settings need the Manage pipelines permission. Ask an admin to update your role."
        >
            <PipelinesSettingsContent />
        </SettingsPageGate>
    )
}

function PipelinesSettingsContent() {
    const {
        entityType,
        setEntityType,
        isDeveloper,
        isLoading,
        loadErrorQuery,
        pipeline,
        currentStages,
        currentFeatureConfig,
        dependencyGraph,
        deleteStageState,
        selectedDeleteStage,
        impactAreas,
        validationErrors,
        blockingIssues,
        requiredRemaps,
        safeAutoFixes,
        showSurrogateEditors,
        hasChanges,
        changeCount,
        stageErrors,
        stageErrorCount,
        focusStageId,
        isResetPending,
        isSaving,
        isPreviewLoading,
        setDeleteStageState,
        handleAddStage,
        handleDuplicateStage,
        handleRequestDeleteStage,
        handleConfirmDeleteStage,
        handleDeleteStageDialogOpenChange,
        handleReset,
        handleResetToRecommended,
        handleRollback,
        handleSave,
        updateDraftFeatureConfig,
        updateDraftStages,
    } = usePipelineSettingsEditor()
    const [versionHistoryOpen, setVersionHistoryOpen] = useState(false)
    const contentRef = useRef<HTMLDivElement>(null)
    const serverErrorCount = validationErrors.length + blockingIssues.length

    const handleErrorsClick = () => {
        if (focusFirstInvalid(contentRef.current)) return
        const impactPreview = document.getElementById(IMPACT_PREVIEW_ID)
        impactPreview?.scrollIntoView?.({ block: "center" })
        impactPreview?.focus({ preventScroll: true })
    }

    const header = (
        <PageHeader
            title="Pipelines"
            meta={pipeline ? <Badge variant="outline">v{pipeline.current_version}</Badge> : null}
            actions={
                <>
                    <PipelineEntityToggle entityType={entityType} onEntityTypeChange={setEntityType} />
                    <Button
                        type="button"
                        variant="outline"
                        onClick={() => setVersionHistoryOpen(true)}
                        disabled={!pipeline}
                    >
                        <HistoryIcon className="mr-2 size-4" aria-hidden="true" />
                        Version history
                    </Button>
                </>
            }
        />
    )

    if (isLoading || loadErrorQuery || !pipeline) {
        return (
            <div className="flex flex-1 flex-col">
                {header}
                <div className="p-6">
                    {isLoading ? (
                        <div className="flex items-center justify-center p-6" role="status" aria-label="Loading">
                            <Loader2Icon className="size-8 animate-spin text-muted-foreground" aria-hidden="true" />
                        </div>
                    ) : loadErrorQuery ? (
                        <QueryErrorState
                            error={loadErrorQuery.error}
                            onRetry={() => void loadErrorQuery.refetch()}
                            isRetrying={loadErrorQuery.isFetching}
                            title="Couldn't load the pipeline"
                            headingLevel={2}
                        />
                    ) : (
                        <EmptyState icon={WorkflowIcon} title="No default pipeline" headingLevel={2} />
                    )}
                </div>
            </div>
        )
    }

    return (
        <div className="flex flex-1 flex-col">
            {header}
            <div ref={contentRef} className="flex flex-1 flex-col gap-6 p-6">
                <PipelineEditorCard
                    entityType={entityType}
                    pipelineName={pipeline.name || "Default Pipeline"}
                    isResetPending={isResetPending}
                    stages={currentStages}
                    stageErrors={stageErrors}
                    focusStageId={focusStageId}
                    dependencyGraph={dependencyGraph}
                    onResetToRecommended={handleResetToRecommended}
                    onStagesChange={updateDraftStages}
                    onAddStage={handleAddStage}
                    onDuplicateStage={handleDuplicateStage}
                    onRequestDeleteStage={handleRequestDeleteStage}
                />

                {showSurrogateEditors && currentFeatureConfig ? (
                    <SurrogatePipelineSections
                        stages={currentStages}
                        featureConfig={currentFeatureConfig}
                        onFeatureConfigChange={updateDraftFeatureConfig}
                    />
                ) : null}

                {hasChanges ? (
                    <ImpactPreviewCard
                        isLoading={isPreviewLoading}
                        impactAreas={impactAreas}
                        safeAutoFixes={safeAutoFixes}
                        requiredRemaps={requiredRemaps}
                        validationErrors={validationErrors}
                        blockingIssues={blockingIssues}
                    />
                ) : null}
            </div>

            <DeleteStageDialog
                entityType={entityType}
                stage={selectedDeleteStage}
                stages={currentStages}
                dependencyGraph={dependencyGraph}
                open={Boolean(deleteStageState)}
                state={deleteStageState}
                onOpenChange={handleDeleteStageDialogOpenChange}
                onStateChange={setDeleteStageState}
                onConfirm={handleConfirmDeleteStage}
            />

            <VersionHistorySheet
                open={versionHistoryOpen}
                onOpenChange={setVersionHistoryOpen}
                pipeline={pipeline}
                entityType={entityType}
                onRollback={handleRollback}
                canRollback={isDeveloper}
            />

            <SaveBar
                dirty={changeCount > 0}
                changeCount={changeCount}
                errorCount={stageErrorCount + serverErrorCount}
                onErrorsClick={handleErrorsClick}
                saving={isSaving}
                saveDisabled={isPreviewLoading}
                onSave={() => void handleSave()}
                onDiscard={handleReset}
            />
        </div>
    )
}
