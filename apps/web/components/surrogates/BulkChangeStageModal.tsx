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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import type { PipelineStage } from "@/lib/api/pipelines"
import { stageHasCapability, stageUsesPauseBehavior } from "@/lib/surrogate-stage-context"

function getStageLabel(
    value: string | null | undefined,
    stages: PipelineStage[],
): string {
    if (!value) return "Select a stage"
    return stages.find((stage) => stage.id === value)?.label ?? "Select a stage"
}

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

    const immediateStages = React.useMemo(
        () =>
            [...stages]
                .filter(
                    (stage) =>
                        stage.is_active &&
                        !stageUsesPauseBehavior(stage) &&
                        !stageHasCapability(stage, "requires_delivery_details"),
                )
                .sort((a, b) => a.order - b.order),
        [stages],
    )

    React.useEffect(() => {
        if (open) {
            setTargetStageId("")
        }
    }, [open])

    const handleSubmit = async () => {
        if (!targetStageId) return
        await onSubmit(targetStageId)
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
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
                        <Select
                            value={targetStageId}
                            onValueChange={(value) => setTargetStageId(value ?? "")}
                        >
                            <SelectTrigger
                                id="bulk-change-stage-target"
                                aria-label="Target stage"
                            >
                                <SelectValue placeholder="Select a stage">
                                    {(value: string | null) => getStageLabel(value, immediateStages)}
                                </SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                {immediateStages.map((stage) => (
                                    <SelectItem key={stage.id} value={stage.id}>
                                        {stage.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isPending}>
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
