"use client"

import { useState, useMemo } from "react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Loader2Icon, HeartHandshakeIcon, AlertCircleIcon } from "lucide-react"
import { toast } from "sonner"
import { useCreateMatch } from "@/lib/hooks/use-matches"
import { useCases } from "@/lib/hooks/use-cases"

interface ProposeMatchFromIPDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    intendedParentId: string
    ipName?: string
    onSuccess?: () => void
}

export function ProposeMatchFromIPDialog({
    open,
    onOpenChange,
    intendedParentId,
    ipName,
    onSuccess,
}: ProposeMatchFromIPDialogProps) {
    const [selectedCaseId, setSelectedCaseId] = useState<string>("")
    const [compatibilityScore, setCompatibilityScore] = useState<string>("")
    const [notes, setNotes] = useState("")
    const [error, setError] = useState<string | null>(null)

    // Only fetch cases in pending_match status
    const { data: casesData, isLoading: casesLoading } = useCases({
        per_page: 100
    })
    const createMatch = useCreateMatch()

    // Filter to only pending_match cases (prefer stage_slug when available)
    const eligibleCases = useMemo(() => {
        if (!casesData?.items) return []
        return casesData.items.filter((c) => {
            if (c.stage_slug) {
                return c.stage_slug === "pending_match"
            }
            return c.status_label?.toLowerCase() === "pending match"
        })
    }, [casesData])

    const handleSubmit = async () => {
        if (!selectedCaseId) return
        setError(null)

        try {
            await createMatch.mutateAsync({
                case_id: selectedCaseId,
                intended_parent_id: intendedParentId,
                ...(compatibilityScore ? { compatibility_score: parseFloat(compatibilityScore) } : {}),
                ...(notes.trim() ? { notes: notes.trim() } : {}),
            })
            toast.success("Match proposed successfully!")
            onOpenChange(false)
            setSelectedCaseId("")
            setCompatibilityScore("")
            setNotes("")
            onSuccess?.()
        } catch (e: unknown) {
            console.error("Failed to propose match:", e instanceof Error ? e.message : e)
            setError(e instanceof Error ? e.message : "Failed to propose match. Please try again.")
        }
    }

    const handleClose = () => {
        onOpenChange(false)
        setSelectedCaseId("")
        setCompatibilityScore("")
        setNotes("")
        setError(null)
    }

    return (
        <Dialog open={open} onOpenChange={handleClose}>
            <DialogContent className="max-w-lg">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <HeartHandshakeIcon className="size-5" />
                        Propose Match
                    </DialogTitle>
                    <DialogDescription>
                        {ipName ? `Create a match proposal for ${ipName}` : "Create a match proposal for this intended parent"}
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    {error && (
                        <Alert variant="destructive">
                            <AlertCircleIcon className="size-4" />
                            <AlertDescription>{error}</AlertDescription>
                        </Alert>
                    )}

                    <div className="space-y-2">
                        <Label htmlFor="case-select">Surrogate (Pending Match Only)</Label>
                        {casesLoading ? (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                <Loader2Icon className="size-4 animate-spin" />
                                Loading available surrogates...
                            </div>
                        ) : eligibleCases.length === 0 ? (
                            <div className="text-sm text-muted-foreground p-3 border rounded-md bg-muted/30">
                                No surrogates are currently in "Pending Match" status.
                            </div>
                        ) : (
                            <Select value={selectedCaseId} onValueChange={(v) => setSelectedCaseId(v || "")}>
                                <SelectTrigger className="w-full">
                                    <SelectValue placeholder="Select a surrogate" />
                                </SelectTrigger>
                                <SelectContent className="max-h-[300px]">
                                    {eligibleCases.map((c) => (
                                        <SelectItem key={c.id} value={c.id} className="py-2">
                                            <span className="font-medium">{c.full_name || "Unknown"}</span>
                                            <span className="text-muted-foreground ml-2">#{c.case_number}</span>
                                            {c.state && <span className="text-muted-foreground ml-2">• {c.state}</span>}
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
                    <Button variant="outline" onClick={handleClose}>
                        Cancel
                    </Button>
                    <Button
                        onClick={handleSubmit}
                        disabled={!selectedCaseId || createMatch.isPending}
                        className="bg-teal-600 hover:bg-teal-700"
                    >
                        {createMatch.isPending && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                        Propose Match
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
