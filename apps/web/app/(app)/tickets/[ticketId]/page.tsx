"use client"

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { getTicketAttachmentDownloadUrl } from '@/lib/api/tickets'
import type { TicketPriority, TicketStatus } from '@/lib/api/tickets'
import {
    useAddTicketNote,
    useLinkTicketSurrogate,
    usePatchTicket,
    useReplyTicket,
    useTicket,
} from '@/lib/hooks/use-tickets'

const STATUS_OPTIONS = ['new', 'open', 'pending', 'resolved', 'closed', 'spam'] as const
const PRIORITY_OPTIONS = ['low', 'normal', 'high', 'urgent'] as const

export default function TicketDetailPage() {
    const params = useParams<{ ticketId: string }>()
    const ticketId = params.ticketId

    const { data, isLoading } = useTicket(ticketId)

    const patchMutation = usePatchTicket()
    const replyMutation = useReplyTicket()
    const addNoteMutation = useAddTicketNote()
    const linkMutation = useLinkTicketSurrogate()

    const [statusValue, setStatusValue] = useState<TicketStatus>('new')
    const [priorityValue, setPriorityValue] = useState<TicketPriority>('normal')
    const [replyTo, setReplyTo] = useState('')
    const [replyBody, setReplyBody] = useState('')
    const [noteBody, setNoteBody] = useState('')
    const [surrogateId, setSurrogateId] = useState('')

    useEffect(() => {
        if (!data?.ticket) return
        setStatusValue(data.ticket.status)
        setPriorityValue(data.ticket.priority)
        setReplyTo(data.ticket.requester_email || '')
        setSurrogateId(data.ticket.surrogate_id || '')
    }, [data?.ticket])

    const handleUpdate = async () => {
        if (!data?.ticket) return
        try {
            await patchMutation.mutateAsync({
                ticketId: data.ticket.id,
                data: {
                    status: statusValue,
                    priority: priorityValue,
                },
            })
            toast.success('Ticket updated')
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Failed to update ticket'
            toast.error(message)
        }
    }

    const handleReply = async () => {
        if (!data?.ticket) return
        const recipient = replyTo.trim()
        const body = replyBody.trim()
        if (!recipient || !body) {
            toast.error('Reply recipient and body are required')
            return
        }

        try {
            const result = await replyMutation.mutateAsync({
                ticketId: data.ticket.id,
                data: {
                    to_emails: [recipient],
                    subject: data.ticket.subject || 'Re:',
                    body_text: body,
                },
            })
            toast.success(result.status === 'queued' ? 'Reply queued' : 'Reply sent')
            setReplyBody('')
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Failed to send reply'
            toast.error(message)
        }
    }

    const handleAddNote = async () => {
        if (!data?.ticket) return
        const body = noteBody.trim()
        if (!body) {
            toast.error('Note cannot be empty')
            return
        }

        try {
            await addNoteMutation.mutateAsync({
                ticketId: data.ticket.id,
                bodyMarkdown: body,
            })
            toast.success('Note added')
            setNoteBody('')
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Failed to add note'
            toast.error(message)
        }
    }

    const handleLink = async () => {
        if (!data?.ticket) return
        try {
            await linkMutation.mutateAsync({
                ticketId: data.ticket.id,
                surrogateId: surrogateId.trim() || null,
            })
            toast.success('Surrogate link updated')
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Failed to update surrogate link'
            toast.error(message)
        }
    }

    const handleAttachmentDownload = async (attachmentId: string) => {
        try {
            const url = await getTicketAttachmentDownloadUrl(ticketId, attachmentId)
            window.open(url, '_blank', 'noopener,noreferrer')
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Failed to get attachment URL'
            toast.error(message)
        }
    }

    if (isLoading) {
        return <div className="p-4 text-sm text-muted-foreground md:p-6">Loading ticket...</div>
    }

    if (!data?.ticket) {
        return <div className="p-4 text-sm text-muted-foreground md:p-6">Ticket not found.</div>
    }

    return (
        <div className="space-y-6 p-4 md:p-6">
            <Card>
                <CardHeader>
                    <CardTitle>{data.ticket.ticket_code}</CardTitle>
                    <CardDescription>{data.ticket.subject || '(No subject)'}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                    <div className="flex flex-wrap gap-2">
                        <Badge variant="secondary">{data.ticket.status}</Badge>
                        <Badge variant="outline">{data.ticket.priority}</Badge>
                        {data.ticket.surrogate_link_status === 'needs_review' && (
                            <Badge variant="destructive">Needs review</Badge>
                        )}
                    </div>
                    <p className="text-sm text-muted-foreground">
                        Requester: {data.ticket.requester_email || 'Unknown sender'}
                    </p>

                    <div className="grid gap-3 md:grid-cols-3">
                        <Select
                            value={statusValue}
                            onValueChange={(value) => setStatusValue((value ?? 'new') as TicketStatus)}
                        >
                            <SelectTrigger>
                                <SelectValue placeholder="Status" />
                            </SelectTrigger>
                            <SelectContent>
                                {STATUS_OPTIONS.map((value) => (
                                    <SelectItem key={value} value={value}>
                                        {value}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        <Select
                            value={priorityValue}
                            onValueChange={(value) =>
                                setPriorityValue((value ?? 'normal') as TicketPriority)
                            }
                        >
                            <SelectTrigger>
                                <SelectValue placeholder="Priority" />
                            </SelectTrigger>
                            <SelectContent>
                                {PRIORITY_OPTIONS.map((value) => (
                                    <SelectItem key={value} value={value}>
                                        {value}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        <Button onClick={handleUpdate} disabled={patchMutation.isPending}>
                            {patchMutation.isPending ? 'Saving...' : 'Save'}
                        </Button>
                    </div>

                    <div className="grid gap-3 md:grid-cols-3">
                        <Input
                            placeholder="Surrogate ID (manual link)"
                            value={surrogateId}
                            onChange={(event) => setSurrogateId(event.target.value)}
                        />
                        <Button
                            variant="outline"
                            onClick={handleLink}
                            disabled={linkMutation.isPending}
                            className="md:col-span-2"
                        >
                            {linkMutation.isPending ? 'Updating link...' : 'Update Surrogate Link'}
                        </Button>
                    </div>
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Reply</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                    <Input
                        placeholder="Recipient"
                        value={replyTo}
                        onChange={(event) => setReplyTo(event.target.value)}
                    />
                    <Textarea
                        placeholder="Write your reply"
                        value={replyBody}
                        onChange={(event) => setReplyBody(event.target.value)}
                        rows={4}
                    />
                    <Button onClick={handleReply} disabled={replyMutation.isPending}>
                        {replyMutation.isPending ? 'Sending...' : 'Send reply'}
                    </Button>
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Internal Notes</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                    <Textarea
                        placeholder="Add internal note"
                        value={noteBody}
                        onChange={(event) => setNoteBody(event.target.value)}
                        rows={3}
                    />
                    <Button onClick={handleAddNote} disabled={addNoteMutation.isPending}>
                        {addNoteMutation.isPending ? 'Saving...' : 'Add note'}
                    </Button>
                    <div className="space-y-2">
                        {data.notes.map((note) => (
                            <div key={note.id} className="rounded border p-2 text-sm">
                                <p>{note.body_markdown}</p>
                                <p className="mt-1 text-xs text-muted-foreground">
                                    {new Date(note.created_at).toLocaleString()}
                                </p>
                            </div>
                        ))}
                    </div>
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Messages</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                    {data.messages.map((message) => (
                        <div key={message.id} className="rounded border p-3">
                            <div className="mb-2 flex flex-wrap items-center gap-2">
                                <Badge variant="outline">{message.direction}</Badge>
                                <span className="text-xs text-muted-foreground">
                                    {message.date_header
                                        ? new Date(message.date_header).toLocaleString()
                                        : 'Unknown time'}
                                </span>
                            </div>
                            <p className="text-sm font-medium">{message.subject || '(No subject)'}</p>
                            <p className="text-xs text-muted-foreground">From: {message.from_email || 'Unknown'}</p>
                            {message.body_text && (
                                <p className="mt-2 whitespace-pre-wrap text-sm">{message.body_text}</p>
                            )}
                            {!!message.attachments.length && (
                                <div className="mt-2 flex flex-wrap gap-2">
                                    {message.attachments.map((attachment) => (
                                        <Button
                                            key={attachment.id}
                                            variant="outline"
                                            size="sm"
                                            onClick={() => handleAttachmentDownload(attachment.attachment_id)}
                                        >
                                            {attachment.filename || 'Attachment'}
                                        </Button>
                                    ))}
                                </div>
                            )}
                        </div>
                    ))}
                </CardContent>
            </Card>
        </div>
    )
}
