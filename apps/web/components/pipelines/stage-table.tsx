"use client"

import { useCallback, useState } from "react"
import type * as React from "react"
import {
    ChevronRightIcon,
    CopyIcon,
    GripVerticalIcon,
    Loader2Icon,
    LockIcon,
    PlusIcon,
    SparklesIcon,
    Trash2Icon,
} from "lucide-react"

import { INLINE_SELECT_TRIGGER_CLASS, PipelineSelectField } from "@/components/pipelines/pipeline-select-field"
import { StageFieldError, StageSwatch, type StageChangeHandler } from "@/components/pipelines/stage-settings"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type {
    PipelineDependencyGraph,
    PipelineEntityType,
    PipelineFeatureConfig,
    StageType,
} from "@/lib/api/pipelines"
import {
    buildPresetSemantics,
    createMilestoneLabelGetter,
    getBehaviorPreset,
    getBehaviorPresetLabel,
    getDependencyByStageKey,
    getEntityCountColumnLabel,
    getPresetOptions,
    getStageCategoryLabel,
    getStageCategoryOptions,
    getStageMilestoneSlugs,
    isUuidLike,
    normalizeIdentifier,
    STAGE_LABEL_MAX_LENGTH,
    STAGE_SLUG_MAX_LENGTH,
    withAutoStageColor,
    type BehaviorPreset,
    type EditableStage,
    type StageFieldErrors,
} from "@/lib/pipelines/stage-editor"
import { cn } from "@/lib/utils"

/** Inline table input: reads as text until hovered or focused. */
const INLINE_INPUT_CLASS =
    "-ml-1.5 h-7 border-transparent bg-transparent px-1.5 shadow-none hover:border-input focus-visible:bg-background aria-invalid:border-destructive dark:bg-transparent md:text-[13px]"
// Clicks on these keep the row from opening the drawer.
const ROW_INTERACTIVE_SELECTOR = "input, button, a, label, [role='combobox'], [role='checkbox'], [data-drag-handle]"

/** Pipeline name, stage and lock counts, Reset to Default and Add Custom Stage. */
export function StagesToolbar({
    pipelineName,
    stageCount,
    lockedCount,
    isResetPending,
    onResetToRecommended,
    onAddStage,
}: {
    pipelineName: string
    stageCount: number
    lockedCount: number
    isResetPending: boolean
    onResetToRecommended: () => void
    onAddStage: () => void
}) {
    return (
        <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-base font-semibold">{pipelineName}</h2>
            <Badge variant="outline">
                {stageCount} {stageCount === 1 ? "stage" : "stages"}
            </Badge>
            {lockedCount > 0 ? (
                <Badge variant="outline">
                    <LockIcon aria-hidden="true" />
                    {lockedCount} locked
                </Badge>
            ) : null}
            <div className="ml-auto flex flex-wrap items-center gap-2">
                <Button type="button" variant="outline" onClick={onResetToRecommended} disabled={isResetPending}>
                    {isResetPending ? (
                        <Loader2Icon className="animate-spin" aria-hidden="true" />
                    ) : (
                        <SparklesIcon aria-hidden="true" />
                    )}
                    Reset to Default
                </Button>
                <Button type="button" onClick={onAddStage}>
                    <PlusIcon aria-hidden="true" />
                    Add Custom Stage
                </Button>
            </div>
        </div>
    )
}

type StageRowProps = {
    entityType: PipelineEntityType
    stage: EditableStage
    index: number
    errors: StageFieldErrors | undefined
    recordCount: number
    milestoneText: string | null
    inFunnel: boolean
    showSurrogateEditors: boolean
    selected: boolean
    dragging: boolean
    autoFocusLabel: boolean
    onStageChange: StageChangeHandler
    onOpen: () => void
    onDuplicate: () => void
    onRequestDelete: () => void
    onFunnelChange: (included: boolean) => void
    onDragStart: () => void
    onDragOver: (event: React.DragEvent) => void
    onDragEnd: () => void
}

