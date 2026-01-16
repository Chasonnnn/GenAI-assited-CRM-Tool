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
    MoreVerticalIcon,
    CopyIcon,
    CheckIcon,
    XIcon,
    TrashIcon,
    Loader2Icon,
    ArrowLeftIcon,
    SparklesIcon,
    MailIcon,
    BrainIcon,
    HeartHandshakeIcon,
    PhoneIcon,
    VideoIcon,
} from "lucide-react"
import { InlineEditField } from "@/components/inline-edit-field"
import { FileUploadZone } from "@/components/FileUploadZone"
import { useSurrogate, useSurrogateActivity, useChangeSurrogateStatus, useArchiveSurrogate, useRestoreSurrogate, useUpdateSurrogate, useAssignSurrogate, useAssignees } from "@/lib/hooks/use-surrogates"
import { useQueues, useClaimSurrogate, useReleaseSurrogate } from "@/lib/hooks/use-queues"
import { useDefaultPipeline } from "@/lib/hooks/use-pipelines"
import { useNotes, useCreateNote, useDeleteNote } from "@/lib/hooks/use-notes"
import { useTasks, useCompleteTask, useUncompleteTask, useCreateTask, useUpdateTask, useDeleteTask } from "@/lib/hooks/use-tasks"
import { useZoomStatus, useCreateZoomMeeting, useSendZoomInvite } from "@/lib/hooks/use-user-integrations"
import { useSummarizeSurrogate, useDraftEmail, useAISettings } from "@/lib/hooks/use-ai"
import { useSetAIContext } from "@/lib/context/ai-context"
import { EmailComposeDialog } from "@/components/email/EmailComposeDialog"
import { ProposeMatchDialog } from "@/components/matches/ProposeMatchDialog"
import { SurrogateApplicationTab } from "@/components/surrogates/SurrogateApplicationTab"
import { SurrogateInterviewTab } from "@/components/surrogates/interviews/SurrogateInterviewTab"
import { SurrogateTasksCalendar } from "@/components/surrogates/SurrogateTasksCalendar"
import { AddSurrogateTaskDialog, type SurrogateTaskFormData } from "@/components/surrogates/AddSurrogateTaskDialog"
import { TaskEditModal } from "@/components/tasks/TaskEditModal"
import { SurrogateProfileCard } from "@/components/surrogates/SurrogateProfileCard"
import { LogContactAttemptDialog } from "@/components/surrogates/LogContactAttemptDialog"
import { InsuranceInfoCard } from "@/components/surrogates/InsuranceInfoCard"
import { MedicalInfoCard } from "@/components/surrogates/MedicalInfoCard"
import { LatestUpdatesCard } from "@/components/surrogates/LatestUpdatesCard"
import { PregnancyTrackerCard } from "@/components/surrogates/PregnancyTrackerCard"
import { useAttachments } from "@/lib/hooks/use-attachments"
import { ChangeStageModal } from "@/components/surrogates/ChangeStageModal"
import { useForms } from "@/lib/hooks/use-forms"
import type { EmailType, SummarizeSurrogateResponse, DraftEmailResponse } from "@/lib/api/ai"
import type { TaskListItem } from "@/lib/types/task"
import { useAuth } from "@/lib/auth-context"
import { ROLE_STAGE_VISIBILITY, type StageType } from "@/lib/constants/stages.generated"
import { cn } from "@/lib/utils"
import { parseDateInput } from "@/lib/utils/date"
import { format, parseISO } from "date-fns"
import { buildRecurringDates, MAX_TASK_OCCURRENCES } from "@/lib/utils/task-recurrence"
import { toast } from "sonner"

const EMAIL_TYPES: EmailType[] = [
    "follow_up",
    "status_update",
    "meeting_request",
    "document_request",
    "introduction",
]

type TaskEditPayload = {
    id: string
    title: string
    description: string | null
    task_type: string
    due_date: string | null
    due_time: string | null
    is_completed: boolean
    surrogate_id: string | null
}

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
        surrogate_created: 'Surrogate Created',
        info_edited: 'Information Edited',
        stage_changed: 'Stage Changed',
        assigned: 'Assigned',
        unassigned: 'Unassigned',
        surrogate_assigned_to_queue: 'Assigned to Queue',
        surrogate_claimed: 'Surrogate Claimed',
        surrogate_released: 'Released to Queue',
        priority_changed: 'Priority Changed',
        archived: 'Archived',
        restored: 'Restored',
        note_added: 'Note Added',
        note_deleted: 'Note Deleted',
        attachment_added: 'Attachment Uploaded',
        attachment_deleted: 'Attachment Deleted',
        task_created: 'Task Created',
        task_deleted: 'Task Deleted',
        contact_attempt: 'Contact Attempt',
    }
    return labels[type] || type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value)
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
            if (isRecord(details.changes)) {
                const changes = Object.entries(details.changes)
                    .map(([field, value]) => `${field.replace(/_/g, ' ')}: ${String(value)}`)
                    .join(', ')
                return aiPrefix ? withAiPrefix(changes) : changes
            }
            return aiOnly()
        case 'assigned':
            return aiPrefix ? withAiPrefix(details.from_user_id ? 'Reassigned' : 'Assigned to user') : (details.from_user_id ? 'Reassigned' : 'Assigned to user')
        case 'unassigned':
            return aiPrefix ? withAiPrefix('Removed assignment') : 'Removed assignment'
        case 'surrogate_assigned_to_queue': {
            const toQueue = details.to_queue_id ? `Queue ${String(details.to_queue_id)}` : 'queue'
            return withAiPrefix(`Assigned to ${toQueue}`)
        }
        case 'surrogate_claimed': {
            const fromQueue = details.from_queue_id ? `Queue ${String(details.from_queue_id)}` : 'queue'
            return withAiPrefix(`Claimed from ${fromQueue}`)
        }
        case 'surrogate_released': {
            const toQueue = details.to_queue_id ? `Queue ${String(details.to_queue_id)}` : 'queue'
            return withAiPrefix(`Released to ${toQueue}`)
        }
        case 'priority_changed':
            return aiPrefix ? withAiPrefix(details.is_priority ? 'Marked as priority' : 'Removed priority') : (details.is_priority ? 'Marked as priority' : 'Removed priority')
        case 'note_added': {
            // Use preview field (sanitized snapshot at creation time)
            const preview = details.preview ? String(details.preview) : ''
            return preview
                ? withAiPrefix(preview)
                : withAiPrefix('Note added')
        }
        case 'note_deleted': {
            // Use preview field (sanitized snapshot, preserved after deletion)
            const preview = details.preview ? String(details.preview) : ''
            return preview
                ? withAiPrefix(`${preview} (deleted)`)
                : withAiPrefix('Note deleted')
        }
        case 'attachment_added': {
            const filename = details.filename ? String(details.filename) : 'file'
            return withAiPrefix(`Uploaded: ${filename}`)
        }
        case 'attachment_deleted': {
            const filename = details.filename ? String(details.filename) : 'file'
            return withAiPrefix(`Deleted: ${filename}`)
        }
        case 'task_created':
            return details.title ? withAiPrefix(`Task: ${String(details.title)}`) : aiOnly()
        case 'task_deleted':
            return details.title ? withAiPrefix(`Deleted: ${String(details.title)}`) : withAiPrefix('Task deleted')
        case 'contact_attempt': {
            const methods = Array.isArray(details.contact_methods)
                ? details.contact_methods.map((method) => String(method)).join(', ')
                : ''
            const outcome = String(details.outcome || '').replace(/_/g, ' ')
            const backdated = details.is_backdated ? ' (backdated)' : ''
            return withAiPrefix(`${methods}: ${outcome}${backdated}`)
        }
        default:
            return aiOnly()
    }
}

