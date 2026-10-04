"use client"

import { useState } from "react"
import { CheckIcon, ChevronDownIcon, ChevronUpIcon, InfoIcon, Loader2Icon, RotateCcwIcon, TriangleAlertIcon } from "lucide-react"

import { QueryErrorState } from "@/components/error-state"
import { PipelineSelectField } from "@/components/pipelines/pipeline-select-field"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import type {
    PipelineDependencyGraph,
    PipelineEntityType,
    PipelineFeatureConfig,
    PipelineRequiredRemap,
} from "@/lib/api/pipelines"
import { formatRelativeTime } from "@/lib/formatters"
import { usePipelineVersions } from "@/lib/hooks/use-pipelines"
import {
    deepClone,
    getActiveRemapTargetStages,
    getDeleteRequirements,
    getDependencyByStageKey,
    IMPACT_LABELS,
    IMPACT_PREVIEW_ID,
    isPipelineEntityType,
    PIPELINE_ENTITY_OPTIONS,
    REMAP_REASON_LABELS,
    type DeleteStageState,
    type EditableStage,
    type ImpactArea,
    type PipelineSelectOption,
} from "@/lib/pipelines/stage-editor"
import { createSelectLabelGetter } from "@/lib/select-labels"

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

export function DeleteStageDialog({
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

export function SurrogatePipelineSections({
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

export function ImpactPreviewCard({
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

export function PipelineEntityToggle({
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

export function VersionHistorySheet({
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

const getPipelineEntityLabel = createSelectLabelGetter(PIPELINE_ENTITY_OPTIONS, {
    emptyLabel: "Select pipeline",
    unknownLabel: "Unknown pipeline",
})

/** Phone entity selector; the header toggle group does not fit a 390px screen. */
export function PipelineEntitySelect({
    entityType,
    onEntityTypeChange,
}: {
    entityType: PipelineEntityType
    onEntityTypeChange: (entityType: PipelineEntityType) => void
}) {
    return (
        <Select
            value={entityType}
            onValueChange={(next) => {
                if (isPipelineEntityType(next)) onEntityTypeChange(next)
            }}
        >
            <SelectTrigger aria-label="Entity" className="min-w-0 flex-1">
                <SelectValue>{getPipelineEntityLabel}</SelectValue>
            </SelectTrigger>
            <SelectContent>
                {PIPELINE_ENTITY_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                        {getPipelineEntityLabel(option.value)}
                    </SelectItem>
                ))}
            </SelectContent>
        </Select>
    )
}