function StageRow({
    entityType,
    stage,
    index,
    errors,
    recordCount,
    milestoneText,
    inFunnel,
    showSurrogateEditors,
    selected,
    dragging,
    autoFocusLabel,
    onStageChange,
    onOpen,
    onDuplicate,
    onRequestDelete,
    onFunnelChange,
    onDragStart,
    onDragOver,
    onDragEnd,
}: StageRowProps) {
    const locked = Boolean(stage.is_locked)
    const labelErrorId = `stage-label-error-${stage.id}`
    const slugErrorId = `stage-slug-error-${stage.id}`
    const preset = getBehaviorPreset(stage, entityType)
    const presetEditable = !locked && stage.category === "intake"
    const focusNewStageLabel = useCallback((node: HTMLInputElement | null) => {
        if (!node) return
        node.scrollIntoView?.({ block: "center" })
        node.focus({ preventScroll: true })
        node.select()
    }, [])

    return (
        <TableRow
            data-testid={`stage-row-${stage.id}`}
            data-selected={selected ? "" : undefined}
            className={cn(
                "group/row data-selected:bg-primary/[0.07] cursor-default [&>td]:h-10 [&>td]:px-2 [&>td]:py-1",
                dragging && "opacity-60",
            )}
            onDragOver={onDragOver}
            onDrop={(event) => event.preventDefault()}
            onClick={(event) => {
                // Select popups are portaled, but React still bubbles their clicks to the row.
                if (!(event.target instanceof Element) || !event.currentTarget.contains(event.target)) return
                if (event.target.closest(ROW_INTERACTIVE_SELECTOR)) return
                onOpen()
            }}
        >
            <TableCell className="text-muted-foreground">
                {locked ? (
                    <span role="img" aria-label="System stage" className="flex justify-center">
                        <LockIcon className="size-3.5" aria-hidden="true" />
                    </span>
                ) : (
                    <span
                        data-drag-handle=""
                        draggable
                        onDragStart={(event) => {
                            event.dataTransfer.effectAllowed = "move"
                            event.dataTransfer.setData("text/plain", stage.stage_key)
                            const row = event.currentTarget.closest("tr")
                            if (row) event.dataTransfer.setDragImage(row, 16, 20)
                            onDragStart()
                        }}
                        onDragEnd={onDragEnd}
                        aria-hidden="true"
                        className="flex cursor-grab justify-center active:cursor-grabbing"
                    >
                        <GripVerticalIcon className="size-4" />
                    </span>
                )}
            </TableCell>
            <TableCell
                data-testid={`stage-order-${stage.id}`}
                className="text-muted-foreground text-right tabular-nums"
            >
                {index + 1}
            </TableCell>
            <TableCell className="whitespace-normal">
                <div className="flex min-w-0 items-center gap-2.5">
                    <StageSwatch color={stage.color} />
                    {locked ? (
                        <span className="truncate">{stage.label}</span>
                    ) : (
                        <Input
                            id={`stage-label-${stage.id}`}
                            ref={autoFocusLabel ? focusNewStageLabel : undefined}
                            value={stage.label}
                            maxLength={STAGE_LABEL_MAX_LENGTH}
                            onChange={(event) =>
                                onStageChange((current) =>
                                    withAutoStageColor(current, { ...current, label: event.target.value }),
                                )
                            }
                            placeholder="Label"
                            aria-label={`Stage ${index + 1} label`}
                            aria-invalid={errors?.label ? true : undefined}
                            aria-describedby={errors?.label ? labelErrorId : undefined}
                            className={INLINE_INPUT_CLASS}
                        />
                    )}
                </div>
                <StageFieldError id={labelErrorId} message={errors?.label} />
            </TableCell>
            <TableCell className="whitespace-normal">
                {locked ? (
                    <span className="text-muted-foreground block truncate font-mono text-xs">{stage.slug}</span>
                ) : (
                    <Input
                        value={stage.slug}
                        maxLength={STAGE_SLUG_MAX_LENGTH}
                        spellCheck={false}
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
                        aria-label={`Stage ${index + 1} slug`}
                        aria-invalid={errors?.slug ? true : undefined}
                        aria-describedby={errors?.slug ? slugErrorId : undefined}
                        className={cn(INLINE_INPUT_CLASS, "text-muted-foreground focus-visible:text-foreground font-mono md:text-xs")}
                    />
                )}
                <StageFieldError id={slugErrorId} message={errors?.slug} />
            </TableCell>
            <TableCell>
                {locked ? (
                    <span className="text-muted-foreground">{getStageCategoryLabel(stage.category)}</span>
                ) : (
                    <PipelineSelectField
                        id={`stage-category-${stage.id}`}
                        label={`Stage ${index + 1} type`}
                        value={stage.category}
                        options={getStageCategoryOptions(stage)}
                        srOnlyLabel
                        triggerClassName={INLINE_SELECT_TRIGGER_CLASS}
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
                )}
            </TableCell>
            <TableCell>
                <div className="flex min-w-0 items-center gap-1.5">
                    {presetEditable ? (
                        <PipelineSelectField
                            id={`stage-preset-${stage.id}`}
                            label={`Stage ${index + 1} behavior preset`}
                            value={preset}
                            options={getPresetOptions(stage, entityType)}
                            srOnlyLabel
                            triggerClassName={INLINE_SELECT_TRIGGER_CLASS}
                            onValueChange={(value) =>
                                onStageChange((current) => ({
                                    ...current,
                                    semantics: buildPresetSemantics(current, value as BehaviorPreset, entityType),
                                }))
                            }
                        />
                    ) : (
                        <span className={cn("truncate", locked && "text-muted-foreground")}>
                            {getBehaviorPresetLabel(preset, entityType)}
                        </span>
                    )}
                    {stage.semantics.requires_reason_on_enter ? (
                        <Badge variant="outline" className="h-4 px-1.5 text-[10px]">
                            Reason
                        </Badge>
                    ) : null}
                </div>
            </TableCell>
            {showSurrogateEditors ? (
                <>
                    <TableCell className="text-muted-foreground">
                        <span className="block truncate" title={milestoneText ?? undefined}>
                            {milestoneText ?? "—"}
                        </span>
                    </TableCell>
                    <TableCell className="text-center">
                        <Checkbox
                            checked={inFunnel}
                            disabled={!stage.is_active}
                            onCheckedChange={(checked) => onFunnelChange(checked)}
                            aria-label={`${stage.label} in analytics funnel`}
                            className="mx-auto"
                        />
                    </TableCell>
                </>
            ) : null}
            <TableCell className="text-right tabular-nums">{recordCount}</TableCell>
            <TableCell>
                <div className="flex items-center justify-end gap-0.5">
                    {locked ? null : (
                        <div className="flex items-center gap-0.5 opacity-0 transition-opacity group-hover/row:opacity-100 group-focus-within/row:opacity-100">
                            <Button
                                type="button"
                                variant="ghost"
                                size="icon-sm"
                                className="size-7"
                                onClick={onDuplicate}
                                aria-label={`Duplicate ${stage.label}`}
                            >
                                <CopyIcon aria-hidden="true" />
                            </Button>
                            <Button
                                type="button"
                                variant="ghost"
                                size="icon-sm"
                                className="size-7"
                                onClick={onRequestDelete}
                                aria-label={`Remove ${stage.label}`}
                            >
                                <Trash2Icon aria-hidden="true" />
                            </Button>
                        </div>
                    )}
                    <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        className="text-muted-foreground size-7"
                        onClick={onOpen}
                        aria-label={`Open ${stage.label || `stage ${index + 1}`} settings`}
                    >
                        <ChevronRightIcon aria-hidden="true" />
                    </Button>
                </div>
            </TableCell>
        </TableRow>
    )
}

