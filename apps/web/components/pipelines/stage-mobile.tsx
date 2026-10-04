"use client"

import {
    ArrowDownIcon,
    ArrowLeftIcon,
    ArrowUpDownIcon,
    ArrowUpIcon,
    ChevronRightIcon,
    CopyIcon,
    EllipsisIcon,
    GripVerticalIcon,
    Loader2Icon,
    LockIcon,
    PlusIcon,
    SparklesIcon,
    Trash2Icon,
} from "lucide-react"

import { StageSettingsFields, StageSwatch, type StageChangeHandler } from "@/components/pipelines/stage-settings"
import { Button } from "@/components/ui/button"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import type {
    PipelineDependencyGraph,
    PipelineEntityType,
    PipelineFeatureConfig,
    PipelineStageDependency,
} from "@/lib/api/pipelines"
import {
    getBehaviorPreset,
    getBehaviorPresetLabel,
    getDependencyByStageKey,
    getStageCategoryLabel,
    type EditableStage,
    type StageFieldErrors,
} from "@/lib/pipelines/stage-editor"
import { cn } from "@/lib/utils"

/** DOM id of a phone list row, so Back can return focus to the stage the user opened. */
export function getMobileStageRowId(stageId: string): string {
    return `mobile-stage-row-${stageId}`
}

function focusOnMount(node: HTMLElement | null) {
    node?.focus({ preventScroll: true })
}

/** Phone stage list header: name, counts, Reorder, Add Custom Stage and Reset to Default. */
export function MobileStagesBar({
    pipelineName,
    stageCount,
    lockedCount,
    isResetPending,
    onReorder,
    onAddStage,
    onResetToRecommended,
}: {
    pipelineName: string
    stageCount: number
    lockedCount: number
    isResetPending: boolean
    onReorder: () => void
    onAddStage: () => void
    onResetToRecommended: () => void
}) {
    return (
        <div className="flex items-center gap-2 border-b px-4 py-3">
            <div className="grid min-w-0 flex-1 leading-tight">
                <h2 className="truncate text-[15px] font-semibold">{pipelineName}</h2>
                <span className="text-muted-foreground text-xs">
                    {stageCount} {stageCount === 1 ? "stage" : "stages"}
                    {lockedCount > 0 ? ` · ${lockedCount} locked` : ""}
                </span>
            </div>
            <Button type="button" variant="outline" size="sm" onClick={onReorder}>
                <ArrowUpDownIcon aria-hidden="true" />
                Reorder
            </Button>
            <Button type="button" size="icon-sm" onClick={onAddStage} aria-label="Add Custom Stage">
                <PlusIcon aria-hidden="true" />
            </Button>
            <DropdownMenu>
                <DropdownMenuTrigger
                    render={
                        <Button type="button" variant="outline" size="icon-sm" aria-label="More pipeline actions">
                            <EllipsisIcon aria-hidden="true" />
                        </Button>
                    }
                />
                <DropdownMenuContent align="end" className="w-auto">
                    <DropdownMenuItem disabled={isResetPending} onClick={onResetToRecommended}>
                        {isResetPending ? (
                            <Loader2Icon className="animate-spin" aria-hidden="true" />
                        ) : (
                            <SparklesIcon aria-hidden="true" />
                        )}
                        Reset to Default
                    </DropdownMenuItem>
                </DropdownMenuContent>
            </DropdownMenu>
        </div>
    )
}

