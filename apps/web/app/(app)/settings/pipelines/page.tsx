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
import type {
    PipelineChangePreview,
    PipelineDependencyGraph,
    PipelineDraft,
    PipelineEntityType,
    PipelineFeatureConfig,
    PipelineRequiredRemap,
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
    return JSON.parse(JSON.stringify(value)) as T
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
        category,
        stage_type: category,
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
): EditableStage {
    const existingKeys = new Set(draft.stages.map((stage) => stage.stage_key))
    const existingSlugs = new Set(draft.stages.map((stage) => stage.slug))
    const stageKey = ensureUniqueIdentifier("custom_stage", existingKeys)
    const slug = ensureUniqueIdentifier(stageKey, existingSlugs)
    const base: EditableStage = {
        id: createLocalId(),
        stage_key: stageKey,
        slug,
        label: "New Stage",
        color: "#6B7280",
        order: draft.stages.length + 1,
        category: "intake",
        stage_type: "intake",
        is_active: true,
        semantics: getStageSemanticsForEntity(entityType, {
            stage_key: stageKey,
            slug,
            stage_type: "intake",
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
    }
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

function StageEditor({
    entityType,
    stages,
    dependencyGraph,
    onChange,
    onAddStage,
    onDuplicateStage,
    onRequestDeleteStage,
}: {
    entityType: PipelineEntityType
    stages: EditableStage[]
    dependencyGraph: PipelineDependencyGraph | null | undefined
    onChange: (stages: EditableStage[]) => void
    onAddStage: () => void
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
            <div className="flex flex-wrap gap-3">
                <Button type="button" variant="outline" onClick={onAddStage}>
                    <PlusIcon className="mr-2 size-4" aria-hidden="true" />
                    Add Stage
                </Button>
            </div>

            {stages.map((stage, index) => {
                const dependency = getDependencyByStageKey(dependencyGraph, stage.stage_key)
                const isExpanded = expandedStageIds[stage.id] ?? false
                return (
                    <div
                        key={stage.id}
                        draggable
                        onDragStart={() => handleDragStart(index)}
                        onDragOver={(event) => handleDragOver(event, index)}
                        onDragEnd={handleDragEnd}
                        className={`rounded-xl border bg-card p-4 ${dragIndex === index ? "opacity-60" : ""}`}
                    >
                        <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
                            <div className="flex items-center gap-3">
                                <GripVerticalIcon
                                    className="size-4 cursor-grab text-muted-foreground"
                                    aria-hidden="true"
                                />
                                <input
                                    id={`stage-color-${stage.id}`}
                                    name={`stage-color-${stage.id}`}
                                    type="color"
                                    value={stage.color}
                                    onChange={(event) =>
                                        updateStage(index, (current) => ({
                                            ...current,
                                            color: event.target.value,
                                        }))
                                    }
                                    className="h-9 w-9 cursor-pointer rounded border"
                                    aria-label={`Stage ${index + 1} color`}
                                />
                            </div>

                            <div className="grid flex-1 gap-3 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)_minmax(0,1fr)_auto]">
                                <Input
                                    value={stage.label}
                                    onChange={(event) =>
                                        updateStage(index, (current) => ({
                                            ...current,
                                            label: event.target.value,
                                        }))
                                    }
                                    placeholder="Label"
                                    className="h-9"
                                />
                                <Input
                                    value={stage.slug}
                                    onChange={(event) =>
                                        updateStage(index, (current) => {
                                            const slug = normalizeIdentifier(event.target.value)
                                            return {
                                                ...current,
                                                slug,
                                                stage_key: isUuidLike(current.id)
                                                    ? current.stage_key
                                                    : slug || current.stage_key,
                                            }
                                        })
                                    }
                                    className="h-9 font-mono text-sm"
                                    aria-label="Stage slug"
                                />
                                <label className="space-y-2 text-sm">
                                    <span className="sr-only">Stage category</span>
                                    <select
                                        value={stage.category}
                                        onChange={(event) =>
                                            updateStage(index, (current) => ({
                                                ...current,
                                                category: event.target.value as StageType,
                                                stage_type: event.target.value as StageType,
                                            }))
                                        }
                                        className="h-9 w-full rounded-md border bg-background px-3 text-sm"
                                        aria-label="Stage category"
                                    >
                                        {STAGE_CATEGORIES.map((category) => (
                                            <option key={category} value={category}>
                                                {category.replaceAll("_", " ")}
                                            </option>
                                        ))}
                                    </select>
                                </label>
                                <div className="flex min-h-9 items-center justify-center overflow-hidden rounded-md border bg-muted/30 px-2 py-1 text-xs">
                                    <div className="flex min-w-0 items-center justify-center gap-0.5 sm:gap-1">
                                        <Badge variant="outline" className="shrink-0 tabular-nums">
                                            #{index + 1}
                                        </Badge>
                                        <Button
                                            type="button"
                                            variant="ghost"
                                            size="icon-sm"
                                            className="size-7 shrink-0 sm:size-8"
                                            onClick={() => toggleStageDetails(stage.id)}
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
                                        <Button
                                            type="button"
                                            variant="ghost"
                                            size="icon-sm"
                                            className="size-7 shrink-0 sm:size-8"
                                            onClick={() => onDuplicateStage(stage.stage_key)}
                                            aria-label={`Duplicate ${stage.label}`}
                                        >
                                            <CopyIcon className="size-4" aria-hidden="true" />
                                        </Button>
                                        <Button
                                            type="button"
                                            variant="ghost"
                                            size="icon-sm"
                                            className="size-7 shrink-0 sm:size-8"
                                            onClick={() => onRequestDeleteStage(stage.stage_key)}
                                            aria-label={`Remove ${stage.label}`}
                                        >
                                            <Trash2Icon className="size-4" aria-hidden="true" />
                                        </Button>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {dependency && isExpanded ? (
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
                                    <Badge variant="outline">
                                        Campaigns: {dependency.campaign_refs.length}
                                    </Badge>
                                ) : null}
                                {dependency.workflow_refs.length > 0 ? (
                                    <Badge variant="outline">
                                        Workflows: {dependency.workflow_refs.length}
                                    </Badge>
                                ) : null}
                            </div>
                        ) : null}

                        {isExpanded ? (
                            <div id={`stage-details-${stage.id}`} className="mt-4 space-y-4">
                                <label className="space-y-2 text-sm">
                                    <span className="font-medium">Stage key</span>
                                    <Input
                                        value={stage.stage_key}
                                        readOnly
                                        disabled
                                        className="h-9 bg-muted font-mono text-xs"
                                        title="Stage key is immutable after creation"
                                        aria-label="Stage key"
                                    />
                                </label>
                                <div className="grid gap-4 lg:grid-cols-2">
                                    <label className="space-y-2 text-sm">
                                        <span className="font-medium">Behavior preset</span>
                                        <select
                                            value={getBehaviorPreset(stage, entityType)}
                                            onChange={(event) => {
                                                const preset = event.target.value as BehaviorPreset
                                                updateStage(index, (current) => ({
                                                    ...current,
                                                    semantics: buildPresetSemantics(
                                                        current,
                                                        preset,
                                                        entityType,
                                                    ),
                                                }))
                                            }}
                                            className="h-9 w-full rounded-md border bg-background px-3 text-sm"
                                            aria-label={`Behavior preset for ${stage.label}`}
                                        >
                                            {getPresetOptions(stage, entityType).map((option) => (
                                                <option key={option.value} value={option.value}>
                                                    {option.label}
                                                </option>
                                            ))}
                                        </select>
                                    </label>
                                    {entityType === "surrogate" ? (
                                        <label className="space-y-2 text-sm">
                                            <span className="font-medium">Integration bucket</span>
                                            <select
                                                value={stage.semantics.integration_bucket}
                                                onChange={(event) =>
                                                    updateStage(index, (current) => ({
                                                        ...current,
                                                        semantics: {
                                                            ...current.semantics,
                                                            integration_bucket:
                                                                event.target.value as StageSemantics["integration_bucket"],
                                                        },
                                                    }))
                                                }
                                                className="h-9 w-full rounded-md border bg-background px-3 text-sm"
                                                aria-label={`Integration bucket for ${stage.label}`}
                                            >
                                                <option value="none">Not tracked</option>
                                                <option value="intake">Intake</option>
                                                <option value="qualified">Qualified</option>
                                                <option value="converted">Converted</option>
                                                <option value="lost">Lost</option>
                                                <option value="not_qualified">Not qualified</option>
                                            </select>
                                        </label>
                                    ) : null}
                                    <label className="space-y-2 text-sm">
                                        <span className="font-medium">Pause behavior</span>
                                        <select
                                            value={stage.semantics.pause_behavior}
                                            onChange={(event) =>
                                                updateStage(index, (current) => ({
                                                    ...current,
                                                    semantics: {
                                                        ...current.semantics,
                                                        pause_behavior:
                                                            event.target.value as StageSemantics["pause_behavior"],
                                                    },
                                                }))
                                            }
                                            className="h-9 w-full rounded-md border bg-background px-3 text-sm"
                                            aria-label={`Pause behavior for ${stage.label}`}
                                        >
                                            <option value="none">None</option>
                                            <option value="resume_previous_stage">
                                                Resume previous stage
                                            </option>
                                        </select>
                                    </label>
                                    <label className="space-y-2 text-sm">
                                        <span className="font-medium">Terminal outcome</span>
                                        <select
                                            value={stage.semantics.terminal_outcome}
                                            onChange={(event) =>
                                                updateStage(index, (current) => ({
                                                    ...current,
                                                    semantics: {
                                                        ...current.semantics,
                                                        terminal_outcome:
                                                            event.target.value as StageSemantics["terminal_outcome"],
                                                    },
                                                }))
                                            }
                                            className="h-9 w-full rounded-md border bg-background px-3 text-sm"
                                            aria-label={`Terminal outcome for ${stage.label}`}
                                        >
                                            <option value="none">None</option>
                                            <option value="lost">Lost</option>
                                            <option value="disqualified">Disqualified</option>
                                        </select>
                                    </label>
                                    {entityType === "surrogate" ? (
                                        <>
                                            <label className="space-y-2 text-sm">
                                                <span className="font-medium">Suggestion profile</span>
                                                <select
                                                    value={stage.semantics.suggestion_profile_key ?? ""}
                                                    onChange={(event) =>
                                                        updateStage(index, (current) => ({
                                                            ...current,
                                                            semantics: {
                                                                ...current.semantics,
                                                                suggestion_profile_key: event.target.value || null,
                                                            },
                                                        }))
                                                    }
                                                    className="h-9 w-full rounded-md border bg-background px-3 text-sm"
                                                    aria-label={`Suggestion profile for ${stage.label}`}
                                                >
                                                    {SUGGESTION_PROFILE_OPTIONS.map((option) => (
                                                        <option key={option || "none"} value={option}>
                                                            {option || "None"}
                                                        </option>
                                                    ))}
                                                </select>
                                            </label>
                                            <label
                                                className="space-y-2 text-sm"
                                                htmlFor={`analytics-bucket-${stage.id}`}
                                            >
                                                <span className="font-medium">Analytics bucket</span>
                                                <Input
                                                    id={`analytics-bucket-${stage.id}`}
                                                    value={stage.semantics.analytics_bucket ?? ""}
                                                    onChange={(event) =>
                                                        updateStage(index, (current) => ({
                                                            ...current,
                                                            semantics: {
                                                                ...current.semantics,
                                                                analytics_bucket:
                                                                    event.target.value.trim() || null,
                                                            },
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

                                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                                    {getVisibleCapabilityLabels(entityType).map((capability) => (
                                        <label
                                            key={capability.key}
                                            className="flex items-start gap-3 rounded-lg border bg-muted/20 p-3 text-sm"
                                        >
                                            <input
                                                type="checkbox"
                                                checked={stage.semantics.capabilities[capability.key]}
                                                onChange={(event) =>
                                                    updateStage(index, (current) => ({
                                                        ...current,
                                                        semantics: {
                                                            ...current.semantics,
                                                            capabilities: {
                                                                ...current.semantics.capabilities,
                                                                [capability.key]: event.target.checked,
                                                            },
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
                                            onChange={(event) =>
                                                updateStage(index, (current) => ({
                                                    ...current,
                                                    semantics: {
                                                        ...current.semantics,
                                                        requires_reason_on_enter: event.target.checked,
                                                    },
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
                            </div>
                        ) : null}
                    </div>
                )
            })}

            <Alert>
                <InfoIcon className="size-4" aria-hidden="true" />
                <AlertDescription>
                    Drag stages to reorder. Slugs remain editable, stage keys stay immutable, and
                    downstream behaviors resolve from stage semantics and stage key instead of the
                    slug.
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

                    <label className="space-y-2 text-sm">
                        <span className="font-medium">Remap target stage</span>
                        <select
                            value={state.targetStageKey}
                            onChange={(event) =>
                                onStateChange({
                                    ...state,
                                    targetStageKey: event.target.value,
                                })
                            }
                            className="h-9 w-full rounded-md border bg-background px-3 text-sm"
                            aria-label="Remap target stage"
                        >
                            <option value="">No remap</option>
                            {targetOptions.map((targetStage) => (
                                <option key={targetStage.stage_key} value={targetStage.stage_key}>
                                    {targetStage.label}
                                </option>
                            ))}
                        </select>
                    </label>
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

export default function PipelinesSettingsPage() {
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
    const draft = draftOverride?.contextKey === editorContextKey ? draftOverride.value : null
    const deleteStageState =
        deleteStageOverride?.contextKey === editorContextKey ? deleteStageOverride.value : null
    const currentDraft = draft ?? baselineDraft
    const hasChanges = useMemo(() => {
        if (!baselineDraft || !currentDraft) return false
        return stringifyDraft(baselineDraft) !== stringifyDraft(currentDraft)
    }, [baselineDraft, currentDraft])
    const previewDraft = useMemo(() => {
        if (!currentDraft || !hasChanges) return null
        return {
            ...buildApiDraft(currentDraft),
            ...(pipeline?.current_version
                ? { expected_version: pipeline.current_version }
                : {}),
        }
    }, [currentDraft, hasChanges, pipeline?.current_version])
    const previewQuery = usePipelineChangePreview(defaultPipeline?.id || null, previewDraft, entityType)
    const preview: PipelineChangePreview | null = previewQuery.data ?? null
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
        updateDraft((current) => ({
            ...current,
            stages: [...current.stages, buildNewStage(current, entityType)],
        }))
    }

    const handleDuplicateStage = (stageKey: string) => {
        if (!currentDraft) return
        const source = currentDraft.stages.find((stage) => stage.stage_key === stageKey)
        if (!source) return
        updateDraft((current) => ({
            ...current,
            stages: [...current.stages, buildDuplicateStage(source, current)],
        }))
    }

    const handleRequestDeleteStage = (stageKey: string) => {
        const stage = currentStages.find((item) => item.stage_key === stageKey)
        if (!stage) return
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
            setScopedDraft(
                buildDraft({
                    name: recommended.name,
                    stages: recommended.stages as PipelineStage[],
                    feature_config: recommended.feature_config,
                }, entityType),
            )
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

    if (isLoading) {
        return (
            <div className="flex flex-1 items-center justify-center p-6">
                <Loader2Icon className="size-8 animate-spin text-muted-foreground" aria-hidden="true" />
            </div>
        )
    }

    const selectedDeleteStage = deleteStageState
        ? currentStages.find((stage) => stage.stage_key === deleteStageState.stageKey)
        : undefined
    const impactAreas = (preview?.impact_areas ?? []) as ImpactArea[]
    const validationErrors = preview?.validation_errors ?? []
    const blockingIssues = preview?.blocking_issues ?? []
    const requiredRemaps = preview?.required_remaps ?? []
    const entityLabel = getEntityLabel(entityType)
    const entityDescription = getEntityDescription(entityType)
    const showSurrogateEditors = entityType === "surrogate"

    return (
        <div className="mx-auto flex max-w-6xl flex-1 flex-col gap-6 p-6">
            <div className="max-w-3xl">
                <h1 className="text-2xl font-semibold">Pipeline Settings</h1>
                <p className="text-sm text-muted-foreground">
                    {showSurrogateEditors
                        ? "Configure per-org stage identity, category, behavior, journey mappings, and analytics funnel from one versioned draft."
                        : "Configure intended-parent stage identity, category, and stage semantics from one versioned draft."}
                </p>
            </div>

            <DeleteStageDialog
                entityType={entityType}
                stage={selectedDeleteStage}
                stages={currentStages}
                dependencyGraph={dependencyGraph}
                open={Boolean(deleteStageState)}
                state={deleteStageState}
                onOpenChange={(open) => {
                    if (!open) setScopedDeleteStageState(null)
                }}
                onStateChange={setScopedDeleteStageState}
                onConfirm={handleConfirmDeleteStage}
            />

            <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
                <div className="space-y-6">
                    <Card>
                        <CardHeader>
                            <div className="flex flex-wrap items-start justify-between gap-4">
                                <div className="space-y-2">
                                    <CardTitle className="flex items-center gap-2 text-lg">
                                        {pipeline?.name || "Default Pipeline"}
                                        <Badge variant="outline">v{pipeline?.current_version || 1}</Badge>
                                        {entityLabel ? <Badge variant="secondary">{entityLabel}</Badge> : null}
                                    </CardTitle>
                                    <CardDescription>
                                        {showSurrogateEditors
                                            ? "Stage keys are immutable. Slugs, category, order, and semantics stay org-configurable, and downstream features refresh from the pipeline snapshot."
                                            : "Stage keys are immutable. Slugs, category, order, and stage semantics stay org-configurable, and downstream match and campaign behavior refresh from the pipeline snapshot."}
                                    </CardDescription>
                                </div>
                                <div className="flex flex-wrap gap-2">
                                    <Button
                                        type="button"
                                        variant="outline"
                                        onClick={handleResetToRecommended}
                                        disabled={recommendedDraft.isPending}
                                    >
                                        {recommendedDraft.isPending ? (
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
                                stages={currentStages}
                                dependencyGraph={dependencyGraph}
                                onChange={updateDraftStages}
                                onAddStage={handleAddStage}
                                onDuplicateStage={handleDuplicateStage}
                                onRequestDeleteStage={handleRequestDeleteStage}
                            />
                        </CardContent>
                    </Card>

                    {showSurrogateEditors && currentFeatureConfig ? (
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
                                        stages={currentStages}
                                        featureConfig={currentFeatureConfig}
                                        onChange={updateDraftFeatureConfig}
                                    />
                                </CardContent>
                            </Card>

                            <Card>
                                <CardHeader>
                                    <CardTitle className="text-base">Analytics Funnel</CardTitle>
                                    <CardDescription>
                                        Choose which live stages participate in analytics funnel
                                        reporting and preserve the pipeline order in the response.
                                    </CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <AnalyticsFunnelEditor
                                        stages={currentStages}
                                        featureConfig={currentFeatureConfig}
                                        onChange={updateDraftFeatureConfig}
                                    />
                                </CardContent>
                            </Card>
                        </>
                    ) : null}

                    {hasChanges ? (
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-base">Impact Preview</CardTitle>
                                <CardDescription>
                                    Server-validated preview of the pipeline-connected areas that will
                                    refresh or change when this draft is saved.
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                {previewQuery.isLoading ? (
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
                                    <p className="text-sm text-muted-foreground">
                                        No downstream impact detected yet.
                                    </p>
                                )}

                                {preview?.safe_auto_fixes.length ? (
                                    <Alert>
                                        <InfoIcon className="size-4" aria-hidden="true" />
                                        <AlertDescription>
                                            {preview.safe_auto_fixes.join(" ")}
                                        </AlertDescription>
                                    </Alert>
                                ) : null}

                                {requiredRemaps.length > 0 ? (
                                    <Alert variant="destructive">
                                        <TriangleAlertIcon className="size-4" aria-hidden="true" />
                                        <AlertDescription>
                                            <div className="space-y-2">
                                                <p className="font-medium">These removals still need a remap target:</p>
                                                <ul className="list-disc space-y-1 pl-5">
                                                    {requiredRemaps.map((item: PipelineRequiredRemap) => (
                                                        <li key={item.stage_key}>
                                                            {item.label}: {item.reasons.map((reason) => REMAP_REASON_LABELS[reason] ?? reason).join(", ")}
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
                                                <p className="font-medium">
                                                    Fix these guarded invariants before saving:
                                                </p>
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
                    ) : null}

                    {hasChanges ? (
                        <Card>
                            <CardContent className="pt-6">
                                <div className="flex flex-col gap-3 sm:flex-row">
                                    <Button
                                        onClick={handleSave}
                                        disabled={
                                            previewQuery.isLoading
                                            || validationErrors.length > 0
                                            || blockingIssues.length > 0
                                            || applyDraft.isPending
                                        }
                                        className="flex-1"
                                    >
                                        {applyDraft.isPending ? (
                                            <Loader2Icon className="mr-2 size-4 animate-spin" aria-hidden="true" />
                                        ) : (
                                            <SaveIcon className="mr-2 size-4" aria-hidden="true" />
                                        )}
                                        Save Changes
                                    </Button>
                                    <Button variant="outline" onClick={handleReset}>
                                        Discard
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>
                    ) : null}
                </div>

                <div className="space-y-6" data-testid="pipelines-sidebar">
                    <div className="space-y-2">
                        <Label htmlFor="pipeline-entity">Entity</Label>
                        <Select
                            value={entityType}
                            onValueChange={(value) => {
                                if (!value) return
                                setEntityType(value as PipelineEntityType)
                            }}
                        >
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
                            {pipeline ? (
                                <VersionHistory
                                    pipelineId={pipeline.id}
                                    entityType={entityType}
                                    onRollback={handleRollback}
                                    canRollback={isDeveloper}
                                />
                            ) : null}
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    )
}
