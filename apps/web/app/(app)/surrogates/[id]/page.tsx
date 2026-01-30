"use client"

import * as React from "react"
import { useRouter, useParams, useSearchParams } from "next/navigation"
import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
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
import {
    MoreVerticalIcon,
    CopyIcon,
    CheckIcon,
    XIcon,
    Loader2Icon,
    SparklesIcon,
    MailIcon,
    HeartHandshakeIcon,
    PhoneIcon,
    VideoIcon,
    UserIcon,
    InfoIcon,
    ClipboardCheckIcon,
} from "lucide-react"
import { InlineEditField } from "@/components/inline-edit-field"
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
import { AddSurrogateTaskDialog, type SurrogateTaskFormData } from "@/components/surrogates/AddSurrogateTaskDialog"
import { TaskEditModal } from "@/components/tasks/TaskEditModal"
import { SurrogateProfileCard } from "@/components/surrogates/SurrogateProfileCard"
import { LogContactAttemptDialog } from "@/components/surrogates/LogContactAttemptDialog"
import { InsuranceInfoCard } from "@/components/surrogates/InsuranceInfoCard"
import { MedicalInfoCard } from "@/components/surrogates/MedicalInfoCard"
import { ActivityTimeline } from "@/components/surrogates/ActivityTimeline"
import { PregnancyTrackerCard } from "@/components/surrogates/PregnancyTrackerCard"
import { SurrogateJourneyTab } from "@/components/surrogates/journey/SurrogateJourneyTab"
import { SurrogateOverviewCard } from "@/components/surrogates/SurrogateOverviewCard"
import { SurrogateNotesTab } from "@/components/surrogates/tabs/SurrogateNotesTab"
import { SurrogateTasksTab } from "@/components/surrogates/tabs/SurrogateTasksTab"
import { ChangeStageModal } from "@/components/surrogates/ChangeStageModal"
import { SurrogateDetailHeader } from "@/components/surrogates/detail/SurrogateDetailHeader"
import { SurrogateHistoryTab } from "@/components/surrogates/detail/SurrogateHistoryTab"
import { SurrogateAiTab } from "@/components/surrogates/detail/SurrogateAiTab"
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

const TAB_VALUES = [
    "overview",
    "notes",
    "tasks",
    "interviews",
    "application",
    "profile",
    "history",
    "journey",
    "ai",
] as const
type TabValue = (typeof TAB_VALUES)[number]

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

