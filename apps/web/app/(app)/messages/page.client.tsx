"use client"

import { useState } from "react"
import { format } from "date-fns"
import { AlertTriangleIcon, InboxIcon, Loader2Icon, PaperclipIcon } from "lucide-react"

import { useAuth } from "@/lib/auth-context"
import {
    useLinkMessagingConversation,
    useMarkMessagingConversationRead,
    useMessagingConversation,
    useMessagingConversations,
    useUpdateMessagingReconciliation,
} from "@/lib/hooks/use-messaging-inbox"
import type { MessagingPurpose } from "@/lib/api/messaging-inbox"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

const friendly = (value: string) =>
    value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase())

const consentLabel = (value: string) => ({
    opted_in: "Opted in",
    opted_out: "Opted out",
    reopt_pending: "Re-enrollment pending",
    unknown: "Unknown",
}[value] ?? friendly(value))

const reconciliationStatusLabel = (value: string) => ({
    action_required: "Reconciliation required",
    pending: "Pending",
    running: "In progress",
    resolved: "Resolved",
    dismissed: "Dismissed",
}[value] ?? friendly(value))

function EmptyInbox() {
    return (
        <div className="flex min-h-72 flex-col items-center justify-center text-center">
            <InboxIcon className="mb-3 size-9 text-muted-foreground" />
            <h2 className="font-medium">No conversations yet</h2>
            <p className="mt-1 max-w-sm text-sm text-muted-foreground">
                Inbound and automated outbound SMS or MMS will appear here.
            </p>
        </div>
    )
}

