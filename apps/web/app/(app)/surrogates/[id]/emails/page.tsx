"use client"

import Link from 'next/link'
import { useState } from 'react'
import { useParams } from 'next/navigation'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import type { SurrogateEmailContactCreatePayload } from '@/lib/api/surrogate-emails'
import {
    useCreateSurrogateEmailContact,
    useDeactivateSurrogateEmailContact,
    useSurrogateEmailContacts,
    useSurrogateEmails,
} from '@/lib/hooks/use-surrogate-emails'

export default function SurrogateEmailsPage() {
    const params = useParams<{ id: string }>()
    const surrogateId = params.id

    const { data: emailsData, isLoading: emailsLoading } = useSurrogateEmails(surrogateId)
    const { data: contactsData, isLoading: contactsLoading } = useSurrogateEmailContacts(surrogateId)

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
            const message = error instanceof Error ? error.message : 'Failed to add contact'
            toast.error(message)
        }
    }

    const handleDeactivate = async (contactId: string) => {
        try {
            await deactivateContact.mutateAsync(contactId)
            toast.success('Contact deactivated')
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Failed to deactivate contact'
            toast.error(message)
        }
    }

    return (
        <div className="space-y-6">
            <Card>
                <CardHeader>
                    <CardTitle>Email History</CardTitle>
                </CardHeader>
                <CardContent>
                    {emailsLoading ? (
                        <p className="text-sm text-muted-foreground">Loading emails...</p>
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
                                        <Badge variant="secondary">{item.status}</Badge>
                                        <Badge variant="outline">{item.priority}</Badge>
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
                    <div className="grid gap-2 md:grid-cols-4">
                        <Input
                            placeholder="Email"
                            value={contactEmail}
                            onChange={(event) => setContactEmail(event.target.value)}
                            className="md:col-span-2"
                        />
                        <Input
                            placeholder="Label"
                            value={contactLabel}
                            onChange={(event) => setContactLabel(event.target.value)}
                        />
                        <Input
                            placeholder="Type"
                            value={contactType}
                            onChange={(event) => setContactType(event.target.value)}
                        />
                    </div>
                    <Button onClick={handleAddContact} disabled={createContact.isPending}>
                        {createContact.isPending ? 'Adding...' : 'Add Contact'}
                    </Button>

                    {contactsLoading ? (
                        <p className="text-sm text-muted-foreground">Loading contacts...</p>
                    ) : (
                        <div className="space-y-2">
                            {contactsData?.items.map((contact) => (
                                <div key={contact.id} className="flex items-center justify-between rounded border p-2">
                                    <div>
                                        <p className="text-sm font-medium">{contact.email}</p>
                                        <p className="text-xs text-muted-foreground">
                                            {contact.source}
                                            {contact.label ? ` • ${contact.label}` : ''}
                                            {contact.contact_type ? ` • ${contact.contact_type}` : ''}
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