export default function SurrogateDetailPage() {
    const params = useParams<{ id: string }>()
    const id = params.id
    const router = useRouter()
    const { user } = useAuth()
    const canViewProfile = user
        ? ["case_manager", "admin", "developer"].includes(user.role)
        : false
    const { data: defaultPipeline } = useDefaultPipeline()
    const stageOptions = React.useMemo(() => defaultPipeline?.stages || [], [defaultPipeline])
    const stageById = React.useMemo(
        () => new Map(stageOptions.map(stage => [stage.id, stage])),
        [stageOptions]
    )
    const visibleStageOptions = React.useMemo(() => {
        if (!user?.role) return stageOptions
        const rules = ROLE_STAGE_VISIBILITY[user.role]
        if (!rules) return stageOptions
        return stageOptions.filter((stage) => {
            const stageType = stage.stage_type as StageType | null
            return (
                (stageType && rules.stageTypes.includes(stageType)) ||
                rules.extraSlugs.includes(stage.slug)
            )
        })
    }, [stageOptions, user?.role])

    // Stage visibility for medical info and pregnancy tracker cards
    const readyToMatchStage = React.useMemo(
        () => stageOptions.find(s => s.slug === 'ready_to_match'),
        [stageOptions]
    )
    const heartbeatStage = React.useMemo(
        () => stageOptions.find(s => s.slug === 'heartbeat_confirmed'),
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
    const [aiSummary, setAiSummary] = React.useState<SummarizeSurrogateResponse | null>(null)
    const [aiDraftEmail, setAiDraftEmail] = React.useState<DraftEmailResponse | null>(null)
    const [selectedEmailType, setSelectedEmailType] = React.useState<EmailType | null>(null)
    const [emailDialogOpen, setEmailDialogOpen] = React.useState(false)
    const [proposeMatchOpen, setProposeMatchOpen] = React.useState(false)
    const [contactAttemptDialogOpen, setContactAttemptDialogOpen] = React.useState(false)
    const [addTaskDialogOpen, setAddTaskDialogOpen] = React.useState(false)
    const [editingTask, setEditingTask] = React.useState<TaskListItem | null>(null)
    const [changeStageModalOpen, setChangeStageModalOpen] = React.useState(false)

    const timezoneName = React.useMemo(() => {
        try {
            return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
        } catch {
            return 'UTC'
        }
    }, [])

    // Fetch data
    const { data: surrogateData, isLoading, error } = useSurrogate(id)
    const { data: activityData } = useSurrogateActivity(id)
    const { data: notes } = useNotes(id)
    const { data: attachments } = useAttachments(id)
    const { data: tasksData, isLoading: tasksLoading } = useTasks({ surrogate_id: id, exclude_approvals: true })

    // Mutations
    const changeStatusMutation = useChangeSurrogateStatus()
    const archiveMutation = useArchiveSurrogate()
    const restoreMutation = useRestoreSurrogate()
    const createNoteMutation = useCreateNote()
    const deleteNoteMutation = useDeleteNote()
    const completeTaskMutation = useCompleteTask()
    const uncompleteTaskMutation = useUncompleteTask()
    const createTaskMutation = useCreateTask()
    const updateTaskMutation = useUpdateTask()
    const deleteTaskMutation = useDeleteTask()
    const updateSurrogateMutation = useUpdateSurrogate()
    const claimSurrogateMutation = useClaimSurrogate()
    const releaseSurrogateMutation = useReleaseSurrogate()
    const createZoomMeetingMutation = useCreateZoomMeeting()
    const sendZoomInviteMutation = useSendZoomInvite()
    const summarizeSurrogateMutation = useSummarizeSurrogate()
    const draftEmailMutation = useDraftEmail()
    const assignSurrogateMutation = useAssignSurrogate()
    const { data: assignees } = useAssignees()

    // Check if user has Zoom connected
    const { data: zoomStatus } = useZoomStatus()
    const { data: aiSettings } = useAISettings()
    const { data: forms } = useForms()
    const defaultFormId = forms?.find((f) => f.status === "published")?.id || ""

    // Set AI context for the chat panel
    useSetAIContext(
        surrogateData
            ? {
                entityType: "surrogate",
                entityId: surrogateData.id,
                entityName: `Surrogate #${surrogateData.surrogate_number} - ${surrogateData.full_name}`,
            }
            : null
    )

    // Fetch queues for release dialog
    const canManageQueue = user?.role && ['case_manager', 'admin', 'developer'].includes(user.role)
    const { data: queues } = useQueues()
    const isOwnedByCurrentUser = !!(
        surrogateData?.owner_type === 'user' &&
        user?.user_id &&
        surrogateData.owner_id === user.user_id
    )
    const canChangeStage = !!(
        surrogateData &&
        !surrogateData.is_archived &&
        (
            ["admin", "developer"].includes(user?.role || "") ||
            (user?.role === "case_manager" && isOwnedByCurrentUser) ||
            (user?.role === "intake_specialist" && isOwnedByCurrentUser)
        )
    )

    const copyEmail = () => {
        if (!surrogateData) return
        navigator.clipboard.writeText(surrogateData.email)
        setCopiedEmail(true)
        setTimeout(() => setCopiedEmail(false), 2000)
    }

    const handleStatusChange = async (data: {
        stage_id: string
        reason?: string
        effective_at?: string
    }): Promise<{ status: "applied" | "pending_approval"; request_id?: string }> => {
        if (!surrogateData || !canChangeStage) {
            return { status: "applied" }
        }
        const previousStageId = surrogateData.stage_id
        const targetStageLabel = stageById.get(data.stage_id)?.label || "Stage"
        const payload: { stage_id: string; reason?: string; effective_at?: string } = {
            stage_id: data.stage_id,
        }
        if (data.reason) payload.reason = data.reason
        if (data.effective_at) payload.effective_at = data.effective_at

        const result = await changeStatusMutation.mutateAsync({
            surrogateId: id,
            data: payload,
        })
        setChangeStageModalOpen(false)
        const response: { status: "applied" | "pending_approval"; request_id?: string } = {
            status: result.status,
        }
        if (result.request_id) response.request_id = result.request_id

        if (result.status === "applied") {
            toast.success(`Stage updated to ${targetStageLabel}`, {
                action: {
                    label: "Undo (5 min)",
                    onClick: async () => {
                        try {
                            await changeStatusMutation.mutateAsync({
                                surrogateId: id,
                                data: { stage_id: previousStageId },
                            })
                            toast.success("Stage change undone")
                        } catch (error) {
                            const message =
                                error instanceof Error ? error.message : "Undo failed"
                            toast.error(message)
                        }
                    },
                },
                duration: 60000,
            })
        } else {
            toast("Stage change request submitted for approval")
        }
        return response
    }

    const handleArchive = async () => {
        await archiveMutation.mutateAsync(id)
        router.push('/surrogates')
    }

    const handleRestore = async () => {
        await restoreMutation.mutateAsync(id)
    }

    const handleAddNote = async (html: string) => {
        if (!html || html === '<p></p>') return
        await createNoteMutation.mutateAsync({ surrogateId: id, body: html })
    }

    const handleDeleteNote = async (noteId: string) => {
        await deleteNoteMutation.mutateAsync({ noteId, surrogateId: id })
    }

    const handleTaskToggle = async (taskId: string, isCompleted: boolean) => {
        if (isCompleted) {
            await uncompleteTaskMutation.mutateAsync(taskId)
        } else {
            await completeTaskMutation.mutateAsync(taskId)
        }
    }

    const handleAddTask = async (data: SurrogateTaskFormData) => {
        const dueTime = data.due_time ? `${data.due_time}:00` : undefined
        const buildPayload = (dueDate?: string) => ({
            title: data.title,
            task_type: data.task_type,
            surrogate_id: id,
            ...(data.description ? { description: data.description } : {}),
            ...(dueDate ? { due_date: dueDate } : {}),
            ...(dueTime ? { due_time: dueTime } : {}),
        })

        if (data.recurrence === "none") {
            await createTaskMutation.mutateAsync(buildPayload(data.due_date))
            return
        }

        if (!data.due_date || !data.repeat_until) {
            return
        }

        const start = parseISO(data.due_date)
        const end = parseISO(data.repeat_until)
        const dates = buildRecurringDates(start, end, data.recurrence)

        const lastDate = dates[dates.length - 1]
        if (dates.length >= MAX_TASK_OCCURRENCES && lastDate && end > lastDate) {
            return
        }

        for (const date of dates) {
            await createTaskMutation.mutateAsync(buildPayload(format(date, "yyyy-MM-dd")))
        }
    }

    const handleTaskClick = (task: TaskListItem) => {
        setEditingTask(task)
    }

    const handleSaveTask = async (taskId: string, data: Partial<TaskEditPayload>) => {
        const payload: Record<string, unknown> = {}
        for (const [key, value] of Object.entries(data)) {
            payload[key] = value === null ? undefined : value
        }
        await updateTaskMutation.mutateAsync({ taskId, data: payload })
    }

    const handleDeleteTask = async (taskId: string) => {
        await deleteTaskMutation.mutateAsync(taskId)
        setEditingTask(null)
    }

    const handleClaimSurrogate = async () => {
        await claimSurrogateMutation.mutateAsync(id)
    }

    const handleReleaseSurrogate = async () => {
        if (!selectedQueueId) return
        await releaseSurrogateMutation.mutateAsync({ surrogateId: id, queueId: selectedQueueId })
        setReleaseDialogOpen(false)
        setSelectedQueueId("")
    }

    // Check if surrogate is in a queue (can be claimed)
    const isInQueue = surrogateData?.owner_type === 'queue'
    const isOwnedByUser = surrogateData?.owner_type === 'user'

    if (isLoading) {
        return (
            <div className="flex min-h-screen items-center justify-center">
                <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                <span className="ml-2 text-muted-foreground">Loading surrogate...</span>
            </div>
        )
    }

    if (error || !surrogateData) {
        return (
            <div className="flex min-h-screen items-center justify-center">
                <Card className="p-6">
                    <p className="text-destructive">Error loading surrogate: {error?.message || 'Not found'}</p>
                    <Button variant="outline" className="mt-4" onClick={() => router.push('/surrogates')}>
                        Back to Surrogates
                    </Button>
                </Card>
            </div>
        )
    }

    const stage = stageById.get(surrogateData.stage_id)
    const statusLabel = surrogateData.status_label || stage?.label || 'Unknown'
    const statusColor = stage?.color || '#6B7280'

    return (
        <div className="flex flex-1 flex-col">
            {/* Surrogate Header */}
            <header className="flex h-16 shrink-0 items-center justify-between gap-2 border-b px-4">
                <div className="flex items-center gap-2">
                    <Button variant="ghost" size="sm" onClick={() => router.push('/surrogates')}>
                        <ArrowLeftIcon className="mr-2 size-4" />
                        Back
                    </Button>
                    <h1 className="text-xl font-semibold">Surrogate #{surrogateData.surrogate_number}</h1>
                    <Badge style={{ backgroundColor: statusColor, color: 'white' }}>{statusLabel}</Badge>
                    {surrogateData.is_archived && <Badge variant="secondary">Archived</Badge>}
                </div>
                <div className="flex items-center gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setChangeStageModalOpen(true)}
                        disabled={surrogateData.is_archived || !canChangeStage}
                    >
                        Change Stage
                    </Button>

                    {/* Send Email Button */}
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setEmailDialogOpen(true)}
                        disabled={surrogateData.is_archived || !surrogateData.email}
                        className="gap-2"
                    >
                        <MailIcon className="size-4" />
                        Send Email
                    </Button>

                    {/* Log Contact Attempt Button - only for intake stage (before contacted) surrogates owned by user */}
                    {(() => {
                        const currentStage = stageById.get(surrogateData.stage_id)
                        const contactedStage = stageOptions.find(stage => stage.slug === 'contacted')
                        const isIntakeStage = currentStage?.stage_type === 'intake'
                        const isBeforeContacted = !!(
                            currentStage &&
                            contactedStage &&
                            currentStage.order < contactedStage.order
                        )
                        const isAssignee = !!(user?.user_id && surrogateData.owner_id === user.user_id)
                        const canLogContact = (
                            surrogateData.owner_type === 'user' &&
                            (isAssignee || canManageQueue) &&
                            isIntakeStage &&
                            isBeforeContacted &&
                            !surrogateData.is_archived
                        )
                        return canLogContact ? (
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setContactAttemptDialogOpen(true)}
                                className="gap-2"
                            >
                                <PhoneIcon className="size-4" />
                                Log Contact
                            </Button>
                        ) : null
                    })()}

                    {/* Claim/Release buttons (case_manager+ only) */}
                    {canManageQueue && isInQueue && (
                        <Button
                            variant="default"
                            size="sm"
                            onClick={handleClaimSurrogate}
                            disabled={claimSurrogateMutation.isPending || surrogateData.is_archived}
                        >
                            {claimSurrogateMutation.isPending ? 'Claiming...' : 'Claim Surrogate'}
                        </Button>
                    )}
                    {canManageQueue && isOwnedByUser && queues && queues.length > 0 && (
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setReleaseDialogOpen(true)}
                            disabled={surrogateData.is_archived}
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
                                setZoomTopic(`Call with ${surrogateData.full_name}`)
                                const nextHour = new Date()
                                nextHour.setSeconds(0, 0)
                                nextHour.setMinutes(0)
                                nextHour.setHours(nextHour.getHours() + 1)
                                setZoomStartAt(nextHour)
                                setLastMeetingResult(null)
                                setZoomDialogOpen(true)
                            }}
                            disabled={surrogateData.is_archived}
                        >
                            <VideoIcon className="mr-2 size-4" />
                            Schedule Zoom
                        </Button>
                    )}

                    {/* Propose Match Button - only for case_manager+ at Ready to Match stage */}
                    {(() => {
                        const currentStage = stageById.get(surrogateData.stage_id)
                        const isReadyToMatchStage = currentStage?.slug === 'ready_to_match'
                        const isManagerRole = user?.role && ['case_manager', 'admin', 'developer'].includes(user.role)
                        const canProposeMatch = isManagerRole && isReadyToMatchStage && !surrogateData.is_archived

                        return canProposeMatch ? (
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setProposeMatchOpen(true)}
                            >
                                <HeartHandshakeIcon className="size-4 mr-2" />
                                Propose Match
                            </Button>
                        ) : null
                    })()}

                    {/* Assign Dropdown - case_manager+ only */}
                    {user?.role && ['case_manager', 'admin', 'developer'].includes(user.role) && !surrogateData.is_archived && (
                        <DropdownMenu>
                            <DropdownMenuTrigger className={cn(buttonVariants({ variant: "outline", size: "sm" }))} disabled={assignSurrogateMutation.isPending}>
                                {assignSurrogateMutation.isPending ? (
                                    <Loader2Icon className="size-4 mr-2 animate-spin" />
                                ) : null}
                                Assign
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                                {/* Unassign option - only when currently assigned to a user */}
                                {surrogateData.owner_type === 'user' && surrogateData.owner_id && (() => {
                                    const defaultQueue = queues?.find(q => q.name === 'Unassigned')
                                    if (!defaultQueue) return null
                                    return (
                                        <>
                                            <DropdownMenuItem
                                                onClick={() => releaseSurrogateMutation.mutate({
                                                    surrogateId: surrogateData.id,
                                                    queueId: defaultQueue.id,
                                                })}
                                                disabled={releaseSurrogateMutation.isPending}
                                            >
                                                <XIcon className="size-4 mr-2" />
                                                Unassign
                                            </DropdownMenuItem>
                                            <DropdownMenuSeparator />
                                        </>
                                    )
                                })()}
                                {assignees?.map((assignee) => (
                                    <DropdownMenuItem
                                        key={assignee.id}
                                        onClick={() => assignSurrogateMutation.mutate({
                                            surrogateId: surrogateData.id,
                                            owner_type: 'user',
                                            owner_id: assignee.id,
                                        })}
                                        disabled={surrogateData.owner_id === assignee.id}
                                    >
                                        {assignee.name}
                                        {surrogateData.owner_id === assignee.id && (
                                            <CheckIcon className="size-4 ml-auto" />
                                        )}
                                    </DropdownMenuItem>
                                ))}
                                {(!assignees || assignees.length === 0) && (
                                    <DropdownMenuItem disabled>No users available</DropdownMenuItem>
                                )}
                            </DropdownMenuContent>
                        </DropdownMenu>
                    )}
                    <DropdownMenu>
                        <DropdownMenuTrigger className={cn(buttonVariants({ variant: "ghost", size: "icon-sm" }))}>
                            <span className="inline-flex items-center justify-center">
                                <MoreVerticalIcon className="h-4 w-4" />
                            </span>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => setEditDialogOpen(true)}>Edit</DropdownMenuItem>
                            {surrogateData.is_archived ? (
                                <DropdownMenuItem onClick={handleRestore}>Restore</DropdownMenuItem>
                            ) : (
                                <DropdownMenuItem onClick={handleArchive}>Archive</DropdownMenuItem>
                            )}
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
                        <TabsTrigger value="interviews">Interviews</TabsTrigger>
                        <TabsTrigger value="application">Application</TabsTrigger>
                        {canViewProfile && <TabsTrigger value="profile">Profile</TabsTrigger>}
                        <TabsTrigger value="history">History</TabsTrigger>
                        <TabsTrigger value="ai" className="gap-1">
                            <SparklesIcon className="h-3 w-3" />
                            AI
                        </TabsTrigger>
                    </TabsList>

                    {/* OVERVIEW TAB */}
                    <TabsContent value="overview" className="space-y-4">
                        {(() => {
                            // Stage visibility for conditional cards
                            const currentStage = stageById.get(surrogateData.stage_id)
                            const isReadyToMatchOrLater = !!(
                                currentStage &&
                                readyToMatchStage &&
                                currentStage.order >= readyToMatchStage.order
                            )
                            const isHeartbeatConfirmedOrLater = !!(
                                currentStage &&
                                heartbeatStage &&
                                currentStage.order >= heartbeatStage.order
                            )

                            return (
                                <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
                                    {/* LEFT COLUMN */}
                                    <div className="space-y-4">
                                        {/* Contact Information */}
                                        <Card>
                                            <CardHeader>
                                                <CardTitle>Contact Information</CardTitle>
                                            </CardHeader>
                                            <CardContent className="space-y-3">
                                                <div>
                                                    <span className="text-sm text-muted-foreground">Name:</span>
                                                    <InlineEditField
                                                        value={surrogateData.full_name}
                                                        onSave={async (value) => {
                                                            await updateSurrogateMutation.mutateAsync({ surrogateId: id, data: { full_name: value } })
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
                                                        value={surrogateData.email}
                                                        onSave={async (value) => {
                                                            await updateSurrogateMutation.mutateAsync({ surrogateId: id, data: { email: value } })
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
                                                        value={surrogateData.phone ?? undefined}
                                                        onSave={async (value) => {
                                                            await updateSurrogateMutation.mutateAsync({ surrogateId: id, data: { phone: value || null } })
                                                        }}
                                                        type="tel"
                                                        placeholder="-"
                                                        label="Phone"
                                                    />
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-sm text-muted-foreground">State:</span>
                                                    <InlineEditField
                                                        value={surrogateData.state ?? undefined}
                                                        onSave={async (value) => {
                                                            await updateSurrogateMutation.mutateAsync({ surrogateId: id, data: { state: value || null } })
                                                        }}
                                                        placeholder="-"
                                                        validate={(v) => v && v.length !== 2 ? 'Use 2-letter code (e.g., CA, TX)' : null}
                                                        label="State"
                                                    />
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-sm text-muted-foreground">Source:</span>
                                                    <Badge variant="secondary" className="capitalize">{surrogateData.source}</Badge>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-sm text-muted-foreground">Created:</span>
                                                    <span className="text-sm">{formatDate(surrogateData.created_at)}</span>
                                                </div>
                                            </CardContent>
                                        </Card>

                                        {/* Demographics */}
                                        <Card>
                                            <CardHeader>
                                                <CardTitle>Demographics</CardTitle>
                                            </CardHeader>
                                            <CardContent className="space-y-3">
                                                <div className="flex items-center gap-2">
                                                    <span className="text-sm text-muted-foreground">Date of Birth:</span>
                                                    <span className="text-sm">{surrogateData.date_of_birth ? formatDate(surrogateData.date_of_birth) : '-'}</span>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-sm text-muted-foreground">Race:</span>
                                                    <span className="text-sm">{surrogateData.race || '-'}</span>
                                                </div>
                                                {(surrogateData.height_ft || surrogateData.weight_lb) && (
                                                    <>
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-sm text-muted-foreground">Height:</span>
                                                            <span className="text-sm">{surrogateData.height_ft ? `${surrogateData.height_ft} ft` : '-'}</span>
                                                        </div>
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-sm text-muted-foreground">Weight:</span>
                                                            <span className="text-sm">{surrogateData.weight_lb ? `${surrogateData.weight_lb} lb` : '-'}</span>
                                                        </div>
                                                    </>
                                                )}
                                            </CardContent>
                                        </Card>

                                        {/* Insurance Info - Always visible */}
                                        <InsuranceInfoCard
                                            surrogateData={surrogateData}
                                            onUpdate={async (data) => {
                                                await updateSurrogateMutation.mutateAsync({ surrogateId: id, data })
                                            }}
                                        />

                                        {/* Medical Information - Visible at Ready to Match+ */}
                                        {isReadyToMatchOrLater && (
                                            <MedicalInfoCard
                                                surrogateData={surrogateData}
                                                onUpdate={async (data) => {
                                                    await updateSurrogateMutation.mutateAsync({ surrogateId: id, data })
                                                }}
                                            />
                                        )}
                                    </div>

                                    {/* RIGHT COLUMN */}
                                    <div className="space-y-4">
                                        {/* Latest Updates - Always visible */}
                                        <LatestUpdatesCard
                                            surrogateId={id}
                                            notes={notes}
                                            attachments={attachments}
                                        />

                                        {/* Eligibility Checklist */}
                                        <Card>
                                            <CardHeader>
                                                <CardTitle>Eligibility Checklist</CardTitle>
                                            </CardHeader>
                                            <CardContent className="space-y-3">
                                                {[
                                                    { label: 'Age Eligible (18-42)', value: surrogateData.is_age_eligible },
                                                    { label: 'US Citizen or PR', value: surrogateData.is_citizen_or_pr },
                                                    { label: 'Has Child', value: surrogateData.has_child },
                                                    { label: 'Non-Smoker', value: surrogateData.is_non_smoker },
                                                    { label: 'Prior Surrogate Experience', value: surrogateData.has_surrogate_experience },
                                                ].map(({ label, value }) => (
                                                    <div key={label} className="flex items-center gap-2">
                                                        {value === true && <CheckIcon className="h-4 w-4 text-green-500" />}
                                                        {value === false && <XIcon className="h-4 w-4 text-red-500" />}
                                                        {value === null && <span className="h-4 w-4 text-center text-muted-foreground">-</span>}
                                                        <span className="text-sm">{label}</span>
                                                    </div>
                                                ))}
                                                {(surrogateData.num_deliveries !== null || surrogateData.num_csections !== null) && (
                                                    <div className="border-t pt-3 space-y-2">
                                                        {surrogateData.num_deliveries !== null && (
                                                            <div className="flex items-center gap-2">
                                                                <span className="text-sm text-muted-foreground">Deliveries:</span>
                                                                <span className="text-sm">{surrogateData.num_deliveries}</span>
                                                            </div>
                                                        )}
                                                        {surrogateData.num_csections !== null && (
                                                            <div className="flex items-center gap-2">
                                                                <span className="text-sm text-muted-foreground">C-Sections:</span>
                                                                <span className="text-sm">{surrogateData.num_csections}</span>
                                                            </div>
                                                        )}
                                                    </div>
                                                )}
                                            </CardContent>
                                        </Card>

                                        {/* Pregnancy Tracker - Visible at Heartbeat Confirmed+ */}
                                        {isHeartbeatConfirmedOrLater && (
                                            <PregnancyTrackerCard
                                                surrogateData={surrogateData}
                                                onUpdate={async (data) => {
                                                    await updateSurrogateMutation.mutateAsync({ surrogateId: id, data })
                                                }}
                                            />
                                        )}
                                    </div>
                                </div>
                            )
                        })()}
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
                                <FileUploadZone surrogateId={id} />
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* TASKS TAB */}
                    <TabsContent value="tasks" className="space-y-4">
                        <SurrogateTasksCalendar
                            surrogateId={id}
                            tasks={tasksData?.items || []}
                            isLoading={tasksLoading}
                            onTaskToggle={handleTaskToggle}
                            onAddTask={() => setAddTaskDialogOpen(true)}
                            onTaskClick={handleTaskClick}
                        />
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

                    <AddSurrogateTaskDialog
                        open={addTaskDialogOpen}
                        onOpenChange={setAddTaskDialogOpen}
                        onSubmit={handleAddTask}
                        isPending={createTaskMutation.isPending}
                        surrogateName={surrogateData?.full_name || "this surrogate"}
                    />
                    <TaskEditModal
                        task={editingTask ? {
                            id: editingTask.id,
                            title: editingTask.title,
                            description: editingTask.description ?? null,
                            task_type: editingTask.task_type,
                            due_date: editingTask.due_date,
                            due_time: editingTask.due_time ?? null,
                            is_completed: editingTask.is_completed,
                            surrogate_id: editingTask.surrogate_id,
                        } : null}
                        open={!!editingTask}
                        onClose={() => setEditingTask(null)}
                        onSave={handleSaveTask}
                        onDelete={handleDeleteTask}
                        isDeleting={deleteTaskMutation.isPending}
                    />

                    {/* APPLICATION TAB */}
                    <TabsContent value="application" className="space-y-4">
                        <SurrogateApplicationTab
                            surrogateId={id}
                            formId={defaultFormId}
                        />
                    </TabsContent>

                    {/* INTERVIEWS TAB */}
                    <TabsContent value="interviews" className="space-y-4">
                        <SurrogateInterviewTab surrogateId={id} />
                    </TabsContent>

                    {/* PROFILE TAB */}
                    {canViewProfile && (
                        <TabsContent value="profile" className="space-y-4">
                            <SurrogateProfileCard surrogateId={id} />
                        </TabsContent>
                    )}

                    {/* AI TAB */}
                    <TabsContent value="ai" className="space-y-4">
                        {aiSettings && !aiSettings.is_enabled ? (
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="flex flex-col items-center justify-center py-8 text-center">
                                        <BrainIcon className="h-12 w-12 text-muted-foreground mb-4" />
                                        <h3 className="text-lg font-medium">AI Assistant Not Enabled</h3>
                                        <p className="text-sm text-muted-foreground mt-2 max-w-md">
                                            Contact your admin to enable AI features and configure an API key in Settings.
                                        </p>
                                    </div>
                                </CardContent>
                            </Card>
                        ) : (
                            <div className="grid gap-4 md:grid-cols-2">
                                {/* Summarize Surrogate Card */}
                                <Card>
                                    <CardHeader>
                                        <CardTitle className="flex items-center gap-2">
                                            <SparklesIcon className="h-4 w-4" />
                                            Surrogate Summary
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent className="space-y-4">
                                        <Button
                                            onClick={async () => {
                                                const result = await summarizeSurrogateMutation.mutateAsync(id)
                                                setAiSummary(result)
                                            }}
                                            disabled={summarizeSurrogateMutation.isPending}
                                            className="w-full"
                                        >
                                            {summarizeSurrogateMutation.isPending ? (
                                                <><Loader2Icon className="h-4 w-4 mr-2 animate-spin" /> Generating...</>
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
                                            {EMAIL_TYPES.map((emailType) => {
                                                const label =
                                                    emailType === 'meeting_request'
                                                        ? 'appointment request'
                                                        : emailType.replace(/_/g, ' ')
                                                return (
                                                    <Button
                                                        key={emailType}
                                                        variant={selectedEmailType === emailType ? 'default' : 'outline'}
                                                        size="sm"
                                                        onClick={() => setSelectedEmailType(emailType)}
                                                        className="capitalize text-xs"
                                                    >
                                                        {label}
                                                    </Button>
                                                )
                                            })}
                                        </div>

                                        <Button
                                            onClick={async () => {
                                                if (!selectedEmailType) return
                                                const result = await draftEmailMutation.mutateAsync({
                                                    surrogate_id: id,
                                                    email_type: selectedEmailType,
                                                })
                                                setAiDraftEmail(result)
                                            }}
                                            disabled={!selectedEmailType || draftEmailMutation.isPending}
                                            className="w-full"
                                        >
                                            {draftEmailMutation.isPending ? (
                                                <><Loader2Icon className="h-4 w-4 mr-2 animate-spin" /> Drafting...</>
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

            {/* Edit Surrogate Dialog */}
            <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
                <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle>Edit Surrogate: #{surrogateData?.surrogate_number}</DialogTitle>
                    </DialogHeader>
                    <form onSubmit={async (e: React.FormEvent<HTMLFormElement>) => {
                        e.preventDefault()
                        const form = e.currentTarget
                        const formData = new FormData(form)
                        const data: Record<string, unknown> = {}
                        const getString = (key: string) => {
                            const value = formData.get(key)
                            return typeof value === "string" ? value : ""
                        }

                        // Text fields
                        const fullName = getString("full_name")
                        if (fullName) data.full_name = fullName
                        const email = getString("email")
                        if (email) data.email = email
                        const phone = getString("phone")
                        data.phone = phone || null
                        const state = getString("state")
                        data.state = state || null
                        const dateOfBirth = getString("date_of_birth")
                        data.date_of_birth = dateOfBirth || null
                        const race = getString("race")
                        data.race = race || null

                        // Number fields
                        const heightFt = getString("height_ft")
                        data.height_ft = heightFt ? parseFloat(heightFt) : null
                        const weightLb = getString("weight_lb")
                        data.weight_lb = weightLb ? parseFloat(weightLb) : null
                        const numDeliveries = getString("num_deliveries")
                        data.num_deliveries = numDeliveries ? parseInt(numDeliveries, 10) : null
                        const numCsections = getString("num_csections")
                        data.num_csections = numCsections ? parseInt(numCsections, 10) : null

                        // Boolean fields (checkboxes)
                        data.is_age_eligible = formData.get('is_age_eligible') === 'on'
                        data.is_citizen_or_pr = formData.get('is_citizen_or_pr') === 'on'
                        data.has_child = formData.get('has_child') === 'on'
                        data.is_non_smoker = formData.get('is_non_smoker') === 'on'
                        data.has_surrogate_experience = formData.get('has_surrogate_experience') === 'on'
                        data.is_priority = formData.get('is_priority') === 'on'

                        await updateSurrogateMutation.mutateAsync({ surrogateId: id, data })
                        setEditDialogOpen(false)
                    }}>
                        <div className="grid gap-4 py-4">
                            {/* Contact Info */}
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="full_name">Full Name *</Label>
                                    <Input id="full_name" name="full_name" defaultValue={surrogateData?.full_name} required />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="email">Email *</Label>
                                    <Input id="email" name="email" type="email" defaultValue={surrogateData?.email} required />
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="phone">Phone</Label>
                                    <Input id="phone" name="phone" defaultValue={surrogateData?.phone ?? ''} />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="state">State</Label>
                                    <Input id="state" name="state" defaultValue={surrogateData?.state ?? ''} />
                                </div>
                            </div>

                            {/* Personal Info */}
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="date_of_birth">Date of Birth</Label>
                                    <Input id="date_of_birth" name="date_of_birth" type="date" defaultValue={surrogateData?.date_of_birth ?? ''} />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="race">Race</Label>
                                    <Input id="race" name="race" defaultValue={surrogateData?.race ?? ''} />
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="height_ft">Height (ft)</Label>
                                    <Input id="height_ft" name="height_ft" type="number" step="0.1" defaultValue={surrogateData?.height_ft ?? ''} />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="weight_lb">Weight (lb)</Label>
                                    <Input id="weight_lb" name="weight_lb" type="number" defaultValue={surrogateData?.weight_lb ?? ''} />
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="num_deliveries">Number of Deliveries</Label>
                                    <Input id="num_deliveries" name="num_deliveries" type="number" min="0" max="20" defaultValue={surrogateData?.num_deliveries ?? ''} />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="num_csections">Number of C-Sections</Label>
                                    <Input id="num_csections" name="num_csections" type="number" min="0" max="10" defaultValue={surrogateData?.num_csections ?? ''} />
                                </div>
                            </div>

                            {/* Boolean Fields */}
                            <div className="grid grid-cols-2 gap-4 pt-2">
                                <div className="flex items-center gap-2">
                                    <Checkbox id="is_priority" name="is_priority" defaultChecked={surrogateData?.is_priority} />
                                    <Label htmlFor="is_priority">Priority Surrogate</Label>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Checkbox id="is_age_eligible" name="is_age_eligible" defaultChecked={surrogateData?.is_age_eligible ?? false} />
                                    <Label htmlFor="is_age_eligible">Age Eligible</Label>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Checkbox id="is_citizen_or_pr" name="is_citizen_or_pr" defaultChecked={surrogateData?.is_citizen_or_pr ?? false} />
                                    <Label htmlFor="is_citizen_or_pr">US Citizen/PR</Label>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Checkbox id="has_child" name="has_child" defaultChecked={surrogateData?.has_child ?? false} />
                                    <Label htmlFor="has_child">Has Child</Label>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Checkbox id="is_non_smoker" name="is_non_smoker" defaultChecked={surrogateData?.is_non_smoker ?? false} />
                                    <Label htmlFor="is_non_smoker">Non-Smoker</Label>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Checkbox id="has_surrogate_experience" name="has_surrogate_experience" defaultChecked={surrogateData?.has_surrogate_experience ?? false} />
                                    <Label htmlFor="has_surrogate_experience">Surrogate Experience</Label>
                                </div>
                            </div>
                        </div>
                        <DialogFooter>
                            <Button type="button" variant="outline" onClick={() => setEditDialogOpen(false)}>
                                Cancel
                            </Button>
                            <Button type="submit" disabled={updateSurrogateMutation.isPending}>
                                {updateSurrogateMutation.isPending ? 'Saving...' : 'Save Changes'}
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
                            onClick={handleReleaseSurrogate}
                            disabled={!selectedQueueId || releaseSurrogateMutation.isPending}
                        >
                            {releaseSurrogateMutation.isPending ? 'Releasing...' : 'Release'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Schedule Zoom Dialog */}
            <Dialog open={zoomDialogOpen} onOpenChange={setZoomDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <VideoIcon className="size-5" />
                            Schedule Zoom Appointment
                        </DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        <div>
                            <Label htmlFor="zoom-topic">Topic</Label>
                            <Input
                                id="zoom-topic"
                                value={zoomTopic}
                                onChange={(e) => setZoomTopic(e.target.value)}
                                placeholder="Appointment topic"
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
                            An appointment task is created automatically.
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
                                        if (!surrogateData?.email) return
                                        try {
                                            await sendZoomInviteMutation.mutateAsync({
                                                recipient_email: surrogateData.email,
                                                meeting_id: lastMeetingResult.meeting_id,
                                                join_url: lastMeetingResult.join_url,
                                                topic: zoomTopic,
                                                duration: zoomDuration,
                                                contact_name: surrogateData.full_name || 'there',
                                                surrogate_id: id,
                                                ...(lastMeetingResult.start_time ? { start_time: lastMeetingResult.start_time } : {}),
                                                ...(lastMeetingResult.password ? { password: lastMeetingResult.password } : {}),
                                            })
                                            setZoomDialogOpen(false)
                                            setLastMeetingResult(null)
                                        } catch {
                                            // Error handled by react-query
                                        }
                                    }}
                                    disabled={sendZoomInviteMutation.isPending || !surrogateData?.email}
                                >
                                    {sendZoomInviteMutation.isPending ? 'Sending...' : 'Send Invite'}
                                </Button>
                            </>
                        ) : (
                            <Button
                                onClick={async () => {
                                    if (!zoomStartAt) return
                                    try {
                                        const result = await createZoomMeetingMutation.mutateAsync({
                                            entity_type: 'surrogate',
                                            entity_id: id,
                                            topic: zoomTopic,
                                            start_time: toLocalIsoDateTime(zoomStartAt),
                                            timezone: timezoneName,
                                            duration: zoomDuration,
                                            contact_name: surrogateData?.full_name,
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
                                {createZoomMeetingMutation.isPending ? 'Creating...' : 'Create Appointment'}
                            </Button>
                        )}
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Email Compose Dialog */}
            <EmailComposeDialog
                open={emailDialogOpen}
                onOpenChange={setEmailDialogOpen}
                surrogateData={{
                    id: surrogateData.id,
                    email: surrogateData.email,
                    full_name: surrogateData.full_name,
                    surrogate_number: surrogateData.surrogate_number,
                    status: surrogateData.status_label,
                    ...(surrogateData.state ? { state: surrogateData.state } : {}),
                    ...(surrogateData.phone ? { phone: surrogateData.phone } : {}),
                }}
            />

            {/* Propose Match Dialog */}
            <ProposeMatchDialog
                open={proposeMatchOpen}
                onOpenChange={setProposeMatchOpen}
                surrogateId={surrogateData.id}
                surrogateName={surrogateData.full_name}
            />

            {/* Log Contact Attempt Dialog */}
            <LogContactAttemptDialog
                open={contactAttemptDialogOpen}
                onOpenChange={setContactAttemptDialogOpen}
                surrogateId={surrogateData.id}
                surrogateName={surrogateData.full_name}
            />

            {/* Change Stage Modal */}
            <ChangeStageModal
                open={changeStageModalOpen}
                onOpenChange={setChangeStageModalOpen}
                stages={visibleStageOptions}
                currentStageId={surrogateData.stage_id}
                currentStageLabel={statusLabel}
                onSubmit={handleStatusChange}
                isPending={changeStatusMutation.isPending}
            />
        </div>
    )
}
