"use client"

import { useState } from "react"
import { format, startOfDay, isBefore } from "date-fns"
import {
    AlertCircleIcon,
    AlertTriangleIcon,
    CalendarIcon,
    ClockIcon,
    Loader2Icon,
    CheckIcon,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { Calendar } from "@/components/ui/calendar"
import { Input } from "@/components/ui/input"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { SchedulingTimePicker } from "@/components/appointments/SchedulingTimePicker"
import { useInterviewSlots } from "@/lib/hooks/use-interview-appointment"
import { localDateTimeToIso, schedulingDateKey } from "@/lib/scheduling-time"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import {
    stageHasCapability,
    stageMatchesKey,
    stageRequiresReasonOnEnter,
    stageUsesPauseBehavior,
} from "@/lib/surrogate-stage-context"
import { cn } from "@/lib/utils"
import type { PipelineStage } from "@/lib/api/pipelines"

type FollowUpMonths = "none" | "1" | "3" | "6"

const FOLLOW_UP_OPTIONS: Array<{
    value: FollowUpMonths
    label: string
    description: string
}> = [
    {
        value: "none",
        label: "No follow-up",
        description: "Keep this paused without a reminder task.",
    },
    {
        value: "1",
        label: "1 month",
        description: "Create a reminder one month from the effective date.",
    },
    {
        value: "3",
        label: "3 months",
        description: "Create a reminder three months from the effective date.",
    },
    {
        value: "6",
        label: "6 months",
        description: "Create a reminder six months from the effective date.",
    },
]

interface ChangeStageModalProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    stages: PipelineStage[]
    currentStageId: string
    comparisonStageId?: string
    currentStageLabel: string
    entityLabel?: string
    onSubmit: (data: {
        stage_id: string
        reason?: string
        effective_at?: string // ISO datetime
        interview_scheduled_at?: string
        override_availability?: boolean
        override_reason?: string
        on_hold_follow_up_months?: 1 | 3 | 6 | null
        delivery_baby_gender?: string | null
        delivery_baby_weight?: string | null
    }) => Promise<{ status: "applied" | "pending_approval"; request_id?: string }>
    isPending?: boolean
    deliveryFieldsEnabled?: boolean
    initialDeliveryBabyGender?: string | null
    initialDeliveryBabyWeight?: string | null
    onHoldFollowUpAssigneeLabel?: string | null
    canSelfApproveRegression?: boolean
    appointmentManager?: React.ReactNode
    surrogateId?: string
}

function StageSelectionList({
    label,
    stages,
    currentStageId,
    selectedStageId,
    onStageSelect,
}: {
    label: string
    stages: PipelineStage[]
    currentStageId: string
    selectedStageId: string | null
    onStageSelect: (stage: PipelineStage) => void
}) {
    return (
        <div className="space-y-2">
            <Label>New {label}</Label>
            <div className="grid max-h-64 gap-1.5 overflow-y-auto pr-1">
                {stages.map((stage) => {
                    const isCurrent = stage.id === currentStageId
                    const isSelected = stage.id === selectedStageId

                    return (
                        <Button unstyled
                            key={stage.id}
                            type="button"
                            disabled={isCurrent}
                            onClick={() => onStageSelect(stage)}
                            className={cn(
                                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-colors",
                                "hover:bg-muted/50 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                                isSelected && "bg-primary/10 ring-1 ring-primary/30",
                                isCurrent && "cursor-not-allowed bg-muted/30 opacity-50",
                            )}
                        >
                            <div
                                className="size-3 shrink-0 rounded-full ring-1 ring-black/10"
                                style={{ backgroundColor: stage.color }}
                            />
                            <span className="flex-1 font-medium">{stage.label}</span>
                            {isCurrent ? (
                                <span className="text-xs text-muted-foreground">Current</span>
                            ) : null}
                            {isSelected ? <CheckIcon className="size-4 text-primary" /> : null}
                        </Button>
                    )
                })}
            </div>
        </div>
    )
}

