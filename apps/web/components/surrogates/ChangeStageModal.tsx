"use client"

import { useReducer, useState } from "react"
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
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import {
    stageHasCapability,
    stageMatchesKey,
    stageRequiresReasonOnEnter,
    stageUsesPauseBehavior,
} from "@/lib/surrogate-stage-context"
import { cn } from "@/lib/utils"
import type { PipelineStage } from "@/lib/api/pipelines"

type InterviewMeridiem = "AM" | "PM"
type FollowUpMonths = "none" | "1" | "3" | "6"

type InterviewState = {
    date: Date | undefined
    datePickerOpen: boolean
    hourInput: string
    minuteInput: string
    meridiem: InterviewMeridiem
}

type InterviewAction =
    | { type: "reset" }
    | { type: "setDate"; date: Date | undefined }
    | { type: "setDatePickerOpen"; open: boolean }
    | { type: "setHourInput"; value: string }
    | { type: "setMinuteInput"; value: string }
    | { type: "normalizeHour" }
    | { type: "normalizeMinute" }
    | { type: "toggleMeridiem" }

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

function normalizeInterviewTime(
    hourInput: string,
    minuteInput: string,
    meridiem: InterviewMeridiem,
): string | null {
    const hourText = hourInput.trim()
    const minuteText = minuteInput.trim()
    if (!/^\d{1,2}$/.test(hourText) || !/^\d{1,2}$/.test(minuteText)) return null

    let hour = Number(hourText)
    const minute = Number(minuteText)
    if (hour < 1 || hour > 12 || minute < 0 || minute > 59) return null

    if (meridiem === "PM" && hour !== 12) hour += 12
    if (meridiem === "AM" && hour === 12) hour = 0

    return `${hour.toString().padStart(2, "0")}:${minute.toString().padStart(2, "0")}`
}

function firstDigitGroup(value: string): string {
    return value.match(/\d+/)?.[0] ?? ""
}

function interviewStateReducer(state: InterviewState, action: InterviewAction): InterviewState {
    if (action.type === "reset") {
        return {
            date: undefined,
            datePickerOpen: false,
            hourInput: "",
            minuteInput: "",
            meridiem: "PM",
        }
    }

    if (action.type === "setDate") {
        return { ...state, date: action.date }
    }

    if (action.type === "setDatePickerOpen") {
        return { ...state, datePickerOpen: action.open }
    }

    if (action.type === "setHourInput") {
        const digitGroups = action.value.match(/\d+/g) ?? []
        return {
            ...state,
            hourInput: (digitGroups[0] ?? "").slice(0, 2),
            minuteInput: digitGroups.length > 1
                ? (digitGroups[1] ?? "").slice(0, 2)
                : state.minuteInput,
        }
    }

    if (action.type === "setMinuteInput") {
        return { ...state, minuteInput: firstDigitGroup(action.value).slice(0, 2) }
    }

    if (action.type === "normalizeHour") {
        const hour = Number(state.hourInput)
        if (state.hourInput && hour >= 1 && hour <= 12) {
            return { ...state, hourInput: hour.toString() }
        }
        return state
    }

    if (action.type === "normalizeMinute") {
        const minute = Number(state.minuteInput)
        if (state.minuteInput && minute >= 0 && minute <= 59) {
            return { ...state, minuteInput: minute.toString().padStart(2, "0") }
        }
        return state
    }

    return { ...state, meridiem: state.meridiem === "AM" ? "PM" : "AM" }
}

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
                        <button
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
                        </button>
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
                        <button
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
                        </button>
                    )
                })}
            </div>
        </div>
    )
}

