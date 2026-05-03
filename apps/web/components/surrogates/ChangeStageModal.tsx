"use client"

import { useState, useMemo, useEffect } from "react"
import { format, startOfDay, isBefore } from "date-fns"
import {
    AlertCircleIcon,
    AlertTriangleIcon,
    CalendarIcon,
    ClockIcon,
    Loader2Icon,
    CheckIcon
} from "lucide-react"

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
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { Calendar } from "@/components/ui/calendar"
import { Input } from "@/components/ui/input"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import {
    stageHasCapability,
    stageMatchesKey,
    stageRequiresReasonOnEnter,
    stageUsesPauseBehavior,
} from "@/lib/surrogate-stage-context"
import { cn } from "@/lib/utils"
import type { PipelineStage } from "@/lib/api/pipelines"

type InterviewMeridiem = "AM" | "PM"

function normalizeInterviewTime(
    hourInput: string,
    minuteInput: string,
    meridiem: InterviewMeridiem
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

export function ChangeStageModal({
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
    // State
    const [selectedStageId, setSelectedStageId] = useState<string | null>(null)
    const [effectiveNow, setEffectiveNow] = useState(true)
    const [selectedDate, setSelectedDate] = useState<Date | undefined>(undefined)
    const [selectedTime, setSelectedTime] = useState("")
    const [reason, setReason] = useState("")
    const [datePickerOpen, setDatePickerOpen] = useState(false)
    const [interviewDatePickerOpen, setInterviewDatePickerOpen] = useState(false)
    const [deliveryBabyGender, setDeliveryBabyGender] = useState("")
    const [deliveryBabyWeight, setDeliveryBabyWeight] = useState("")
    const [onHoldFollowUpMonths, setOnHoldFollowUpMonths] = useState<"none" | "1" | "3" | "6">("none")
    const [interviewDate, setInterviewDate] = useState<Date | undefined>(undefined)
    const [interviewHourInput, setInterviewHourInput] = useState("")
    const [interviewMinuteInput, setInterviewMinuteInput] = useState("")
    const [interviewMeridiem, setInterviewMeridiem] = useState<InterviewMeridiem>("PM")

    // Reset state when modal opens
    useEffect(() => {
        if (open) {
            setSelectedStageId(null)
            setEffectiveNow(true)
            setSelectedDate(undefined)
            setSelectedTime("")
            setReason("")
            setDeliveryBabyGender(initialDeliveryBabyGender ?? "")
            setDeliveryBabyWeight(initialDeliveryBabyWeight ?? "")
            setOnHoldFollowUpMonths("none")
            setInterviewDate(undefined)
            setInterviewHourInput("")
            setInterviewMinuteInput("")
            setInterviewMeridiem("PM")
            setInterviewDatePickerOpen(false)
        }
    }, [open, initialDeliveryBabyGender, initialDeliveryBabyWeight])

    // Get the current stage order
    const currentStage = useMemo(
        () => stages.find(s => s.id === currentStageId),
        [stages, currentStageId]
    )
    const comparisonStage = useMemo(
        () => stages.find((stage) => stage.id === (comparisonStageId ?? currentStageId)) ?? currentStage,
        [stages, comparisonStageId, currentStageId, currentStage]
    )

    // Get selected stage
    const selectedStage = useMemo(
        () => stages.find(s => s.id === selectedStageId),
        [stages, selectedStageId]
    )
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

    const isResumeSelection = useMemo(() => {
        if (!selectedStage || !currentStage || !comparisonStage) return false
        return stageUsesPauseBehavior(currentStage) && selectedStage.id === comparisonStage.id
    }, [selectedStage, currentStage, comparisonStage])

    // Calculate if this is a regression (moving to earlier stage)
    const isRegression = useMemo(() => {
        if (!selectedStage || !comparisonStage) return false
        return !isResumeSelection && selectedStage.order < comparisonStage.order
    }, [selectedStage, comparisonStage, isResumeSelection])
    const requiresApproval = isRegression && !canSelfApproveRegression

    const hasTime = selectedTime.trim().length > 0
    const effectiveDateTime = useMemo(() => {
        if (effectiveNow || !selectedDate || !hasTime) return null
        const dateWithTime = new Date(selectedDate)
        const [hours, minutes] = selectedTime.split(":").map(Number)
        dateWithTime.setHours(hours || 0, minutes || 0, 0, 0)
        return dateWithTime
    }, [effectiveNow, selectedDate, selectedTime, hasTime])

    // Calculate if this is backdated (past date/time)
    const isBackdated = useMemo(() => {
        if (effectiveNow) return false
        if (!selectedDate) return false
        if (!hasTime) {
            const today = startOfDay(new Date())
            const selected = startOfDay(selectedDate)
            return isBefore(selected, today)
        }
        if (!effectiveDateTime) return false
        return isBefore(effectiveDateTime, new Date())
    }, [effectiveNow, selectedDate, hasTime, effectiveDateTime])

    // Check if reason is required
    const reasonRequired =
        isRegression || isBackdated || stageRequiresReasonOnEnter(selectedStage)

    // Validation
    const canSubmit = useMemo(() => {
        if (!selectedStageId) return false
        if (selectedStageId === currentStageId) return false
        if (!effectiveNow && !selectedDate) return false
        if (isInterviewScheduledStage && !interviewDateTime) return false
        if (reasonRequired && !reason.trim()) return false
        return true
    }, [selectedStageId, currentStageId, effectiveNow, selectedDate, isInterviewScheduledStage, interviewDateTime, reasonRequired, reason])

    // Build effective_at ISO string
    const buildEffectiveAt = (): string | undefined => {
        if (effectiveNow) return undefined
        if (!selectedDate) return undefined

        const datePart = format(selectedDate, "yyyy-MM-dd")
        if (!hasTime) {
            return `${datePart}T00:00:00`
        }
        return `${datePart}T${selectedTime}:00`
    }

    // Submit handler
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

    // Close handler
    const handleClose = () => {
        if (!isPending) {
            onOpenChange(false)
        }
    }

    const label = entityLabel ?? "Stage"
    const updateInterviewHourInput = (value: string) => {
        const digitGroups = value.match(/\d+/g) ?? []
        setInterviewHourInput((digitGroups[0] ?? "").slice(0, 2))
        if (digitGroups.length > 1) {
            setInterviewMinuteInput((digitGroups[1] ?? "").slice(0, 2))
        }
    }
    const updateInterviewMinuteInput = (value: string) => {
        setInterviewMinuteInput(firstDigitGroup(value).slice(0, 2))
    }
    const normalizeInterviewHourInput = () => {
        const hour = Number(interviewHourInput)
        if (interviewHourInput && hour >= 1 && hour <= 12) {
            setInterviewHourInput(hour.toString())
        }
    }
    const normalizeInterviewMinuteInput = () => {
        const minute = Number(interviewMinuteInput)
        if (interviewMinuteInput && minute >= 0 && minute <= 59) {
            setInterviewMinuteInput(minute.toString().padStart(2, "0"))
        }
    }

    // Button text based on context
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

    // Filter active stages and sort by order
    const sortedStages = useMemo(
        () => [...stages].filter(s => s.is_active).sort((a, b) => a.order - b.order),
        [stages]
    )

    return (
        <Dialog open={open} onOpenChange={handleClose}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>Change {label}</DialogTitle>
                    <DialogDescription>
                        Current: {currentStageLabel}
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-5">
                    {/* Stage Selector */}
                    <div className="space-y-2">
                        <Label>New {label}</Label>
                        <div className="grid gap-1.5 max-h-64 overflow-y-auto pr-1">
                            {sortedStages.map((stage) => {
                                const isCurrent = stage.id === currentStageId
                                const isSelected = stage.id === selectedStageId

                                return (
                                    <button
                                        key={stage.id}
                                        type="button"
                                        disabled={isCurrent}
                                        onClick={() => setSelectedStageId(stage.id)}
                                        className={cn(
                                            "flex items-center gap-3 px-3 py-2.5 rounded-lg text-left text-sm transition-colors",
                                            "hover:bg-muted/50 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                                            isSelected && "bg-primary/10 ring-1 ring-primary/30",
                                            isCurrent && "opacity-50 cursor-not-allowed bg-muted/30"
                                        )}
                                    >
                                        {/* Color dot */}
                                        <div
                                            className="size-3 rounded-full shrink-0 ring-1 ring-black/10"
                                            style={{ backgroundColor: stage.color }}
                                        />

                                        {/* Label */}
                                        <span className="flex-1 font-medium">{stage.label}</span>

                                        {/* Current indicator */}
                                        {isCurrent && (
                                            <span className="text-xs text-muted-foreground">Current</span>
                                        )}

                                        {/* Selected checkmark */}
                                        {isSelected && (
                                            <CheckIcon className="size-4 text-primary" />
                                        )}
                                    </button>
                                )
                            })}
                        </div>
                    </div>

                    {/* Effective Now Toggle */}
                    <div className="flex items-center justify-between">
                        <Label htmlFor="effective-now" className="cursor-pointer">
                            Effective now
                        </Label>
                        <Switch
                            id="effective-now"
                            checked={effectiveNow}
                            onCheckedChange={setEffectiveNow}
                        />
                    </div>

                    {/* Date/Time Picker (when not effective now) */}
                    {!effectiveNow && (
                        <div className="space-y-3">
                            <div className="space-y-2">
                                <Label>Effective Date</Label>
                                <Popover open={datePickerOpen} onOpenChange={setDatePickerOpen}>
                                    <PopoverTrigger
                                        className={cn(
                                            "inline-flex w-full items-center justify-start gap-2 rounded-md border border-input bg-background px-3 py-2 text-sm font-normal hover:bg-accent hover:text-accent-foreground",
                                            !selectedDate && "text-muted-foreground"
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
                                                setSelectedDate(date)
                                                setDatePickerOpen(false)
                                            }}
                                            disabled={(date) => date > new Date()}
                                            defaultMonth={selectedDate || new Date()}
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
                                    onChange={(e) => setSelectedTime(e.target.value)}
                                    className="w-full"
                                />
                                <p className="text-xs text-muted-foreground">
                                    Leave blank to use now (today) or noon (past dates)
                                </p>
                            </div>
                        </div>
                    )}

                    {isOnHoldStage && (
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
                                    task assigned to {onHoldFollowUpAssigneeLabel ?? "the current owner"}.
                                </p>
                            </div>
                            <div className="grid gap-2 sm:grid-cols-2">
                                {[
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
                                ].map((option) => {
                                    const isSelected = onHoldFollowUpMonths === option.value
                                    return (
                                        <button
                                            key={option.value}
                                            type="button"
                                            onClick={() => setOnHoldFollowUpMonths(option.value as "none" | "1" | "3" | "6")}
                                            className={cn(
                                                "rounded-lg border px-3 py-3 text-left transition-colors",
                                                "hover:border-primary/40 hover:bg-background/80",
                                                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                                                isSelected
                                                    ? "border-primary bg-background shadow-sm"
                                                    : "border-border/70 bg-background/40"
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
                    )}

                    {isInterviewScheduledStage && (
                        <div className="space-y-3 rounded-lg border border-muted/60 bg-muted/20 p-3">
                            <div className="space-y-1">
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
                                    <Popover open={interviewDatePickerOpen} onOpenChange={setInterviewDatePickerOpen}>
                                        <PopoverTrigger
                                            className={cn(
                                                "inline-flex h-9 w-full items-center justify-start gap-2 rounded-md border border-input bg-input/30 px-3 py-2 text-sm font-normal transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                                                !interviewDate && "text-muted-foreground"
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
                                                    setInterviewDate(date)
                                                    setInterviewDatePickerOpen(false)
                                                }}
                                                disabled={(date) => date < startOfDay(new Date())}
                                                defaultMonth={interviewDate || new Date()}
                                            />
                                        </PopoverContent>
                                    </Popover>
                                </div>
                                <div className="space-y-2">
                                    <Label>
                                        Interview time <span className="text-destructive">*</span>
                                    </Label>
                                    <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] items-end gap-2">
                                        <div className="space-y-1">
                                            <Label htmlFor="interview-hour" className="text-xs text-muted-foreground">
                                                Hour
                                            </Label>
                                            <Input
                                                id="interview-hour"
                                                value={interviewHourInput}
                                                onChange={(event) => updateInterviewHourInput(event.target.value)}
                                                onBlur={normalizeInterviewHourInput}
                                                placeholder="1"
                                                inputMode="numeric"
                                                pattern="[0-9]*"
                                                maxLength={5}
                                                className="text-center"
                                                aria-label="Interview hour"
                                                aria-invalid={interviewTimeInvalid}
                                            />
                                        </div>
                                        <div className="space-y-1">
                                            <Label htmlFor="interview-minute" className="text-xs text-muted-foreground">
                                                Minute
                                            </Label>
                                            <Input
                                                id="interview-minute"
                                                value={interviewMinuteInput}
                                                onChange={(event) => updateInterviewMinuteInput(event.target.value)}
                                                onBlur={normalizeInterviewMinuteInput}
                                                placeholder="35"
                                                inputMode="numeric"
                                                pattern="[0-9]*"
                                                maxLength={2}
                                                className="text-center"
                                                aria-label="Interview minute"
                                                aria-invalid={interviewTimeInvalid}
                                            />
                                        </div>
                                        <div className="space-y-1">
                                            <Label id="interview-meridiem-label" className="text-xs text-muted-foreground">
                                                AM/PM
                                            </Label>
                                            <ToggleGroup
                                                value={[interviewMeridiem]}
                                                onValueChange={(value) => {
                                                    const nextValue = Array.isArray(value) ? value[0] : value
                                                    if (nextValue === "AM" || nextValue === "PM") {
                                                        setInterviewMeridiem(nextValue)
                                                    }
                                                }}
                                                aria-labelledby="interview-meridiem-label"
                                                variant="outline"
                                                size="sm"
                                                spacing={0}
                                                className="h-9"
                                            >
                                                <ToggleGroupItem value="AM" className="h-9 px-3">AM</ToggleGroupItem>
                                                <ToggleGroupItem value="PM" className="h-9 px-3">PM</ToggleGroupItem>
                                            </ToggleGroup>
                                        </div>
                                    </div>
                                    {interviewTimeInvalid && (
                                        <p className="text-xs text-destructive">
                                            Enter an hour from 1-12 and minutes from 00-59.
                                        </p>
                                    )}
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Delivery details (only when moving to Delivered) */}
                    {showDeliveryFields && (
                        <div className="space-y-3 rounded-lg border border-muted/60 bg-muted/20 p-3">
                            <div className="text-sm font-medium text-foreground">Delivery details</div>
                            <div className="grid gap-3 sm:grid-cols-2">
                                <div className="space-y-2">
                                    <Label htmlFor="delivery-baby-gender">Baby gender</Label>
                                    <Input
                                        id="delivery-baby-gender"
                                        value={deliveryBabyGender}
                                        onChange={(e) => setDeliveryBabyGender(e.target.value)}
                                        placeholder="Optional"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="delivery-baby-weight">Baby weight</Label>
                                    <Input
                                        id="delivery-baby-weight"
                                        value={deliveryBabyWeight}
                                        onChange={(e) => setDeliveryBabyWeight(e.target.value)}
                                        placeholder="Optional"
                                    />
                                </div>
                            </div>
                            <p className="text-xs text-muted-foreground">
                                These fields sync to the pregnancy tracker after delivery.
                            </p>
                        </div>
                    )}

                    {/* Backdating Info Banner */}
                    {isBackdated && !isRegression && (
                        <Alert className="border-blue-500/30 bg-blue-500/5">
                            <AlertCircleIcon className="size-4 text-blue-600" />
                            <AlertTitle className="text-blue-600">Backdated Change</AlertTitle>
                            <AlertDescription className="text-blue-600/80">
                                This change will be recorded with a past effective date.
                                A reason is required for audit purposes.
                            </AlertDescription>
                        </Alert>
                    )}

                    {/* Regression Warning Banner */}
                    {requiresApproval && (
                        <Alert className="border-amber-500/30 bg-amber-500/5">
                            <AlertTriangleIcon className="size-4 text-amber-600" />
                            <AlertTitle className="text-amber-600">Admin Approval Required</AlertTitle>
                            <AlertDescription className="text-amber-600/80">
                                Moving to an earlier {label.toLowerCase()} requires admin approval.
                                Your request will be submitted for review.
                            </AlertDescription>
                        </Alert>
                    )}

                    {isRegression && canSelfApproveRegression && (
                        <Alert className="border-blue-500/30 bg-blue-500/5">
                            <AlertCircleIcon className="size-4 text-blue-600" />
                            <AlertTitle className="text-blue-600">Earlier Stage Change</AlertTitle>
                            <AlertDescription className="text-blue-600/80">
                                You can apply this earlier stage change immediately.
                                A reason is still required for audit purposes.
                            </AlertDescription>
                        </Alert>
                    )}

                    {/* Reason Field (required for backdate/regression) */}
                    {reasonRequired && (
                        <div className="space-y-2">
                            <Label htmlFor="reason">
                                Reason <span className="text-destructive">*</span>
                            </Label>
                            <Textarea
                                id="reason"
                                placeholder="Why is this change being made?"
                                value={reason}
                                onChange={(e) => setReason(e.target.value)}
                                rows={3}
                                className="resize-none"
                            />
                        </div>
                    )}
                </div>

                <DialogFooter className="mt-2">
                    <Button
                        variant="outline"
                        onClick={handleClose}
                        disabled={isPending}
                    >
                        Cancel
                    </Button>
                    <Button
                        onClick={handleSubmit}
                        disabled={!canSubmit || isPending}
                    >
                        {isPending ? (
                            <>
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                                {submitButtonLoadingText}
                            </>
                        ) : (
                            submitButtonText
                        )}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
