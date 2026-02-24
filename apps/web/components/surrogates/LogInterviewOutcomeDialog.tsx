"use client"

import * as React from "react"
import { useState } from "react"
import { Loader2Icon, CalendarIcon } from "lucide-react"
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
import { Textarea } from "@/components/ui/textarea"
import { Input } from "@/components/ui/input"
import { Checkbox } from "@/components/ui/checkbox"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { useLogInterviewOutcome } from "@/lib/hooks/use-surrogates"
import type { InterviewOutcome, InterviewOutcomeCreatePayload } from "@/lib/api/surrogates"
import { toast } from "sonner"

interface LogInterviewOutcomeDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    surrogateId: string | null
    surrogateName?: string
    appointmentId?: string
}

const INTERVIEW_OUTCOMES: { value: InterviewOutcome; label: string; description: string }[] = [
    { value: "completed", label: "Completed", description: "Interview was completed" },
    { value: "no_show", label: "No Show", description: "Surrogate did not attend" },
    { value: "rescheduled", label: "Rescheduled", description: "Interview moved to another time" },
    { value: "cancelled", label: "Cancelled", description: "Interview was cancelled" },
]

export function LogInterviewOutcomeDialog({
    open,
    onOpenChange,
    surrogateId,
    surrogateName = "surrogate",
    appointmentId,
}: LogInterviewOutcomeDialogProps) {
    const [outcome, setOutcome] = useState<InterviewOutcome | "">("")
    const [notes, setNotes] = useState("")
    const [isBackdating, setIsBackdating] = useState(false)
    const [occurredAt, setOccurredAt] = useState("")

    const logInterviewOutcome = useLogInterviewOutcome()

    const maxLocalDateTime = React.useMemo(() => {
        const now = new Date()
        const offsetMs = now.getTimezoneOffset() * 60 * 1000
        return new Date(now.getTime() - offsetMs).toISOString().slice(0, 16)
    }, [])

    const isAppointmentUnlinked = !!appointmentId && !surrogateId

    const resetForm = () => {
        setOutcome("")
        setNotes("")
        setIsBackdating(false)
        setOccurredAt("")
    }

    const handleCancel = () => {
        resetForm()
        onOpenChange(false)
    }

    const handleOpenChange = (isOpen: boolean) => {
        if (!isOpen) {
            resetForm()
        }
        onOpenChange(isOpen)
    }

    const handleSubmit = async () => {
        if (!surrogateId || !outcome) return

        try {
            const data: InterviewOutcomeCreatePayload = { outcome }
            const trimmedNotes = notes.trim()
            if (trimmedNotes) {
                data.notes = trimmedNotes
            }
            if (isBackdating && occurredAt) {
                data.occurred_at = new Date(occurredAt).toISOString()
            }
            if (appointmentId) {
                data.appointment_id = appointmentId
            }

            await logInterviewOutcome.mutateAsync({
                surrogateId,
                data,
            })

            toast.success("Interview outcome logged")
            resetForm()
            onOpenChange(false)
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to log interview outcome")
        }
    }

    const isValid = Boolean(outcome) && (!isBackdating || Boolean(occurredAt))
    const canSubmit = !isAppointmentUnlinked && Boolean(surrogateId) && isValid

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                    <DialogTitle>Log Interview Outcome</DialogTitle>
                    <DialogDescription>
                        Record interview outcome details for {surrogateName}.
                    </DialogDescription>
                </DialogHeader>

                <div className="grid gap-4 py-4">
                    {isAppointmentUnlinked && (
                        <div className="rounded-md border border-amber-300/60 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                            Link surrogate first
                        </div>
                    )}

                    <div className="grid gap-2">
                        <Label htmlFor="interview-outcome">Outcome</Label>
                        <Select
                            value={outcome}
                            onValueChange={(value) => setOutcome(value as InterviewOutcome)}
                        >
                            <SelectTrigger id="interview-outcome">
                                <SelectValue placeholder="Select outcome..." />
                            </SelectTrigger>
                            <SelectContent>
                                {INTERVIEW_OUTCOMES.map((item) => (
                                    <SelectItem key={item.value} value={item.value}>
                                        <div className="flex flex-col">
                                            <span>{item.label}</span>
                                            <span className="text-xs text-muted-foreground">
                                                {item.description}
                                            </span>
                                        </div>
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    <div className="grid gap-2">
                        <Label htmlFor="interview-notes">Notes (optional)</Label>
                        <Textarea
                            id="interview-notes"
                            placeholder="Add any relevant details..."
                            value={notes}
                            onChange={(event) => setNotes(event.target.value)}
                            rows={3}
                            className="resize-none"
                        />
                    </div>

                    <div className="grid gap-2">
                        <div className="flex items-center gap-2">
                            <Checkbox
                                id="interview-outcome-backdate"
                                checked={isBackdating}
                                onCheckedChange={(checked) => setIsBackdating(checked === true)}
                            />
                            <Label htmlFor="interview-outcome-backdate" className="cursor-pointer">
                                Log for a different date/time
                            </Label>
                        </div>
                        {isBackdating && (
                            <div className="flex items-center gap-2">
                                <CalendarIcon className="h-4 w-4 text-muted-foreground" />
                                <div className="grid flex-1 gap-1">
                                    <Label htmlFor="interview-occurred-at">Occurred at</Label>
                                    <Input
                                        id="interview-occurred-at"
                                        type="datetime-local"
                                        value={occurredAt}
                                        onChange={(event) => setOccurredAt(event.target.value)}
                                        max={maxLocalDateTime}
                                    />
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                <DialogFooter>
                    <Button
                        variant="outline"
                        onClick={handleCancel}
                        disabled={logInterviewOutcome.isPending}
                    >
                        Cancel
                    </Button>
                    <Button
                        onClick={handleSubmit}
                        disabled={!canSubmit || logInterviewOutcome.isPending}
                        className="gap-2"
                    >
                        {logInterviewOutcome.isPending ? (
                            <>
                                <Loader2Icon className="h-4 w-4 animate-spin" />
                                Logging...
                            </>
                        ) : (
                            <>
                                <CalendarIcon className="h-4 w-4" />
                                Log Outcome
                            </>
                        )}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
