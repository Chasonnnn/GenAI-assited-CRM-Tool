"use client"

import Link from 'next/link'
import { useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { useComposeTicket, useTickets } from '@/lib/hooks/use-tickets'
import type { TicketListParams, TicketPriority, TicketStatus } from '@/lib/api/tickets'

const STATUS_OPTIONS = ['new', 'open', 'pending', 'resolved', 'closed', 'spam'] as const
const PRIORITY_OPTIONS = ['low', 'normal', 'high', 'urgent'] as const
type TicketStatusFilter = TicketStatus | 'all'
type TicketPriorityFilter = TicketPriority | 'all'

export default function TicketsPage() {
    const router = useRouter()

    const [statusFilter, setStatusFilter] = useState<TicketStatusFilter>('all')
    const [priorityFilter, setPriorityFilter] = useState<TicketPriorityFilter>('all')
    const [query, setQuery] = useState('')
    const [composeTo, setComposeTo] = useState('')
    const [composeSubject, setComposeSubject] = useState('')
    const [composeBody, setComposeBody] = useState('')

    const filters = useMemo(() => {
        const next: TicketListParams = { limit: 50 }
        if (statusFilter !== 'all') {
            next.status = statusFilter
        }
        if (priorityFilter !== 'all') {
            next.priority = priorityFilter
        }
        const trimmedQuery = query.trim()
        if (trimmedQuery) {
            next.q = trimmedQuery
        }
        return next
    }, [statusFilter, priorityFilter, query])

    const { data, isLoading } = useTickets(filters)
    const composeMutation = useComposeTicket()

    const handleCompose = async () => {
        const to = composeTo.trim()
        const subject = composeSubject.trim()
        const body = composeBody.trim()

        if (!to || !subject || !body) {
            toast.error('To, subject, and body are required')
            return
        }

        try {
            const result = await composeMutation.mutateAsync({
                to_emails: [to],
                subject,
                body_text: body,
            })
            toast.success(
                result.status === 'queued'
                    ? 'Email queued and ticket created'
                    : 'Email sent and ticket created'
            )
            setComposeTo('')
            setComposeSubject('')
            setComposeBody('')
            router.push(`/tickets/${result.ticket_id}`)
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Failed to compose ticket email'
            toast.error(message)
        }
    }

    return (
        <div className="space-y-6 p-4 md:p-6">
            <Card>
                <CardHeader>
                    <CardTitle>Tickets</CardTitle>
                    <CardDescription>Global inbox for inbound and outbound ticket threads.</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3 md:grid-cols-5">
                    <Input
                        placeholder="Search subject, requester, code"
                        value={query}
                        onChange={(event) => setQuery(event.target.value)}
                        className="md:col-span-3"
                    />
                    <Select
                        value={statusFilter}
                        onValueChange={(value) => setStatusFilter((value ?? 'all') as TicketStatusFilter)}
                    >
                        <SelectTrigger>
                            <SelectValue placeholder="Status" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All statuses</SelectItem>
                            {STATUS_OPTIONS.map((value) => (
                                <SelectItem key={value} value={value}>
                                    {value}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    <Select
                        value={priorityFilter}
                        onValueChange={(value) =>
                            setPriorityFilter((value ?? 'all') as TicketPriorityFilter)
                        }
                    >
                        <SelectTrigger>
                            <SelectValue placeholder="Priority" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All priorities</SelectItem>
                            {PRIORITY_OPTIONS.map((value) => (
                                <SelectItem key={value} value={value}>
                                    {value}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Compose</CardTitle>
                    <CardDescription>Send a new email and open a ticket thread.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                    <Input
                        placeholder="To email"
                        value={composeTo}
                        onChange={(event) => setComposeTo(event.target.value)}
                    />
                    <Input
                        placeholder="Subject"
                        value={composeSubject}
                        onChange={(event) => setComposeSubject(event.target.value)}
                    />
                    <Textarea
                        placeholder="Message"
                        value={composeBody}
                        onChange={(event) => setComposeBody(event.target.value)}
                        rows={4}
                    />
                    <Button onClick={handleCompose} disabled={composeMutation.isPending}>
                        {composeMutation.isPending ? 'Sending...' : 'Send'}
                    </Button>
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Inbox</CardTitle>
                </CardHeader>
                <CardContent>
                    {isLoading ? (
                        <p className="text-sm text-muted-foreground">Loading tickets...</p>
                    ) : data?.items.length ? (
                        <div className="space-y-2">
                            {data.items.map((ticket) => (
                                <Link
                                    key={ticket.id}
                                    href={`/tickets/${ticket.id}`}
                                    className="block rounded-md border p-3 transition hover:bg-accent"
                                >
                                    <div className="flex flex-wrap items-center gap-2">
                                        <span className="text-sm font-semibold">{ticket.ticket_code}</span>
                                        <Badge variant="secondary">{ticket.status}</Badge>
                                        <Badge variant="outline">{ticket.priority}</Badge>
                                        {ticket.surrogate_link_status === 'needs_review' && (
                                            <Badge variant="destructive">Needs review</Badge>
                                        )}
                                    </div>
                                    <p className="mt-1 text-sm font-medium">{ticket.subject || '(No subject)'}</p>
                                    <p className="text-xs text-muted-foreground">
                                        {ticket.requester_email || 'Unknown sender'}
                                    </p>
                                </Link>
                            ))}
                        </div>
                    ) : (
                        <p className="text-sm text-muted-foreground">No tickets match your filters.</p>
                    )}
                </CardContent>
            </Card>
        </div>
    )
}