/** Phone stage list: one row per stage, opening the full-screen stage page. */
export function MobileStageList({
    entityType,
    stages,
    stageErrors,
    dependencyGraph,
    onOpenStage,
}: {
    entityType: PipelineEntityType
    stages: EditableStage[]
    stageErrors: Record<string, StageFieldErrors>
    dependencyGraph: PipelineDependencyGraph | null | undefined
    onOpenStage: (stageId: string) => void
}) {
    return (
        <ul className="bg-card divide-y border-b" aria-label="Stages">
            {stages.map((stage, index) => {
                const hasErrors = Boolean(stageErrors[stage.id])
                const count = getDependencyByStageKey(dependencyGraph, stage.stage_key)?.surrogate_count ?? 0
                return (
                    <li key={stage.id}>
                        <Button
                            unstyled
                            type="button"
                            id={getMobileStageRowId(stage.id)}
                            onClick={() => onOpenStage(stage.id)}
                            className="hover:bg-muted/50 focus-visible:bg-muted/50 flex h-[52px] w-full items-center gap-2.5 px-4 text-left outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:ring-inset"
                        >
                            <StageSwatch color={stage.color} />
                            <span className="grid min-w-0 flex-1 leading-tight">
                                <span
                                    className={cn(
                                        "truncate text-sm font-medium",
                                        hasErrors && "text-destructive",
                                    )}
                                >
                                    {stage.label || `Stage ${index + 1}`}
                                </span>
                                <span className="text-muted-foreground truncate text-xs">
                                    {getStageCategoryLabel(stage.category)} ·{" "}
                                    {getBehaviorPresetLabel(getBehaviorPreset(stage, entityType), entityType)}
                                </span>
                            </span>
                            {stage.is_locked ? (
                                <LockIcon
                                    className="text-muted-foreground size-3.5 shrink-0"
                                    role="img"
                                    aria-label="System stage"
                                />
                            ) : null}
                            <span className="text-muted-foreground text-xs tabular-nums">{count}</span>
                            <ChevronRightIcon className="text-muted-foreground size-4 shrink-0" aria-hidden="true" />
                        </Button>
                    </li>
                )
            })}
        </ul>
    )
}

/** Full-screen stage page on phones, rendered in place of the list so the save bar stays below. */
export function MobileStagePage({
    entityType,
    stage,
    index,
    total,
    errors,
    dependency,
    featureConfig,
    showSurrogateEditors,
    onBack,
    onStageChange,
    onMove,
    onMilestonesChange,
    onFunnelChange,
    onDuplicate,
    onRequestDelete,
    autoFocusLabel = false,
}: {
    entityType: PipelineEntityType
    stage: EditableStage
    index: number
    total: number
    errors: StageFieldErrors | undefined
    dependency: PipelineStageDependency | undefined
    featureConfig: PipelineFeatureConfig | undefined
    showSurrogateEditors: boolean
    onBack: () => void
    onStageChange: StageChangeHandler
    onMove: (delta: -1 | 1) => void
    onMilestonesChange: (milestoneSlugs: string[]) => void
    onFunnelChange: (included: boolean) => void
    onDuplicate: () => void
    onRequestDelete: () => void
    autoFocusLabel?: boolean
}) {
    return (
        <section aria-labelledby={`mobile-stage-title-${stage.id}`} className="bg-card flex flex-1 flex-col">
            <div className="bg-card sticky top-0 z-10 flex h-14 items-center gap-2 border-b pr-2 pl-1">
                <Button type="button" variant="ghost" size="icon-sm" onClick={onBack} aria-label="Back to stages">
                    <ArrowLeftIcon aria-hidden="true" />
                </Button>
                <StageSwatch color={stage.color} />
                {/* The page replaces the focused list row, so focus moves here unless the label of a new stage takes it. */}
                <h2
                    id={`mobile-stage-title-${stage.id}`}
                    ref={autoFocusLabel ? undefined : focusOnMount}
                    tabIndex={-1}
                    className="min-w-0 flex-1 truncate text-base font-semibold outline-none"
                >
                    {stage.label || `Stage ${index + 1}`}
                </h2>
                {stage.is_locked ? null : (
                    <DropdownMenu>
                        <DropdownMenuTrigger
                            render={
                                <Button type="button" variant="ghost" size="icon-sm" aria-label="Stage actions">
                                    <EllipsisIcon aria-hidden="true" />
                                </Button>
                            }
                        />
                        <DropdownMenuContent align="end" className="w-auto">
                            <DropdownMenuItem onClick={onDuplicate}>
                                <CopyIcon aria-hidden="true" />
                                Duplicate
                            </DropdownMenuItem>
                            <DropdownMenuItem variant="destructive" onClick={onRequestDelete}>
                                <Trash2Icon aria-hidden="true" />
                                Remove
                            </DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>
                )}
            </div>
            <div className="px-4 py-1">
                <StageSettingsFields
                    key={stage.id}
                    idPrefix="mobile"
                    entityType={entityType}
                    stage={stage}
                    index={index}
                    total={total}
                    errors={errors}
                    dependency={dependency}
                    featureConfig={featureConfig}
                    showSurrogateEditors={showSurrogateEditors}
                    onStageChange={onStageChange}
                    onMove={onMove}
                    onMilestonesChange={onMilestonesChange}
                    onFunnelChange={onFunnelChange}
                    autoFocusLabel={autoFocusLabel}
                />
            </div>
        </section>
    )
}

