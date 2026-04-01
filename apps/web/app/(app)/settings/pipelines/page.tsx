"use client"

import { useEffect, useMemo, useState } from "react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
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
    SaveIcon,
    SparklesIcon,
    TriangleAlertIcon,
    Trash2Icon,
} from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { formatRelativeTime } from "@/lib/formatters"
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value"
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
    description: string
}> = [
    {
        value: "surrogate",
        label: "Surrogates",
        description: "Full journey, analytics, and role-aware pipeline configuration.",
    },
    {
        value: "intended_parent",
        label: "Intended Parents",
        description: "Stage behavior and matching semantics for intended parents.",
    },
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
    return CAPABILITY_LABELS
}

function getEntityRecordLabel(entityType: PipelineEntityType, count: number) {
    if (entityType === "intended_parent") {
        return `${count} active record${count === 1 ? "" : "s"}`
    }
    return `${count} active surrogate${count === 1 ? "" : "s"}`
}

function getEntityLabel(entityType: string | null | undefined) {
    return PIPELINE_ENTITY_OPTIONS.find((option) => option.value === entityType)?.label ?? "Select entity"
}

function getEntityDescription(entityType: PipelineEntityType) {
    return PIPELINE_ENTITY_OPTIONS.find((option) => option.value === entityType)?.description
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
    return {
        ...base,
        ...stage?.semantics,
        capabilities: {
            ...base.capabilities,
            ...(stage?.semantics?.capabilities ?? {}),
        },
    }
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

function getBehaviorPreset(
    stage: EditableStage,
    entityType: PipelineEntityType,
): BehaviorPreset {
    const semantics = stage.semantics
    if (semantics.pause_behavior === "resume_previous_stage") return "pause"
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

    if (entityType === "intended_parent") {
        switch (preset) {
            case "intake":
                return reset
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
                    pause_behavior: "resume_previous_stage",
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
    return [
        { value: "intake", label: "Intake" },
        { value: "contacted", label: "Contacted" },
        { value: "custom", label: "Custom" },
    ]
}

function remapStageKeys(values: string[], removedStageKey: string, targetStageKey?: string): string[] {
    const replaced = values
        .map((value) => (value === removedStageKey ? targetStageKey ?? null : value))
        .filter((value): value is string => Boolean(value))
    return Array.from(new Set(replaced))
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
    const base: EditableStage = {
        id: createLocalId(),
        stage_key: stageKey,
        slug,
        label: "New Stage",
        color: "#6B7280",
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

function VersionHistory({
    pipelineId,
    entityType,
    onRollback,
    canRollback,
}: {
    pipelineId: string
    entityType: PipelineEntityType
    onRollback: (version: number) => void
    canRollback: boolean
}) {
    const { data: versions, isLoading, isError } = usePipelineVersions(pipelineId, entityType)

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-8">
                <Loader2Icon className="size-5 animate-spin text-muted-foreground" aria-hidden="true" />
            </div>
        )
    }

    if (isError) {
        return (
            <div className="py-8 text-center text-sm text-muted-foreground">
                Version history requires Developer role
            </div>
        )
    }

    if (!versions?.length) {
        return <div className="py-8 text-center text-sm text-muted-foreground">No version history</div>
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
                                <span className="flex items-center gap-1 text-xs text-green-600">
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
}

const EMPTY_SELECT_SENTINEL = "__empty_select_value__"

function normalizeSelectValue(value: string | null | undefined): string {
    return value && value.length > 0 ? value : EMPTY_SELECT_SENTINEL
}

function denormalizeSelectValue(value: string | null | undefined): string {
    return !value || value === EMPTY_SELECT_SENTINEL ? "" : value
}

function getSelectOptionLabel(options: PipelineSelectOption[], value: string | null): string {
    const normalizedValue = normalizeSelectValue(value)
    return (
        options.find((option) => normalizeSelectValue(option.value) === normalizedValue)?.label
        ?? ""
    )
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
        <div className="space-y-2 text-sm">
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
                        {(nextValue: string | null) => getSelectOptionLabel(options, nextValue)}
                    </SelectValue>
                </SelectTrigger>
                <SelectContent>
                    {options.map((option) => (
                        <SelectItem
                            key={normalizeSelectValue(option.value)}
                            value={normalizeSelectValue(option.value)}
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

function StageSummaryFields({
    stage,
    index,
    isExpanded,
    onStageChange,
    onToggleDetails,
    onDuplicateStage,
    onRequestDeleteStage,
}: {
    stage: EditableStage
    index: number
    isExpanded: boolean
    onStageChange: StageChangeHandler
    onToggleDetails: () => void
    onDuplicateStage: () => void
    onRequestDeleteStage: () => void
}) {
    const stageCategoryOptions = (stage.is_locked ? STAGE_CATEGORIES : CUSTOM_STAGE_CATEGORIES).map(
        (category) => ({
            value: category,
            label: category.replaceAll("_", " "),
        }),
    )

    return (
        <div className="grid flex-1 gap-3 lg:grid-cols-[minmax(0,1.8fr)_minmax(0,1.1fr)_152px_168px]">
            <Input
                value={stage.label}
                disabled={stage.is_locked}
                onChange={(event) =>
                    onStageChange((current) => ({
                        ...current,
                        label: event.target.value,
                    }))
                }
                placeholder="Label"
                className="h-9 truncate"
            />
            <Input
                value={stage.slug}
                disabled={stage.is_locked}
                onChange={(event) =>
                    onStageChange((current) => {
                        const slug = normalizeIdentifier(event.target.value)
                        return {
                            ...current,
                            slug,
                            stage_key: isUuidLike(current.id) ? current.stage_key : slug || current.stage_key,
                        }
                    })
                }
                className="h-9 truncate font-mono text-sm"
                aria-label="Stage slug"
            />
            <PipelineSelectField
                id={`stage-category-${stage.id}`}
                label="Stage category"
                ariaLabel="Stage category"
                value={stage.category}
                options={stageCategoryOptions}
                disabled={Boolean(stage.is_locked)}
                srOnlyLabel
                onValueChange={(value) =>
                    onStageChange((current) => ({
                        ...current,
                        category: value as StageType,
                        stage_type: value as StageType,
                    }))
                }
            />
            <div className="flex min-h-9 w-full items-center justify-center overflow-hidden rounded-md border bg-muted/30 px-2 py-1 text-xs">
                <div className="flex min-w-0 items-center justify-center gap-1">
                    <Badge variant="outline" className="shrink-0 tabular-nums">
                        #{index + 1}
                    </Badge>
                    {stage.is_locked ? (
                        <Badge variant="secondary" className="shrink-0" aria-label="System stage">
                            Locked
                        </Badge>
                    ) : null}
                    <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        className="size-7 shrink-0 sm:size-8"
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
                    {!stage.is_locked ? (
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
                    ) : null}
                    {!stage.is_locked ? (
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
                    ) : null}
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
        label: option || "None",
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
                    <input
                        type="checkbox"
                        checked={stage.semantics.capabilities[capability.key]}
                        disabled={stage.is_locked || RESERVED_CAPABILITY_KEYS.has(capability.key)}
                        onChange={(event) =>
                            updateSemantics((semantics) => ({
                                ...semantics,
                                capabilities: {
                                    ...semantics.capabilities,
                                    [capability.key]: event.target.checked,
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
                <input
                    type="checkbox"
                    checked={stage.semantics.requires_reason_on_enter}
                    disabled={stage.is_locked}
                    onChange={(event) =>
                        updateSemantics((semantics) => ({
                            ...semantics,
                            requires_reason_on_enter: event.target.checked,
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
    dependency,
    isExpanded,
    isDragging,
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
    dependency: PipelineStageDependency | undefined
    isExpanded: boolean
    isDragging: boolean
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
            className={`rounded-xl border bg-card p-4 ${isDragging ? "opacity-60" : ""}`}
        >
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
                <div className="flex items-center gap-3">
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
                        className="h-9 w-9 cursor-pointer rounded border disabled:cursor-not-allowed"
                        aria-label={`Stage ${index + 1} color`}
                    />
                </div>
                <StageSummaryFields
                    stage={stage}
                    index={index}
                    isExpanded={isExpanded}
                    onStageChange={onStageChange}
                    onToggleDetails={onToggleDetails}
                    onDuplicateStage={onDuplicateStage}
                    onRequestDeleteStage={onRequestDeleteStage}
                />
            </div>
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
    dependencyGraph,
    onChange,
    onDuplicateStage,
    onRequestDeleteStage,
}: {
    entityType: PipelineEntityType
    stages: EditableStage[]
    dependencyGraph: PipelineDependencyGraph | null | undefined
    onChange: (stages: EditableStage[]) => void
    onDuplicateStage: (stageKey: string) => void
    onRequestDeleteStage: (stageKey: string) => void
}) {
    const [dragIndex, setDragIndex] = useState<number | null>(null)
    const [expandedStageIds, setExpandedStageIds] = useState<Record<string, boolean>>({})

    useEffect(() => {
        setExpandedStageIds((current) => {
            const next: Record<string, boolean> = {}
            for (const stage of stages) {
                next[stage.id] = current[stage.id] ?? false
            }
            return next
        })
    }, [stages])

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

    const toggleStageDetails = (stageId: string) => {
        setExpandedStageIds((current) => ({
            ...current,
            [stageId]: !current[stageId],
        }))
    }

    return (
        <div className="space-y-4">
            {stages.map((stage, index) => {
                const dependency = getDependencyByStageKey(dependencyGraph, stage.stage_key)
                const isExpanded = expandedStageIds[stage.id] ?? false
                return (
                    <StageCard
                        key={stage.id}
                        entityType={entityType}
                        stage={stage}
                        index={index}
                        dependency={dependency}
                        isExpanded={isExpanded}
                        isDragging={dragIndex === index}
                        onStageChange={(updater) => updateStage(index, updater)}
                        onToggleDetails={() => toggleStageDetails(stage.id)}
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

    useEffect(() => {
        setExpandedMilestones((current) => {
            const next: Record<string, boolean> = {}
            for (const milestone of featureConfig.journey.milestones) {
                next[milestone.slug] = current[milestone.slug] ?? false
            }
            return next
        })
    }, [featureConfig.journey.milestones])

    const stageOptions = stages.map((stage) => ({
        stageKey: stage.stage_key,
        label: stage.label,
    }))

    return (
        <div className="space-y-4">
            {featureConfig.journey.milestones.map((milestone, milestoneIndex) => {
                const isExpanded = expandedMilestones[milestone.slug] ?? false
                const mappedLabels = stageOptions
                    .filter((stage) => milestone.mapped_stage_keys.includes(stage.stageKey))
                    .map((stage) => stage.label)

                return (
                    <div key={milestone.slug} className="rounded-xl border p-4">
                        <div className="space-y-1">
                            <p className="font-medium">{milestone.label}</p>
                            <p className="text-sm text-muted-foreground">{milestone.description}</p>
                        </div>
                        <div className="mt-3 flex items-center justify-between gap-3">
                            <div className="flex flex-wrap gap-2">
                                <Badge variant="outline">
                                    {milestone.mapped_stage_keys.length} mapped stage
                                    {milestone.mapped_stage_keys.length === 1 ? "" : "s"}
                                </Badge>
                                {mappedLabels.length > 0 ? (
                                    <Badge variant="outline">
                                        {mappedLabels.slice(0, 2).join(", ")}
                                        {mappedLabels.length > 2 ? ` +${mappedLabels.length - 2}` : ""}
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
                                            <input
                                                type="checkbox"
                                                checked={checked}
                                                onChange={(event) => {
                                                    const next = deepClone(featureConfig)
                                                    const nextMilestone = next.journey.milestones[milestoneIndex]
                                                    if (!nextMilestone) return
                                                    const nextKeys = new Set(nextMilestone.mapped_stage_keys)
                                                    if (event.target.checked) {
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
    const activeStages = stages.filter((stage) => stage.is_active)
    const funnelStageKeys = new Set(featureConfig.analytics.funnel_stage_keys)
    const selectedLabels = activeStages
        .filter((stage) => funnelStageKeys.has(stage.stage_key))
        .map((stage) => stage.label)

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
                            <input
                                type="checkbox"
                                checked={funnelStageKeys.has(stage.stage_key)}
                                onChange={(event) => {
                                    const next = deepClone(featureConfig)
                                    const nextKeys = new Set(next.analytics.funnel_stage_keys)
                                    if (event.target.checked) {
                                        nextKeys.add(stage.stage_key)
                                    } else {
                                        nextKeys.delete(stage.stage_key)
                                    }
                                    next.analytics.funnel_stage_keys = activeStages
                                        .map((activeStage) => activeStage.stage_key)
                                        .filter((stageKey) => nextKeys.has(stageKey))
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
    const targetOptions = stages.filter((candidate) => candidate.stage_key !== stage.stage_key)
    const remapTargetOptions: PipelineSelectOption[] = [
        { value: "", label: "No remap" },
        ...targetOptions.map((targetStage) => ({
            value: targetStage.stage_key,
            label: targetStage.label,
        })),
    ]

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-lg">
                <DialogHeader>
                    <DialogTitle>Remove {stage.label}?</DialogTitle>
                    <DialogDescription>
                        Remove this stage from the draft and optionally remap existing{" "}
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
                    <Button type="button" onClick={onConfirm}>
                        Confirm Removal
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

function PipelinePageIntro({ showSurrogateEditors }: { showSurrogateEditors: boolean }) {
    return (
        <div className="max-w-3xl">
            <h1 className="text-2xl font-semibold">Pipeline Settings</h1>
            <p className="text-sm text-muted-foreground">
                {showSurrogateEditors
                    ? "Configure per-org stage identity, category, behavior, journey mappings, and analytics funnel from one versioned draft."
                    : "Configure intended-parent stage identity, category, and stage semantics from one versioned draft."}
            </p>
        </div>
    )
}

function PipelineEditorCard({
    entityType,
    pipelineName,
    pipelineVersion,
    entityLabel,
    showSurrogateEditors,
    hasChanges,
    isResetPending,
    stages,
    dependencyGraph,
    onResetToRecommended,
    onStagesChange,
    onAddStage,
    onDuplicateStage,
    onRequestDeleteStage,
}: {
    entityType: PipelineEntityType
    pipelineName: string
    pipelineVersion: number
    entityLabel: string
    showSurrogateEditors: boolean
    hasChanges: boolean
    isResetPending: boolean
    stages: EditableStage[]
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
                <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="space-y-2">
                        <CardTitle className="flex items-center gap-2 text-lg">
                            {pipelineName}
                            <Badge variant="outline">v{pipelineVersion}</Badge>
                            {entityLabel ? <Badge variant="secondary">{entityLabel}</Badge> : null}
                        </CardTitle>
                        <CardDescription>
                            {showSurrogateEditors
                                ? "Stage keys are immutable. Slugs, category, order, and semantics stay org-configurable, and downstream features refresh from the pipeline snapshot."
                                : "Stage keys are immutable. Slugs, category, order, and stage semantics stay org-configurable, and downstream match and campaign behavior refresh from the pipeline snapshot."}
                        </CardDescription>
                    </div>
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
                        {hasChanges ? (
                            <Badge variant="secondary" className="bg-amber-100 text-amber-700">
                                Unsaved changes
                            </Badge>
                        ) : null}
                    </div>
                </div>
            </CardHeader>
            <CardContent>
                <StageEditor
                    entityType={entityType}
                    stages={stages}
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
        <Card>
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
                        Refreshing preview...
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

function DraftActionsCard({
    isSaving,
    isPreviewLoading,
    hasValidationErrors,
    hasBlockingIssues,
    onSave,
    onDiscard,
}: {
    isSaving: boolean
    isPreviewLoading: boolean
    hasValidationErrors: boolean
    hasBlockingIssues: boolean
    onSave: () => void
    onDiscard: () => void
}) {
    return (
        <Card>
            <CardContent className="pt-6">
                <div className="flex flex-col gap-3 sm:flex-row">
                    <Button
                        onClick={onSave}
                        disabled={isPreviewLoading || hasValidationErrors || hasBlockingIssues || isSaving}
                        className="flex-1"
                    >
                        {isSaving ? (
                            <Loader2Icon className="mr-2 size-4 animate-spin" aria-hidden="true" />
                        ) : (
                            <SaveIcon className="mr-2 size-4" aria-hidden="true" />
                        )}
                        Save Changes
                    </Button>
                    <Button variant="outline" onClick={onDiscard}>
                        Discard
                    </Button>
                </div>
            </CardContent>
        </Card>
    )
}

function PipelineSidebar({
    entityType,
    onEntityTypeChange,
    pipelineId,
    onRollback,
    canRollback,
}: {
    entityType: PipelineEntityType
    onEntityTypeChange: (entityType: PipelineEntityType) => void
    pipelineId: string | null
    onRollback: (version: number) => void
    canRollback: boolean
}) {
    const entityDescription = getEntityDescription(entityType)

    return (
        <div className="space-y-6" data-testid="pipelines-sidebar">
            <div className="space-y-2">
                <Label htmlFor="pipeline-entity">Entity</Label>
                <Select value={entityType} onValueChange={(value) => value && onEntityTypeChange(value as PipelineEntityType)}>
                    <SelectTrigger id="pipeline-entity" className="w-full">
                        <SelectValue placeholder="Select entity">
                            {(value: string | null) => getEntityLabel(value)}
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        {PIPELINE_ENTITY_OPTIONS.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                                {option.label}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                {entityDescription ? (
                    <p className="text-xs text-muted-foreground">{entityDescription}</p>
                ) : null}
            </div>

            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-base">
                        <HistoryIcon className="size-4" aria-hidden="true" />
                        Version History
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {pipelineId ? (
                        <VersionHistory
                            pipelineId={pipelineId}
                            entityType={entityType}
                            onRollback={onRollback}
                            canRollback={canRollback}
                        />
                    ) : null}
                </CardContent>
            </Card>
        </div>
    )
}

function usePipelineSettingsEditor() {
    const { user } = useAuth()
    const isDeveloper = user?.role === "developer"
    const [entityType, setEntityType] = useState<PipelineEntityType>("surrogate")

    const { data: pipelines, isLoading: pipelinesLoading } = usePipelines(entityType)
    const defaultPipeline = pipelines?.find((pipeline) => pipeline.is_default)
    const { data: pipeline, isLoading: pipelineLoading } = usePipeline(
        defaultPipeline?.id || null,
        entityType,
    )
    const dependencyGraphQuery = usePipelineDependencyGraph(defaultPipeline?.id || null, entityType)
    const applyDraft = useApplyPipelineDraft()
    const rollbackPipeline = useRollbackPipeline()
    const recommendedDraft = useRecommendedPipelineDraft()
    const editorContextKey = `${entityType}:${defaultPipeline?.id ?? "none"}:${pipeline?.current_version ?? 0}`

    const [draftOverride, setDraftOverride] = useState<ScopedEditorState<PipelineDraftState> | null>(null)
    const [deleteStageOverride, setDeleteStageOverride] = useState<ScopedEditorState<DeleteStageState> | null>(null)

    const isLoading = pipelinesLoading || pipelineLoading
    const baselineDraft = useMemo(() => buildDraft(pipeline, entityType), [entityType, pipeline])
    const scopedDraft = draftOverride?.contextKey === editorContextKey ? draftOverride : null
    const debouncedScopedDraft = useDebouncedValue(scopedDraft, 1200)
    const draft = scopedDraft?.value ?? null
    const debouncedDraft = debouncedScopedDraft?.contextKey === editorContextKey ? debouncedScopedDraft.value : null
    const deleteStageState =
        deleteStageOverride?.contextKey === editorContextKey ? deleteStageOverride.value : null
    const currentDraft = draft ?? baselineDraft
    const baselineDraftFingerprint = useMemo(
        () => (baselineDraft ? stringifyDraft(baselineDraft) : null),
        [baselineDraft],
    )
    const debouncedDraftFingerprint = useMemo(
        () => (debouncedDraft ? stringifyDraft(debouncedDraft) : null),
        [debouncedDraft],
    )
    const draftIsDebounced = scopedDraft === debouncedScopedDraft
    const hasChanges = useMemo(() => {
        if (!scopedDraft) return false
        if (!draftIsDebounced) return true
        return debouncedDraftFingerprint !== baselineDraftFingerprint
    }, [baselineDraftFingerprint, debouncedDraftFingerprint, draftIsDebounced, scopedDraft])
    const previewDraftPayload = useMemo(() => {
        if (!debouncedDraft || debouncedDraftFingerprint === baselineDraftFingerprint) return null
        return {
            ...buildApiDraft(debouncedDraft),
            ...(pipeline?.current_version
                ? { expected_version: pipeline.current_version }
                : {}),
        }
    }, [baselineDraftFingerprint, debouncedDraft, debouncedDraftFingerprint, pipeline?.current_version])
    const previewDraftFingerprint = useMemo(
        () => (previewDraftPayload ? JSON.stringify(previewDraftPayload) : ""),
        [previewDraftPayload],
    )
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
        updateDraft((current) => {
            const insertIndex = getDefaultStageInsertIndex(current.stages)
            const nextStages = [...current.stages]
            nextStages.splice(insertIndex, 0, buildNewStage(current, entityType, insertIndex))
            return {
                ...current,
                stages: nextStages.map((stage, index) => ({ ...stage, order: index + 1 })),
            }
        })
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
        setScopedDeleteStageState({ stageKey, targetStageKey: "" })
    }

    const handleConfirmDeleteStage = () => {
        if (!deleteStageState) return
        const removedStageKey = deleteStageState.stageKey
        const targetStageKey = deleteStageState.targetStageKey || undefined
        updateDraft((current) => ({
            ...current,
            stages: current.stages
                .filter((stage) => stage.stage_key !== removedStageKey)
                .map((stage, index) => ({ ...stage, order: index + 1 })),
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
        }))
        setScopedDeleteStageState(null)
    }

    const handleReset = () => {
        setScopedDraft(null)
        setScopedDeleteStageState(null)
    }

    const handleResetToRecommended = async () => {
        if (!pipeline) return
        try {
            const recommended = await recommendedDraft.mutateAsync({
                id: pipeline.id,
                entityType,
            })
            const nextDraft = buildDraft(
                {
                    name: recommended.name,
                    stages: recommended.stages as PipelineStage[],
                    feature_config: recommended.feature_config,
                },
                entityType,
            )
            if (!nextDraft) return
            nextDraft.remaps = buildRecommendedDraftRemaps(pipeline.stages, nextDraft.stages)
            setScopedDraft(nextDraft)
        } catch {
            // Hook toasts surface the error.
        }
    }

    const handleSave = async () => {
        if (!pipeline || !currentDraft) return
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
    const entityLabel = getEntityLabel(entityType)
    const showSurrogateEditors = entityType === "surrogate"

    return {
        entityType,
        setEntityType,
        isDeveloper,
        isLoading,
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
        entityLabel,
        showSurrogateEditors,
        hasChanges,
        isResetPending: recommendedDraft.isPending,
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
    const {
        entityType,
        setEntityType,
        isDeveloper,
        isLoading,
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
        entityLabel,
        showSurrogateEditors,
        hasChanges,
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

    if (isLoading) {
        return (
            <div className="flex flex-1 items-center justify-center p-6">
                <Loader2Icon className="size-8 animate-spin text-muted-foreground" aria-hidden="true" />
            </div>
        )
    }

    return (
        <div className="mx-auto flex max-w-6xl flex-1 flex-col gap-6 p-6">
            <PipelinePageIntro showSurrogateEditors={showSurrogateEditors} />

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

            <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
                <div className="space-y-6">
                    <PipelineEditorCard
                        entityType={entityType}
                        pipelineName={pipeline?.name || "Default Pipeline"}
                        pipelineVersion={pipeline?.current_version || 1}
                        entityLabel={entityLabel}
                        showSurrogateEditors={showSurrogateEditors}
                        hasChanges={hasChanges}
                        isResetPending={isResetPending}
                        stages={currentStages}
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

                    {hasChanges ? (
                        <DraftActionsCard
                            isSaving={isSaving}
                            isPreviewLoading={isPreviewLoading}
                            hasValidationErrors={validationErrors.length > 0}
                            hasBlockingIssues={blockingIssues.length > 0}
                            onSave={handleSave}
                            onDiscard={handleReset}
                        />
                    ) : null}
                </div>

                <PipelineSidebar
                    entityType={entityType}
                    onEntityTypeChange={setEntityType}
                    pipelineId={pipeline?.id ?? null}
                    onRollback={handleRollback}
                    canRollback={isDeveloper}
                />
            </div>
        </div>
    )
}
