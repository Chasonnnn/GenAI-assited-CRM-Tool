"use client"

import { useState, useMemo, useCallback } from "react"
import { useParams, useSearchParams, useRouter } from "next/navigation"
import Link from "next/link"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Separator } from "@/components/ui/separator"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
    MailIcon,
    PhoneIcon,
    MapPinIcon,
    CakeIcon,
    DollarSignIcon,
    StickyNoteIcon,
    FolderIcon,
    CheckSquareIcon,
    HistoryIcon,
    Loader2Icon,
    ArrowLeftIcon,
    UserIcon,
    UsersIcon,
    TrashIcon,
    DownloadIcon,
    CalendarPlusIcon,
    UploadIcon,
} from "lucide-react"
import { useMatch, matchKeys, useAcceptMatch, useRejectMatch } from "@/lib/hooks/use-matches"
import { MatchTasksCalendar } from "@/components/matches/MatchTasksCalendar"
import { RejectMatchDialog } from "@/components/matches/RejectMatchDialog"
import { AddNoteDialog } from "@/components/matches/AddNoteDialog"
import { UploadFileDialog } from "@/components/matches/UploadFileDialog"
import { AddTaskDialog, type TaskFormData } from "@/components/matches/AddTaskDialog"
import { useCase, useChangeStatus, useCaseActivity, caseKeys } from "@/lib/hooks/use-cases"
import { useNotes, useCreateNote } from "@/lib/hooks/use-notes"
import { useIntendedParent, useIntendedParentNotes, useIntendedParentHistory, intendedParentKeys, useCreateIntendedParentNote } from "@/lib/hooks/use-intended-parents"
import { useDefaultPipeline } from "@/lib/hooks/use-pipelines"
import { useTasks, useCreateTask, taskKeys } from "@/lib/hooks/use-tasks"
import { useAttachments, useIPAttachments, useUploadAttachment, useUploadIPAttachment, useDeleteAttachment, useDownloadAttachment } from "@/lib/hooks/use-attachments"
import { useAuth } from "@/lib/auth-context"
import { useQueryClient } from "@tanstack/react-query"
import { ScheduleParserDialog } from "@/components/ai/ScheduleParserDialog"
import { useSetAIContext } from "@/lib/context/ai-context"
import { cn } from "@/lib/utils"
import { parseDateInput } from "@/lib/utils/date"

const STATUS_LABELS: Record<string, string> = {
    proposed: "Proposed",
    reviewing: "Reviewing",
    accepted: "Accepted",
    rejected: "Rejected",
    cancelled: "Cancelled",
}

const STATUS_COLORS: Record<string, string> = {
    proposed: "bg-yellow-500/10 text-yellow-500 border-yellow-500/20",
    reviewing: "bg-blue-500/10 text-blue-500 border-blue-500/20",
    accepted: "bg-green-500/10 text-green-500 border-green-500/20",
    rejected: "bg-red-500/10 text-red-500 border-red-500/20",
    cancelled: "bg-gray-500/10 text-gray-500 border-gray-500/20",
}

type TabType = "notes" | "files" | "tasks" | "activity"
type DataSource = "case" | "ip" | "match"
type SourceFilter = "all" | DataSource

const SOURCE_OPTIONS: { value: SourceFilter; label: string }[] = [
    { value: "all", label: "All Source" },
    { value: "case", label: "Case" },
    { value: "ip", label: "Intended Parent" },
    { value: "match", label: "Match" },
]

const sourceLabel = (value: SourceFilter | null | undefined) =>
    SOURCE_OPTIONS.find((opt) => opt.value === value)?.label ?? "All Source"

const isTabType = (value: string | null): value is TabType =>
    value === "notes" || value === "files" || value === "tasks" || value === "activity"
const isSourceFilter = (value: string | null): value is SourceFilter =>
    value === "all" || value === "case" || value === "ip" || value === "match"
const isDeletableSource = (value: DataSource): value is "case" | "ip" =>
    value === "case" || value === "ip"