function computeBmi(heightFt: number | null, weightLb: number | null): number | null {
    if (!heightFt || !weightLb) return null
    const heightInches = heightFt * 12
    if (heightInches <= 0) return null
    return Math.round((weightLb / (heightInches ** 2)) * 703 * 10) / 10
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


// Format activity type for display
export default function SurrogateDetailPage() {
    const params = useParams<{ id: string }>()
    const id = params.id
    const router = useRouter()
    const searchParams = useSearchParams()
    const { user } = useAuth()
    const canViewProfile = user
        ? ["case_manager", "admin", "developer"].includes(user.role)
        : false
    const allowedTabs = React.useMemo<TabValue[]>(
        () => (canViewProfile ? [...TAB_VALUES] : TAB_VALUES.filter((tab) => tab !== "profile")),
        [canViewProfile]
    )
    const isTabValue = (value: string | null, allowed: TabValue[]): value is TabValue => {
        if (!value) return false
        return allowed.includes(value as TabValue)
    }
    const tabParam = searchParams.get("tab")
    const urlTab: TabValue = isTabValue(tabParam, allowedTabs) ? tabParam : "overview"
    const [currentTab, setCurrentTab] = React.useState<TabValue>(urlTab)
    const searchParamsString = searchParams.toString()

    React.useEffect(() => {
        setCurrentTab(urlTab)
    }, [urlTab])

    const handleTabChange = React.useCallback(
        (value: string) => {
            const nextTab: TabValue = isTabValue(value, allowedTabs) ? value : "overview"
            setCurrentTab(nextTab)
            const nextParams = new URLSearchParams(searchParamsString)
            if (nextTab === "overview") {
                nextParams.delete("tab")
            } else {
                nextParams.set("tab", nextTab)
            }
            const queryString = nextParams.toString()
            const nextUrl = queryString ? `/surrogates/${id}?${queryString}` : `/surrogates/${id}`
            router.replace(nextUrl, { scroll: false })
        },
        [allowedTabs, searchParamsString, router, id]
    )
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
    // Stage visibility for Journey tab (visible at "matched" stage or later)
    const matchedStage = React.useMemo(
        () => stageOptions.find(s => s.slug === 'matched'),
        [stageOptions]
    )

    // Fetch data
    const { data: surrogateData, isLoading, error } = useSurrogate(id)
    const bmiValue = React.useMemo(() => {
        if (!surrogateData) return null
        if (typeof surrogateData.bmi === "number") return surrogateData.bmi
        return computeBmi(surrogateData.height_ft, surrogateData.weight_lb)
    }, [surrogateData])

    // Compute if journey tab should be visible based on current stage
    const canViewJourney = React.useMemo(() => {
        if (!surrogateData || !matchedStage) return false
        const currentStage = stageById.get(surrogateData.stage_id)
        if (!currentStage) return false
        return currentStage.order >= matchedStage.order
    }, [surrogateData, matchedStage, stageById])

    // Redirect away from journey tab if not available
    React.useEffect(() => {
        if (surrogateData && currentTab === "journey" && !canViewJourney) {
            handleTabChange("overview")
        }
    }, [surrogateData, currentTab, canViewJourney, handleTabChange])

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
    const zoomIdempotencyKeyRef = React.useRef<string | null>(null)
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

    React.useEffect(() => {
        if (!zoomDialogOpen) {
            zoomIdempotencyKeyRef.current = null
        }
    }, [zoomDialogOpen])

    // Additional data fetches
    const { data: activityData } = useSurrogateActivity(id)
    const { data: notes } = useNotes(id)
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
        delivery_baby_gender?: string | null
        delivery_baby_weight?: string | null
    }): Promise<{ status: "applied" | "pending_approval"; request_id?: string }> => {
        if (!surrogateData || !canChangeStage) {
            return { status: "applied" }
        }
        const previousStageId = surrogateData.stage_id
        const targetStageLabel = stageById.get(data.stage_id)?.label || "Stage"
        const payload: {
            stage_id: string
            reason?: string
            effective_at?: string
            delivery_baby_gender?: string | null
            delivery_baby_weight?: string | null
        } = {
            stage_id: data.stage_id,
        }
        if (data.reason) payload.reason = data.reason
        if (data.effective_at) payload.effective_at = data.effective_at
        if (data.delivery_baby_gender !== undefined) {
            payload.delivery_baby_gender = data.delivery_baby_gender
        }
        if (data.delivery_baby_weight !== undefined) {
            payload.delivery_baby_weight = data.delivery_baby_weight
        }

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

    const handleGenerateSummary = async () => {
        const result = await summarizeSurrogateMutation.mutateAsync(id)
        setAiSummary(result)
    }

    const handleDraftEmail = async () => {
        if (!selectedEmailType) return
        const result = await draftEmailMutation.mutateAsync({
            surrogate_id: id,
            email_type: selectedEmailType,
        })
        setAiDraftEmail(result)
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
            <SurrogateDetailHeader
                surrogateNumber={surrogateData.surrogate_number}
                statusLabel={statusLabel}
                statusColor={statusColor}
                isArchived={surrogateData.is_archived}
                onBack={() => router.push('/surrogates')}
            >
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
            </SurrogateDetailHeader>

            {/* Tabs Content */}
            <div className="flex flex-1 flex-col gap-4 p-4 md:p-6">
                <Tabs value={currentTab} onValueChange={handleTabChange} className="w-full">
                    <TabsList className="mb-4 overflow-x-auto print:hidden">
                        <TabsTrigger value="overview">Overview</TabsTrigger>
                        <TabsTrigger value="notes">Notes {notes && notes.length > 0 && `(${notes.length})`}</TabsTrigger>
                        <TabsTrigger value="tasks">Tasks {tasksData && tasksData.items.length > 0 && `(${tasksData.items.length})`}</TabsTrigger>
                        <TabsTrigger value="interviews">Interviews</TabsTrigger>
                        <TabsTrigger value="application">Application</TabsTrigger>
                        {canViewProfile && <TabsTrigger value="profile">Profile</TabsTrigger>}
                        <TabsTrigger value="history">History</TabsTrigger>
                        <TabsTrigger value="journey" disabled={!canViewJourney}>
                            Journey
                        </TabsTrigger>
                        <TabsTrigger value="ai" className="gap-1">
                            <SparklesIcon className="h-3 w-3" />
                            AI
                        </TabsTrigger>
                    </TabsList>
                    {surrogateData && !canViewJourney && (
                        <p className="mt-1 text-xs text-muted-foreground">
                            Journey available after Match Confirmed
                        </p>
                    )}

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
                                        <SurrogateOverviewCard title="Contact Information" icon={UserIcon}>
                                            <div className="flex items-center gap-2">
                                                <span className="text-sm text-muted-foreground">Name:</span>
                                                <InlineEditField
                                                    value={surrogateData.full_name}
                                                    onSave={async (value) => {
                                                        await updateSurrogateMutation.mutateAsync({ surrogateId: id, data: { full_name: value } })
                                                    }}
                                                    placeholder="Enter name"
                                                    className="text-base font-medium"
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
                                        </SurrogateOverviewCard>

                                        {/* Demographics */}
                                        <SurrogateOverviewCard title="Demographics" icon={InfoIcon}>
                                            <div className="flex items-center gap-2">
                                                <span className="text-sm text-muted-foreground">Date of Birth:</span>
                                                <span className="text-sm">{surrogateData.date_of_birth ? formatDate(surrogateData.date_of_birth) : '-'}</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <span className="text-sm text-muted-foreground">Race:</span>
                                                <span className="text-sm">{surrogateData.race || '-'}</span>
                                            </div>
                                            {(surrogateData.height_ft || surrogateData.weight_lb || bmiValue !== null) && (
                                                <>
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-sm text-muted-foreground">Height:</span>
                                                        <span className="text-sm">{surrogateData.height_ft ? `${surrogateData.height_ft} ft` : '-'}</span>
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-sm text-muted-foreground">Weight:</span>
                                                        <span className="text-sm">{surrogateData.weight_lb ? `${surrogateData.weight_lb} lb` : '-'}</span>
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-sm text-muted-foreground">BMI:</span>
                                                        <span className="text-sm">{bmiValue ?? '-'}</span>
                                                    </div>
                                                </>
                                            )}
                                        </SurrogateOverviewCard>

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
                                        {/* Pregnancy Tracker - Visible at Heartbeat Confirmed+ */}
                                        {isHeartbeatConfirmedOrLater && (
                                            <PregnancyTrackerCard
                                                surrogateData={surrogateData}
                                                onUpdate={async (data) => {
                                                    await updateSurrogateMutation.mutateAsync({ surrogateId: id, data })
                                                }}
                                            />
                                        )}

                                        {/* Activity Timeline - Stage-grouped activity */}
                                        <ActivityTimeline
                                            surrogateId={id}
                                            currentStageId={surrogateData.stage_id}
                                            stages={stageOptions}
                                            activities={activityData?.items ?? []}
                                            tasks={tasksData?.items ?? []}
                                        />

                                        {/* Eligibility Checklist */}
                                        <SurrogateOverviewCard title="Eligibility Checklist" icon={ClipboardCheckIcon}>
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
                                        </SurrogateOverviewCard>

                                    </div>
                                </div>
                            )
                        })()}
                    </TabsContent>

                    {/* NOTES TAB */}
                    <SurrogateNotesTab
                        surrogateId={id}
                        notes={notes}
                        onAddNote={handleAddNote}
                        isSubmitting={createNoteMutation.isPending}
                        onDeleteNote={handleDeleteNote}
                        formatDateTime={formatDateTime}
                    />

                    {/* TASKS TAB */}
                    <SurrogateTasksTab
                        surrogateId={id}
                        tasks={tasksData?.items || []}
                        isLoading={tasksLoading}
                        onTaskToggle={handleTaskToggle}
                        onAddTask={() => setAddTaskDialogOpen(true)}
                        onTaskClick={handleTaskClick}
                    />

                    {/* HISTORY TAB */}
                    <TabsContent value="history" className="space-y-4">
                        <SurrogateHistoryTab
                            activities={activityData?.items ?? []}
                            formatDateTime={formatDateTime}
                        />
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
                        <SurrogateAiTab
                            aiSettings={aiSettings}
                            aiSummary={aiSummary}
                            aiDraftEmail={aiDraftEmail}
                            selectedEmailType={selectedEmailType}
                            onSelectEmailType={setSelectedEmailType}
                            onGenerateSummary={handleGenerateSummary}
                            onDraftEmail={handleDraftEmail}
                            isGeneratingSummary={summarizeSurrogateMutation.isPending}
                            isDraftingEmail={draftEmailMutation.isPending}
                        />
                    </TabsContent>

                    {/* JOURNEY TAB */}
                    {canViewJourney && (
                        <TabsContent value="journey" className="space-y-4">
                            <SurrogateJourneyTab surrogateId={id} />
                        </TabsContent>
                    )}
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
                                        if (!zoomIdempotencyKeyRef.current) {
                                            zoomIdempotencyKeyRef.current =
                                                typeof crypto !== 'undefined' && 'randomUUID' in crypto
                                                    ? crypto.randomUUID()
                                                    : `${Date.now()}-${Math.random().toString(16).slice(2)}`
                                        }
                                        const result = await createZoomMeetingMutation.mutateAsync({
                                            entity_type: 'surrogate',
                                            entity_id: id,
                                            topic: zoomTopic,
                                            start_time: toLocalIsoDateTime(zoomStartAt),
                                            timezone: timezoneName,
                                            duration: zoomDuration,
                                            contact_name: surrogateData?.full_name,
                                            idempotency_key: zoomIdempotencyKeyRef.current,
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
                deliveryFieldsEnabled
                initialDeliveryBabyGender={surrogateData.delivery_baby_gender}
                initialDeliveryBabyWeight={surrogateData.delivery_baby_weight}
            />
        </div>
    )
}