/**
 * Dense stage table: label, slug, type and (intake) preset edit inline; every other setting is
 * in the stage drawer. Unlocked rows reorder by dragging the grip; the drawer has Move up/down.
 */
export function StageTable({
    entityType,
    stages,
    stageErrors,
    dependencyGraph,
    featureConfig,
    showSurrogateEditors,
    focusStageId,
    selectedStageId,
    onStageChange,
    onReorder,
    onOpenStage,
    onDuplicateStage,
    onRequestDeleteStage,
    onFunnelChange,
}: {
    entityType: PipelineEntityType
    stages: EditableStage[]
    stageErrors: Record<string, StageFieldErrors>
    dependencyGraph: PipelineDependencyGraph | null | undefined
    featureConfig: PipelineFeatureConfig | undefined
    showSurrogateEditors: boolean
    focusStageId: string | null
    selectedStageId: string | null
    onStageChange: (stageId: string, updater: (stage: EditableStage) => EditableStage) => void
    onReorder: (fromIndex: number, toIndex: number) => void
    onOpenStage: (stageId: string) => void
    onDuplicateStage: (stageKey: string) => void
    onRequestDeleteStage: (stageKey: string) => void
    onFunnelChange: (stageKey: string, included: boolean) => void
}) {
    const [dragIndex, setDragIndex] = useState<number | null>(null)
    const showJourney = showSurrogateEditors && Boolean(featureConfig)
    const getMilestoneLabel = featureConfig ? createMilestoneLabelGetter(featureConfig) : null
    const funnelKeys = new Set(featureConfig?.analytics.funnel_stage_keys ?? [])

    return (
        <div className="bg-card overflow-hidden rounded-xl border">
            {/* The Stage column takes the remaining width; the fixed columns fit a 1440px window with the sidebar open. */}
            <Table className={cn("table-fixed text-[13px]", showJourney ? "min-w-[1080px]" : "min-w-[860px]")}>
                <colgroup>
                    <col className="w-8" />
                    <col className="w-9" />
                    <col />
                    <col className="w-[140px]" />
                    <col className="w-[148px]" />
                    <col className="w-[144px]" />
                    {showJourney ? (
                        <>
                            <col className="w-[160px]" />
                            <col className="w-14" />
                        </>
                    ) : null}
                    <col className="w-[84px]" />
                    <col className="w-[100px]" />
                </colgroup>
                <TableHeader className="bg-muted/50">
                    <TableRow className="hover:bg-transparent [&>th]:text-muted-foreground [&>th]:h-9 [&>th]:px-2 [&>th]:text-xs">
                        <TableHead>
                            <span className="sr-only">Reorder</span>
                        </TableHead>
                        <TableHead className="text-right">#</TableHead>
                        <TableHead>Stage</TableHead>
                        <TableHead>Slug</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Behavior</TableHead>
                        {showJourney ? (
                            <>
                                <TableHead>Journey milestone</TableHead>
                                <TableHead className="text-center">Funnel</TableHead>
                            </>
                        ) : null}
                        <TableHead className="text-right">{getEntityCountColumnLabel(entityType)}</TableHead>
                        <TableHead>
                            <span className="sr-only">Actions</span>
                        </TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {stages.map((stage, index) => {
                        const milestoneSlugs = featureConfig ? getStageMilestoneSlugs(featureConfig, stage.stage_key) : []
                        const milestoneText = getMilestoneLabel && milestoneSlugs.length > 0
                            ? milestoneSlugs.map((slug) => getMilestoneLabel(slug)).join(", ")
                            : null
                        return (
                            <StageRow
                                key={stage.id}
                                entityType={entityType}
                                stage={stage}
                                index={index}
                                errors={stageErrors[stage.id]}
                                recordCount={getDependencyByStageKey(dependencyGraph, stage.stage_key)?.surrogate_count ?? 0}
                                milestoneText={milestoneText}
                                inFunnel={funnelKeys.has(stage.stage_key)}
                                showSurrogateEditors={showJourney}
                                selected={stage.id === selectedStageId}
                                dragging={dragIndex === index}
                                autoFocusLabel={stage.id === focusStageId}
                                onStageChange={(updater) => onStageChange(stage.id, updater)}
                                onOpen={() => onOpenStage(stage.id)}
                                onDuplicate={() => onDuplicateStage(stage.stage_key)}
                                onRequestDelete={() => onRequestDeleteStage(stage.stage_key)}
                                onFunnelChange={(included) => onFunnelChange(stage.stage_key, included)}
                                onDragStart={() => setDragIndex(index)}
                                onDragOver={(event) => {
                                    if (dragIndex === null) return
                                    event.preventDefault()
                                    if (dragIndex === index) return
                                    onReorder(dragIndex, index)
                                    setDragIndex(index)
                                }}
                                onDragEnd={() => setDragIndex(null)}
                            />
                        )
                    })}
                </TableBody>
            </Table>
        </div>
    )
}
