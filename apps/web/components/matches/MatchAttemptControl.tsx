"use client"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useMatchAttempts } from "@/lib/hooks/use-matches"
import { MatchAttemptDialog, getMatchAttemptLabel } from "./MatchAttemptDialog"
import type { MatchRead } from "@/lib/api/matches"

export function MatchAttemptControl({ match, selectedId, onSelect, canEdit }: { match: MatchRead; selectedId: string; onSelect: (id: string) => void; canEdit: boolean }) {
    const query = useMatchAttempts(match.id)
    const [editing, setEditing] = useState<string | null>(null)
    const attempts = query.data ?? []
    const selected = attempts.find((attempt) => attempt.id === selectedId)
    return <div className="flex flex-wrap items-center gap-2">
        {query.isError ? <Button size="sm" variant="outline" onClick={() => { void query.refetch() }}>Retry Attempts</Button> : <Select value={selectedId || "all"} onValueChange={(value) => onSelect(value === "all" || !value ? "" : value)} disabled={query.isLoading}>
            <SelectTrigger aria-label="Treatment attempt" className="h-8 w-full sm:w-[260px] text-xs"><SelectValue>{(value: string | null) => value === "all" || !value ? "All Attempts" : attempts.find((attempt) => attempt.id === value) ? getMatchAttemptLabel(attempts.find((attempt) => attempt.id === value)!) : "Selected Attempt"}</SelectValue></SelectTrigger>
            <SelectContent><SelectItem value="all">All Attempts</SelectItem>{attempts.map((attempt) => <SelectItem value={attempt.id} key={attempt.id}>{getMatchAttemptLabel(attempt)}</SelectItem>)}</SelectContent>
        </Select>}
        {canEdit && match.status === "accepted" && <>
            <Button size="sm" variant="outline" className="h-8 text-xs" onClick={() => setEditing("new")}>Add Attempt</Button>
            {selected && <Button size="sm" variant="outline" className="h-8 text-xs" onClick={() => setEditing(selected.id)}>Edit Attempt</Button>}
        </>}
        {selected?.outcome && <span className="text-xs text-muted-foreground">{selected.outcome}</span>}
        {editing && <MatchAttemptDialog key={editing} matchId={match.id} kind={match.match_kind ?? "surrogate"} {...(editing !== "new" && selected ? { attempt: selected } : {})} onClose={() => setEditing(null)} />}
    </div>
}
