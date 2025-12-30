"use client"

import * as React from "react"
import { useRouter, useParams } from "next/navigation"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { DateTimePicker } from "@/components/ui/date-time-picker"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { RichTextEditor } from "@/components/rich-text-editor"
import {
    PlusIcon,
    MoreVerticalIcon,
    CopyIcon,
    CheckIcon,
    XIcon,
    TrashIcon,
    LoaderIcon,
    ArrowLeftIcon,
    SparklesIcon,
    MailIcon,
    BrainIcon,
    HeartHandshakeIcon,
} from "lucide-react"
import { InlineEditField } from "@/components/inline-edit-field"
import { FileUploadZone } from "@/components/FileUploadZone"
import { useCase, useCaseActivity, useChangeStatus, useArchiveCase, useRestoreCase, useUpdateCase } from "@/lib/hooks/use-cases"
import { useQueues, useClaimCase, useReleaseCase } from "@/lib/hooks/use-queues"
import { useDefaultPipeline } from "@/lib/hooks/use-pipelines"
import { useNotes, useCreateNote, useDeleteNote } from "@/lib/hooks/use-notes"
import { useTasks, useCompleteTask, useUncompleteTask } from "@/lib/hooks/use-tasks"
import { useZoomStatus, useCreateZoomMeeting, useSendZoomInvite } from "@/lib/hooks/use-user-integrations"
import { useSummarizeCase, useDraftEmail, useAISettings } from "@/lib/hooks/use-ai"
import { useSetAIContext } from "@/lib/context/ai-context"
import { EmailComposeDialog } from "@/components/email/EmailComposeDialog"
import { ProposeMatchDialog } from "@/components/matches/ProposeMatchDialog"
import { CaseApplicationTab } from "@/components/cases/CaseApplicationTab"
import { useForms } from "@/lib/hooks/use-forms"
import type { EmailType, SummarizeCaseResponse, DraftEmailResponse } from "@/lib/api/ai"
import type { TaskListItem } from "@/lib/types/task"
import { useAuth } from "@/lib/auth-context"
import { cn } from "@/lib/utils"
import { parseDateInput } from "@/lib/utils/date"

// Format date for display
function formatDateTime(dateString: string): string {
    const parsed = parseDateInput(dateString)
    if (Number.isNaN(parsed.getTime())) return "—"
    return parsed.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    })
}

function formatDate(dateString: string): string {
    const parsed = parseDateInput(dateString)
    if (Number.isNaN(parsed.getTime())) return "—"
    return parsed.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
    })
}

function formatTaskDueLabel(task: TaskListItem): string | null {
    if (!task.due_date) return null
    if (!task.due_time) return `Due: ${formatDate(task.due_date)}`

    const start = new Date(`${task.due_date}T${task.due_time}`)
    const dateLabel = start.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
    const startTime = start.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })

    if (!task.duration_minutes) return `Due: ${dateLabel} ${startTime}`

    const end = new Date(start.getTime() + task.duration_minutes * 60_000)
    const endTime = end.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
    return `Due: ${dateLabel} ${startTime}–${endTime}`
}

