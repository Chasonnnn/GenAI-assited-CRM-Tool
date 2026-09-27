"use client"

import Link from 'next/link'
import { useState } from 'react'
import { useParams } from 'next/navigation'
import { toast } from '@/components/ui/toast'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { LoadErrorState, PermissionDeniedState, QueryErrorState } from '@/components/error-state'
import type { SurrogateEmailContactCreatePayload } from '@/lib/api/surrogate-emails'
import { usePermissionCheck } from '@/lib/hooks/use-permission-check'
import { createSelectLabelGetter } from '@/lib/select-labels'
import { getCorrespondenceTicketStatusLabel } from '@/lib/ticket-status-labels'
import { getActionErrorMessage } from '@/lib/forms/api-field-errors'
import {
    useCreateSurrogateEmailContact,
    useDeactivateSurrogateEmailContact,
    useSurrogateEmailContacts,
    useSurrogateEmails,
} from '@/lib/hooks/use-surrogate-emails'

const getContactSourceLabel = createSelectLabelGetter(
    { system: 'System', manual: 'Manual' },
    { emptyLabel: 'Unknown source', unknownLabel: 'Unknown source' },
)

const getTicketPriorityLabel = createSelectLabelGetter(
    { low: 'Low', normal: 'Normal', high: 'High', urgent: 'Urgent' },
    { emptyLabel: 'Unknown priority', unknownLabel: 'Unknown priority' },
)

// Contact type is free text; only the value the system writes is mapped.
const SYSTEM_CONTACT_TYPE_LABELS: Record<string, string> = { surrogate: 'Surrogate' }

function formatContactType(value: string): string {
    return Object.hasOwn(SYSTEM_CONTACT_TYPE_LABELS, value) ? SYSTEM_CONTACT_TYPE_LABELS[value] ?? value : value
}