function EffectiveScheduleSection({
    effectiveNow,
    selectedDate,
    selectedTime,
    datePickerOpen,
    calendarToday,
    selectedDateDefaultMonth,
    onEffectiveNowChange,
    onDatePickerOpenChange,
    onSelectedDateChange,
    onSelectedTimeChange,
}: {
    effectiveNow: boolean
    selectedDate: Date | undefined
    selectedTime: string
    datePickerOpen: boolean
    calendarToday: Date
    selectedDateDefaultMonth: Date
    onEffectiveNowChange: (value: boolean) => void
    onDatePickerOpenChange: (open: boolean) => void
    onSelectedDateChange: (date: Date | undefined) => void
    onSelectedTimeChange: (value: string) => void
}) {
    return (
        <>
            <div className="flex items-center justify-between">
                <Label htmlFor="effective-now" className="cursor-pointer">
                    Effective now
                </Label>
                <Switch
                    id="effective-now"
                    checked={effectiveNow}
                    onCheckedChange={onEffectiveNowChange}
                />
            </div>

            {!effectiveNow ? (
                <div className="space-y-3">
                    <div className="space-y-2">
                        <Label>Effective Date</Label>
                        <Popover open={datePickerOpen} onOpenChange={onDatePickerOpenChange}>
                            <PopoverTrigger
                                className={cn(
                                    "inline-flex w-full items-center justify-start gap-2 rounded-md border border-input bg-background px-3 py-2 text-sm font-normal hover:bg-accent hover:text-accent-foreground",
                                    !selectedDate && "text-muted-foreground",
                                )}
                            >
                                <CalendarIcon className="size-4" />
                                {selectedDate ? format(selectedDate, "PPP") : "Select date"}
                            </PopoverTrigger>
                            <PopoverContent className="w-auto p-0" align="start">
                                <Calendar
                                    mode="single"
                                    selected={selectedDate}
                                    onSelect={(date) => {
                                        onSelectedDateChange(date)
                                        onDatePickerOpenChange(false)
                                    }}
                                    disabled={(date) => date > calendarToday}
                                    defaultMonth={selectedDateDefaultMonth}
                                />
                            </PopoverContent>
                        </Popover>
                    </div>

                    <div className="space-y-2">
                        <Label className="inline-flex items-center gap-2">
                            <ClockIcon className="size-4" />
                            Time (optional)
                        </Label>
                        <Input
                            type="time"
                            value={selectedTime}
                            onChange={(e) => onSelectedTimeChange(e.target.value)}
                            className="w-full"
                        />
                        <p className="text-xs text-muted-foreground">
                            Leave blank to use now (today) or noon (past dates)
                        </p>
                    </div>
                </div>
            ) : null}
        </>
    )
}

function OnHoldFollowUpSection({
    selectedMonths,
    assigneeLabel,
    onSelectedMonthsChange,
}: {
    selectedMonths: FollowUpMonths
    assigneeLabel: string | null
    onSelectedMonthsChange: (value: FollowUpMonths) => void
}) {
    return (
        <div className="space-y-3 rounded-lg border border-muted/60 bg-muted/20 p-3">
            <div className="space-y-1">
                <div className="text-sm font-medium text-foreground">
                    Follow-up reminder
                </div>
                <p className="text-xs text-muted-foreground">
                    Optional. If selected, we&apos;ll create an{" "}
                    <span className="font-medium text-foreground">
                        On-Hold follow-up
                    </span>{" "}
                    task assigned to {assigneeLabel ?? "the current owner"}.
                </p>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
                {FOLLOW_UP_OPTIONS.map((option) => {
                    const isSelected = selectedMonths === option.value
                    return (
                        <Button unstyled
                            key={option.value}
                            type="button"
                            onClick={() => onSelectedMonthsChange(option.value)}
                            className={cn(
                                "rounded-lg border px-3 py-3 text-left transition-colors",
                                "hover:border-primary/40 hover:bg-background/80",
                                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                                isSelected
                                    ? "border-primary bg-background shadow-sm"
                                    : "border-border/70 bg-background/40",
                            )}
                        >
                            <div className="text-sm font-medium text-foreground">
                                {option.label}
                            </div>
                            <div className="mt-1 text-xs text-muted-foreground">
                                {option.description}
                            </div>
                        </Button>
                    )
                })}
            </div>
        </div>
    )
}

