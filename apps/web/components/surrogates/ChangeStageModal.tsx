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
import { cn } from "@/lib/utils"
import type { PipelineStage } from "@/lib/api/pipelines"

interface ChangeStageModalProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    stages: PipelineStage[]
    currentStageId: string
    currentStageLabel: string
    entityLabel?: string
    onSubmit: (data: {
        stage_id: string
        reason?: string
        effective_at?: string // ISO datetime
    }) => Promise<{ status: "applied" | "pending_approval"; request_id?: string }>
    isPending?: boolean
}

export function ChangeStageModal({
    open,
    onOpenChange,
    stages,
    currentStageId,
    currentStageLabel,
    entityLabel,
    onSubmit,
    isPending = false,
}: ChangeStageModalProps) {
    // State
    const [selectedStageId, setSelectedStageId] = useState<string | null>(null)
    const [effectiveNow, setEffectiveNow] = useState(true)
    const [selectedDate, setSelectedDate] = useState<Date | undefined>(undefined)
    const [selectedTime, setSelectedTime] = useState("")
    const [reason, setReason] = useState("")
    const [datePickerOpen, setDatePickerOpen] = useState(false)

    // Reset state when modal opens
    useEffect(() => {
        if (open) {
            setSelectedStageId(null)
            setEffectiveNow(true)
            setSelectedDate(undefined)
            setSelectedTime("")
            setReason("")
        }
    }, [open])

    // Get the current stage order
    const currentStage = useMemo(
        () => stages.find(s => s.id === currentStageId),
        [stages, currentStageId]
    )

    // Get selected stage
    const selectedStage = useMemo(
        () => stages.find(s => s.id === selectedStageId),
        [stages, selectedStageId]
    )

    // Calculate if this is a regression (moving to earlier stage)
    const isRegression = useMemo(() => {
        if (!selectedStage || !currentStage) return false
        return selectedStage.order < currentStage.order
    }, [selectedStage, currentStage])

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
    const reasonRequired = isRegression || isBackdated

    // Validation
    const canSubmit = useMemo(() => {
        if (!selectedStageId) return false
        if (selectedStageId === currentStageId) return false
        if (!effectiveNow && !selectedDate) return false
        if (reasonRequired && !reason.trim()) return false
        return true
    }, [selectedStageId, currentStageId, effectiveNow, selectedDate, reasonRequired, reason])

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

        const payload: { stage_id: string; reason?: string; effective_at?: string } = {
            stage_id: selectedStageId,
        }
        const trimmedReason = reason.trim()
        if (trimmedReason) payload.reason = trimmedReason
        if (effective_at) payload.effective_at = effective_at

        await onSubmit(payload)
    }

    // Close handler
    const handleClose = () => {
        if (!isPending) {
            onOpenChange(false)
        }
    }

    const label = entityLabel ?? "Stage"

    // Button text based on context
    const submitButtonText = isRegression ? "Request Approval" : "Save Change"
    const submitButtonLoadingText = isRegression ? "Requesting..." : "Saving..."

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
                    {isRegression && (
                        <Alert className="border-amber-500/30 bg-amber-500/5">
                            <AlertTriangleIcon className="size-4 text-amber-600" />
                            <AlertTitle className="text-amber-600">Admin Approval Required</AlertTitle>
                            <AlertDescription className="text-amber-600/80">
                                Moving to an earlier {label.toLowerCase()} requires admin approval.
                                Your request will be submitted for review.
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
