"use client"

import Link from 'next/link'
import { Suspense, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { toast } from '@/components/ui/toast'
import { InboxIcon, Loader2Icon, PlusIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
    Dialog,
    DialogClose,
    DialogContent,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'
import { ValidatedField } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { EmptyState } from '@/components/empty-state'
import { PermissionDeniedState, QueryErrorState } from '@/components/error-state'
import { ListToolbar, ListToolbarSearch } from '@/components/list-toolbar'
import { PageHeader } from '@/components/page-header'
import { useAuth } from '@/lib/auth-context'
import { useFormValidation } from '@/lib/forms/use-form-validation'
import { EMAIL_INVALID_MESSAGE, validateEmail, validateRequired } from '@/lib/forms/validators'
import { useComposeTicket, useTickets } from '@/lib/hooks/use-tickets'
import type { TicketListParams, TicketPriority, TicketStatus } from '@/lib/api/tickets'
import MessagesPageClient from '../messages/page.client'

const STATUS_OPTIONS = ['new', 'open', 'pending', 'resolved', 'closed', 'spam'] as const
const PRIORITY_OPTIONS = ['low', 'normal', 'high', 'urgent'] as const
type TicketStatusFilter = TicketStatus | 'all'
type TicketPriorityFilter = TicketPriority | 'all'

import { TICKET_STATUS_LABELS } from "@/lib/ticket-status-labels"

const TICKET_PRIORITY_LABELS: Record<TicketPriority, string> = {
    low: 'Low',
    normal: 'Normal',
    high: 'High',
    urgent: 'Urgent',
}

function getTicketStatusLabel(value: TicketStatusFilter | null | undefined): string {
    if (!value || value === 'all') return 'All statuses'
    return TICKET_STATUS_LABELS[value] ?? 'Unknown status'
}

function getTicketPriorityLabel(value: TicketPriorityFilter | null | undefined): string {
    if (!value || value === 'all') return 'All priorities'
    return TICKET_PRIORITY_LABELS[value] ?? 'Unknown priority'
}

export default function TicketsPage() {
    const { user, isLoading } = useAuth()
    const isDeveloper = user?.role === 'developer'

    if (isLoading) {
        return <TicketsLoadingState />
    }

    if (!isDeveloper) {
        return (
            <div className="flex min-h-full flex-col">
                <PageHeader title="Tickets" />
                <PermissionDeniedState
                    description="Tickets are available only to developers."
                    secondaryHref="/dashboard"
                    headingLevel={2}
                />
            </div>
        )
    }

    return (
        <Suspense fallback={<TicketsLoadingState />}>
            <DeveloperTicketsWorkspace />
        </Suspense>
    )
}

function TicketsLoadingState() {
    return (
        <div className="flex min-h-96 items-center justify-center" aria-label="Loading tickets">
            <Loader2Icon className="size-7 animate-spin text-muted-foreground" />
        </div>
    )
}

function DeveloperTicketsWorkspace() {
    const { replace } = useRouter()
    const searchParams = useSearchParams()
    const activeView = searchParams.get('view') === 'messages' ? 'messages' : 'email'
    const [composeOpen, setComposeOpen] = useState(false)

    const handleViewChange = (value: string | number) => {
        replace(value === 'messages' ? '/tickets?view=messages' : '/tickets', { scroll: false })
    }

    return (
        <div className="flex min-h-full flex-col">
            <PageHeader
                title="Tickets"
                actions={
                    activeView === 'email' ? (
                        <Button onClick={() => setComposeOpen(true)}>
                            <PlusIcon aria-hidden="true" />
                            New ticket
                        </Button>
                    ) : null
                }
            />

            <div className="space-y-6 p-6">
                <Tabs value={activeView} onValueChange={handleViewChange}>
                    <TabsList aria-label="Ticket channels">
                        <TabsTrigger value="email">Email tickets</TabsTrigger>
                        <TabsTrigger value="messages">SMS/MMS</TabsTrigger>
                    </TabsList>
                </Tabs>

                {activeView === 'messages' ? (
                    <MessagesPageClient embedded />
                ) : (
                    <EmailTicketsView />
                )}
            </div>

            <ComposeTicketDialog open={composeOpen} onOpenChange={setComposeOpen} />
        </div>
    )
}

type ComposeValues = { to: string; subject: string; body: string }

const EMPTY_COMPOSE_VALUES: ComposeValues = { to: '', subject: '', body: '' }

function validateCompose(values: ComposeValues) {
    return {
        to: validateEmail(values.to, { requiredMessage: 'Enter a recipient email.' }),
        subject: validateRequired(values.subject, 'Enter a subject.'),
        body: validateRequired(values.body, 'Enter a message.'),
    }
}

function ComposeTicketDialog({
    open,
    onOpenChange,
}: {
    open: boolean
    onOpenChange: (open: boolean) => void
}) {
    const { push } = useRouter()
    const composeMutation = useComposeTicket()
    const [values, setValues] = useState<ComposeValues>(EMPTY_COMPOSE_VALUES)
    const form = useFormValidation({ values, validate: validateCompose })

    const setField = (name: keyof ComposeValues, value: string) => {
        setValues((current) => ({ ...current, [name]: value }))
    }

    const handleOpenChange = (nextOpen: boolean) => {
        // The draft stays for the next open; validation state starts fresh.
        if (!nextOpen) form.reset()
        onOpenChange(nextOpen)
    }

    const submit = async (current: ComposeValues) => {
        try {
            const result = await composeMutation.mutateAsync({
                to_emails: [current.to.trim()],
                subject: current.subject.trim(),
                body_text: current.body.trim(),
            })
            toast.success(
                result.status === 'queued'
                    ? 'Email queued and ticket created'
                    : 'Email sent and ticket created'
            )
            setValues(EMPTY_COMPOSE_VALUES)
            form.reset()
            onOpenChange(false)
            push(`/tickets/${result.ticket_id}`)
        } catch (error) {
            const message = form.applyApiError(error, {
                fields: { to_emails: 'to', 'to_emails.0': 'to', subject: 'subject', body_text: 'body' },
                messages: { to: EMAIL_INVALID_MESSAGE },
                fallback: "Couldn't send the email. Try again.",
            })
            if (message) toast.error(message)
        }
    }

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogContent size="lg">
                <form noValidate onSubmit={form.handleSubmit(submit)} className="grid gap-4">
                    <DialogHeader>
                        <DialogTitle>New ticket</DialogTitle>
                    </DialogHeader>
                    <ValidatedField label="To" error={form.errorFor('to')}>
                        {(control) => (
                            <Input
                                {...control}
                                type="email"
                                autoComplete="email"
                                value={values.to}
                                onChange={(event) => setField('to', event.target.value)}
                                onBlur={() => form.touch('to')}
                            />
                        )}
                    </ValidatedField>
                    <ValidatedField label="Subject" error={form.errorFor('subject')}>
                        {(control) => (
                            <Input
                                {...control}
                                value={values.subject}
                                onChange={(event) => setField('subject', event.target.value)}
                                onBlur={() => form.touch('subject')}
                            />
                        )}
                    </ValidatedField>
                    <ValidatedField label="Message" error={form.errorFor('body')}>
                        {(control) => (
                            <Textarea
                                {...control}
                                rows={8}
                                value={values.body}
                                onChange={(event) => setField('body', event.target.value)}
                                onBlur={() => form.touch('body')}
                            />
                        )}
                    </ValidatedField>
                    <DialogFooter>
                        <DialogClose render={<Button type="button" variant="outline" />}>Cancel</DialogClose>
                        <Button type="submit" disabled={composeMutation.isPending}>
                            {composeMutation.isPending ? (
                                <Loader2Icon className="animate-spin" aria-hidden="true" />
                            ) : null}
                            Send
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    )
}

function EmailTicketsView() {
    const [statusFilter, setStatusFilter] = useState<TicketStatusFilter>('all')
    const [priorityFilter, setPriorityFilter] = useState<TicketPriorityFilter>('all')
    const [query, setQuery] = useState('')

    const filters: TicketListParams = { limit: 50 }
    if (statusFilter !== 'all') {
        filters.status = statusFilter
    }
    if (priorityFilter !== 'all') {
        filters.priority = priorityFilter
    }
    const trimmedQuery = query.trim()
    if (trimmedQuery) {
        filters.q = trimmedQuery
    }

    const ticketsQuery = useTickets(filters)
    const { data, isLoading } = ticketsQuery
    const hasActiveFilters = statusFilter !== 'all' || priorityFilter !== 'all' || trimmedQuery !== ''

    const resetFilters = () => {
        setStatusFilter('all')
        setPriorityFilter('all')
        setQuery('')
    }

    return (
        <div className="space-y-4">
            <ListToolbar
                className="border-b-0 px-0 py-0"
                filters={
                    <>
                        <Select
                            value={statusFilter}
                            onValueChange={(value) => setStatusFilter((value ?? 'all') as TicketStatusFilter)}
                        >
                            <SelectTrigger aria-label="Filter by status" className="min-w-36 flex-1 sm:w-[180px] sm:flex-none">
                                <SelectValue placeholder="All statuses">
                                    {(value: string | null) => getTicketStatusLabel((value ?? 'all') as TicketStatusFilter)}
                                </SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">All statuses</SelectItem>
                                {STATUS_OPTIONS.map((value) => (
                                    <SelectItem key={value} value={value}>
                                        {getTicketStatusLabel(value)}
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
                            <SelectTrigger aria-label="Filter by priority" className="min-w-36 flex-1 sm:w-[180px] sm:flex-none">
                                <SelectValue placeholder="All priorities">
                                    {(value: string | null) =>
                                        getTicketPriorityLabel((value ?? 'all') as TicketPriorityFilter)
                                    }
                                </SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">All priorities</SelectItem>
                                {PRIORITY_OPTIONS.map((value) => (
                                    <SelectItem key={value} value={value}>
                                        {getTicketPriorityLabel(value)}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </>
                }
                search={
                    <ListToolbarSearch
                        value={query}
                        onValueChange={setQuery}
                        placeholder="Search subject, requester, code"
                        aria-label="Search tickets"
                    />
                }
                chips={[
                    statusFilter !== 'all' && {
                        key: 'status',
                        label: `Status: ${getTicketStatusLabel(statusFilter)}`,
                        onRemove: () => setStatusFilter('all'),
                    },
                    priorityFilter !== 'all' && {
                        key: 'priority',
                        label: `Priority: ${getTicketPriorityLabel(priorityFilter)}`,
                        onRemove: () => setPriorityFilter('all'),
                    },
                ]}
                onReset={resetFilters}
            />

            <div className="rounded-xl border bg-card">
                {isLoading ? (
                    <div className="flex min-h-56 items-center justify-center" aria-label="Loading tickets">
                        <Loader2Icon className="size-6 animate-spin text-muted-foreground" aria-hidden="true" />
                    </div>
                ) : ticketsQuery.isError ? (
                    <QueryErrorState
                        error={ticketsQuery.error}
                        onRetry={() => void ticketsQuery.refetch()}
                        isRetrying={ticketsQuery.isFetching}
                        title="Couldn't load tickets"
                        className="min-h-0 py-10"
                    />
                ) : data?.items.length ? (
                    <ul className="divide-y">
                        {data.items.map((ticket) => (
                            <li key={ticket.id}>
                                <Link
                                    href={`/tickets/${ticket.id}`}
                                    className="block px-4 py-3 transition-colors hover:bg-accent focus-visible:bg-accent focus-visible:outline-none"
                                >
                                    <div className="flex flex-wrap items-center gap-2">
                                        <span className="text-sm font-semibold">{ticket.ticket_code}</span>
                                        <Badge variant="secondary">{getTicketStatusLabel(ticket.status)}</Badge>
                                        <Badge variant="outline">{getTicketPriorityLabel(ticket.priority)}</Badge>
                                        {ticket.surrogate_link_status === 'needs_review' && (
                                            <Badge variant="destructive">Needs review</Badge>
                                        )}
                                    </div>
                                    <p className="mt-1 text-sm font-medium">{ticket.subject || '(No subject)'}</p>
                                    <p className="text-xs text-muted-foreground">
                                        {ticket.requester_email || 'Unknown sender'}
                                    </p>
                                </Link>
                            </li>
                        ))}
                    </ul>
                ) : hasActiveFilters ? (
                    <EmptyState icon={InboxIcon} title="No matching tickets" onClearFilters={resetFilters} />
                ) : (
                    <EmptyState icon={InboxIcon} title="No tickets" />
                )}
            </div>
        </div>
    )
}
