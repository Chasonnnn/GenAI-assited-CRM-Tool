"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import Link from "@/components/app-link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ProposeMatchDialog } from "@/components/matches/ProposeMatchDialog"
import { listMatches } from "@/lib/api/matches"
import { matchKeys } from "@/lib/queries/matches"
import { formatDate } from "@/lib/formatters"
import { getMatchKindLabel, getMatchStatusBadgeClassName, getMatchStatusLabel } from "@/lib/match-status-definitions"

export function RelatedMatchesCard({ kind, recordId, name, canView, canPropose, archived = false }: {
    kind: "intended_parent" | "donor"
    recordId: string
    name: string
    canView: boolean
    canPropose: boolean
    archived?: boolean
}) {
    const [page, setPage] = useState(1)
    const [proposeOpen, setProposeOpen] = useState(false)
    const params = {
        ...(kind === "donor" ? { donor_id: recordId } : { intended_parent_id: recordId }),
        page, per_page: 5,
    }
    const matches = useQuery({
        queryKey: matchKeys.list(params), queryFn: () => listMatches(params), enabled: canView,
    })
    if (!canView) return null
    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-2">
                <CardTitle>Related Matches</CardTitle>
                {kind === "donor" && canPropose && !archived && (
                    <Button variant="outline" size="sm" onClick={() => setProposeOpen(true)}>Propose Match</Button>
                )}
            </CardHeader>
            <CardContent className="space-y-3">
                {matches.isPending ? <p className="text-sm text-muted-foreground">Loading matches…</p>
                    : matches.isError ? <div role="alert" className="flex items-center justify-between gap-2 text-sm">
                        <span>Unable to load matches.</span>
                        <Button variant="outline" size="sm" onClick={() => void matches.refetch()}>Retry</Button>
                    </div>
                        : matches.data.items.length === 0 ? <p className="text-sm text-muted-foreground">No matches yet.</p>
                            : matches.data.items.map(match => (
                                <Link key={match.id} href={`/intended-parents/matches/${match.id}`}
                                    className="flex min-w-0 flex-wrap items-center justify-between gap-2 rounded-lg border p-3 hover:bg-muted/50">
                                    <div className="min-w-0">
                                        <p className="truncate text-sm font-medium">{match.match_number} · {kind === "donor" ? match.ip_name : match.donor_name || match.surrogate_name}</p>
                                        <p className="text-xs text-muted-foreground">{getMatchKindLabel(match.match_kind)} · {formatDate(match.proposed_at)}</p>
                                    </div>
                                    <Badge className={getMatchStatusBadgeClassName(match.status)}>{getMatchStatusLabel(match.status)}</Badge>
                                </Link>
                            ))}
                {matches.data && matches.data.total > 5 && <div className="flex items-center justify-between gap-2">
                    <Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</Button>
                    <span className="text-xs text-muted-foreground">Page {page} of {Math.ceil(matches.data.total / 5)}</span>
                    <Button variant="outline" size="sm" disabled={page * 5 >= matches.data.total} onClick={() => setPage(page + 1)}>Next</Button>
                </div>}
            </CardContent>
            {kind === "donor" && canPropose && !archived && <ProposeMatchDialog open={proposeOpen} onOpenChange={setProposeOpen} donorId={recordId} donorName={name} />}
        </Card>
    )
}
