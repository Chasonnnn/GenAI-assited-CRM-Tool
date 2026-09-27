"use client"

import * as React from "react"

import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { StageSelect } from "@/components/stage-select"
import type { PipelineStage } from "@/lib/api/pipelines"
import { pipelineStageOptions } from "@/lib/stage-options"
import { stageHasCapability, stageUsesPauseBehavior } from "@/lib/surrogate-stage-context"

export function BulkChangeStageModal({
    open,
    onOpenChange,
    selectedCount,
    stages,
    isPending,
    onSubmit,
}: {
    open: boolean
    onOpenChange: (open: boolean) => void
    selectedCount: number
    stages: PipelineStage[]
    isPending: boolean
    onSubmit: (stageId: string) => Promise<void> | void
}) {
    const [targetStageId, setTargetStageId] = React.useState("")

    const immediateStageOptions = pipelineStageOptions(
        stages.filter(
            (stage) =>
                !stageUsesPauseBehavior(stage) &&
                !stageHasCapability(stage, "requires_delivery_details"),
        ),
        { activeOnly: true },
    )

    const handleOpenChange = (nextOpen: boolean) => {
        if (!nextOpen) {
            setTargetStageId("")
        }
        onOpenChange(nextOpen)
    }

    const handleSubmit = async () => {
        if (!targetStageId) return
        await onSubmit(targetStageId)
        setTargetStageId("")
    }

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Change stage</DialogTitle>
                    <DialogDescription>
                        Move {selectedCount} selected surrogate{selectedCount === 1 ? "" : "s"} to an
                        immediate stage.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4">
                    <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950">
                        This bulk action supports immediate moves only. Regressions, on-hold changes,
                        and delivery stages still need per-surrogate review.
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="bulk-change-stage-target">Target stage</Label>
                        <StageSelect
                            id="bulk-change-stage-target"
                            value={targetStageId}
                            onValueChange={setTargetStageId}
                            options={immediateStageOptions}
                            className="w-full"
                            // A shorter list fits below the trigger, so it does not flip up over the title.
                            contentClassName="max-h-[min(18rem,var(--available-height))]"
                        />
                    </div>
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={() => handleOpenChange(false)} disabled={isPending}>
                        Cancel
                    </Button>
                    <Button onClick={handleSubmit} disabled={isPending || !targetStageId}>
                        Change stage
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
