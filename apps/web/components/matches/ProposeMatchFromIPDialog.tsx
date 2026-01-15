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
import { useSurrogates } from "@/lib/hooks/use-surrogates"

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
    const [selectedSurrogateId, setSelectedSurrogateId] = useState<string>("")
    const [compatibilityScore, setCompatibilityScore] = useState<string>("")
    const [notes, setNotes] = useState("")
    const [error, setError] = useState<string | null>(null)

    // Only fetch surrogates in ready_to_match status
    const { data: surrogatesData, isLoading: surrogatesLoading } = useSurrogates({
        per_page: 100
    })
    const createMatch = useCreateMatch()

    // Filter to only ready_to_match surrogates (prefer stage_slug when available)
    const eligibleSurrogates = useMemo(() => {
        if (!surrogatesData?.items) return []
        return surrogatesData.items.filter((s) => {
            if (s.stage_slug) {
                return s.stage_slug === "ready_to_match"
            }
            return s.status_label?.toLowerCase() === "ready to match"
        })
    }, [surrogatesData])

    const handleSubmit = async () => {
        if (!selectedSurrogateId) return
        setError(null)

        try {
            await createMatch.mutateAsync({
                surrogate_id: selectedSurrogateId,
                intended_parent_id: intendedParentId,
                ...(compatibilityScore ? { compatibility_score: parseFloat(compatibilityScore) } : {}),
                ...(notes.trim() ? { notes: notes.trim() } : {}),
            })
            toast.success("Match proposed successfully!")
            onOpenChange(false)
            setSelectedSurrogateId("")
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
        setSelectedSurrogateId("")
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
                        <Label htmlFor="surrogate-select">Surrogate (Ready to Match Only)</Label>
                        {surrogatesLoading ? (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                <Loader2Icon className="size-4 animate-spin" />
                                Loading available surrogates...
                            </div>
                        ) : eligibleSurrogates.length === 0 ? (
                            <div className="text-sm text-muted-foreground p-3 border rounded-md bg-muted/30">
                                No surrogates are currently in "Ready to Match" status.
                            </div>
                        ) : (
                            <Select value={selectedSurrogateId} onValueChange={(v) => setSelectedSurrogateId(v || "")}>
                                <SelectTrigger className="w-full">
                                    <SelectValue placeholder="Select a surrogate" />
                                </SelectTrigger>
                                <SelectContent className="max-h-[300px]">
                                    {eligibleSurrogates.map((s) => (
                                        <SelectItem key={s.id} value={s.id} className="py-2">
                                            <span className="font-medium">{s.full_name || "Unknown"}</span>
                                            <span className="text-muted-foreground ml-2">#{s.surrogate_number}</span>
                                            {s.state && <span className="text-muted-foreground ml-2">• {s.state}</span>}
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
                        disabled={!selectedSurrogateId || createMatch.isPending}
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