function DeliveryDetailsSection({
    deliveryBabyGender,
    deliveryBabyWeight,
    onDeliveryBabyGenderChange,
    onDeliveryBabyWeightChange,
}: {
    deliveryBabyGender: string
    deliveryBabyWeight: string
    onDeliveryBabyGenderChange: (value: string) => void
    onDeliveryBabyWeightChange: (value: string) => void
}) {
    return (
        <div className="space-y-3 rounded-lg border border-muted/60 bg-muted/20 p-3">
            <div className="text-sm font-medium text-foreground">Delivery details</div>
            <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-2">
                    <Label htmlFor="delivery-baby-gender">Baby gender</Label>
                    <Input
                        id="delivery-baby-gender"
                        value={deliveryBabyGender}
                        onChange={(e) => onDeliveryBabyGenderChange(e.target.value)}
                        placeholder="Optional"
                    />
                </div>
                <div className="space-y-2">
                    <Label htmlFor="delivery-baby-weight">Baby weight</Label>
                    <Input
                        id="delivery-baby-weight"
                        value={deliveryBabyWeight}
                        onChange={(e) => onDeliveryBabyWeightChange(e.target.value)}
                        placeholder="Optional"
                    />
                </div>
            </div>
            <p className="text-xs text-muted-foreground">
                These fields sync to the pregnancy tracker after delivery.
            </p>
        </div>
    )
}

function ChangeStageWarnings({
    label,
    isBackdated,
    isRegression,
    requiresApproval,
    canSelfApproveRegression,
}: {
    label: string
    isBackdated: boolean
    isRegression: boolean
    requiresApproval: boolean
    canSelfApproveRegression: boolean
}) {
    return (
        <>
            {isBackdated && !isRegression ? (
                <Alert className="border-blue-500/30 bg-blue-500/5">
                    <AlertCircleIcon className="size-4 text-blue-600" />
                    <AlertTitle className="text-blue-600">Backdated Change</AlertTitle>
                    <AlertDescription className="text-blue-600/80">
                        This change will be recorded with a past effective date.
                        A reason is required for audit purposes.
                    </AlertDescription>
                </Alert>
            ) : null}

            {requiresApproval ? (
                <Alert className="border-amber-500/30 bg-amber-500/5">
                    <AlertTriangleIcon className="size-4 text-amber-600" />
                    <AlertTitle className="text-amber-600">Admin Approval Required</AlertTitle>
                    <AlertDescription className="text-amber-600/80">
                        Moving to an earlier {label.toLowerCase()} requires admin approval.
                        Your request will be submitted for review.
                    </AlertDescription>
                </Alert>
            ) : null}

            {isRegression && canSelfApproveRegression ? (
                <Alert className="border-blue-500/30 bg-blue-500/5">
                    <AlertCircleIcon className="size-4 text-blue-600" />
                    <AlertTitle className="text-blue-600">Earlier Stage Change</AlertTitle>
                    <AlertDescription className="text-blue-600/80">
                        You can apply this earlier stage change immediately.
                        A reason is still required for audit purposes.
                    </AlertDescription>
                </Alert>
            ) : null}
        </>
    )
}

function ReasonField({
    reason,
    onReasonChange,
}: {
    reason: string
    onReasonChange: (value: string) => void
}) {
    return (
        <div className="space-y-2">
            <Label htmlFor="reason">
                Reason <span className="text-destructive">*</span>
            </Label>
            <Textarea
                id="reason"
                placeholder="Why is this change being made?"
                value={reason}
                onChange={(e) => onReasonChange(e.target.value)}
                rows={3}
                className="resize-none"
            />
        </div>
    )
}

