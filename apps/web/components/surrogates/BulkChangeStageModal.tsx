"use client"

import * as React from "react"
import { Loader2Icon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
    Dialog,
    DialogBody,
    DialogContent,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { useCurrentMinuteTimestamp } from "@/components/ui/use-current-minute-timestamp"
import { StageSelect } from "@/components/stage-select"
import type { PipelineStage } from "@/lib/api/pipelines"
import type { BulkChangeStageInterviewTime } from "@/lib/api/surrogates"
import { localDateTimeToIso, schedulingTimezoneLabel } from "@/lib/scheduling-time"
import { pipelineStageOptions } from "@/lib/stage-options"
import {
    getSurrogateStageContext,
    stageMatchesKey,
    stageRequiresReasonOnEnter,
    stageUsesPauseBehavior,
} from "@/lib/surrogate-stage-context"
import type { SurrogateListItem } from "@/lib/types/surrogate"
import { cn } from "@/lib/utils"

// Matches the max_length of BulkStageChange.surrogate_ids.
export const BULK_STAGE_CHANGE_LIMIT = 100

export type BulkStageSurrogate = Pick<SurrogateListItem, "id" | "full_name" | "stage_id" | "paused_from_stage_id">

export interface BulkStageChangeInput {
    stage_id: string
    reason?: string
    on_hold_follow_up_months?: 1 | 3 | 6
    interview_times?: BulkChangeStageInterviewTime[]
    override_availability?: boolean
}

type FollowUpMonths = "none" | "1" | "3" | "6"

const FOLLOW_UP_OPTIONS: Array<{ value: FollowUpMonths; label: string }> = [
    { value: "none", label: "No follow-up" },
    { value: "1", label: "1 month" },
    { value: "3", label: "3 months" },
    { value: "6", label: "6 months" },
]

function movesBackward(
    surrogate: BulkStageSurrogate,
    target: PipelineStage,
    stageById: Map<string, PipelineStage>,
): boolean {
    const context = getSurrogateStageContext(
        {
            stage_id: surrogate.stage_id,
            stage_slug: null,
            stage_type: null,
            paused_from_stage_id: surrogate.paused_from_stage_id ?? null,
        },
        stageById,
    )
    const { currentStage, effectiveStage } = context
    if (!currentStage || !effectiveStage || currentStage.id === target.id) return false
    if (context.isOnHold && context.pausedFromStage?.id === target.id) return false
    if (stageMatchesKey(currentStage, "reschedule_needed") && stageMatchesKey(target, "interview_scheduled")) {
        return false
    }
    return target.order < effectiveStage.order
}

function toLocalDateTimeValue(timestamp: number): string {
    const date = new Date(timestamp)
    return new Date(timestamp - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16)
}

function futureIso(value: string | undefined, now: number): string | null {
    const iso = value ? localDateTimeToIso(value) : null
    if (!iso || new Date(iso).getTime() <= now) return null
    return iso
}

export function BulkChangeStageModal({
    open,
    ...props
}: {
    open: boolean
    onOpenChange: (open: boolean) => void
    surrogates: BulkStageSurrogate[]
    stages: PipelineStage[]
    isPending: boolean
    onSubmit: (input: BulkStageChangeInput) => Promise<void> | void
}) {
    if (!open) return null

    return <BulkChangeStageModalContent {...props} />
}

function BulkChangeStageModalContent({
    onOpenChange,
    surrogates,
    stages,
    isPending,
    onSubmit,
}: {
    onOpenChange: (open: boolean) => void
    surrogates: BulkStageSurrogate[]
    stages: PipelineStage[]
    isPending: boolean
    onSubmit: (input: BulkStageChangeInput) => Promise<void> | void
}) {
    const [targetStageId, setTargetStageId] = React.useState("")
    const [reason, setReason] = React.useState("")
    const [followUpMonths, setFollowUpMonths] = React.useState<FollowUpMonths>("none")
    const [interviewTimes, setInterviewTimes] = React.useState<Record<string, string>>({})
    const [overrideAvailability, setOverrideAvailability] = React.useState(false)
    const [openedAt] = React.useState(() => Date.now())
    const now = useCurrentMinuteTimestamp() ?? openedAt
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone

    const stageOptions = pipelineStageOptions(stages, { activeOnly: true })
    const stageById = new Map(stages.map((stage) => [stage.id, stage]))
    const targetStage = stages.find((stage) => stage.id === targetStageId && stage.is_active)
    const isOnHoldTarget = stageUsesPauseBehavior(targetStage)
    const isInterviewTarget = stageMatchesKey(targetStage, "interview_scheduled")
    const isOverridingAvailability = isInterviewTarget && overrideAvailability
    const overLimit = surrogates.length > BULK_STAGE_CHANGE_LIMIT
    // Rows already in the target stage fail on the server either way, so they get no time input.
    const interviewSurrogates = surrogates
        .slice(0, BULK_STAGE_CHANGE_LIMIT)
        .filter((surrogate) => surrogate.stage_id !== targetStageId)

    const anyBackward = targetStage
        ? surrogates.some((surrogate) => movesBackward(surrogate, targetStage, stageById))
        : false
    const reasonRequired =
        stageRequiresReasonOnEnter(targetStage) || anyBackward || isOverridingAvailability
    const interviewTimesValid =
        !isInterviewTarget ||
        interviewSurrogates.every((surrogate) => futureIso(interviewTimes[surrogate.id], now) !== null)

    const canSubmit =
        Boolean(targetStage) &&
        !overLimit &&
        !isPending &&
        (!reasonRequired || reason.trim().length > 0) &&
        interviewTimesValid

    const handleOpenChange = (nextOpen: boolean) => {
        if (!nextOpen && isPending) return
        onOpenChange(nextOpen)
    }

    const handleSubmit = async () => {
        if (!targetStage || !canSubmit) return
        const input: BulkStageChangeInput = { stage_id: targetStage.id }
        const trimmedReason = reason.trim()
        if (reasonRequired && trimmedReason) input.reason = trimmedReason
        if (isOnHoldTarget && followUpMonths !== "none") {
            input.on_hold_follow_up_months = Number(followUpMonths) as 1 | 3 | 6
        }
        if (isOverridingAvailability) input.override_availability = true
        if (isInterviewTarget) {
            const times: BulkChangeStageInterviewTime[] = []
            for (const surrogate of interviewSurrogates) {
                const scheduledAt = futureIso(interviewTimes[surrogate.id], now)
                if (!scheduledAt) return
                times.push({ surrogate_id: surrogate.id, scheduled_at: scheduledAt })
            }
            input.interview_times = times
        }
        await onSubmit(input)
    }

    const count = surrogates.length
    const minDateTime = toLocalDateTimeValue(now)

    return (
        <Dialog open onOpenChange={handleOpenChange}>
            <DialogContent size={isInterviewTarget ? "xl" : "lg"} layout="sectioned">
                <DialogHeader>
                    <DialogTitle>
                        Change stage for {count} surrogate{count === 1 ? "" : "s"}
                    </DialogTitle>
                </DialogHeader>

                <DialogBody>
                    <div className="space-y-2">
                        <Label htmlFor="bulk-change-stage-target">Target stage</Label>
                        <StageSelect
                            id="bulk-change-stage-target"
                            value={targetStageId}
                            onValueChange={setTargetStageId}
                            options={stageOptions}
                            disabled={isPending}
                            className="w-full"
                            // A shorter list fits below the trigger, so it does not flip up over the title.
                            contentClassName="max-h-[min(18rem,var(--available-height))]"
                        />
                    </div>

                    {isOnHoldTarget ? (
                        <fieldset className="space-y-2">
                            <legend className="text-sm font-medium">Follow-up reminder</legend>
                            <div className="grid grid-cols-2 gap-2">
                                {FOLLOW_UP_OPTIONS.map((option) => {
                                    const isSelected = followUpMonths === option.value
                                    return (
                                        <Button
                                            key={option.value}
                                            type="button"
                                            variant="outline"
                                            aria-pressed={isSelected}
                                            disabled={isPending}
                                            onClick={() => setFollowUpMonths(option.value)}
                                            className={cn(
                                                isSelected &&
                                                    "border-primary bg-primary/10 dark:border-primary dark:bg-primary/10",
                                            )}
                                        >
                                            {option.label}
                                        </Button>
                                    )
                                })}
                            </div>
                        </fieldset>
                    ) : null}

                    {isInterviewTarget ? (
                        <section aria-label="Interview times" className="space-y-2">
                            <div className="text-sm font-medium">
                                Interview times · {schedulingTimezoneLabel(timezone)}
                            </div>
                            <div className="max-h-72 space-y-2 overflow-y-auto pr-1">
                                {interviewSurrogates.map((surrogate) => {
                                    const value = interviewTimes[surrogate.id] ?? ""
                                    const inputId = `bulk-interview-${surrogate.id}`
                                    return (
                                        <div
                                            key={surrogate.id}
                                            className="grid items-center gap-2 sm:grid-cols-[minmax(0,1fr)_14rem]"
                                        >
                                            <Label htmlFor={inputId} className="truncate">
                                                {surrogate.full_name}
                                            </Label>
                                            <Input
                                                id={inputId}
                                                type="datetime-local"
                                                value={value}
                                                min={minDateTime}
                                                required
                                                disabled={isPending}
                                                aria-invalid={value !== "" && futureIso(value, now) === null}
                                                onValueChange={(next) =>
                                                    setInterviewTimes((current) => ({ ...current, [surrogate.id]: next }))
                                                }
                                            />
                                        </div>
                                    )
                                })}
                            </div>
                            <div className="flex items-center gap-2 pt-1">
                                <Checkbox
                                    id="bulk-change-stage-override"
                                    checked={overrideAvailability}
                                    onCheckedChange={(checked) => setOverrideAvailability(checked === true)}
                                    disabled={isPending}
                                />
                                <Label htmlFor="bulk-change-stage-override" className="cursor-pointer">
                                    Allow times outside availability
                                </Label>
                            </div>
                        </section>
                    ) : null}

                    {reasonRequired ? (
                        <div className="space-y-2">
                            <Label htmlFor="bulk-change-stage-reason">
                                Reason <span className="text-destructive">*</span>
                            </Label>
                            <Textarea
                                id="bulk-change-stage-reason"
                                required
                                maxLength={500}
                                disabled={isPending}
                                value={reason}
                                onChange={(event) => setReason(event.target.value)}
                                rows={3}
                                className="resize-none"
                            />
                        </div>
                    ) : null}

                    {overLimit ? (
                        <p role="alert" className="text-sm text-destructive">
                            Select up to {BULK_STAGE_CHANGE_LIMIT} surrogates.
                        </p>
                    ) : null}
                </DialogBody>

                <DialogFooter>
                    <Button variant="outline" onClick={() => handleOpenChange(false)} disabled={isPending}>
                        Cancel
                    </Button>
                    <Button onClick={() => void handleSubmit()} disabled={!canSubmit}>
                        {isPending ? (
                            <>
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                                Changing...
                            </>
                        ) : (
                            "Change stage"
                        )}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
