"use client"

import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import Link from "@/components/app-link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import api from "@/lib/api"
import { getTickets } from "@/lib/api/tickets"
import { getMessageStatusLabel } from "@/components/email-operations/email-operation-labels"
import { getCorrespondenceTicketStatusLabel } from "@/lib/ticket-status-labels"
import { formatDateTime } from "@/lib/formatters"

type CorrespondenceItem = { id: string; kind: "ticket" | "email"; subject: string; status: string; recipient: string | null; occurred_at: string; ticket_code: string | null }
type CorrespondenceList = { items: CorrespondenceItem[]; total: number }

export function RecordCorrespondenceCard({ kind, recordId, canView, canEdit }: {
    kind: "donor" | "intended_parent"; recordId: string; canView: boolean; canEdit: boolean
}) {
    const [page, setPage] = useState(0)
    const [linkOpen, setLinkOpen] = useState(false)
    const [search, setSearch] = useState("")
    const client = useQueryClient()
    const path = `/records/${kind}/${recordId}/correspondence`
    const key = ["record-correspondence", kind, recordId]
    const history = useQuery({ queryKey: [...key, page], queryFn: () => api.get<CorrespondenceList>(`${path}?limit=10&offset=${page * 10}`), enabled: canView })
    const tickets = useQuery({ queryKey: ["record-correspondence-tickets", search], queryFn: () => getTickets({ q: search, limit: 20 }), enabled: canView && canEdit && linkOpen })
    const link = useMutation({ mutationFn: ({ id, remove }: { id: string; remove: boolean }) => remove ? api.delete(`${path}/${id}`) : api.put(`${path}/${id}`), onSuccess: () => { void client.invalidateQueries({ queryKey: key }); setLinkOpen(false) } })
    if (!canView) return null
    return <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-2"><CardTitle>Correspondence</CardTitle>{canEdit && <Button variant="outline" size="sm" onClick={() => setLinkOpen(true)}>Link Conversation</Button>}</CardHeader>
        <CardContent className="space-y-3">
            {history.isLoading ? <p role="status" className="text-sm text-muted-foreground">Loading correspondence…</p> : history.isError ? <div role="alert">Unable to load correspondence. <Button variant="outline" size="sm" onClick={() => void history.refetch()}>Retry</Button></div> : !history.data?.items.length ? <p className="text-sm text-muted-foreground">No linked correspondence</p> : history.data.items.map(item => <div key={`${item.kind}-${item.id}`} className="flex items-start justify-between gap-3 rounded-md border p-3">
                <div className="min-w-0 space-y-1">{item.kind === "ticket" ? <Link className="block truncate text-sm font-medium hover:underline" href={`/tickets/${item.id}`}>{item.ticket_code} · {item.subject}</Link> : <p className="truncate text-sm font-medium">{item.subject}</p>}<p className="truncate text-xs text-muted-foreground">{item.recipient}</p><p className="text-xs text-muted-foreground">{formatDateTime(item.occurred_at)}</p><Badge variant="outline">{item.kind === "email" ? "Email" : "Conversation"} · {item.kind === "email" ? getMessageStatusLabel(item.status) : getCorrespondenceTicketStatusLabel(item.status)}</Badge></div>
                {canEdit && item.kind === "ticket" && <Button variant="ghost" size="sm" disabled={link.isPending} onClick={() => link.mutate({ id: item.id, remove: true })}>Unlink</Button>}
            </div>)}
            {link.isError && <p role="alert" className="text-sm text-destructive">{link.error.message}</p>}
            {(history.data?.total ?? 0) > 10 && <div className="flex items-center justify-between"><Button variant="outline" size="sm" disabled={!page} onClick={() => setPage(page - 1)}>Previous</Button><span className="text-sm">{page + 1} / {Math.ceil((history.data?.total ?? 0) / 10)}</span><Button variant="outline" size="sm" disabled={(page + 1) * 10 >= (history.data?.total ?? 0)} onClick={() => setPage(page + 1)}>Next</Button></div>}
        </CardContent>
        <Dialog open={linkOpen} onOpenChange={setLinkOpen}><DialogContent><DialogHeader><DialogTitle>Link Conversation</DialogTitle></DialogHeader><div className="space-y-3"><Label htmlFor="record-ticket-search">Search conversations</Label><Input id="record-ticket-search" value={search} onChange={event => setSearch(event.target.value)} />{tickets.isLoading ? <p role="status">Loading conversations…</p> : tickets.isError ? <div role="alert">Unable to load conversations. <Button onClick={() => void tickets.refetch()}>Retry</Button></div> : !tickets.data?.items.length ? <p>No conversations found</p> : <div className="max-h-80 space-y-2 overflow-y-auto">{tickets.data.items.map(ticket => <Button key={ticket.id} className="h-auto w-full justify-start whitespace-normal text-left" variant="outline" disabled={link.isPending} onClick={() => link.mutate({ id: ticket.id, remove: false })}>{ticket.ticket_code} · {ticket.subject ?? "No subject"}</Button>)}</div>}{link.isError && <p role="alert" className="text-destructive">{link.error.message}</p>}</div></DialogContent></Dialog>
    </Card>
}