export default function MatchDetailPage() {
    const params = useParams<{ id: string }>()
    const searchParams = useSearchParams()
    const router = useRouter()
    const matchId = params.id

    // Read initial values from URL params
    const urlTab = searchParams.get("tab")
    const urlSource = searchParams.get("source")

    const [activeTab, setActiveTab] = useState<TabType>(
        isTabType(urlTab) ? urlTab : "notes"
    )
    const [sourceFilter, setSourceFilter] = useState<SourceFilter>(
        isSourceFilter(urlSource) ? urlSource : "all"
    )
    const [rejectDialogOpen, setRejectDialogOpen] = useState(false)
    const [addNoteDialogOpen, setAddNoteDialogOpen] = useState(false)
    const [uploadFileDialogOpen, setUploadFileDialogOpen] = useState(false)
    const [addTaskDialogOpen, setAddTaskDialogOpen] = useState(false)
    const [showScheduleParser, setShowScheduleParser] = useState(false)
    const { user } = useAuth()
    const queryClient = useQueryClient()

    // Sync state changes back to URL (preserving other params)
    const updateUrlParams = useCallback((tab: TabType, source: SourceFilter) => {
        const newParams = new URLSearchParams(searchParams.toString())
        if (tab !== "notes") {
            newParams.set("tab", tab)
        } else {
            newParams.delete("tab")
        }
        if (source !== "all") {
            newParams.set("source", source)
        } else {
            newParams.delete("source")
        }
        const newUrl = newParams.toString() ? `?${newParams}` : ""
        router.replace(`/intended-parents/matches/${matchId}${newUrl}`, { scroll: false })
    }, [searchParams, router, matchId])

    // Update URL when tab changes
    const handleTabChange = useCallback((tab: TabType) => {
        if (tab !== activeTab) {
            setActiveTab(tab)
            updateUrlParams(tab, sourceFilter)
        }
    }, [activeTab, sourceFilter, updateUrlParams])

    // Update URL when source filter changes
    const handleSourceFilterChange = useCallback((source: SourceFilter) => {
        if (source !== sourceFilter) {
            setSourceFilter(source)
            updateUrlParams(activeTab, source)
        }
    }, [activeTab, sourceFilter, updateUrlParams])

    const { data: match, isLoading: matchLoading } = useMatch(matchId)
    const acceptMatchMutation = useAcceptMatch()
    const rejectMatchMutation = useRejectMatch()
    const createNoteMutation = useCreateNote()
    const createIPNoteMutation = useCreateIntendedParentNote()
    const uploadAttachmentMutation = useUploadAttachment()
    const uploadIPAttachmentMutation = useUploadIPAttachment()
    const deleteAttachmentMutation = useDeleteAttachment()
    const downloadAttachmentMutation = useDownloadAttachment()
    const createTaskMutation = useCreateTask()

    // Set AI context for this page.
    // NOTE: The chat API currently supports case/task/global. For match pages, we attach AI to the case.
    const matchName = match ? `${match.case_name} & ${match.ip_name}` : ""
    useSetAIContext(match?.case_id ? { entityType: "case", entityId: match.case_id, entityName: matchName } : null)

    // Fetch full profile data for both sides
    const { data: caseData, isLoading: caseLoading } = useCase(match?.case_id || "")
    const { data: ipData, isLoading: ipLoading } = useIntendedParent(match?.intended_parent_id || "")

    // Fetch notes from all sources
    const { data: caseNotes = [] } = useNotes(match?.case_id || "")
    const { data: ipNotes = [] } = useIntendedParentNotes(match?.intended_parent_id || "")

    // Fetch files/attachments from Case and IP
    const { data: caseFiles = [] } = useAttachments(match?.case_id || null)
    const { data: ipFiles = [] } = useIPAttachments(match?.intended_parent_id || null)

    // Fetch tasks from Case and IP
    const { data: caseTasks } = useTasks(
        { case_id: match?.case_id || undefined, exclude_approvals: true },
        { enabled: !!match?.case_id }
    )
    const { data: ipTasks } = useTasks(
        {
            intended_parent_id: match?.intended_parent_id || undefined,
            exclude_approvals: true,
        },
        { enabled: !!match?.intended_parent_id }
    )

    // Fetch activity from Case and IP
    const { data: caseActivity } = useCaseActivity(match?.case_id || "", 1, 50)
    const { data: ipHistory } = useIntendedParentHistory(match?.intended_parent_id || null)

    // Pipeline stages for status change dropdown
    const { data: defaultPipeline } = useDefaultPipeline()
    const changeStatusMutation = useChangeStatus()

    // Filter to post-approval stages only (case managers can only move to post-approval)
    const postApprovalStages = useMemo(() => {
        if (!defaultPipeline?.stages) return []
        return defaultPipeline.stages.filter(s => s.stage_type === 'post_approval')
    }, [defaultPipeline])

    // Combine notes from all sources with source labels
    type CombinedNote = {
        id: string
        content: string
        created_at: string
        source: 'case' | 'ip' | 'match'
        author_name?: string
    }
    const combinedNotes = useMemo<CombinedNote[]>(() => {
        const notes: CombinedNote[] = []
        // Case notes
        for (const n of caseNotes) {
            notes.push({ id: n.id, content: n.body, created_at: n.created_at, source: 'case', author_name: n.author_name ?? undefined })
        }
        // IP notes
        for (const n of ipNotes) {
            notes.push({ id: n.id, content: n.content, created_at: n.created_at, source: 'ip' })
        }
        // Match notes (single field)
        if (match?.notes) {
            notes.push({
                id: 'match-notes',
                content: match.notes,
                created_at: match.updated_at || match.created_at,
                source: 'match',
            })
        }
        // Sort by created_at descending
        notes.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        return notes
    }, [caseNotes, ipNotes, match])

    const filteredNotes = useMemo(() => {
        if (sourceFilter === 'all') return combinedNotes
        return combinedNotes.filter(n => n.source === sourceFilter)
    }, [combinedNotes, sourceFilter])

    // Combine files from all sources
    type CombinedFile = {
        id: string
        filename: string
        file_size: number
        created_at: string
        source: 'case' | 'ip' | 'match'
    }
    const combinedFiles = useMemo<CombinedFile[]>(() => {
        const files: CombinedFile[] = []
        // Case files
        for (const f of caseFiles) {
            files.push({ id: f.id, filename: f.filename, file_size: f.file_size, created_at: f.created_at, source: 'case' })
        }
        // IP files
        for (const f of ipFiles) {
            files.push({ id: f.id, filename: f.filename, file_size: f.file_size, created_at: f.created_at, source: 'ip' })
        }
        files.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        return files
    }, [caseFiles, ipFiles])

    const filteredFiles = useMemo(() => {
        if (sourceFilter === 'all') return combinedFiles
        return combinedFiles.filter(f => f.source === sourceFilter)
    }, [combinedFiles, sourceFilter])

    // Combine tasks from all sources
    type CombinedTask = {
        id: string
        title: string
        due_date: string | null
        is_completed: boolean
        source: 'case' | 'ip' | 'match'
    }
    const combinedTasks = useMemo<CombinedTask[]>(() => {
        const tasks: CombinedTask[] = []
        // Case tasks
        for (const t of caseTasks?.items || []) {
            tasks.push({ id: t.id, title: t.title, due_date: t.due_date, is_completed: t.is_completed, source: 'case' })
        }
        // IP tasks
        for (const t of ipTasks?.items || []) {
            tasks.push({ id: t.id, title: t.title, due_date: t.due_date, is_completed: t.is_completed, source: 'ip' })
        }
        return tasks
    }, [caseTasks, ipTasks])

    const filteredTasks = useMemo(() => {
        if (sourceFilter === 'all') return combinedTasks
        return combinedTasks.filter(t => t.source === sourceFilter)
    }, [combinedTasks, sourceFilter])

    // Combine activity from all sources
    type CombinedActivity = {
        id: string
        event_type: string
        description: string
        actor_name: string | null
        created_at: string
        source: 'case' | 'ip' | 'match'
    }
    const combinedActivity = useMemo<CombinedActivity[]>(() => {
        const activities: CombinedActivity[] = []
        // Case activity (includes actor_name)
        for (const a of caseActivity?.items || []) {
            const description =
                typeof a.details?.description === "string" ? a.details.description : a.activity_type
            activities.push({
                id: a.id,
                event_type: a.activity_type,
                description,
                actor_name: a.actor_name,
                created_at: a.created_at,
                source: 'case',
            })
        }
        // IP history
        for (const h of ipHistory || []) {
            activities.push({
                id: h.id,
                event_type: 'Status Change',
                description: `Status: ${h.old_status || 'new'} → ${h.new_status}${h.reason ? ` (${h.reason})` : ''}`,
                actor_name: h.changed_by_name,
                created_at: h.changed_at,
                source: 'ip'
            })
        }
        // Match proposed event only (accept/reject already appears in case activity)
        if (match?.proposed_at) {
            activities.push({
                id: 'match-proposed',
                event_type: 'Match Proposed',
                description: 'Match was proposed',
                actor_name: null,
                created_at: match.proposed_at,
                source: 'match',
            })
        }
        // Sort by created_at descending
        activities.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        return activities
    }, [caseActivity, ipHistory, match])

    const filteredActivity = useMemo(() => {
        if (sourceFilter === 'all') return combinedActivity
        return combinedActivity.filter(a => a.source === sourceFilter)
    }, [combinedActivity, sourceFilter])

    // Check if user can change case status (case_manager+)
    const canChangeStatus = user?.role && ['case_manager', 'admin', 'developer'].includes(user.role)

    const formatDate = (dateStr: string | null | undefined) => {
        if (!dateStr) return "—"
        const parsed = parseDateInput(dateStr)
        if (Number.isNaN(parsed.getTime())) return "—"
        return parsed.toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
        })
    }

    const formatDateTime = (dateStr: string) => {
        const parsed = parseDateInput(dateStr)
        if (Number.isNaN(parsed.getTime())) return "—"
        return parsed.toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
            hour: "numeric",
            minute: "2-digit",
        })
    }

    // Handle case status change from Match detail
    const handleCaseStatusChange = async (newStageId: string) => {
        if (!match?.case_id) return
        await changeStatusMutation.mutateAsync({ caseId: match.case_id, data: { stage_id: newStageId } })
        // Invalidate match query to refresh case_stage fields
        queryClient.invalidateQueries({ queryKey: matchKeys.detail(matchId) })
    }

    // Handle Accept match
    const handleAcceptMatch = async () => {
        await acceptMatchMutation.mutateAsync({ matchId })
        // Invalidate all related queries to refresh UI
        if (match?.case_id) {
            queryClient.invalidateQueries({ queryKey: caseKeys.detail(match.case_id) })
            queryClient.invalidateQueries({ queryKey: caseKeys.lists() })
        }
        if (match?.intended_parent_id) {
            queryClient.invalidateQueries({ queryKey: intendedParentKeys.detail(match.intended_parent_id) })
            queryClient.invalidateQueries({ queryKey: intendedParentKeys.lists() })
        }
        queryClient.invalidateQueries({ queryKey: matchKeys.detail(matchId) })
    }

    // Handle Reject match
    const handleRejectMatch = async (reason: string) => {
        await rejectMatchMutation.mutateAsync({ matchId, data: { rejection_reason: reason } })
        // Refresh related data after rejection
        if (match?.case_id) {
            queryClient.invalidateQueries({ queryKey: caseKeys.detail(match.case_id) })
        }
        if (match?.intended_parent_id) {
            queryClient.invalidateQueries({ queryKey: intendedParentKeys.detail(match.intended_parent_id) })
        }
        queryClient.invalidateQueries({ queryKey: matchKeys.detail(matchId) })
        queryClient.invalidateQueries({ queryKey: matchKeys.lists() })
    }

    // Handle Add Note
    const handleAddNote = async (target: "case" | "ip", content: string) => {
        try {
            if (target === "case" && match?.case_id) {
                await createNoteMutation.mutateAsync({ caseId: match.case_id, body: content })
            } else if (target === "ip" && match?.intended_parent_id) {
                await createIPNoteMutation.mutateAsync({ id: match.intended_parent_id, data: { content } })
            }
            toast.success("Note added successfully")
        } catch {
            toast.error("Failed to add note")
        }
    }

    // Handle File Upload
    const handleUploadFile = async (target: "case" | "ip", file: File) => {
        try {
            if (target === "case" && match?.case_id) {
                await uploadAttachmentMutation.mutateAsync({ caseId: match.case_id, file })
            } else if (target === "ip" && match?.intended_parent_id) {
                await uploadIPAttachmentMutation.mutateAsync({ ipId: match.intended_parent_id, file })
            }
            toast.success("File uploaded successfully")
        } catch {
            toast.error("Failed to upload file")
        }
    }

    // Handle Delete File
    const handleDeleteFile = async (attachmentId: string, source: "case" | "ip") => {
        if (!confirm("Are you sure you want to delete this file?")) return
        try {
            const caseId = source === "case" ? match?.case_id : undefined
            await deleteAttachmentMutation.mutateAsync({ attachmentId, caseId: caseId || "" })
            // Invalidate the appropriate query based on source
            if (source === "case" && match?.case_id) {
                queryClient.invalidateQueries({ queryKey: ["attachments", match.case_id] })
            } else if (source === "ip" && match?.intended_parent_id) {
                queryClient.invalidateQueries({ queryKey: ["ip-attachments", match.intended_parent_id] })
            }
            toast.success("File deleted successfully")
        } catch {
            toast.error("Failed to delete file")
        }
    }

    // Handle Add Task
    const handleAddTask = async (target: "case" | "ip", data: TaskFormData) => {
        try {
            if (target === "case" && match?.case_id) {
                await createTaskMutation.mutateAsync({
                    title: data.title,
                    description: data.description,
                    task_type: data.task_type,
                    due_date: data.due_date,
                    case_id: match.case_id,
                })
            } else if (target === "ip" && match?.intended_parent_id) {
                await createTaskMutation.mutateAsync({
                    title: data.title,
                    description: data.description,
                    task_type: data.task_type,
                    due_date: data.due_date,
                    intended_parent_id: match.intended_parent_id,
                })
            }
            queryClient.invalidateQueries({ queryKey: taskKeys.lists() })
            toast.success("Task created successfully")
        } catch {
            toast.error("Failed to create task")
        }
    }

    if (matchLoading) {
        return (
            <div className="flex min-h-screen items-center justify-center">
                <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (!match) {
        return (
            <div className="flex min-h-screen flex-col items-center justify-center">
                <h2 className="text-xl font-semibold">Match not found</h2>
                <Link href="/intended-parents/matches">
                    <Button variant="outline" className="mt-4">
                        <ArrowLeftIcon className="mr-2 size-4" />
                        Back to Matches
                    </Button>
                </Link>
            </div>
        )
    }

    return (
        <>
            <div className="flex min-h-screen flex-col">
                {/* Page Header */}
                <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                    <div className="flex h-12 items-center gap-4 px-4">
                        <Link href="/intended-parents/matches">
                            <Button variant="ghost" size="sm" className="h-7 text-xs">
                                <ArrowLeftIcon className="mr-1 size-3" />
                                Matches
                            </Button>
                        </Link>
                        <div className="flex-1 flex items-center gap-2">
                            <h1 className="text-base font-semibold">
                                {match.case_name || "Surrogate"} ↔ {match.ip_name || "Intended Parents"}
                            </h1>
                            {/* Case Stage Badge */}
                            {match.case_stage_label && (
                                <Badge variant="secondary" className="text-xs">
                                    {match.case_stage_label}
                                </Badge>
                            )}
                        </div>
                        {/* Match Stage Badge */}
                        <Badge className={STATUS_COLORS[match.status]}>
                            {STATUS_LABELS[match.status]}
                        </Badge>
                        {/* Accept/Reject buttons for proposed/reviewing matches */}
                        {canChangeStatus && (match.status === 'proposed' || match.status === 'reviewing') && (
                            <>
                                <Button
                                    variant="default"
                                    size="sm"
                                    className="h-7 text-xs bg-green-600 hover:bg-green-700"
                                    onClick={handleAcceptMatch}
                                    disabled={acceptMatchMutation.isPending}
                                >
                                    {acceptMatchMutation.isPending ? 'Accepting...' : 'Accept Match'}
                                </Button>
                                <Button
                                    variant="destructive"
                                    size="sm"
                                    className="h-7 text-xs"
                                    onClick={() => setRejectDialogOpen(true)}
                                    disabled={rejectMatchMutation.isPending}
                                >
                                    {rejectMatchMutation.isPending ? 'Rejecting...' : 'Reject'}
                                </Button>
                            </>
                        )}
                        {/* Change Stage Dropdown - only for case_manager+ on accepted matches */}
                        {canChangeStatus && match.status === 'accepted' && postApprovalStages.length > 0 && (
                            <DropdownMenu>
                                <DropdownMenuTrigger
                                    className={cn(buttonVariants({ variant: "outline", size: "sm" }), "h-7 text-xs")}
                                >
                                    <span className="inline-flex items-center">Change Stage</span>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end">
                                    {postApprovalStages.map((stage) => (
                                        <DropdownMenuItem
                                            key={stage.id}
                                            onClick={() => handleCaseStatusChange(stage.id)}
                                            disabled={stage.id === caseData?.stage_id}
                                        >
                                            <span
                                                className="mr-2 size-2 rounded-full"
                                                style={{ backgroundColor: stage.color }}
                                            />
                                            {stage.label}
                                        </DropdownMenuItem>
                                    ))}
                                </DropdownMenuContent>
                            </DropdownMenu>
                        )}
                    </div>
                </div>

                {/* Main Content */}
                <div className="flex-1 p-4">
                    <Tabs defaultValue="overview" className="w-full">
                        <div className="flex items-center justify-between mb-3">
                            <TabsList>
                                <TabsTrigger value="overview">Overview</TabsTrigger>
                                <TabsTrigger value="calendar">Calendar</TabsTrigger>
                            </TabsList>
                            {user?.ai_enabled && (
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className="h-7 text-xs gap-1"
                                    onClick={() => setShowScheduleParser(true)}
                                >
                                    <CalendarPlusIcon className="size-3" />
                                    Parse Schedule
                                </Button>
                            )}
                        </div>

                        <TabsContent value="overview" className="h-[calc(100vh-145px)]">
                            {/* 3-Column Horizontal Layout: 35% | 35% | 30% */}
                            <div className="grid gap-4 h-full" style={{ gridTemplateColumns: '35% 35% 30%' }}>
                                {/* Surrogate Column - 35% */}
                                <div className="border rounded-lg p-4 overflow-y-auto">
                                    <div className="flex items-center gap-2 mb-3">
                                        <UserIcon className="size-4 text-purple-500" />
                                        <h2 className="text-sm font-semibold text-purple-500">Surrogate</h2>
                                    </div>

                                    {caseLoading ? (
                                        <div className="flex items-center justify-center h-32">
                                            <Loader2Icon className="size-5 animate-spin text-muted-foreground" />
                                        </div>
                                    ) : caseData ? (
                                        <div className="space-y-3">
                                            {/* Profile Header */}
                                            <div className="flex items-start gap-3">
                                                <Avatar className="h-10 w-10">
                                                    <AvatarFallback className="bg-purple-500/10 text-purple-500 text-sm">
                                                        {(caseData.full_name || "S").charAt(0).toUpperCase()}
                                                    </AvatarFallback>
                                                </Avatar>
                                                <div className="flex-1 min-w-0">
                                                    <h3 className="text-base font-semibold truncate">{caseData.full_name}</h3>
                                                    <div className="flex items-center gap-1 mt-0.5">
                                                        <Badge variant="outline" className="text-xs px-1.5 py-0">#{caseData.case_number}</Badge>
                                                        <Badge variant="secondary" className="text-xs px-1.5 py-0">{caseData.status_label}</Badge>
                                                    </div>
                                                </div>
                                            </div>

                                            <Separator />

                                            {/* Contact Info - Compact */}
                                            <div className="space-y-2 text-sm">
                                                <div className="flex items-center gap-2">
                                                    <MailIcon className="size-3.5 text-muted-foreground flex-shrink-0" />
                                                    <span className="truncate">{caseData.email || "—"}</span>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <PhoneIcon className="size-3.5 text-muted-foreground flex-shrink-0" />
                                                    <span>{caseData.phone || "—"}</span>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <MapPinIcon className="size-3.5 text-muted-foreground flex-shrink-0" />
                                                    <span>{caseData.state || "—"}</span>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <CakeIcon className="size-3.5 text-muted-foreground flex-shrink-0" />
                                                    <span>{formatDate(caseData.date_of_birth)}</span>
                                                </div>
                                            </div>

                                            <Separator />

                                            {/* Demographics - Compact */}
                                            <div>
                                                <p className="text-xs text-muted-foreground mb-1">Demographics</p>
                                                <div className="grid grid-cols-3 gap-1 text-xs">
                                                    <div><span className="text-muted-foreground">Race:</span> {caseData.race || "—"}</div>
                                                    <div><span className="text-muted-foreground">Ht:</span> {caseData.height_ft ? `${caseData.height_ft}ft` : "—"}</div>
                                                    <div><span className="text-muted-foreground">Wt:</span> {caseData.weight_lb ? `${caseData.weight_lb}lb` : "—"}</div>
                                                </div>
                                            </div>

                                            <Link href={`/cases/${caseData.id}`}>
                                                <Button variant="outline" size="sm" className="w-full text-xs h-7">View Full Profile</Button>
                                            </Link>
                                        </div>
                                    ) : (
                                        <div className="flex items-center justify-center h-32 text-muted-foreground text-sm">
                                            No surrogate data
                                        </div>
                                    )}
                                </div>

                                {/* Intended Parents Column - 35% */}
                                <div className="border rounded-lg p-4 overflow-y-auto">
                                    <div className="flex items-center gap-2 mb-3">
                                        <UsersIcon className="size-4 text-green-500" />
                                        <h2 className="text-sm font-semibold text-green-500">Intended Parents</h2>
                                    </div>

                                    {ipLoading ? (
                                        <div className="flex items-center justify-center h-32">
                                            <Loader2Icon className="size-5 animate-spin text-muted-foreground" />
                                        </div>
                                    ) : ipData ? (
                                        <div className="space-y-3">
                                            {/* Profile Header */}
                                            <div className="flex items-start gap-3">
                                                <Avatar className="h-10 w-10">
                                                    <AvatarFallback className="bg-green-500/10 text-green-500 text-sm">
                                                        {(ipData.full_name || "IP").charAt(0).toUpperCase()}
                                                    </AvatarFallback>
                                                </Avatar>
                                                <div className="flex-1 min-w-0">
                                                    <h3 className="text-base font-semibold truncate">{ipData.full_name}</h3>
                                                    <Badge variant="secondary" className="text-xs px-1.5 py-0 mt-0.5">{ipData.status}</Badge>
                                                </div>
                                            </div>

                                            <Separator />

                                            {/* Contact Info - Compact */}
                                            <div className="space-y-2 text-sm">
                                                <div className="flex items-center gap-2">
                                                    <MailIcon className="size-3.5 text-muted-foreground flex-shrink-0" />
                                                    <span className="truncate">{ipData.email || "—"}</span>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <PhoneIcon className="size-3.5 text-muted-foreground flex-shrink-0" />
                                                    <span>{ipData.phone || "—"}</span>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <MapPinIcon className="size-3.5 text-muted-foreground flex-shrink-0" />
                                                    <span>{ipData.state || "—"}</span>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <DollarSignIcon className="size-3.5 text-muted-foreground flex-shrink-0" />
                                                    <span>
                                                        {ipData.budget
                                                            ? new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(ipData.budget)
                                                            : "—"}
                                                    </span>
                                                </div>
                                            </div>

                                            {ipData.notes_internal && (
                                                <>
                                                    <Separator />
                                                    <div>
                                                        <p className="text-xs text-muted-foreground mb-1">Notes</p>
                                                        <p className="text-xs line-clamp-2">{ipData.notes_internal}</p>
                                                    </div>
                                                </>
                                            )}

                                            <Link href={`/intended-parents/${ipData.id}`}>
                                                <Button variant="outline" size="sm" className="w-full text-xs h-7">View Full Profile</Button>
                                            </Link>
                                        </div>
                                    ) : (
                                        <div className="flex items-center justify-center h-32 text-muted-foreground text-sm">
                                            No intended parent data
                                        </div>
                                    )}
                                </div>

                                {/* Notes/Files/Tasks/Activity Column - 30% */}
                                <div className="border rounded-lg flex flex-col overflow-hidden">
                                    {/* Source Filter - above tabs */}
                                    <div className="flex items-center gap-2 px-3 py-2 border-b bg-muted/30">
                                        <Select
                                            value={sourceFilter}
                                            onValueChange={(value) => {
                                                if (isSourceFilter(value)) {
                                                    handleSourceFilterChange(value)
                                                }
                                            }}
                                        >
                                            <SelectTrigger className="w-[160px] h-9 text-sm">
                                                <SelectValue placeholder="All Source">
                                                    {(value: string | null) =>
                                                        sourceLabel(isSourceFilter(value) ? value : null)
                                                    }
                                                </SelectValue>
                                            </SelectTrigger>
                                            <SelectContent>
                                                {SOURCE_OPTIONS.map((opt) => (
                                                    <SelectItem key={opt.value} value={opt.value}>
                                                        {opt.label}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    {/* Tab Buttons */}
                                    <div className="flex border-b p-1.5 gap-0.5 flex-shrink-0">
                                        <Button
                                            variant={activeTab === "notes" ? "secondary" : "ghost"}
                                            size="sm"
                                            className="h-7 text-sm px-2"
                                            onClick={() => handleTabChange("notes")}
                                        >
                                            <StickyNoteIcon className="size-3.5 mr-1" />
                                            Notes
                                        </Button>
                                        <Button
                                            variant={activeTab === "files" ? "secondary" : "ghost"}
                                            size="sm"
                                            className="h-7 text-sm px-2"
                                            onClick={() => handleTabChange("files")}
                                        >
                                            <FolderIcon className="size-3.5 mr-1" />
                                            Files
                                        </Button>
                                        <Button
                                            variant={activeTab === "tasks" ? "secondary" : "ghost"}
                                            size="sm"
                                            className="h-7 text-sm px-2"
                                            onClick={() => handleTabChange("tasks")}
                                        >
                                            <CheckSquareIcon className="size-3.5 mr-1" />
                                            Tasks
                                        </Button>
                                        <Button
                                            variant={activeTab === "activity" ? "secondary" : "ghost"}
                                            size="sm"
                                            className="h-7 text-sm px-2"
                                            onClick={() => handleTabChange("activity")}
                                        >
                                            <HistoryIcon className="size-3.5 mr-1" />
                                            Activity
                                        </Button>
                                    </div>

                                    {/* Tab Content */}
                                    <div className="flex-1 p-3 overflow-y-auto">
                                        {activeTab === "notes" && (
                                            <div className="space-y-2">
                                                {/* Add Note Button */}
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    className="w-full h-8 text-xs mb-3"
                                                    onClick={() => setAddNoteDialogOpen(true)}
                                                >
                                                    <StickyNoteIcon className="size-3.5 mr-1.5" />
                                                    Add Note
                                                </Button>
                                                {filteredNotes.length > 0 ? (
                                                    <div className="space-y-2">
                                                        {filteredNotes.map((note) => (
                                                            <div
                                                                key={note.id}
                                                                className="p-3 rounded-lg border border-border bg-card hover:bg-accent/30 transition-colors"
                                                            >
                                                                <div className="flex items-center gap-1.5 mb-2">
                                                                    <Badge
                                                                        variant="outline"
                                                                        className={`text-[10px] px-1.5 py-0 ${note.source === 'case' ? 'border-green-500/50 text-green-600 bg-green-500/5' :
                                                                            note.source === 'ip' ? 'border-blue-500/50 text-blue-600 bg-blue-500/5' :
                                                                                'border-purple-500/50 text-purple-600 bg-purple-500/5'
                                                                            }`}
                                                                    >
                                                                        {note.source === 'case' ? 'Case' :
                                                                            note.source === 'ip' ? 'IP' : 'Match'}
                                                                    </Badge>
                                                                    {note.author_name && (
                                                                        <span className="text-xs text-muted-foreground">by {note.author_name}</span>
                                                                    )}
                                                                </div>
                                                                <div
                                                                    className="text-sm prose prose-sm max-w-none dark:prose-invert whitespace-pre-wrap leading-relaxed"
                                                                    dangerouslySetInnerHTML={{ __html: note.content }}
                                                                />
                                                                <p className="text-xs text-muted-foreground mt-2">
                                                                    {formatDateTime(note.created_at)}
                                                                </p>
                                                            </div>
                                                        ))}
                                                    </div>
                                                ) : (
                                                    <div className="flex flex-col items-center justify-center py-8 text-center">
                                                        <StickyNoteIcon className="size-8 text-muted-foreground/40 mb-2" />
                                                        <p className="text-sm text-muted-foreground">No notes yet</p>
                                                    </div>
                                                )}
                                            </div>
                                        )}

                                        {activeTab === "files" && (
                                            <div className="space-y-2">
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    className="w-full h-8 text-xs mb-3"
                                                    onClick={() => setUploadFileDialogOpen(true)}
                                                >
                                                    <UploadIcon className="size-3.5 mr-1.5" />
                                                    Upload File
                                                </Button>
                                                {filteredFiles.length > 0 ? (
                                                    filteredFiles.map((file) => {
                                                        const deletableSource = isDeletableSource(file.source)
                                                            ? file.source
                                                            : null
                                                        return (
                                                            <div key={file.id} className="p-2 rounded bg-muted/30 flex items-center gap-2">
                                                                <FolderIcon className="size-4 text-muted-foreground flex-shrink-0" />
                                                                <div className="flex-1 min-w-0">
                                                                    <div className="flex items-center gap-1 mb-0.5">
                                                                        <Badge
                                                                            variant="outline"
                                                                            className={`text-[10px] px-1 py-0 ${file.source === 'case' ? 'border-green-500 text-green-600' :
                                                                                file.source === 'ip' ? 'border-blue-500 text-blue-600' :
                                                                                    'border-purple-500 text-purple-600'
                                                                                }`}
                                                                        >
                                                                            {file.source === 'case' ? 'Case' :
                                                                                file.source === 'ip' ? 'IP' : 'Match'}
                                                                        </Badge>
                                                                    </div>
                                                                    <p className="text-sm font-medium truncate">{file.filename}</p>
                                                                    <p className="text-xs text-muted-foreground">
                                                                        {(file.file_size / 1024).toFixed(1)} KB • {formatDateTime(file.created_at)}
                                                                    </p>
                                                                </div>
                                                                <Button
                                                                    variant="ghost"
                                                                    size="sm"
                                                                    className="h-7 w-7 p-0 text-muted-foreground hover:text-primary"
                                                                    onClick={() => downloadAttachmentMutation.mutate(file.id)}
                                                                    disabled={downloadAttachmentMutation.isPending}
                                                                    title="Download file"
                                                                >
                                                                    <DownloadIcon className="size-4" />
                                                                </Button>
                                                                {deletableSource && (
                                                                    <Button
                                                                        variant="ghost"
                                                                        size="sm"
                                                                        className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                                                                        onClick={() => handleDeleteFile(file.id, deletableSource)}
                                                                        disabled={deleteAttachmentMutation.isPending}
                                                                        title="Delete file"
                                                                    >
                                                                        <TrashIcon className="size-4" />
                                                                    </Button>
                                                                )}
                                                            </div>
                                                        )
                                                    })
                                                ) : (
                                                    <div className="text-center py-4">
                                                        <FolderIcon className="mx-auto h-6 w-6 text-muted-foreground mb-1" />
                                                        <p className="text-sm text-muted-foreground">
                                                            No files yet
                                                        </p>
                                                    </div>
                                                )}
                                            </div>
                                        )}

                                        {activeTab === "tasks" && (
                                            <div className="space-y-2">
                                                {filteredTasks.length > 0 ? (
                                                    filteredTasks.map((task) => (
                                                        <div key={task.id} className="p-2 rounded bg-muted/30 flex items-center gap-2">
                                                            <CheckSquareIcon className={`size-4 flex-shrink-0 ${task.is_completed ? 'text-green-500' : 'text-muted-foreground'}`} />
                                                            <div className="flex-1 min-w-0">
                                                                <div className="flex items-center gap-1 mb-0.5">
                                                                    <Badge
                                                                        variant="outline"
                                                                        className={`text-[10px] px-1 py-0 ${task.source === 'case' ? 'border-green-500 text-green-600' :
                                                                            task.source === 'ip' ? 'border-blue-500 text-blue-600' :
                                                                                'border-purple-500 text-purple-600'
                                                                            }`}
                                                                    >
                                                                        {task.source === 'case' ? 'Case' :
                                                                            task.source === 'ip' ? 'IP' : 'Match'}
                                                                    </Badge>
                                                                    {task.is_completed && (
                                                                        <Badge variant="secondary" className="text-[10px] px-1 py-0">Done</Badge>
                                                                    )}
                                                                </div>
                                                                <p className={`text-sm font-medium truncate ${task.is_completed ? 'line-through text-muted-foreground' : ''}`}>
                                                                    {task.title}
                                                                </p>
                                                                {task.due_date && (
                                                                    <p className="text-xs text-muted-foreground">
                                                                        Due: {formatDate(task.due_date)}
                                                                    </p>
                                                                )}
                                                            </div>
                                                        </div>
                                                    ))
                                                ) : (
                                                    <div className="text-center py-4">
                                                        <CheckSquareIcon className="mx-auto h-6 w-6 text-muted-foreground mb-1" />
                                                        <p className="text-sm text-muted-foreground">
                                                            No tasks yet
                                                        </p>
                                                    </div>
                                                )}
                                            </div>
                                        )}

                                        {activeTab === "activity" && (
                                            <div className="space-y-2">
                                                {filteredActivity.length > 0 ? (
                                                    filteredActivity.map((activity) => (
                                                        <div key={activity.id} className="flex gap-2">
                                                            <div className={`h-2 w-2 rounded-full mt-1.5 flex-shrink-0 ${activity.source === 'case' ? 'bg-green-500' :
                                                                activity.source === 'ip' ? 'bg-blue-500' :
                                                                    'bg-purple-500'
                                                                }`}></div>
                                                            <div className="flex-1 min-w-0">
                                                                <div className="flex items-center gap-1 mb-0.5">
                                                                    <Badge
                                                                        variant="outline"
                                                                        className={`text-[10px] px-1 py-0 ${activity.source === 'case' ? 'border-green-500 text-green-600' :
                                                                            activity.source === 'ip' ? 'border-blue-500 text-blue-600' :
                                                                                'border-purple-500 text-purple-600'
                                                                            }`}
                                                                    >
                                                                        {activity.source === 'case' ? 'Case' :
                                                                            activity.source === 'ip' ? 'IP' : 'Match'}
                                                                    </Badge>
                                                                </div>
                                                                <p className="text-sm font-medium">{activity.event_type}</p>
                                                                <p className="text-xs text-muted-foreground">{activity.description}</p>
                                                                <p className="text-xs text-muted-foreground">
                                                                    {formatDateTime(activity.created_at)}
                                                                    {activity.actor_name && <span className="ml-1">by {activity.actor_name}</span>}
                                                                </p>
                                                            </div>
                                                        </div>
                                                    ))
                                                ) : (
                                                    <div className="text-center py-4">
                                                        <HistoryIcon className="mx-auto h-6 w-6 text-muted-foreground mb-1" />
                                                        <p className="text-sm text-muted-foreground">
                                                            No activity yet
                                                        </p>
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </TabsContent>

                        <TabsContent value="calendar" className="h-[calc(100vh-145px)]">
                            {match && (
                                <MatchTasksCalendar
                                    caseId={match.case_id}
                                    ipId={match.intended_parent_id}
                                    onAddTask={() => setAddTaskDialogOpen(true)}
                                />
                            )}
                        </TabsContent>
                    </Tabs>
                </div>
            </div>

            {/* Reject Match Dialog */}
            <RejectMatchDialog
                open={rejectDialogOpen}
                onOpenChange={setRejectDialogOpen}
                onConfirm={handleRejectMatch}
                isPending={rejectMatchMutation.isPending}
            />

            {/* Add Note Dialog */}
            <AddNoteDialog
                open={addNoteDialogOpen}
                onOpenChange={setAddNoteDialogOpen}
                onSubmit={handleAddNote}
                isPending={createNoteMutation.isPending || createIPNoteMutation.isPending}
                caseName={caseData?.full_name || "Surrogate Case"}
                ipName={ipData?.full_name || "Intended Parent"}
            />

            {/* Upload File Dialog */}
            <UploadFileDialog
                open={uploadFileDialogOpen}
                onOpenChange={setUploadFileDialogOpen}
                onUpload={handleUploadFile}
                isPending={uploadAttachmentMutation.isPending || uploadIPAttachmentMutation.isPending}
                caseName={caseData?.full_name || "Surrogate Case"}
                ipName={ipData?.full_name || "Intended Parent"}
            />

            {/* Add Task Dialog */}
            <AddTaskDialog
                open={addTaskDialogOpen}
                onOpenChange={setAddTaskDialogOpen}
                onSubmit={handleAddTask}
                isPending={createTaskMutation.isPending}
                caseName={caseData?.full_name || "Surrogate Case"}
                ipName={ipData?.full_name || "Intended Parent"}
            />

            {/* Schedule Parser Dialog (mount only when open to avoid unnecessary hooks in tests) */}
            {showScheduleParser && (
                <ScheduleParserDialog
                    open={showScheduleParser}
                    onOpenChange={setShowScheduleParser}
                    entityType="match"
                    entityId={matchId}
                    entityName={matchName}
                />
            )}
        </>
    )
}
