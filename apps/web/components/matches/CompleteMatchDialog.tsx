"use client"
import { useState } from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import type { MatchCompleteRequest } from "@/lib/api/matches"

export function CompleteMatchDialog({ onClose, onComplete, isPending }: { onClose: () => void; onComplete: (data: MatchCompleteRequest) => Promise<void>; isPending: boolean }) {
    const [outcome, setOutcome] = useState("")
    const [reason, setReason] = useState("")
    const [error, setError] = useState<string | null>(null)
    const complete = async () => {
        if (!outcome.trim()) return
        setError(null)
        try { await onComplete({ outcome: outcome.trim(), ...(reason.trim() ? { reason: reason.trim() } : {}) }); onClose() }
        catch (error) { setError(error instanceof Error ? error.message : "Unable to complete match") }
    }
    return <Dialog open onOpenChange={(open) => { if (!open && !isPending) onClose() }}><DialogContent className="sm:max-w-md">
        <DialogHeader><DialogTitle>Complete Match</DialogTitle></DialogHeader>
        <div className="space-y-4 py-4">
            {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
            <div className="space-y-2"><Label htmlFor="match-outcome">Outcome</Label><Textarea id="match-outcome" value={outcome} onChange={(event) => setOutcome(event.target.value)} required /></div>
            <div className="space-y-2"><Label htmlFor="match-closure-reason">Reason (optional)</Label><Textarea id="match-closure-reason" value={reason} onChange={(event) => setReason(event.target.value)} /></div>
        </div>
        <DialogFooter><Button variant="outline" onClick={onClose} disabled={isPending}>Cancel</Button><Button onClick={() => { void complete() }} disabled={!outcome.trim() || isPending}>{isPending ? "Completing…" : "Complete Match"}</Button></DialogFooter>
    </DialogContent></Dialog>
}
