"use client"

import { useState } from "react"
import type { ReactNode } from "react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AlertCircleIcon, Loader2Icon } from "lucide-react"

export interface MatchProposalOption {
    value: string
    label: ReactNode
    itemClassName?: string
}

interface MatchProposalDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    title: string
    description: string
    icon: ReactNode
    selectLabel: string
    selectPlaceholder: string
    options: MatchProposalOption[]
    selectedValue: string
    onSelectedValueChange: (value: string | null) => void
    isLoading?: boolean
    loadingText?: string
    emptyState?: ReactNode
    submitLabel?: string
    submitClassName?: string
    submitDisabled?: boolean
    isSubmitting?: boolean
    dialogClassName?: string
    selectTriggerClassName?: string
    selectContentClassName?: string
    onSubmit: (payload: { compatibilityScore?: number; notes?: string }) => Promise<void>
}

export function MatchProposalDialog({
    open,
    onOpenChange,
    title,
    description,
    icon,
    selectLabel,
    selectPlaceholder,
    options,
    selectedValue,
    onSelectedValueChange,
    isLoading = false,
    loadingText = "Loading...",
    emptyState,
    submitLabel = "Propose Match",
    submitClassName,
    submitDisabled = false,
    isSubmitting = false,
    dialogClassName,
    selectTriggerClassName,
    selectContentClassName,
    onSubmit,
}: MatchProposalDialogProps) {
    const [compatibilityScore, setCompatibilityScore] = useState<string>("")
    const [notes, setNotes] = useState("")
    const [error, setError] = useState<string | null>(null)

    const resetForm = () => {
        setCompatibilityScore("")
        setNotes("")
        setError(null)
    }

    const handleOpenChange = (nextOpen: boolean) => {
        if (!nextOpen) {
            resetForm()
        }
        onOpenChange(nextOpen)
    }

    const handleSubmit = async () => {
        if (submitDisabled || isSubmitting) return
        setError(null)

        const parsedScore = compatibilityScore ? parseFloat(compatibilityScore) : undefined
        const sanitizedScore = Number.isFinite(parsedScore) ? parsedScore : undefined
        const trimmedNotes = notes.trim()

        try {
            await onSubmit({
                compatibilityScore: sanitizedScore,
                notes: trimmedNotes ? trimmedNotes : undefined,
            })
            resetForm()
            onOpenChange(false)
        } catch (e: unknown) {
            console.error("Failed to propose match:", e instanceof Error ? e.message : e)
            setError(e instanceof Error ? e.message : "Failed to propose match. Please try again.")
        }
    }

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogContent className={dialogClassName}>
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        {icon}
                        {title}
                    </DialogTitle>
                    <DialogDescription>{description}</DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    {error && (
                        <Alert variant="destructive">
                            <AlertCircleIcon className="size-4" />
                            <AlertDescription>{error}</AlertDescription>
                        </Alert>
                    )}

                    <div className="space-y-2">
                        <Label htmlFor="match-select">{selectLabel}</Label>
                        {isLoading ? (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                <Loader2Icon className="size-4 animate-spin" />
                                {loadingText}
                            </div>
                        ) : options.length === 0 && emptyState ? (
                            emptyState
                        ) : (
                            <Select value={selectedValue} onValueChange={(value) => onSelectedValueChange(value)}>
                                <SelectTrigger className={selectTriggerClassName}>
                                    <SelectValue placeholder={selectPlaceholder} />
                                </SelectTrigger>
                                <SelectContent className={selectContentClassName}>
                                    {options.map((option) => (
                                        <SelectItem
                                            key={option.value}
                                            value={option.value}
                                            className={option.itemClassName}
                                        >
                                            {option.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        )}
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="score">Compatibility Score (optional)</Label>
                        <Input
                            id="score"
                            type="number"
                            min="0"
                            max="100"
                            placeholder="0-100"
                            value={compatibilityScore}
                            onChange={(e) => setCompatibilityScore(e.target.value)}
                        />
                        <p className="text-xs text-muted-foreground">Enter a score between 0-100 if applicable</p>
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="notes">Notes (optional)</Label>
                        <Textarea
                            id="notes"
                            placeholder="Add any notes about this match proposal..."
                            value={notes}
                            onChange={(e) => setNotes(e.target.value)}
                            className="min-h-24"
                        />
                    </div>
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={() => handleOpenChange(false)}>
                        Cancel
                    </Button>
                    <Button
                        onClick={handleSubmit}
                        disabled={submitDisabled || isSubmitting}
                        className={submitClassName}
                    >
                        {isSubmitting && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                        {submitLabel}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
