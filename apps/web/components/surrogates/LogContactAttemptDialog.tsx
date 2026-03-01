"use client"

import * as React from "react"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { Checkbox } from "@/components/ui/checkbox"
import { Loader2Icon, PhoneIcon, MailIcon, MessageSquareIcon, CalendarIcon } from "lucide-react"
import { useCreateContactAttempt } from "@/lib/hooks/use-surrogates"
import { toast } from "sonner"
import type { ContactMethod, ContactOutcome } from "@/lib/api/surrogates"
import { trackFirstContactLogged } from "@/lib/workflow-metrics"

interface LogContactAttemptDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    surrogateId: string
    surrogateName?: string
}

const CONTACT_METHODS: { value: ContactMethod; label: string; icon: React.ReactNode }[] = [
    { value: "phone", label: "Phone", icon: <PhoneIcon className="h-4 w-4" /> },
    { value: "email", label: "Email", icon: <MailIcon className="h-4 w-4" /> },
    { value: "sms", label: "SMS", icon: <MessageSquareIcon className="h-4 w-4" /> },
]

const CONTACT_OUTCOMES: { value: ContactOutcome; label: string; description: string }[] = [
    { value: "reached", label: "Reached", description: "Successfully contacted" },
    { value: "no_answer", label: "No Answer", description: "Call not answered" },
    { value: "voicemail", label: "Voicemail", description: "Left a voicemail" },
    { value: "wrong_number", label: "Wrong Number", description: "Number is incorrect" },
    { value: "email_bounced", label: "Email Bounced", description: "Email delivery failed" },
]

export function LogContactAttemptDialog({
    open,
    onOpenChange,
    surrogateId,
    surrogateName = "Surrogate",
}: LogContactAttemptDialogProps) {
    const [selectedMethods, setSelectedMethods] = useState<ContactMethod[]>([])
    const [outcome, setOutcome] = useState<ContactOutcome | "">("")
    const [notes, setNotes] = useState("")
    const [attemptedAt, setAttemptedAt] = useState("")
    const [isBackdating, setIsBackdating] = useState(false)

    const createContactAttempt = useCreateContactAttempt()
    const maxLocalDateTime = React.useMemo(() => {
        const now = new Date()
        const offsetMs = now.getTimezoneOffset() * 60 * 1000
        return new Date(now.getTime() - offsetMs).toISOString().slice(0, 16)
    }, [])

    const handleMethodToggle = (method: ContactMethod) => {
        setSelectedMethods(prev =>
            prev.includes(method)
                ? prev.filter(m => m !== method)
                : [...prev, method]
        )
    }

    const resetForm = () => {
        setSelectedMethods([])
        setOutcome("")
        setNotes("")
        setAttemptedAt("")
        setIsBackdating(false)
    }

    const handleSubmit = async () => {
        if (selectedMethods.length === 0 || !outcome) return

        try {
            await createContactAttempt.mutateAsync({
                surrogateId,
                data: {
                    contact_methods: selectedMethods,
                    outcome: outcome,
                    notes: notes.trim() || null,
                    attempted_at: isBackdating && attemptedAt ? new Date(attemptedAt).toISOString() : null,
                },
            })

            toast.success(
                outcome === "reached"
                    ? "Surrogate has been marked as contacted."
                    : "Contact attempt logged"
            )

            trackFirstContactLogged(surrogateId, {
                outcome,
                contact_methods: selectedMethods,
                is_backdated: isBackdating,
            })

            resetForm()
            onOpenChange(false)
        } catch (error) {
            toast.error(
                error instanceof Error ? error.message : "Failed to log contact attempt"
            )
        }
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

    const isValid = selectedMethods.length > 0 && outcome !== "" && (!isBackdating || attemptedAt)

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                    <DialogTitle>Log Contact Attempt</DialogTitle>
                    <DialogDescription>
                        Record your attempt to contact {surrogateName}.
                    </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                    {/* Contact Methods - Multi-select checkboxes */}
                    <div className="grid gap-2">
                        <Label>Contact Method(s) Used</Label>
                        <div className="flex flex-wrap gap-3">
                            {CONTACT_METHODS.map(method => (
                                <label
                                    key={method.value}
                                    className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-colors ${selectedMethods.includes(method.value)
                                        ? "border-primary bg-primary/10"
                                        : "border-muted hover:border-muted-foreground/50"
                                        }`}
                                >
                                    <Checkbox
                                        checked={selectedMethods.includes(method.value)}
                                        onCheckedChange={() => handleMethodToggle(method.value)}
                                    />
                                    {method.icon}
                                    <span className="text-sm font-medium">{method.label}</span>
                                </label>
                            ))}
                        </div>
                    </div>

                    {/* Outcome - Dropdown */}
                    <div className="grid gap-2">
                        <Label htmlFor="outcome">Outcome</Label>
                        <Select
                            value={outcome}
                            onValueChange={(v) => setOutcome(v as ContactOutcome)}
                        >
                            <SelectTrigger id="outcome">
                                <SelectValue placeholder="Select outcome..." />
                            </SelectTrigger>
                            <SelectContent>
                                {CONTACT_OUTCOMES.map(opt => (
                                    <SelectItem key={opt.value} value={opt.value}>
                                        <div className="flex flex-col">
                                            <span>{opt.label}</span>
                                            <span className="text-xs text-muted-foreground">
                                                {opt.description}
                                            </span>
                                        </div>
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Notes - Optional */}
                    <div className="grid gap-2">
                        <Label htmlFor="notes">Notes (optional)</Label>
                        <Textarea
                            id="notes"
                            placeholder="Add any relevant details..."
                            value={notes}
                            onChange={(e) => setNotes(e.target.value)}
                            rows={3}
                            className="resize-none"
                        />
                    </div>

                    {/* Back-dating toggle and input */}
                    <div className="grid gap-2">
                        <div className="flex items-center gap-2">
                            <Checkbox
                                id="contact-attempt-backdate"
                                checked={isBackdating}
                                onCheckedChange={(checked) => setIsBackdating(checked === true)}
                            />
                            <Label htmlFor="contact-attempt-backdate" className="cursor-pointer">
                                Log for a different date/time
                            </Label>
                        </div>
                        {isBackdating && (
                            <div className="flex items-center gap-2">
                                <CalendarIcon className="h-4 w-4 text-muted-foreground" />
                                <Input
                                    type="datetime-local"
                                    value={attemptedAt}
                                    onChange={(e) => setAttemptedAt(e.target.value)}
                                    max={maxLocalDateTime}
                                    className="flex-1"
                                />
                            </div>
                        )}
                    </div>
                </div>
                <DialogFooter>
                    <Button
                        variant="outline"
                        onClick={handleCancel}
                        disabled={createContactAttempt.isPending}
                    >
                        Cancel
                    </Button>
                    <Button
                        onClick={handleSubmit}
                        disabled={!isValid || createContactAttempt.isPending}
                    >
                        {createContactAttempt.isPending ? (
                            <>
                                <Loader2Icon className="mr-2 h-4 w-4 animate-spin" />
                                Logging...
                            </>
                        ) : (
                            "Log Attempt"
                        )}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