export default function MessagesPageClient({ embedded = false }: { embedded?: boolean }) {
    const { user, isLoading: authLoading } = useAuth()
    const canAccess = user?.role === "developer"
    const [readFilter, setReadFilter] = useState<"all" | "unread">("all")
    const [linkFilter, setLinkFilter] = useState<"all" | "unlinked">("all")
    const [purpose, setPurpose] = useState<"all" | MessagingPurpose>("all")
    const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null)
    const [linkEntityType, setLinkEntityType] = useState<"surrogate" | "intake_lead" | "meta_lead">("surrogate")
    const [linkEntityId, setLinkEntityId] = useState("")

    const listQuery = useMessagingConversations(
        {
            ...(readFilter === "unread" ? { unread: true } : {}),
            ...(linkFilter === "unlinked" ? { unlinked: true } : {}),
            ...(purpose === "all" ? {} : { purpose }),
            limit: 50,
        },
        canAccess,
    )
    const selectedId = selectedConversationId ?? listQuery.data?.items[0]?.id ?? null
    const detailQuery = useMessagingConversation(selectedId, canAccess)
    const markRead = useMarkMessagingConversationRead()
    const linkConversation = useLinkMessagingConversation()
    const reconcile = useUpdateMessagingReconciliation()

    if (authLoading) {
        return (
            <div className="flex min-h-96 items-center justify-center" aria-label="Loading messages">
                <Loader2Icon className="size-7 animate-spin text-muted-foreground" />
            </div>
        )
    }
    if (!canAccess) {
        return (
            <div className="p-6">
                <Card><CardContent className="p-6">Tickets are available only to developers.</CardContent></Card>
            </div>
        )
    }

    const detail = detailQuery.data

    return (
        <div className={embedded ? "space-y-6" : "space-y-6 p-6"}>
            <header className="flex flex-wrap items-center gap-2">
                <h2 className="text-lg font-semibold">SMS/MMS inbox</h2>
                <Badge variant="secondary">Read-only</Badge>
            </header>

            <div className="grid gap-3 md:grid-cols-3">
                <Select value={readFilter} onValueChange={(value) => setReadFilter(value as "all" | "unread")}>
                    <SelectTrigger aria-label="Read status"><SelectValue>{(value: string | null) => value === "unread" ? "Unread only" : "All messages"}</SelectValue></SelectTrigger>
                    <SelectContent><SelectItem value="all">All messages</SelectItem><SelectItem value="unread">Unread only</SelectItem></SelectContent>
                </Select>
                <Select value={linkFilter} onValueChange={(value) => setLinkFilter(value as "all" | "unlinked")}>
                    <SelectTrigger aria-label="Link status"><SelectValue>{(value: string | null) => value === "unlinked" ? "Unlinked only" : "All contacts"}</SelectValue></SelectTrigger>
                    <SelectContent><SelectItem value="all">All contacts</SelectItem><SelectItem value="unlinked">Unlinked only</SelectItem></SelectContent>
                </Select>
                <Select value={purpose} onValueChange={(value) => setPurpose(value as "all" | MessagingPurpose)}>
                    <SelectTrigger aria-label="Message purpose"><SelectValue>{(value: string | null) => value === "operational" ? "Operational" : value === "promotional" ? "Promotional" : "All purposes"}</SelectValue></SelectTrigger>
                    <SelectContent><SelectItem value="all">All purposes</SelectItem><SelectItem value="operational">Operational</SelectItem><SelectItem value="promotional">Promotional</SelectItem></SelectContent>
                </Select>
            </div>

            {listQuery.isLoading ? (
                <div className="flex min-h-72 items-center justify-center" aria-label="Loading messages"><Loader2Icon className="size-7 animate-spin" /></div>
            ) : listQuery.isError ? (
                <Card><CardContent className="flex min-h-56 flex-col items-center justify-center gap-3 text-center"><AlertTriangleIcon className="size-8 text-destructive" /><h2 className="font-medium">Messages could not be loaded</h2><Button variant="outline" onClick={() => listQuery.refetch()}>Try again</Button></CardContent></Card>
            ) : !listQuery.data?.items.length ? <EmptyInbox /> : (
                <div className="grid min-h-[620px] gap-4 lg:grid-cols-[340px_minmax(0,1fr)]">
                    <Card className="overflow-hidden">
                        <CardHeader><CardTitle className="text-base">Conversations</CardTitle></CardHeader>
                        <CardContent className="space-y-2 p-3 pt-0">
                            {listQuery.data.items.map((conversation) => (
                                <Button unstyled key={conversation.id} type="button" aria-label={`Open conversation ${conversation.masked_phone}`} onClick={() => setSelectedConversationId(conversation.id)} className={`w-full rounded-lg border p-3 text-left transition-colors ${selectedId === conversation.id ? "border-primary bg-primary/5" : "hover:bg-muted/50"}`}>
                                    <div className="flex items-center justify-between gap-2"><span className="font-medium">{conversation.masked_phone}</span>{conversation.unread_count > 0 && <Badge>{conversation.unread_count} unread</Badge>}</div>
                                    <div className="mt-2 flex gap-2"><Badge variant="outline">{friendly(conversation.purpose)}</Badge>{conversation.unlinked && <Badge variant="secondary">Unlinked</Badge>}</div>
                                    <p className="mt-2 truncate text-sm text-muted-foreground">Preview: {conversation.last_message_preview || "No preview"}</p>
                                </Button>
                            ))}
                        </CardContent>
                    </Card>

                    <Card>
                        {detailQuery.isLoading ? <CardContent className="flex min-h-96 items-center justify-center"><Loader2Icon className="size-7 animate-spin" /></CardContent> : detail ? (
                            <>
                                <CardHeader className="border-b">
                                    <div className="flex flex-wrap items-start justify-between gap-3"><div><CardTitle>{detail.masked_phone}</CardTitle><p className="mt-1 text-sm text-muted-foreground">{detail.route_label}</p></div>{detail.unread_count > 0 && <Button variant="outline" size="sm" disabled={markRead.isPending} onClick={() => markRead.mutateAsync(detail.id)}>Mark as read</Button>}</div>
                                    <div className="flex flex-wrap gap-2 pt-2">{Object.entries(detail.consent_states).map(([key, value]) => <Badge key={key} variant="outline"><span>{friendly(key)}</span>: <span>{consentLabel(value)}</span></Badge>)}{detail.global_suppression_active && <Badge variant="destructive">Globally suppressed</Badge>}</div>
                                </CardHeader>
                                <CardContent className="space-y-6 p-5">
                                    {detail.unlinked && <section className="rounded-lg border border-dashed p-4"><h3 className="font-medium">Link this contact</h3><div className="mt-3 grid gap-3 sm:grid-cols-[180px_1fr_auto]"><Select value={linkEntityType} onValueChange={(value) => setLinkEntityType(value as typeof linkEntityType)}><SelectTrigger aria-label="Entity type"><SelectValue>{(value: string | null) => value ? friendly(value) : "Entity type"}</SelectValue></SelectTrigger><SelectContent><SelectItem value="surrogate">Surrogate</SelectItem><SelectItem value="intake_lead">Intake lead</SelectItem><SelectItem value="meta_lead">Meta lead</SelectItem></SelectContent></Select><Input aria-label="Entity ID" placeholder="Entity ID" value={linkEntityId} onChange={(event) => setLinkEntityId(event.target.value)} /><Button disabled={!linkEntityId || linkConversation.isPending} onClick={() => linkConversation.mutateAsync({ conversationId: detail.id, request: { entity_type: linkEntityType, entity_id: linkEntityId } })}>Link</Button></div></section>}

                                    <section className="space-y-3"><h3 className="font-medium">Conversation</h3>{detail.messages.map((message) => <article key={message.id} className={`max-w-[85%] rounded-xl border p-4 ${message.direction === "outbound" ? "ml-auto bg-primary/5" : "bg-muted/40"}`}><div className="flex items-center justify-between gap-3 text-xs text-muted-foreground"><span>{friendly(message.direction)} · {friendly(message.purpose)}</span><time>{format(new Date(message.created_at), "MMM d, yyyy h:mm a")}</time></div><p className="mt-2 whitespace-pre-wrap text-sm">{message.body}</p>{message.media.map((media) => <div key={media.id} className="mt-3 flex items-center gap-2 rounded-md border bg-background p-2 text-xs"><PaperclipIcon className="size-3" /><span>{media.filename || "Media attachment"}</span><Badge variant={media.quarantined ? "destructive" : "secondary"}>{friendly(media.scan_status)}</Badge></div>)}{message.delivery && <details className="mt-3 text-xs"><summary className="cursor-pointer font-medium">Delivery: {friendly(message.delivery.status)}</summary><div className="mt-2 space-y-1 text-muted-foreground">{message.delivery.attempts.map((attempt) => <p key={attempt.id}>Attempt {attempt.attempt_number}: {friendly(attempt.outcome)}</p>)}{message.delivery.status_events.map((event) => <p key={event.id}>Callback: {friendly(event.status || "unknown")}</p>)}</div></details>}</article>)}</section>

                                    {detail.consent_timeline.length > 0 && <section><h3 className="font-medium">Consent history</h3><div className="mt-2 space-y-2">{detail.consent_timeline.map((event) => <div key={event.id} className="rounded-md border p-3 text-sm"><span className="font-medium">{consentLabel(event.action)}</span> · {friendly(event.purpose)}<p className="text-xs text-muted-foreground">{friendly(event.source)} · {format(new Date(event.occurred_at), "MMM d, yyyy h:mm a")}</p></div>)}</div></section>}

                                    {detail.reconciliation_cases.length > 0 && <section><h3 className="font-medium">Reconciliation</h3><div className="mt-2 space-y-2">{detail.reconciliation_cases.map((item) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 rounded-md border p-3"><div><p className="text-sm font-medium">{reconciliationStatusLabel(item.status)}</p><p className="text-xs text-muted-foreground">{friendly(item.reason_code)}</p></div>{item.status !== "resolved" && item.status !== "dismissed" && <Button size="sm" variant="outline" disabled={reconcile.isPending} onClick={() => reconcile.mutateAsync({ caseId: item.id, request: { expected_version: item.version, action: "resolve", resolution_code: "admin_verified" } })}>Resolve</Button>}</div>)}</div></section>}
                                </CardContent>
                            </>
                        ) : <CardContent className="flex min-h-96 items-center justify-center text-muted-foreground">Select a conversation.</CardContent>}
                    </Card>
                </div>
            )}
        </div>
    )
}
