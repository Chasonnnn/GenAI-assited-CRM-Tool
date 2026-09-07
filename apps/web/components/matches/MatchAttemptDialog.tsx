"use client"

import { useState } from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import type { MatchAttempt, MatchAttemptInput, MatchAttemptStatus, MatchAttemptType, MatchKind } from "@/lib/api/matches"
import { useSaveMatchAttempt } from "@/lib/hooks/use-matches"

export const ATTEMPT_TYPE_LABELS: Record<MatchAttemptType, string> = { embryo_transfer: "Embryo Transfer", retrieval: "Retrieval", collection: "Collection", other: "Other" }
export const ATTEMPT_STATUS_LABELS: Record<MatchAttemptStatus, string> = { planned: "Planned", in_progress: "In Progress", completed: "Completed", cancelled: "Cancelled" }
export function getMatchAttemptLabel(attempt: MatchAttempt): string {
    return `Attempt ${attempt.sequence} · ${ATTEMPT_TYPE_LABELS[attempt.attempt_type]} · ${ATTEMPT_STATUS_LABELS[attempt.status]}`
}

export function MatchAttemptDialog({ matchId, kind, attempt, onClose }: { matchId: string; kind: MatchKind; attempt?: MatchAttempt; onClose: () => void }) {
    const [data, setData] = useState<MatchAttemptInput>({
        attempt_type: attempt?.attempt_type ?? (kind === "donor" ? "retrieval" : "embryo_transfer"),
        status: attempt?.status ?? "planned",
        started_at: attempt?.started_at ?? null,
        ended_at: attempt?.ended_at ?? null,
        outcome: attempt?.outcome ?? null,
    })
    const [error, setError] = useState<string | null>(null)
    const mutation = useSaveMatchAttempt(matchId)
    const save = async () => {
        setError(null)
        if (data.started_at && data.ended_at && data.ended_at < data.started_at) { setError("End date must be on or after start date"); return }
        try {
            await mutation.mutateAsync({ ...(attempt ? { attemptId: attempt.id } : {}), data })
            onClose()
        } catch (error) { setError(error instanceof Error ? error.message : "Unable to save attempt") }
    }
    return <Dialog open onOpenChange={(open) => { if (!open && !mutation.isPending) onClose() }}>
        <DialogContent className="sm:max-w-md">
            <DialogHeader><DialogTitle>{attempt ? `Edit Attempt ${attempt.sequence}` : "Add Attempt"}</DialogTitle></DialogHeader>
            <div className="space-y-4 py-4">
                {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
                <div className="space-y-2"><Label htmlFor="attempt-type">Type</Label><Select value={data.attempt_type} onValueChange={(value) => { if (value && value in ATTEMPT_TYPE_LABELS) setData({ ...data, attempt_type: value as MatchAttemptType }) }}><SelectTrigger id="attempt-type"><SelectValue>{(value: string | null) => ATTEMPT_TYPE_LABELS[value as MatchAttemptType] ?? "Type"}</SelectValue></SelectTrigger><SelectContent>{Object.entries(ATTEMPT_TYPE_LABELS).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select></div>
                <div className="space-y-2"><Label htmlFor="attempt-status">Status</Label><Select value={data.status ?? "planned"} onValueChange={(value) => { if (value && value in ATTEMPT_STATUS_LABELS) setData({ ...data, status: value as MatchAttemptStatus }) }}><SelectTrigger id="attempt-status"><SelectValue>{(value: string | null) => ATTEMPT_STATUS_LABELS[value as MatchAttemptStatus] ?? "Status"}</SelectValue></SelectTrigger><SelectContent>{Object.entries(ATTEMPT_STATUS_LABELS).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select></div>
                <div className="grid grid-cols-2 gap-3"><div className="space-y-2"><Label htmlFor="attempt-start">Start Date</Label><Input id="attempt-start" type="date" value={data.started_at ?? ""} onChange={(event) => setData({ ...data, started_at: event.target.value || null })} /></div><div className="space-y-2"><Label htmlFor="attempt-end">End Date</Label><Input id="attempt-end" type="date" value={data.ended_at ?? ""} onChange={(event) => setData({ ...data, ended_at: event.target.value || null })} /></div></div>
                <div className="space-y-2"><Label htmlFor="attempt-outcome">Outcome</Label><Textarea id="attempt-outcome" value={data.outcome ?? ""} onChange={(event) => setData({ ...data, outcome: event.target.value || null })} /></div>
            </div>
            <DialogFooter><Button variant="outline" onClick={onClose} disabled={mutation.isPending}>Cancel</Button><Button onClick={() => { void save() }} disabled={mutation.isPending}>{mutation.isPending ? "Saving…" : "Save Attempt"}</Button></DialogFooter>
        </DialogContent>
    </Dialog>
}