export default function SurrogateEmailsPage() {
    const params = useParams<{ id: string }>()
    const surrogateId = params.id
    const permissionCheck = usePermissionCheck()
    const permissionsLoading = permissionCheck.isLoading
    const canViewEmails = permissionCheck.can('view_tickets')

    const emailsQuery = useSurrogateEmails(surrogateId, { enabled: canViewEmails })
    const contactsQuery = useSurrogateEmailContacts(surrogateId, { enabled: canViewEmails })
    const { data: emailsData, isLoading: emailsLoading } = emailsQuery
    const { data: contactsData, isLoading: contactsLoading } = contactsQuery

    const createContact = useCreateSurrogateEmailContact(surrogateId)
    const deactivateContact = useDeactivateSurrogateEmailContact(surrogateId)

    const [contactEmail, setContactEmail] = useState('')
    const [contactLabel, setContactLabel] = useState('')
    const [contactType, setContactType] = useState('')

    const handleAddContact = async () => {
        const email = contactEmail.trim()
        if (!email) {
            toast.error('Email is required')
            return
        }

        const payload: SurrogateEmailContactCreatePayload = { email }
        const label = contactLabel.trim()
        if (label) {
            payload.label = label
        }
        const trimmedContactType = contactTypeValue(contactType)
        if (trimmedContactType) {
            payload.contact_type = trimmedContactType
        }

        try {
            await createContact.mutateAsync(payload)
            toast.success('Contact added')
            setContactEmail('')
            setContactLabel('')
            setContactType('')
        } catch (error) {
            const message = getActionErrorMessage(error, "Couldn't add contact. Try again.")
            if (message) toast.error(message)
        }
    }

    const handleDeactivate = async (contactId: string) => {
        try {
            await deactivateContact.mutateAsync(contactId)
            toast.success('Contact deactivated')
        } catch (error) {
            const message = getActionErrorMessage(error, "Couldn't deactivate contact. Try again.")
            if (message) toast.error(message)
        }
    }

    if (permissionsLoading) {
        return <p className="text-sm text-muted-foreground">Loading…</p>
    }

    if (permissionCheck.isError) {
        return (
            <LoadErrorState
                title="Couldn't load permissions"
                onRetry={permissionCheck.retry}
                isRetrying={permissionCheck.isRetrying}
                headingLevel={2}
            />
        )
    }

    if (!canViewEmails) {
        return (
            <PermissionDeniedState
                title="No access to emails"
                description="Ask an admin to update your role."
                secondaryHref={`/surrogates/${surrogateId}`}
                secondaryLabel="Back to Overview"
                headingLevel={2}
            />
        )
    }

    return (
        <div className="space-y-6">
            <Card>
                <CardHeader>
                    <CardTitle>Email History</CardTitle>
                </CardHeader>
                <CardContent>
                    {emailsQuery.isError ? (
                        <QueryErrorState
                            error={emailsQuery.error}
                            onRetry={() => void emailsQuery.refetch()}
                            isRetrying={emailsQuery.isFetching}
                            title="Couldn't load emails"
                            className="min-h-0 py-10"
                        />
                    ) : emailsLoading ? (
                        <p className="text-sm text-muted-foreground">Loading emails…</p>
                    ) : emailsData?.items.length ? (
                        <div className="space-y-2">
                            {emailsData.items.map((item) => (
                                <Link
                                    key={item.id}
                                    href={`/tickets/${item.id}`}
                                    className="block rounded-md border p-3 transition hover:bg-accent"
                                >
                                    <div className="flex flex-wrap items-center gap-2">
                                        <span className="text-sm font-semibold">{item.ticket_code}</span>
                                        <Badge variant="secondary">{getCorrespondenceTicketStatusLabel(item.status)}</Badge>
                                        <Badge variant="outline">{getTicketPriorityLabel(item.priority)}</Badge>
                                    </div>
                                    <p className="mt-1 text-sm">{item.subject || '(No subject)'}</p>
                                    <p className="text-xs text-muted-foreground">
                                        {item.requester_email || 'Unknown sender'}
                                    </p>
                                </Link>
                            ))}
                        </div>
                    ) : (
                        <p className="text-sm text-muted-foreground">No linked ticket emails yet.</p>
                    )}
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Email Contacts</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="grid gap-3 md:grid-cols-4">
                        <div className="grid gap-2 md:col-span-2">
                            <Label htmlFor="surrogate-email-contact-email">Email</Label>
                            <Input
                                id="surrogate-email-contact-email"
                                type="email"
                                value={contactEmail}
                                onChange={(event) => setContactEmail(event.target.value)}
                            />
                        </div>
                        <div className="grid gap-2">
                            <Label htmlFor="surrogate-email-contact-label">Label</Label>
                            <Input
                                id="surrogate-email-contact-label"
                                value={contactLabel}
                                onChange={(event) => setContactLabel(event.target.value)}
                            />
                        </div>
                        <div className="grid gap-2">
                            <Label htmlFor="surrogate-email-contact-type">Type</Label>
                            <Input
                                id="surrogate-email-contact-type"
                                value={contactType}
                                onChange={(event) => setContactType(event.target.value)}
                            />
                        </div>
                    </div>
                    <Button onClick={handleAddContact} disabled={createContact.isPending}>
                        {createContact.isPending ? 'Adding…' : 'Add Contact'}
                    </Button>

                    {contactsQuery.isError ? (
                        <QueryErrorState
                            error={contactsQuery.error}
                            onRetry={() => void contactsQuery.refetch()}
                            isRetrying={contactsQuery.isFetching}
                            title="Couldn't load contacts"
                            className="min-h-0 py-10"
                        />
                    ) : contactsLoading ? (
                        <p className="text-sm text-muted-foreground">Loading contacts…</p>
                    ) : (
                        <div className="space-y-2">
                            {contactsData?.items.map((contact) => (
                                <div key={contact.id} className="flex items-center justify-between rounded border p-2">
                                    <div>
                                        <p className="text-sm font-medium">{contact.email}</p>
                                        <p className="text-xs text-muted-foreground">
                                            {getContactSourceLabel(contact.source)}
                                            {contact.label ? ` • ${contact.label}` : ''}
                                            {contact.contact_type ? ` • ${formatContactType(contact.contact_type)}` : ''}
                                        </p>
                                    </div>
                                    {contact.source === 'manual' ? (
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => handleDeactivate(contact.id)}
                                            disabled={!contact.is_active || deactivateContact.isPending}
                                        >
                                            {contact.is_active ? 'Deactivate' : 'Inactive'}
                                        </Button>
                                    ) : (
                                        <Badge variant="secondary">System</Badge>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    )
}

function contactTypeValue(value: string): string | null {
    const next = value.trim()
    return next ? next : null
}
