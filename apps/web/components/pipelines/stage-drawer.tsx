"use client"

import { CopyIcon, Trash2Icon, XIcon } from "lucide-react"

import { StageSettingsFields, StageSwatch, type StageChangeHandler } from "@/components/pipelines/stage-settings"
import { Button } from "@/components/ui/button"
import { Sheet, SheetClose, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import type { PipelineEntityType, PipelineFeatureConfig, PipelineStageDependency } from "@/lib/api/pipelines"
import type { EditableStage, StageFieldErrors } from "@/lib/pipelines/stage-editor"

/** Right-side drawer with every setting of one stage. Opens from the stage table. */
export function StageDrawer({
    open,
    entityType,
    stage,
    index,
    total,
    errors,
    dependency,
    featureConfig,
    showSurrogateEditors,
    onClose,
    onStageChange,
    onMove,
    onMilestonesChange,
    onFunnelChange,
    onDuplicate,
    onRequestDelete,
}: {
    /** Kept apart from `stage` so the panel keeps its content while it slides out. */
    open: boolean
    entityType: PipelineEntityType
    stage: EditableStage | undefined
    index: number
    total: number
    errors: StageFieldErrors | undefined
    dependency: PipelineStageDependency | undefined
    featureConfig: PipelineFeatureConfig | undefined
    showSurrogateEditors: boolean
    onClose: () => void
    onStageChange: StageChangeHandler
    onMove: (delta: -1 | 1) => void
    onMilestonesChange: (milestoneSlugs: string[]) => void
    onFunnelChange: (included: boolean) => void
    onDuplicate: () => void
    onRequestDelete: () => void
}) {
    return (
        <Sheet
            open={open && Boolean(stage)}
            onOpenChange={(open) => {
                if (!open) onClose()
            }}
        >
            <SheetContent
                side="right"
                showCloseButton={false}
                className="gap-0 data-[side=right]:w-full data-[side=right]:sm:max-w-[448px]"
            >
                {stage ? (
                    <>
                        <SheetHeader className="flex-row items-center gap-3 border-b px-5 py-4">
                            <StageSwatch color={stage.color} className="size-5 rounded-[5px]" />
                            <SheetTitle className="min-w-0 flex-1 truncate text-base font-semibold">
                                {stage.label || "Untitled stage"}
                            </SheetTitle>
                            <SheetClose
                                render={
                                    <Button variant="ghost" size="icon-sm" aria-label="Close">
                                        <XIcon aria-hidden="true" />
                                    </Button>
                                }
                            />
                        </SheetHeader>
                        <div className="flex-1 overflow-y-auto px-5 py-2">
                            <StageSettingsFields
                                key={stage.id}
                                idPrefix="drawer"
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
                            />
                        </div>
                        <div className="flex items-center gap-2 border-t px-5 py-3">
                            {stage.is_locked ? null : (
                                <>
                                    <Button type="button" variant="outline" size="sm" onClick={onDuplicate}>
                                        <CopyIcon aria-hidden="true" />
                                        Duplicate
                                    </Button>
                                    <Button
                                        type="button"
                                        variant="destructive-outline"
                                        size="sm"
                                        onClick={onRequestDelete}
                                    >
                                        <Trash2Icon aria-hidden="true" />
                                        Remove
                                    </Button>
                                </>
                            )}
                            <Button type="button" size="sm" className="ml-auto" onClick={onClose}>
                                Done
                            </Button>
                        </div>
                    </>
                ) : null}
            </SheetContent>
        </Sheet>
    )
}