/** Phone reorder mode: up/down arrows, because native drag and drop does not work on touch. */
export function MobileReorderList({
    stages,
    lastMovedStageId,
    onMove,
    onDone,
}: {
    stages: EditableStage[]
    lastMovedStageId: string | null
    onMove: (stageId: string, delta: -1 | 1) => void
    onDone: () => void
}) {
    return (
        <section aria-labelledby="mobile-reorder-title" className="flex flex-1 flex-col">
            <div className="bg-card sticky top-0 z-10 flex h-14 items-center gap-2 border-b pr-2 pl-4">
                <h2 id="mobile-reorder-title" className="min-w-0 flex-1 truncate text-base font-semibold">
                    Reorder stages
                </h2>
                <Button type="button" size="sm" onClick={onDone}>
                    Done
                </Button>
            </div>
            <ol className="bg-card divide-y border-b">
                {stages.map((stage, index) => (
                    <li
                        key={stage.id}
                        data-lifted={stage.id === lastMovedStageId ? "" : undefined}
                        className="data-lifted:ring-ring data-lifted:bg-card relative flex h-[52px] items-center gap-2.5 px-4 data-lifted:z-[1] data-lifted:mx-1.5 data-lifted:rounded-lg data-lifted:shadow-lg data-lifted:ring-1"
                    >
                        {stage.is_locked ? (
                            <LockIcon className="text-muted-foreground size-3.5 shrink-0" role="img" aria-label="System stage" />
                        ) : (
                            <GripVerticalIcon className="text-muted-foreground size-4 shrink-0" aria-hidden="true" />
                        )}
                        <StageSwatch color={stage.color} />
                        <span
                            className={cn(
                                "min-w-0 flex-1 truncate text-sm font-medium",
                                stage.is_locked && "text-muted-foreground",
                            )}
                        >
                            {stage.label || `Stage ${index + 1}`}
                        </span>
                        {stage.is_locked ? null : (
                            <span className="flex items-center gap-1">
                                <Button
                                    type="button"
                                    variant="outline"
                                    size="icon-sm"
                                    className="size-7"
                                    disabled={index === 0}
                                    onClick={() => onMove(stage.id, -1)}
                                    aria-label={`Move ${stage.label} up`}
                                >
                                    <ArrowUpIcon aria-hidden="true" />
                                </Button>
                                <Button
                                    type="button"
                                    variant="outline"
                                    size="icon-sm"
                                    className="size-7"
                                    disabled={index >= stages.length - 1}
                                    onClick={() => onMove(stage.id, 1)}
                                    aria-label={`Move ${stage.label} down`}
                                >
                                    <ArrowDownIcon aria-hidden="true" />
                                </Button>
                            </span>
                        )}
                    </li>
                ))}
            </ol>
        </section>
    )
}