function ChangeStageActions({
    isPending,
    canSubmit,
    submitButtonText,
    submitButtonLoadingText,
    onCancel,
    onSubmit,
}: {
    isPending: boolean
    canSubmit: boolean
    submitButtonText: string
    submitButtonLoadingText: string
    onCancel: () => void
    onSubmit: () => void
}) {
    return (
        <div
            data-testid="change-stage-actions"
            className="shrink-0 border-t bg-background p-4"
        >
            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                <Button variant="outline" onClick={onCancel} disabled={isPending}>
                    Cancel
                </Button>
                <Button onClick={onSubmit} disabled={!canSubmit || isPending}>
                    {isPending ? (
                        <>
                            <Loader2Icon className="mr-2 size-4 animate-spin" />
                            {submitButtonLoadingText}
                        </>
                    ) : (
                        submitButtonText
                    )}
                </Button>
            </div>
        </div>
    )
}

export function ChangeStageModal({
    open,
    ...props
}: ChangeStageModalProps) {
    if (!open) return null

    return <ChangeStageModalContent open={open} {...props} />
}

function ChangeStageModalContent({
    open,
    onOpenChange,
    stages,
    currentStageId,
    comparisonStageId,
    currentStageLabel,
    entityLabel,
    onSubmit,
    isPending = false,
    deliveryFieldsEnabled = false,
    initialDeliveryBabyGender = null,
    initialDeliveryBabyWeight = null,
    onHoldFollowUpAssigneeLabel = null,
    canSelfApproveRegression = false,
    appointmentManager,
    surrogateId,
}: ChangeStageModalProps) {
    const [selectedStageId, setSelectedStageId] = useState<string | null>(null)
    const [effectiveNow, setEffectiveNow] = useState(true)
    const [selectedDate, setSelectedDate] = useState<Date | undefined>(undefined)
    const [selectedTime, setSelectedTime] = useState("")
    const [reason, setReason] = useState("")
    const [datePickerOpen, setDatePickerOpen] = useState(false)
    const [deliveryBabyGender, setDeliveryBabyGender] = useState(initialDeliveryBabyGender ?? "")
    const [deliveryBabyWeight, setDeliveryBabyWeight] = useState(initialDeliveryBabyWeight ?? "")
    const [onHoldFollowUpMonths, setOnHoldFollowUpMonths] = useState<FollowUpMonths>("none")
    const [overrideAvailability, setOverrideAvailability] = useState(false)
    const [overrideReason, setOverrideReason] = useState("")
    const [interviewDate, setInterviewDate] = useState("")
    const [interviewSelectedStart, setInterviewSelectedStart] = useState<string | null>(null)
    const [interviewCustomTime, setInterviewCustomTime] = useState("")
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone
    const [calendarToday] = useState(() => new Date())
    const calendarStartOfToday = startOfDay(calendarToday)
    const selectedDateDefaultMonth = selectedDate ?? calendarToday

    const currentStage = stages.find(s => s.id === currentStageId)
    const comparisonStage =
        stages.find((stage) => stage.id === (comparisonStageId ?? currentStageId)) ?? currentStage

    const selectedStage = stages.find(s => s.id === selectedStageId)
    const isDeliveredStage = stageHasCapability(selectedStage, "requires_delivery_details")
    const isOnHoldStage = stageUsesPauseBehavior(selectedStage)
    const isInterviewScheduledStage = stageMatchesKey(selectedStage, "interview_scheduled")
    const showDeliveryFields = deliveryFieldsEnabled && isDeliveredStage
    const interviewSlots = useInterviewSlots(surrogateId ?? "", interviewDate, timezone, isInterviewScheduledStage && Boolean(surrogateId))
    const interviewDateTime = isInterviewScheduledStage
        ? overrideAvailability ? localDateTimeToIso(interviewCustomTime) : interviewSelectedStart
        : null

    const isResumeSelection = (() => {
        if (!selectedStage || !currentStage || !comparisonStage) return false
        return stageUsesPauseBehavior(currentStage) && selectedStage.id === comparisonStage.id
    })()

    const isRegression = (() => {
        if (!selectedStage || !comparisonStage) return false
        if (stageMatchesKey(currentStage, "reschedule_needed") && stageMatchesKey(selectedStage, "interview_scheduled")) return false
        return !isResumeSelection && selectedStage.order < comparisonStage.order
    })()
    const requiresApproval = isRegression && !canSelfApproveRegression

    const hasTime = selectedTime.trim().length > 0
    const effectiveDateTime = (() => {
        if (effectiveNow || !selectedDate || !hasTime) return null
        const dateWithTime = new Date(selectedDate)
        const [hours, minutes] = selectedTime.split(":").map(Number)
        dateWithTime.setHours(hours || 0, minutes || 0, 0, 0)
        return dateWithTime
    })()

    const isBackdated = (() => {
        if (effectiveNow) return false
        if (!selectedDate) return false
        if (!hasTime) {
            const selected = startOfDay(selectedDate)
            return isBefore(selected, calendarStartOfToday)
        }
        if (!effectiveDateTime) return false
        return isBefore(effectiveDateTime, calendarToday)
    })()

    const reasonRequired =
        isRegression || isBackdated || stageRequiresReasonOnEnter(selectedStage)

    const canSubmit =
        Boolean(selectedStageId) &&
        selectedStageId !== currentStageId &&
        (effectiveNow || Boolean(selectedDate)) &&
        (!isInterviewScheduledStage || Boolean(interviewDateTime)) &&
        (!overrideAvailability || Boolean(overrideReason.trim())) &&
        (!reasonRequired || reason.trim().length > 0)

    const buildEffectiveAt = (): string | undefined => {
        if (effectiveNow) return undefined
        if (!selectedDate) return undefined

        const datePart = format(selectedDate, "yyyy-MM-dd")
        if (!hasTime) {
            return `${datePart}T00:00:00`
        }
        return `${datePart}T${selectedTime}:00`
    }

    const handleSubmit = async () => {
        if (!selectedStageId || !canSubmit) return

        const effective_at = buildEffectiveAt()

        const payload: {
            stage_id: string
            reason?: string
            effective_at?: string
            interview_scheduled_at?: string
            override_availability?: boolean
            override_reason?: string
            on_hold_follow_up_months?: 1 | 3 | 6 | null
            delivery_baby_gender?: string | null
            delivery_baby_weight?: string | null
        } = {
            stage_id: selectedStageId,
        }
        const trimmedReason = reason.trim()
        if (trimmedReason) payload.reason = trimmedReason
        if (effective_at) payload.effective_at = effective_at
        if (interviewDateTime) payload.interview_scheduled_at = interviewDateTime
        if (overrideAvailability) {
            payload.override_availability = true
            payload.override_reason = overrideReason.trim()
        }
        if (isOnHoldStage && onHoldFollowUpMonths !== "none") {
            payload.on_hold_follow_up_months = Number(onHoldFollowUpMonths) as 1 | 3 | 6
        }
        if (showDeliveryFields) {
            const trimmedGender = deliveryBabyGender.trim()
            const trimmedWeight = deliveryBabyWeight.trim()
            if (trimmedGender) payload.delivery_baby_gender = trimmedGender
            if (trimmedWeight) payload.delivery_baby_weight = trimmedWeight
        }

        await onSubmit(payload)
    }

    const handleClose = () => {
        if (!isPending) {
            onOpenChange(false)
        }
    }

    const label = entityLabel ?? "Stage"
    const handleStageSelect = (stage: PipelineStage) => {
        setSelectedStageId(stage.id)
        if (stageMatchesKey(stage, "interview_scheduled")) {
            setInterviewDate(schedulingDateKey(new Date(), timezone))
            setInterviewSelectedStart(null)
            setInterviewCustomTime("")
            setOverrideAvailability(false)
            setOverrideReason("")
        }
    }

    const submitButtonText = isResumeSelection
        ? "Resume"
        : requiresApproval
            ? "Request Approval"
            : "Save Change"
    const submitButtonLoadingText = isResumeSelection
        ? "Resuming..."
        : requiresApproval
            ? "Requesting..."
            : "Saving..."

    const sortedStages = stages.filter(s => s.is_active).toSorted((a, b) => a.order - b.order)

    return (
        <Dialog open={open} onOpenChange={handleClose}>
            <DialogContent
                data-testid="change-stage-dialog"
                className={cn(
                    "flex max-h-[calc(100dvh-2rem)] w-[calc(100vw-2rem)] flex-col gap-0 overflow-hidden p-0",
                    isInterviewScheduledStage ? "sm:max-w-2xl" : "sm:max-w-lg md:max-w-xl",
                )}
            >
                <DialogHeader className="shrink-0 border-b p-5 pr-14">
                    <DialogTitle>Change {label}</DialogTitle>
                    <DialogDescription>
                        Current: {currentStageLabel}
                    </DialogDescription>
                </DialogHeader>

                <div
                    data-testid="change-stage-scroll-body"
                    className="min-h-0 flex-1 space-y-5 overflow-y-auto px-5 py-4"
                >
                    <StageSelectionList
                        label={label}
                        stages={sortedStages}
                        currentStageId={currentStageId}
                        selectedStageId={selectedStageId}
                        onStageSelect={handleStageSelect}
                    />
                    {appointmentManager}
                    <EffectiveScheduleSection
                        effectiveNow={effectiveNow}
                        selectedDate={selectedDate}
                        selectedTime={selectedTime}
                        datePickerOpen={datePickerOpen}
                        calendarToday={calendarToday}
                        selectedDateDefaultMonth={selectedDateDefaultMonth}
                        onEffectiveNowChange={setEffectiveNow}
                        onDatePickerOpenChange={setDatePickerOpen}
                        onSelectedDateChange={setSelectedDate}
                        onSelectedTimeChange={setSelectedTime}
                    />
                    {isOnHoldStage ? (
                        <OnHoldFollowUpSection
                            selectedMonths={onHoldFollowUpMonths}
                            assigneeLabel={onHoldFollowUpAssigneeLabel}
                            onSelectedMonthsChange={setOnHoldFollowUpMonths}
                        />
                    ) : null}
                    {isInterviewScheduledStage ? <section aria-label="Interview appointment" className="space-y-3">
                        <div className="text-sm font-medium">Interview appointment</div>
                        <SchedulingTimePicker
                            idPrefix="stage-interview"
                            date={interviewDate}
                            onDateChange={(next) => { setInterviewDate(next); setInterviewSelectedStart(null) }}
                            timezone={timezone}
                            slots={interviewSlots.data?.slots}
                            selectedStart={interviewSelectedStart}
                            onSelectStart={setInterviewSelectedStart}
                            loading={interviewSlots.isLoading || interviewSlots.isFetching}
                            error={interviewSlots.isError ? "Available times could not be loaded." : undefined}
                            onRetry={() => void interviewSlots.refetch()}
                            minDate={schedulingDateKey(calendarToday, timezone)}
                            override={{ enabled: overrideAvailability, onEnabledChange: setOverrideAvailability, dateTime: interviewCustomTime, onDateTimeChange: setInterviewCustomTime, reason: overrideReason, onReasonChange: setOverrideReason }}
                        />
                    </section> : null}
                    {showDeliveryFields ? (
                        <DeliveryDetailsSection
                            deliveryBabyGender={deliveryBabyGender}
                            deliveryBabyWeight={deliveryBabyWeight}
                            onDeliveryBabyGenderChange={setDeliveryBabyGender}
                            onDeliveryBabyWeightChange={setDeliveryBabyWeight}
                        />
                    ) : null}
                    <ChangeStageWarnings
                        label={label}
                        isBackdated={isBackdated}
                        isRegression={isRegression}
                        requiresApproval={requiresApproval}
                        canSelfApproveRegression={canSelfApproveRegression}
                    />
                    {reasonRequired ? (
                        <ReasonField reason={reason} onReasonChange={setReason} />
                    ) : null}
                </div>

                <ChangeStageActions
                    isPending={isPending}
                    canSubmit={canSubmit}
                    submitButtonText={submitButtonText}
                    submitButtonLoadingText={submitButtonLoadingText}
                    onCancel={handleClose}
                    onSubmit={() => void handleSubmit()}
                />
            </DialogContent>
        </Dialog>
    )
}