function toLocalIsoDateTime(date: Date): string {
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:00`
}

function formatMeetingTimeForInvite(date: Date): string {
    return date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        timeZoneName: 'short',
    })
}

// Get initials from name
function getInitials(name: string | null): string {
    if (!name) return "?"
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
}

// Format activity type for display
function formatActivityType(type: string): string {
    const labels: Record<string, string> = {
        case_created: 'Case Created',
        info_edited: 'Information Edited',
        stage_changed: 'Stage Changed',
        assigned: 'Assigned',
        unassigned: 'Unassigned',
        priority_changed: 'Priority Changed',
        archived: 'Archived',
        restored: 'Restored',
        handoff_accepted: 'Handoff Accepted',
        handoff_denied: 'Handoff Denied',
        note_added: 'Note Added',
        note_deleted: 'Note Deleted',
        task_created: 'Task Created',
    }
    return labels[type] || type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

// Strip HTML tags for plain text display
function stripHtml(html: string): string {
    return html.replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').trim()
}

// Format activity details for display
function formatActivityDetails(type: string, details: Record<string, unknown>): string {
    const aiPrefix = details?.source === 'ai' ? 'AI-generated' : ''
    const withAiPrefix = (detail: string) => (aiPrefix ? `${aiPrefix} · ${detail}` : detail)
    const aiOnly = () => (aiPrefix ? aiPrefix : '')

    switch (type) {
        case 'status_changed':
            return withAiPrefix(`${details.from} → ${details.to}${details.reason ? `: ${details.reason}` : ''}`)
        case 'info_edited':
            if (details.changes && typeof details.changes === 'object') {
                const changes = Object.entries(details.changes as Record<string, unknown>)
                    .map(([field, value]) => `${field.replace(/_/g, ' ')}: ${String(value)}`)
                    .join(', ')
                return aiPrefix ? withAiPrefix(changes) : changes
            }
            return aiOnly()
        case 'assigned':
            return aiPrefix ? withAiPrefix(details.from_user_id ? 'Reassigned' : 'Assigned to user') : (details.from_user_id ? 'Reassigned' : 'Assigned to user')
        case 'unassigned':
            return aiPrefix ? withAiPrefix('Removed assignment') : 'Removed assignment'
        case 'priority_changed':
            return aiPrefix ? withAiPrefix(details.is_priority ? 'Marked as priority' : 'Removed priority') : (details.is_priority ? 'Marked as priority' : 'Removed priority')
        case 'handoff_denied':
            return details.reason ? withAiPrefix(String(details.reason)) : aiOnly()
        case 'note_added': {
            const content = details.content ? stripHtml(String(details.content)) : ''
            return content ? withAiPrefix(content.slice(0, 100) + (content.length > 100 ? '...' : '')) : aiOnly()
        }
        case 'note_deleted': {
            const preview = details.preview ? stripHtml(String(details.preview)) : ''
            return preview ? withAiPrefix(preview.slice(0, 100) + (preview.length > 100 ? '...' : '')) : aiOnly()
        }
        case 'task_created':
            return details.title ? withAiPrefix(`Task: ${String(details.title)}`) : aiOnly()
        default:
            return aiOnly()
    }
}

export default function CaseDetailPage() {
    const params = useParams()
    const id = params.id as string
    const router = useRouter()
    const { user } = useAuth()
    const { data: defaultPipeline } = useDefaultPipeline()
    const stageOptions = React.useMemo(() => defaultPipeline?.stages || [], [defaultPipeline])
    const stageById = React.useMemo(
        () => new Map(stageOptions.map(stage => [stage.id, stage])),
        [stageOptions]
    )
    const [copiedEmail, setCopiedEmail] = React.useState(false)
    const [editDialogOpen, setEditDialogOpen] = React.useState(false)
    const [releaseDialogOpen, setReleaseDialogOpen] = React.useState(false)
    const [selectedQueueId, setSelectedQueueId] = React.useState<string>("")
    const [zoomDialogOpen, setZoomDialogOpen] = React.useState(false)
    const [zoomTopic, setZoomTopic] = React.useState("")
    const [zoomDuration, setZoomDuration] = React.useState(30)
    const [zoomStartAt, setZoomStartAt] = React.useState<Date | undefined>(undefined)
    const [lastMeetingResult, setLastMeetingResult] = React.useState<{
        join_url: string
        meeting_id: number
        password: string | null
        start_time: string | null
    } | null>(null)
    const [aiSummary, setAiSummary] = React.useState<SummarizeCaseResponse | null>(null)
    const [aiDraftEmail, setAiDraftEmail] = React.useState<DraftEmailResponse | null>(null)
    const [selectedEmailType, setSelectedEmailType] = React.useState<EmailType | null>(null)
    const [emailDialogOpen, setEmailDialogOpen] = React.useState(false)
    const [proposeMatchOpen, setProposeMatchOpen] = React.useState(false)

    const timezoneName = React.useMemo(() => {
        try {
            return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
        } catch {
            return 'UTC'
        }
    }, [])

    // Fetch data
    const { data: caseData, isLoading, error } = useCase(id)
    const { data: activityData } = useCaseActivity(id)
    const { data: notes } = useNotes(id)
    const { data: tasksData } = useTasks({ case_id: id })

    // Mutations
    const changeStatusMutation = useChangeStatus()
    const archiveMutation = useArchiveCase()
    const restoreMutation = useRestoreCase()
    const createNoteMutation = useCreateNote()
    const deleteNoteMutation = useDeleteNote()
    const completeTaskMutation = useCompleteTask()
    const uncompleteTaskMutation = useUncompleteTask()
    const updateCaseMutation = useUpdateCase()
    const claimCaseMutation = useClaimCase()
    const releaseCaseMutation = useReleaseCase()
    const createZoomMeetingMutation = useCreateZoomMeeting()
    const sendZoomInviteMutation = useSendZoomInvite()
    const summarizeCaseMutation = useSummarizeCase()
    const draftEmailMutation = useDraftEmail()

    // Check if user has Zoom connected
    const { data: zoomStatus } = useZoomStatus()
    const { data: aiSettings } = useAISettings()
    const { data: forms } = useForms()
    const defaultFormId = forms?.find((f) => f.status === "published")?.id || ""

    // Set AI context for the chat panel
    useSetAIContext(
        caseData
            ? {
                entityType: "case",
                entityId: caseData.id,
                entityName: `Case #${caseData.case_number} - ${caseData.full_name}`,
            }
            : null
    )

    // Fetch queues for release dialog
    const canManageQueue = user?.role && ['case_manager', 'admin', 'developer'].includes(user.role)
    const { data: queues } = useQueues()

    const copyEmail = () => {
        if (!caseData) return
        navigator.clipboard.writeText(caseData.email)
        setCopiedEmail(true)
        setTimeout(() => setCopiedEmail(false), 2000)
    }

    const handleStatusChange = async (newStageId: string) => {
        if (!caseData) return
        await changeStatusMutation.mutateAsync({ caseId: id, data: { stage_id: newStageId } })
    }

    const handleArchive = async () => {
        await archiveMutation.mutateAsync(id)
        router.push('/cases')
    }

    const handleRestore = async () => {
        await restoreMutation.mutateAsync(id)
    }

    const handleAddNote = async (html: string) => {
        if (!html || html === '<p></p>') return
        await createNoteMutation.mutateAsync({ caseId: id, body: html })
    }

    const handleDeleteNote = async (noteId: string) => {
        await deleteNoteMutation.mutateAsync({ noteId, caseId: id })
    }

    const handleTaskToggle = async (taskId: string, isCompleted: boolean) => {
        if (isCompleted) {
            await uncompleteTaskMutation.mutateAsync(taskId)
        } else {
            await completeTaskMutation.mutateAsync(taskId)
        }
    }

    const handleClaimCase = async () => {
        await claimCaseMutation.mutateAsync(id)
    }

    const handleReleaseCase = async () => {
        if (!selectedQueueId) return
        await releaseCaseMutation.mutateAsync({ caseId: id, queueId: selectedQueueId })
        setReleaseDialogOpen(false)
        setSelectedQueueId("")
    }

    // Check if case is in a queue (can be claimed)
    const isInQueue = caseData?.owner_type === 'queue'
    const isOwnedByUser = caseData?.owner_type === 'user'

    if (isLoading) {
        return (
            <div className="flex min-h-screen items-center justify-center">
                <LoaderIcon className="size-6 animate-spin text-muted-foreground" />
                <span className="ml-2 text-muted-foreground">Loading case...</span>
            </div>
        )
    }

    if (error || !caseData) {
        return (
            <div className="flex min-h-screen items-center justify-center">
                <Card className="p-6">
                    <p className="text-destructive">Error loading case: {error?.message || 'Not found'}</p>
                    <Button variant="outline" className="mt-4" onClick={() => router.push('/cases')}>
                        Back to Cases
                    </Button>
                </Card>
            </div>
        )
    }

    const stage = stageById.get(caseData.stage_id)
    const statusLabel = caseData.status_label || stage?.label || 'Unknown'
    const statusColor = stage?.color || '#6B7280'

    return (
        <div className="flex flex-1 flex-col">
            {/* Case Header */}
            <header className="flex h-16 shrink-0 items-center justify-between gap-2 border-b px-4">
                <div className="flex items-center gap-2">
                    <Button variant="ghost" size="sm" onClick={() => router.push('/cases')}>
                        <ArrowLeftIcon className="mr-2 size-4" />
                        Back
                    </Button>
                    <h1 className="text-lg font-semibold">Case #{caseData.case_number}</h1>
                    <Badge style={{ backgroundColor: statusColor, color: 'white' }}>{statusLabel}</Badge>
                    {caseData.is_archived && <Badge variant="secondary">Archived</Badge>}
                </div>
                <div className="flex items-center gap-2">
                    <DropdownMenu>
                        <DropdownMenuTrigger
                            className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
                            disabled={caseData.is_archived}
                        >
                            <span className="inline-flex items-center">Change Stage</span>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                            {stageOptions.map((stageOption) => (
                                <DropdownMenuItem
                                    key={stageOption.id}
                                    onClick={() => handleStatusChange(stageOption.id)}
                                    disabled={stageOption.id === caseData.stage_id}
                                >
                                    <span
                                        className="mr-2 size-2 rounded-full"
                                        style={{ backgroundColor: stageOption.color }}
                                    />
                                    {stageOption.label}
                                </DropdownMenuItem>
                            ))}
                        </DropdownMenuContent>
                    </DropdownMenu>

                    {/* Send Email Button */}
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setEmailDialogOpen(true)}
                        disabled={caseData.is_archived || !caseData.email}
                        className="gap-2"
                    >
                        <MailIcon className="size-4" />
                        Send Email
                    </Button>

                    {/* Claim/Release buttons (case_manager+ only) */}
                    {canManageQueue && isInQueue && (
                        <Button
                            variant="default"
                            size="sm"
                            onClick={handleClaimCase}
                            disabled={claimCaseMutation.isPending || caseData.is_archived}
                        >
                            {claimCaseMutation.isPending ? 'Claiming...' : 'Claim Case'}
                        </Button>
                    )}
                    {canManageQueue && isOwnedByUser && queues && queues.length > 0 && (
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setReleaseDialogOpen(true)}
                            disabled={caseData.is_archived}
                        >
                            Release to Queue
                        </Button>
                    )}

                    {/* Schedule Zoom button (when Zoom connected) */}
                    {zoomStatus?.connected && (
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                                setZoomTopic(`Call with ${caseData.full_name}`)
                                const nextHour = new Date()
                                nextHour.setSeconds(0, 0)
                                nextHour.setMinutes(0)
                                nextHour.setHours(nextHour.getHours() + 1)
                                setZoomStartAt(nextHour)
                                setLastMeetingResult(null)
                                setZoomDialogOpen(true)
                            }}
                            disabled={caseData.is_archived}
                        >
                            📹 Schedule Zoom
                        </Button>
                    )}

                    {/* Propose Match Button - only for manager+ on active cases */}
                    {user?.role && ['case_manager', 'admin', 'developer'].includes(user.role) && !caseData.is_archived && (
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setProposeMatchOpen(true)}
                        >
                            <HeartHandshakeIcon className="size-4 mr-2" />
                            Propose Match
                        </Button>
                    )}

                    <Button variant="outline" size="sm">
                        Assign
                    </Button>
                    <DropdownMenu>
                        <DropdownMenuTrigger className={cn(buttonVariants({ variant: "ghost", size: "icon-sm" }))}>
                            <span className="inline-flex items-center justify-center">
                                <MoreVerticalIcon className="h-4 w-4" />
                            </span>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => setEditDialogOpen(true)}>Edit</DropdownMenuItem>
                            {caseData.is_archived ? (
                                <DropdownMenuItem onClick={handleRestore}>Restore</DropdownMenuItem>
                            ) : (
                                <DropdownMenuItem onClick={handleArchive}>Archive</DropdownMenuItem>
                            )}
                            <DropdownMenuSeparator />
                            <DropdownMenuItem className="text-destructive">Delete</DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>
                </div>
            </header>

            {/* Tabs Content */}
            <div className="flex flex-1 flex-col gap-4 p-4 md:p-6">
                <Tabs defaultValue="overview" className="w-full">
                    <TabsList className="mb-4 overflow-x-auto">
                        <TabsTrigger value="overview">Overview</TabsTrigger>
                        <TabsTrigger value="notes">Notes {notes && notes.length > 0 && `(${notes.length})`}</TabsTrigger>
                        <TabsTrigger value="tasks">Tasks {tasksData && tasksData.items.length > 0 && `(${tasksData.items.length})`}</TabsTrigger>
                        <TabsTrigger value="history">History</TabsTrigger>
                        <TabsTrigger value="application">Application</TabsTrigger>
                        <TabsTrigger value="ai" className="gap-1">
                            <SparklesIcon className="h-3 w-3" />
                            AI
                        </TabsTrigger>
                    </TabsList>

                    {/* OVERVIEW TAB */}
                    <TabsContent value="overview" className="space-y-4">
                        <div className="grid gap-4 md:grid-cols-[1.5fr_1fr]">
                            <div className="space-y-4">
                                <Card>
                                    <CardHeader>
                                        <CardTitle>Contact Information</CardTitle>
                                    </CardHeader>
                                    <CardContent className="space-y-3">
                                        <div>
                                            <span className="text-sm text-muted-foreground">Name:</span>
                                            <InlineEditField
                                                value={caseData.full_name}
                                                onSave={async (value) => {
                                                    await updateCaseMutation.mutateAsync({ caseId: id, data: { full_name: value } })
                                                }}
                                                placeholder="Enter name"
                                                className="text-2xl font-semibold"
                                                displayClassName="-mx-0"
                                                label="Full name"
                                            />
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm text-muted-foreground">Email:</span>
                                            <InlineEditField
                                                value={caseData.email}
                                                onSave={async (value) => {
                                                    await updateCaseMutation.mutateAsync({ caseId: id, data: { email: value } })
                                                }}
                                                type="email"
                                                placeholder="Enter email"
                                                validate={(v) => !v.includes('@') ? 'Invalid email' : null}
                                                label="Email"
                                            />
                                            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={copyEmail}>
                                                {copiedEmail ? <CheckIcon className="h-3 w-3" /> : <CopyIcon className="h-3 w-3" />}
                                            </Button>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm text-muted-foreground">Phone:</span>
                                            <InlineEditField
                                                value={caseData.phone ?? undefined}
                                                onSave={async (value) => {
                                                    await updateCaseMutation.mutateAsync({ caseId: id, data: { phone: value || null } })
                                                }}
                                                type="tel"
                                                placeholder="-"
                                                label="Phone"
                                            />
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm text-muted-foreground">State:</span>
                                            <InlineEditField
                                                value={caseData.state ?? undefined}
                                                onSave={async (value) => {
                                                    await updateCaseMutation.mutateAsync({ caseId: id, data: { state: value || null } })
                                                }}
                                                placeholder="-"
                                                validate={(v) => v && v.length !== 2 ? 'Use 2-letter code (e.g., CA, TX)' : null}
                                                label="State"
                                            />
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm text-muted-foreground">Source:</span>
                                            <Badge variant="secondary" className="capitalize">{caseData.source}</Badge>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm text-muted-foreground">Created:</span>
                                            <span className="text-sm">{formatDate(caseData.created_at)}</span>
                                        </div>
                                    </CardContent>
                                </Card>

                                <Card>
                                    <CardHeader>
                                        <CardTitle>Demographics</CardTitle>
                                    </CardHeader>
                                    <CardContent className="space-y-3">
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm text-muted-foreground">Date of Birth:</span>
                                            <span className="text-sm">{caseData.date_of_birth ? formatDate(caseData.date_of_birth) : '-'}</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm text-muted-foreground">Race:</span>
                                            <span className="text-sm">{caseData.race || '-'}</span>
                                        </div>
                                        {(caseData.height_ft || caseData.weight_lb) && (
                                            <>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-sm text-muted-foreground">Height:</span>
                                                    <span className="text-sm">{caseData.height_ft ? `${caseData.height_ft} ft` : '-'}</span>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-sm text-muted-foreground">Weight:</span>
                                                    <span className="text-sm">{caseData.weight_lb ? `${caseData.weight_lb} lb` : '-'}</span>
                                                </div>
                                            </>
                                        )}
                                    </CardContent>
                                </Card>
                            </div>

                            <div>
                                <Card>
                                    <CardHeader>
                                        <CardTitle>Eligibility Checklist</CardTitle>
                                    </CardHeader>
                                    <CardContent className="space-y-3">
                                        {[
                                            { label: 'Age Eligible (18-42)', value: caseData.is_age_eligible },
                                            { label: 'US Citizen or PR', value: caseData.is_citizen_or_pr },
                                            { label: 'Has Child', value: caseData.has_child },
                                            { label: 'Non-Smoker', value: caseData.is_non_smoker },
                                            { label: 'Prior Surrogate Experience', value: caseData.has_surrogate_experience },
                                        ].map(({ label, value }) => (
                                            <div key={label} className="flex items-center gap-2">
                                                {value === true && <CheckIcon className="h-4 w-4 text-green-500" />}
                                                {value === false && <XIcon className="h-4 w-4 text-red-500" />}
                                                {value === null && <span className="h-4 w-4 text-center text-muted-foreground">-</span>}
                                                <span className="text-sm">{label}</span>
                                            </div>
                                        ))}
                                        {(caseData.num_deliveries !== null || caseData.num_csections !== null) && (
                                            <div className="border-t pt-3 space-y-2">
                                                {caseData.num_deliveries !== null && (
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-sm text-muted-foreground">Deliveries:</span>
                                                        <span className="text-sm">{caseData.num_deliveries}</span>
                                                    </div>
                                                )}
                                                {caseData.num_csections !== null && (
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-sm text-muted-foreground">C-Sections:</span>
                                                        <span className="text-sm">{caseData.num_csections}</span>
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </CardContent>
                                </Card>
                            </div>
                        </div>
                    </TabsContent>

                    {/* NOTES TAB */}
                    <TabsContent value="notes" className="space-y-4">
                        <Card>
                            <CardHeader className="pb-4">
                                <CardTitle className="flex items-center gap-2">
                                    Notes
                                    {notes && notes.length > 0 && (
                                        <Badge variant="secondary" className="text-xs">
                                            {notes.length}
                                        </Badge>
                                    )}
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-6">
                                {/* Add Note Section */}
                                <div className="rounded-lg border border-border bg-muted/30 p-4">
                                    <h4 className="text-sm font-medium mb-3 text-muted-foreground">Add a note</h4>
                                    <RichTextEditor
                                        placeholder="Write your note here..."
                                        onSubmit={handleAddNote}
                                        submitLabel="Add Note"
                                        isSubmitting={createNoteMutation.isPending}
                                    />
                                </div>

                                {/* Notes List */}
                                {notes && notes.length > 0 ? (
                                    <div className="space-y-3">
                                        {notes.map((note) => (
                                            <div
                                                key={note.id}
                                                className="group rounded-lg border border-border bg-card p-4 transition-colors hover:bg-accent/30"
                                            >
                                                <div className="flex items-start gap-3">
                                                    <Avatar className="h-9 w-9 flex-shrink-0">
                                                        <AvatarFallback className="text-xs bg-primary/10 text-primary">
                                                            {getInitials(note.author_name)}
                                                        </AvatarFallback>
                                                    </Avatar>
                                                    <div className="flex-1 min-w-0">
                                                        <div className="flex items-center justify-between gap-2">
                                                            <div className="flex items-center gap-2">
                                                                <span className="text-sm font-medium">{note.author_name || 'Unknown'}</span>
                                                                <span className="text-xs text-muted-foreground">
                                                                    {formatDateTime(note.created_at)}
                                                                </span>
                                                            </div>
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity"
                                                                onClick={() => handleDeleteNote(note.id)}
                                                            >
                                                                <TrashIcon className="h-3.5 w-3.5 text-muted-foreground hover:text-destructive" />
                                                            </Button>
                                                        </div>
                                                        <div
                                                            className="mt-2 text-sm prose prose-sm max-w-none dark:prose-invert"
                                                            dangerouslySetInnerHTML={{ __html: note.body }}
                                                        />
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="text-center py-8">
                                        <p className="text-sm text-muted-foreground">No notes yet. Add the first note above.</p>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                        <Card>
                            <CardHeader>
                                <CardTitle>Attachments</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <FileUploadZone caseId={id} />
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* TASKS TAB */}
                    <TabsContent value="tasks" className="space-y-4">
                        <Card>
                            <CardHeader className="flex flex-row items-center justify-between">
                                <CardTitle>Tasks for Case #{caseData.case_number}</CardTitle>
                                <Button size="sm">
                                    <PlusIcon className="h-4 w-4 mr-2" />
                                    Add Task
                                </Button>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                {tasksData && tasksData.items.length > 0 ? (
                                    tasksData.items.map((task) => (
                                        <div key={task.id} className="flex items-start gap-3">
                                            <Checkbox
                                                id={`task-${task.id}`}
                                                className="mt-1"
                                                checked={task.is_completed}
                                                onCheckedChange={() => handleTaskToggle(task.id, task.is_completed)}
                                            />
                                            <div className="flex-1 space-y-1">
                                                <label
                                                    htmlFor={`task-${task.id}`}
                                                    className={`text-sm font-medium leading-none ${task.is_completed ? 'line-through text-muted-foreground' : ''}`}
                                                >
                                                    {task.title}
                                                </label>
                                                {task.due_date && (
                                                    <div className="flex items-center gap-2">
                                                        <Badge variant="secondary" className="text-xs">
                                                            {formatTaskDueLabel(task)}
                                                        </Badge>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    ))
                                ) : (
                                    <p className="text-sm text-muted-foreground text-center py-4">No tasks for this case.</p>
                                )}
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* HISTORY TAB */}
                    <TabsContent value="history" className="space-y-4">
                        <Card>
                            <CardHeader>
                                <CardTitle>Activity Log</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-6">
                                {activityData && activityData.items.length > 0 ? (
                                    activityData.items.map((entry, idx) => {
                                        const isLast = idx === activityData.items.length - 1
                                        return (
                                            <div key={entry.id} className="flex gap-3">
                                                <div className="relative">
                                                    <div className="h-2 w-2 rounded-full bg-primary mt-1.5"></div>
                                                    {!isLast && <div className="absolute left-1 top-4 h-full w-px bg-border"></div>}
                                                </div>
                                                <div className="flex-1 space-y-1 pb-4">
                                                    <div className="text-sm font-medium">
                                                        {formatActivityType(entry.activity_type)}
                                                    </div>
                                                    <div className="text-xs text-muted-foreground">
                                                        {entry.actor_name || 'System'} • {formatDateTime(entry.created_at)}
                                                    </div>
                                                    {entry.details && (
                                                        <div className="text-sm pt-1 text-muted-foreground">
                                                            {formatActivityDetails(entry.activity_type, entry.details)}
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        )
                                    })
                                ) : (
                                    <p className="text-sm text-muted-foreground text-center py-4">No activity recorded.</p>
                                )}
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* APPLICATION TAB */}
                    <TabsContent value="application" className="space-y-4">
                        <CaseApplicationTab
                            caseId={id}
                            formId={defaultFormId}
                        />
                    </TabsContent>

                    {/* AI TAB */}
                    <TabsContent value="ai" className="space-y-4">
                        {aiSettings && !aiSettings.is_enabled ? (
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="flex flex-col items-center justify-center py-8 text-center">
                                        <BrainIcon className="h-12 w-12 text-muted-foreground mb-4" />
                                        <h3 className="text-lg font-medium">AI Assistant Not Enabled</h3>
                                        <p className="text-sm text-muted-foreground mt-2 max-w-md">
                                            Contact your manager to enable AI features and configure an API key in Settings.
                                        </p>
                                    </div>
                                </CardContent>
                            </Card>
                        ) : (
                            <div className="grid gap-4 md:grid-cols-2">
                                {/* Summarize Case Card */}
                                <Card>
                                    <CardHeader>
                                        <CardTitle className="flex items-center gap-2">
                                            <SparklesIcon className="h-4 w-4" />
                                            Case Summary
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent className="space-y-4">
                                        <Button
                                            onClick={async () => {
                                                const result = await summarizeCaseMutation.mutateAsync(id)
                                                setAiSummary(result)
                                            }}
                                            disabled={summarizeCaseMutation.isPending}
                                            className="w-full"
                                        >
                                            {summarizeCaseMutation.isPending ? (
                                                <><LoaderIcon className="h-4 w-4 mr-2 animate-spin" /> Generating...</>
                                            ) : (
                                                <><SparklesIcon className="h-4 w-4 mr-2" /> Generate Summary</>
                                            )}
                                        </Button>

                                        {aiSummary && (
                                            <div className="space-y-4 pt-4 border-t">
                                                <div>
                                                    <h4 className="text-sm font-medium mb-1">Summary</h4>
                                                    <p className="text-sm text-muted-foreground">{aiSummary.summary}</p>
                                                </div>
                                                <div>
                                                    <h4 className="text-sm font-medium mb-1">Recent Activity</h4>
                                                    <p className="text-sm text-muted-foreground">{aiSummary.recent_activity}</p>
                                                </div>
                                                {aiSummary.suggested_next_steps.length > 0 && (
                                                    <div>
                                                        <h4 className="text-sm font-medium mb-1">Suggested Next Steps</h4>
                                                        <ul className="text-sm text-muted-foreground space-y-1">
                                                            {aiSummary.suggested_next_steps.map((step, i) => (
                                                                <li key={i} className="flex items-start gap-2">
                                                                    <span className="text-primary">•</span>
                                                                    {step}
                                                                </li>
                                                            ))}
                                                        </ul>
                                                    </div>
                                                )}
                                                {aiSummary.pending_tasks.length > 0 && (
                                                    <div>
                                                        <h4 className="text-sm font-medium mb-1">Pending Tasks</h4>
                                                        <ul className="text-sm text-muted-foreground space-y-1">
                                                            {aiSummary.pending_tasks.map((task) => (
                                                                <li key={task.id} className="flex items-center gap-2">
                                                                    <Badge variant="secondary" className="text-xs">
                                                                        {task.due_date || 'No due date'}
                                                                    </Badge>
                                                                    {task.title}
                                                                </li>
                                                            ))}
                                                        </ul>
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </CardContent>
                                </Card>

                                {/* Draft Email Card */}
                                <Card>
                                    <CardHeader>
                                        <CardTitle className="flex items-center gap-2">
                                            <MailIcon className="h-4 w-4" />
                                            Draft Email
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent className="space-y-4">
                                        <div className="grid grid-cols-2 gap-2">
                                            {(['follow_up', 'status_update', 'meeting_request', 'document_request', 'introduction'] as EmailType[]).map((emailType) => (
                                                <Button
                                                    key={emailType}
                                                    variant={selectedEmailType === emailType ? 'default' : 'outline'}
                                                    size="sm"
                                                    onClick={() => setSelectedEmailType(emailType)}
                                                    className="capitalize text-xs"
                                                >
                                                    {emailType.replace(/_/g, ' ')}
                                                </Button>
                                            ))}
                                        </div>

                                        <Button
                                            onClick={async () => {
                                                if (!selectedEmailType) return
                                                const result = await draftEmailMutation.mutateAsync({
                                                    case_id: id,
                                                    email_type: selectedEmailType,
                                                })
                                                setAiDraftEmail(result)
                                            }}
                                            disabled={!selectedEmailType || draftEmailMutation.isPending}
                                            className="w-full"
                                        >
                                            {draftEmailMutation.isPending ? (
                                                <><LoaderIcon className="h-4 w-4 mr-2 animate-spin" /> Drafting...</>
                                            ) : (
                                                <><MailIcon className="h-4 w-4 mr-2" /> Draft Email</>
                                            )}
                                        </Button>

                                        {aiDraftEmail && (
                                            <div className="space-y-3 pt-4 border-t">
                                                <div>
                                                    <h4 className="text-sm font-medium mb-1">To</h4>
                                                    <p className="text-sm text-muted-foreground">
                                                        {aiDraftEmail.recipient_name} &lt;{aiDraftEmail.recipient_email}&gt;
                                                    </p>
                                                </div>
                                                <div>
                                                    <h4 className="text-sm font-medium mb-1">Subject</h4>
                                                    <p className="text-sm text-muted-foreground">{aiDraftEmail.subject}</p>
                                                </div>
                                                <div>
                                                    <h4 className="text-sm font-medium mb-1">Body</h4>
                                                    <div className="text-sm text-muted-foreground bg-muted/50 rounded-md p-3 whitespace-pre-wrap max-h-64 overflow-y-auto">
                                                        {aiDraftEmail.body}
                                                    </div>
                                                </div>
                                                <div className="flex gap-2">
                                                    <Button
                                                        size="sm"
                                                        variant="outline"
                                                        onClick={() => {
                                                            navigator.clipboard.writeText(`Subject: ${aiDraftEmail.subject}\n\n${aiDraftEmail.body}`)
                                                        }}
                                                    >
                                                        <CopyIcon className="h-3 w-3 mr-1" /> Copy
                                                    </Button>
                                                    <Button
                                                        size="sm"
                                                        onClick={() => {
                                                            window.open(`mailto:${aiDraftEmail.recipient_email}?subject=${encodeURIComponent(aiDraftEmail.subject)}&body=${encodeURIComponent(aiDraftEmail.body)}`)
                                                        }}
                                                    >
                                                        <MailIcon className="h-3 w-3 mr-1" /> Open in Email
                                                    </Button>
                                                </div>
                                            </div>
                                        )}
                                    </CardContent>
                                </Card>
                            </div>
                        )}
                    </TabsContent>
                </Tabs>
            </div>

            {/* Edit Case Dialog */}
            <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
                <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle>Edit Case: #{caseData?.case_number}</DialogTitle>
                    </DialogHeader>
                    <form onSubmit={async (e) => {
                        e.preventDefault()
                        const form = e.target as HTMLFormElement
                        const formData = new FormData(form)
                        const data: Record<string, unknown> = {}

                        // Text fields
                        if (formData.get('full_name')) data.full_name = formData.get('full_name')
                        if (formData.get('email')) data.email = formData.get('email')
                        data.phone = formData.get('phone') || null
                        data.state = formData.get('state') || null
                        data.date_of_birth = formData.get('date_of_birth') || null
                        data.race = formData.get('race') || null

                        // Number fields
                        const heightFt = formData.get('height_ft')
                        data.height_ft = heightFt ? parseFloat(heightFt as string) : null
                        const weightLb = formData.get('weight_lb')
                        data.weight_lb = weightLb ? parseFloat(weightLb as string) : null
                        const numDeliveries = formData.get('num_deliveries')
                        data.num_deliveries = numDeliveries ? parseInt(numDeliveries as string) : null
                        const numCsections = formData.get('num_csections')
                        data.num_csections = numCsections ? parseInt(numCsections as string) : null

                        // Boolean fields (checkboxes)
                        data.is_age_eligible = formData.get('is_age_eligible') === 'on'
                        data.is_citizen_or_pr = formData.get('is_citizen_or_pr') === 'on'
                        data.has_child = formData.get('has_child') === 'on'
                        data.is_non_smoker = formData.get('is_non_smoker') === 'on'
                        data.has_surrogate_experience = formData.get('has_surrogate_experience') === 'on'
                        data.is_priority = formData.get('is_priority') === 'on'

                        await updateCaseMutation.mutateAsync({ caseId: id, data })
                        setEditDialogOpen(false)
                    }}>
                        <div className="grid gap-4 py-4">
                            {/* Contact Info */}
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="full_name">Full Name *</Label>
                                    <Input id="full_name" name="full_name" defaultValue={caseData?.full_name} required />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="email">Email *</Label>
                                    <Input id="email" name="email" type="email" defaultValue={caseData?.email} required />
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="phone">Phone</Label>
                                    <Input id="phone" name="phone" defaultValue={caseData?.phone ?? ''} />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="state">State</Label>
                                    <Input id="state" name="state" defaultValue={caseData?.state ?? ''} />
                                </div>
                            </div>

                            {/* Personal Info */}
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="date_of_birth">Date of Birth</Label>
                                    <Input id="date_of_birth" name="date_of_birth" type="date" defaultValue={caseData?.date_of_birth ?? ''} />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="race">Race</Label>
                                    <Input id="race" name="race" defaultValue={caseData?.race ?? ''} />
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="height_ft">Height (ft)</Label>
                                    <Input id="height_ft" name="height_ft" type="number" step="0.1" defaultValue={caseData?.height_ft ?? ''} />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="weight_lb">Weight (lb)</Label>
                                    <Input id="weight_lb" name="weight_lb" type="number" defaultValue={caseData?.weight_lb ?? ''} />
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="num_deliveries">Number of Deliveries</Label>
                                    <Input id="num_deliveries" name="num_deliveries" type="number" min="0" max="20" defaultValue={caseData?.num_deliveries ?? ''} />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="num_csections">Number of C-Sections</Label>
                                    <Input id="num_csections" name="num_csections" type="number" min="0" max="10" defaultValue={caseData?.num_csections ?? ''} />
                                </div>
                            </div>

                            {/* Boolean Fields */}
                            <div className="grid grid-cols-2 gap-4 pt-2">
                                <div className="flex items-center gap-2">
                                    <Checkbox id="is_priority" name="is_priority" defaultChecked={caseData?.is_priority} />
                                    <Label htmlFor="is_priority">Priority Case</Label>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Checkbox id="is_age_eligible" name="is_age_eligible" defaultChecked={caseData?.is_age_eligible ?? false} />
                                    <Label htmlFor="is_age_eligible">Age Eligible</Label>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Checkbox id="is_citizen_or_pr" name="is_citizen_or_pr" defaultChecked={caseData?.is_citizen_or_pr ?? false} />
                                    <Label htmlFor="is_citizen_or_pr">US Citizen/PR</Label>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Checkbox id="has_child" name="has_child" defaultChecked={caseData?.has_child ?? false} />
                                    <Label htmlFor="has_child">Has Child</Label>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Checkbox id="is_non_smoker" name="is_non_smoker" defaultChecked={caseData?.is_non_smoker ?? false} />
                                    <Label htmlFor="is_non_smoker">Non-Smoker</Label>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Checkbox id="has_surrogate_experience" name="has_surrogate_experience" defaultChecked={caseData?.has_surrogate_experience ?? false} />
                                    <Label htmlFor="has_surrogate_experience">Surrogate Experience</Label>
                                </div>
                            </div>
                        </div>
                        <DialogFooter>
                            <Button type="button" variant="outline" onClick={() => setEditDialogOpen(false)}>
                                Cancel
                            </Button>
                            <Button type="submit" disabled={updateCaseMutation.isPending}>
                                {updateCaseMutation.isPending ? 'Saving...' : 'Save Changes'}
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>

            {/* Release to Queue Dialog */}
            <Dialog open={releaseDialogOpen} onOpenChange={setReleaseDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Release to Queue</DialogTitle>
                    </DialogHeader>
                    <div className="py-4">
                        <Label htmlFor="queue-select">Select Queue</Label>
                        <select
                            id="queue-select"
                            value={selectedQueueId}
                            onChange={(e) => setSelectedQueueId(e.target.value)}
                            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 mt-2"
                        >
                            <option value="">Select a queue...</option>
                            {queues?.map((q) => (
                                <option key={q.id} value={q.id}>{q.name}</option>
                            ))}
                        </select>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setReleaseDialogOpen(false)}>
                            Cancel
                        </Button>
                        <Button
                            onClick={handleReleaseCase}
                            disabled={!selectedQueueId || releaseCaseMutation.isPending}
                        >
                            {releaseCaseMutation.isPending ? 'Releasing...' : 'Release'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Schedule Zoom Dialog */}
            <Dialog open={zoomDialogOpen} onOpenChange={setZoomDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>📹 Schedule Zoom Meeting</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        <div>
                            <Label htmlFor="zoom-topic">Topic</Label>
                            <Input
                                id="zoom-topic"
                                value={zoomTopic}
                                onChange={(e) => setZoomTopic(e.target.value)}
                                placeholder="Meeting topic"
                                className="mt-2"
                                disabled={!!lastMeetingResult}
                            />
                        </div>
                        <div>
                            <Label>When</Label>
                            <div className="mt-2">
                                <DateTimePicker value={zoomStartAt} onChange={setZoomStartAt} disabled={!!lastMeetingResult} />
                            </div>
                            <div className="mt-1 text-xs text-muted-foreground">
                                Timezone: {timezoneName}
                            </div>
                        </div>
                        <div>
                            <Label htmlFor="zoom-duration">Duration (minutes)</Label>
                            <select
                                id="zoom-duration"
                                value={zoomDuration}
                                onChange={(e) => setZoomDuration(Number(e.target.value))}
                                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 mt-2"
                                disabled={!!lastMeetingResult}
                            >
                                <option value={15}>15 minutes</option>
                                <option value={30}>30 minutes</option>
                                <option value={45}>45 minutes</option>
                                <option value={60}>1 hour</option>
                                <option value={90}>1.5 hours</option>
                            </select>
                        </div>
                        <div className="text-xs text-muted-foreground">
                            A meeting task is created automatically.
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setZoomDialogOpen(false)}>
                            Cancel
                        </Button>
                        {lastMeetingResult ? (
                            <>
                                <Button
                                    variant="outline"
                                    onClick={() => {
                                        navigator.clipboard.writeText(lastMeetingResult.join_url)
                                    }}
                                >
                                    Copy Link
                                </Button>
                                <Button
                                    onClick={async () => {
                                        if (!caseData?.email) return
                                        try {
                                            await sendZoomInviteMutation.mutateAsync({
                                                recipient_email: caseData.email,
                                                meeting_id: lastMeetingResult.meeting_id,
                                                join_url: lastMeetingResult.join_url,
                                                topic: zoomTopic,
                                                start_time: lastMeetingResult.start_time || undefined,
                                                duration: zoomDuration,
                                                password: lastMeetingResult.password || undefined,
                                                contact_name: caseData.full_name || 'there',
                                                case_id: id,
                                            })
                                            setZoomDialogOpen(false)
                                            setLastMeetingResult(null)
                                        } catch {
                                            // Error handled by react-query
                                        }
                                    }}
                                    disabled={sendZoomInviteMutation.isPending || !caseData?.email}
                                >
                                    {sendZoomInviteMutation.isPending ? 'Sending...' : '📧 Send Invite'}
                                </Button>
                            </>
                        ) : (
                            <Button
                                onClick={async () => {
                                    if (!zoomStartAt) return
                                    try {
                                        const result = await createZoomMeetingMutation.mutateAsync({
                                            entity_type: 'case',
                                            entity_id: id,
                                            topic: zoomTopic,
                                            start_time: toLocalIsoDateTime(zoomStartAt),
                                            timezone: timezoneName,
                                            duration: zoomDuration,
                                            contact_name: caseData?.full_name,
                                        })
                                        setLastMeetingResult({
                                            join_url: result.join_url,
                                            meeting_id: result.meeting_id,
                                            password: result.password,
                                            start_time: formatMeetingTimeForInvite(zoomStartAt),
                                        })
                                        navigator.clipboard.writeText(result.join_url)
                                    } catch {
                                        // Error handled by react-query
                                    }
                                }}
                                disabled={!zoomTopic || !zoomStartAt || createZoomMeetingMutation.isPending}
                            >
                                {createZoomMeetingMutation.isPending ? 'Creating...' : 'Create Meeting'}
                            </Button>
                        )}
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Email Compose Dialog */}
            <EmailComposeDialog
                open={emailDialogOpen}
                onOpenChange={setEmailDialogOpen}
                caseData={{
                    id: caseData.id,
                    email: caseData.email,
                    full_name: caseData.full_name,
                    case_number: caseData.case_number,
                    status: caseData.status_label,
                    state: caseData.state || undefined,
                    phone: caseData.phone || undefined,
                }}
            />

            {/* Propose Match Dialog */}
            <ProposeMatchDialog
                open={proposeMatchOpen}
                onOpenChange={setProposeMatchOpen}
                caseId={caseData.id}
                caseName={caseData.full_name}
            />
        </div>
    )
}