function InterviewAppointmentSection({
    interviewDate,
    interviewDatePickerOpen,
    interviewDateDefaultMonth,
    calendarStartOfToday,
    interviewHourInput,
    interviewMinuteInput,
    interviewMeridiem,
    interviewTimeInvalid,
    onInterviewDateChange,
    onInterviewDatePickerOpenChange,
    onInterviewHourInputChange,
    onInterviewMinuteInputChange,
    onInterviewHourInputBlur,
    onInterviewMinuteInputBlur,
    onInterviewMeridiemToggle,
}: {
    interviewDate: Date | undefined
    interviewDatePickerOpen: boolean
    interviewDateDefaultMonth: Date
    calendarStartOfToday: Date | undefined
    interviewHourInput: string
    interviewMinuteInput: string
    interviewMeridiem: InterviewMeridiem
    interviewTimeInvalid: boolean
    onInterviewDateChange: (date: Date | undefined) => void
    onInterviewDatePickerOpenChange: (open: boolean) => void
    onInterviewHourInputChange: (value: string) => void
    onInterviewMinuteInputChange: (value: string) => void
    onInterviewHourInputBlur: () => void
    onInterviewMinuteInputBlur: () => void
    onInterviewMeridiemToggle: () => void
}) {
    return (
        <section aria-label="Interview appointment" className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
                <div className="text-sm font-medium text-foreground">
                    Interview appointment
                </div>
                <p className="text-xs text-muted-foreground">
                    Select the date and time for the interview appointment.
                </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-2">
                    <Label>
                        Interview date <span className="text-destructive">*</span>
                    </Label>
                    <Popover open={interviewDatePickerOpen} onOpenChange={onInterviewDatePickerOpenChange}>
                        <PopoverTrigger
                            className={cn(
                                "inline-flex h-9 w-full items-center justify-start gap-2 rounded-md border border-input bg-input/30 px-3 py-2 text-sm font-normal transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                                !interviewDate && "text-muted-foreground",
                            )}
                        >
                            <CalendarIcon className="size-4" />
                            {interviewDate ? format(interviewDate, "PPP") : "Select date"}
                        </PopoverTrigger>
                        <PopoverContent className="w-auto p-0" align="start">
                            <Calendar
                                mode="single"
                                selected={interviewDate}
                                onSelect={(date) => {
                                    onInterviewDateChange(date)
                                    onInterviewDatePickerOpenChange(false)
                                }}
                                {...(calendarStartOfToday ? { disabled: (date: Date) => date < calendarStartOfToday } : {})}
                                defaultMonth={interviewDateDefaultMonth}
                            />
                        </PopoverContent>
                    </Popover>
                </div>
                <div className="space-y-2">
                    <Label>
                        Interview time <span className="text-destructive">*</span>
                    </Label>
                    <div className="grid grid-cols-[4.5rem_4.5rem_3.5rem] items-end gap-2">
                        <div className="relative">
                            <Input
                                id="interview-hour"
                                value={interviewHourInput}
                                onChange={(event) => onInterviewHourInputChange(event.target.value)}
                                onBlur={onInterviewHourInputBlur}
                                inputMode="numeric"
                                pattern="[0-9]*"
                                className="text-center text-base"
                                aria-label="Interview hour"
                                aria-invalid={interviewTimeInvalid}
                            />
                            {!interviewHourInput ? (
                                <span className="pointer-events-none absolute inset-0 flex items-center justify-center text-base text-muted-foreground">
                                    1
                                </span>
                            ) : null}
                        </div>
                        <div className="relative">
                            <Input
                                id="interview-minute"
                                value={interviewMinuteInput}
                                onChange={(event) => onInterviewMinuteInputChange(event.target.value)}
                                onBlur={onInterviewMinuteInputBlur}
                                inputMode="numeric"
                                pattern="[0-9]*"
                                className="text-center text-base"
                                aria-label="Interview minute"
                                aria-invalid={interviewTimeInvalid}
                            />
                            {!interviewMinuteInput ? (
                                <span className="pointer-events-none absolute inset-0 flex items-center justify-center text-base text-muted-foreground">
                                    15
                                </span>
                            ) : null}
                        </div>
                        <div>
                            <Button
                                type="button"
                                onClick={onInterviewMeridiemToggle}
                                aria-label={`Switch interview time to ${interviewMeridiem === "AM" ? "PM" : "AM"}`}
                                variant="outline"
                                size="sm"
                                className="h-9 w-full px-0 text-sm font-medium"
                            >
                                {interviewMeridiem}
                            </Button>
                        </div>
                    </div>
                    {interviewTimeInvalid ? (
                        <p className="text-xs text-destructive">
                            Enter an hour from 1-12 and minutes from 00-59.
                        </p>
                    ) : null}
                </div>
            </div>
        </section>
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
    const [interviewState, dispatchInterviewState] = useReducer(interviewStateReducer, {
        date: undefined,
        datePickerOpen: false,
        hourInput: "",
        minuteInput: "",
        meridiem: "PM",
    })
    const [calendarToday] = useState(() => new Date())
    const calendarStartOfToday = startOfDay(calendarToday)
    const selectedDateDefaultMonth = selectedDate ?? calendarToday
    const interviewDate = interviewState.date
    const interviewDatePickerOpen = interviewState.datePickerOpen
    const interviewHourInput = interviewState.hourInput
    const interviewMinuteInput = interviewState.minuteInput
    const interviewMeridiem = interviewState.meridiem
    const interviewDateDefaultMonth = interviewDate ?? calendarToday

    const currentStage = stages.find(s => s.id === currentStageId)
    const comparisonStage =
        stages.find((stage) => stage.id === (comparisonStageId ?? currentStageId)) ?? currentStage

    const selectedStage = stages.find(s => s.id === selectedStageId)
    const isDeliveredStage = stageHasCapability(selectedStage, "requires_delivery_details")
    const isOnHoldStage = stageUsesPauseBehavior(selectedStage)
    const isInterviewScheduledStage = stageMatchesKey(selectedStage, "interview_scheduled")
    const showDeliveryFields = deliveryFieldsEnabled && isDeliveredStage
    const interviewTime = normalizeInterviewTime(interviewHourInput, interviewMinuteInput, interviewMeridiem)
    const interviewTimeStarted = interviewHourInput.trim().length > 0 || interviewMinuteInput.trim().length > 0
    const interviewTimeInvalid = isInterviewScheduledStage && interviewTimeStarted && !interviewTime
    const interviewDateTime = isInterviewScheduledStage && interviewDate && interviewTime
        ? `${format(interviewDate, "yyyy-MM-dd")}T${interviewTime}:00`
        : null

    const isResumeSelection = (() => {
        if (!selectedStage || !currentStage || !comparisonStage) return false
        return stageUsesPauseBehavior(currentStage) && selectedStage.id === comparisonStage.id
    })()

    const isRegression = (() => {
        if (!selectedStage || !comparisonStage) return false
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
    const resetInterviewFields = () => {
        dispatchInterviewState({ type: "reset" })
    }
    const handleStageSelect = (stage: PipelineStage) => {
        setSelectedStageId(stage.id)
        if (stageMatchesKey(stage, "interview_scheduled")) {
            resetInterviewFields()
        }
    }
    const updateInterviewHourInput = (value: string) => {
        dispatchInterviewState({ type: "setHourInput", value })
    }
    const updateInterviewMinuteInput = (value: string) => {
        dispatchInterviewState({ type: "setMinuteInput", value })
    }
    const normalizeInterviewHourInput = () => {
        dispatchInterviewState({ type: "normalizeHour" })
    }
    const normalizeInterviewMinuteInput = () => {
        dispatchInterviewState({ type: "normalizeMinute" })
    }
    const toggleInterviewMeridiem = () => {
        dispatchInterviewState({ type: "toggleMeridiem" })
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
                className="flex max-h-[calc(100dvh-2rem)] w-[calc(100vw-2rem)] max-w-lg flex-col gap-0 overflow-hidden p-0 sm:max-w-lg md:max-w-xl"
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
                    {isInterviewScheduledStage ? (
                        <InterviewAppointmentSection
                            interviewDate={interviewDate}
                            interviewDatePickerOpen={interviewDatePickerOpen}
                            interviewDateDefaultMonth={interviewDateDefaultMonth}
                            calendarStartOfToday={calendarStartOfToday}
                            interviewHourInput={interviewHourInput}
                            interviewMinuteInput={interviewMinuteInput}
                            interviewMeridiem={interviewMeridiem}
                            interviewTimeInvalid={interviewTimeInvalid}
                            onInterviewDateChange={(date) => dispatchInterviewState({ type: "setDate", date })}
                            onInterviewDatePickerOpenChange={(open) => dispatchInterviewState({ type: "setDatePickerOpen", open })}
                            onInterviewHourInputChange={updateInterviewHourInput}
                            onInterviewMinuteInputChange={updateInterviewMinuteInput}
                            onInterviewHourInputBlur={normalizeInterviewHourInput}
                            onInterviewMinuteInputBlur={normalizeInterviewMinuteInput}
                            onInterviewMeridiemToggle={toggleInterviewMeridiem}
                        />
                    ) : null}
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
