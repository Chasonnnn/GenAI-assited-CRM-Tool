"use client"

import { useState } from "react"
import { useParams } from "next/navigation"
import Link from "@/components/app-link"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Separator } from "@/components/ui/separator"
import {
    MailIcon,
    PhoneIcon,
    MapPinIcon,
    CakeIcon,
    DollarSignIcon,
    Loader2Icon,
    ArrowLeftIcon,
    UserIcon,
    UsersIcon,
    CalendarPlusIcon,
} from "lucide-react"
import { useMatch, matchKeys, useAcceptMatch, useRejectMatch, useCancelMatch } from "@/lib/hooks/use-matches"
import { NotFoundState } from "@/components/not-found-state"
import { MatchTasksCalendar } from "@/components/matches/MatchTasksCalendar"
import { RejectMatchDialog } from "@/components/matches/RejectMatchDialog"
import { CancelMatchDialog } from "@/components/matches/CancelMatchDialog"
import { AddNoteDialog } from "@/components/matches/AddNoteDialog"
import { UploadFileDialog } from "@/components/matches/UploadFileDialog"
import { AddTaskDialog, type TaskFormData } from "@/components/matches/AddTaskDialog"
import { useSurrogate, useSurrogateActivity, surrogateKeys } from "@/lib/hooks/use-surrogates"
import { useNotes, useCreateNote } from "@/lib/hooks/use-notes"
import { useIntendedParent, useIntendedParentNotes, useIntendedParentHistory, intendedParentKeys, useCreateIntendedParentNote } from "@/lib/hooks/use-intended-parents"
import { useTasks, useCreateTask, taskKeys } from "@/lib/hooks/use-tasks"
import { useAttachments, useIPAttachments, useUploadAttachment, useUploadIPAttachment, useDeleteAttachment, useDownloadAttachment } from "@/lib/hooks/use-attachments"
import { useAuth } from "@/lib/auth-context"
import { useQueryClient } from "@tanstack/react-query"
import { ScheduleParserDialog } from "@/components/ai/ScheduleParserDialog"
import { useSetAIContext } from "@/lib/context/ai-context"
import { parseDateInput } from "@/lib/utils/date"
import { formatRace } from "@/lib/formatters"
import { formatHeight } from "@/components/surrogates/detail/surrogate-detail-utils"
import { MatchDetailOverviewTabs } from "./components/MatchDetailOverviewTabs"
import { useMatchDetailTabState } from "./hooks/useMatchDetailTabState"
import { useMatchDetailTabData } from "./hooks/useMatchDetailTabData"

const STATUS_LABELS: Record<string, string> = {
    proposed: "Proposed",
    reviewing: "Reviewing",
    accepted: "Accepted",
    cancel_pending: "Cancellation Pending",
    rejected: "Rejected",
    cancelled: "Cancelled",
}

const STATUS_COLORS: Record<string, string> = {
    proposed: "bg-yellow-500/10 text-yellow-500 border-yellow-500/20",
    reviewing: "bg-blue-500/10 text-blue-500 border-blue-500/20",
    accepted: "bg-green-500/10 text-green-500 border-green-500/20",
    cancel_pending: "bg-amber-500/10 text-amber-600 border-amber-500/20",
    rejected: "bg-red-500/10 text-red-500 border-red-500/20",
    cancelled: "bg-gray-500/10 text-gray-500 border-gray-500/20",
}

export default function MatchDetailPage() {
    const params = useParams<{ id: string }>()
    const matchId = params.id

    const { activeTab, sourceFilter, handleTabChange, handleSourceFilterChange } =
        useMatchDetailTabState(matchId)
    const [rejectDialogOpen, setRejectDialogOpen] = useState(false)
    const [cancelDialogOpen, setCancelDialogOpen] = useState(false)
    const [addNoteDialogOpen, setAddNoteDialogOpen] = useState(false)
    const [uploadFileDialogOpen, setUploadFileDialogOpen] = useState(false)
    const [addTaskDialogOpen, setAddTaskDialogOpen] = useState(false)
    const [showScheduleParser, setShowScheduleParser] = useState(false)
    const { user } = useAuth()
    const queryClient = useQueryClient()

    const { data: match, isLoading: matchLoading } = useMatch(matchId)
    const acceptMatchMutation = useAcceptMatch()
    const rejectMatchMutation = useRejectMatch()
    const cancelMatchMutation = useCancelMatch()
    const createNoteMutation = useCreateNote()
    const createIPNoteMutation = useCreateIntendedParentNote()
    const uploadAttachmentMutation = useUploadAttachment()
    const uploadIPAttachmentMutation = useUploadIPAttachment()
    const deleteAttachmentMutation = useDeleteAttachment()
    const downloadAttachmentMutation = useDownloadAttachment()
    const createTaskMutation = useCreateTask()

    // Set AI context for this page.
    // NOTE: The chat API currently supports surrogate/task/global. For match pages, we attach AI to the surrogate.
    const matchName = match ? `${match.surrogate_name} & ${match.ip_name}` : ""
    useSetAIContext(match?.surrogate_id ? { entityType: "surrogate", entityId: match.surrogate_id, entityName: matchName } : null)

    // Fetch full profile data for both sides
    const { data: surrogateData, isLoading: surrogateLoading } = useSurrogate(match?.surrogate_id || "")
    const { data: ipData, isLoading: ipLoading } = useIntendedParent(match?.intended_parent_id || "")

    // Fetch notes from all sources
    const { data: surrogateNotes = [] } = useNotes(match?.surrogate_id || "")
    const { data: ipNotes = [] } = useIntendedParentNotes(match?.intended_parent_id || "")

    // Fetch files/attachments from Surrogate and IP
    const { data: surrogateFiles = [] } = useAttachments(match?.surrogate_id || null)
    const { data: ipFiles = [] } = useIPAttachments(match?.intended_parent_id || null)

    // Fetch tasks from Surrogate and IP
    const { data: surrogateTasks } = useTasks(
        match?.surrogate_id ? { surrogate_id: match.surrogate_id, exclude_approvals: true } : { exclude_approvals: true },
        { enabled: !!match?.surrogate_id }
    )
    const { data: ipTasks } = useTasks(
        match?.intended_parent_id
            ? { intended_parent_id: match.intended_parent_id, exclude_approvals: true }
            : { exclude_approvals: true },
        { enabled: !!match?.intended_parent_id }
    )

    // Fetch activity from Surrogate and IP
    const { data: surrogateActivity } = useSurrogateActivity(match?.surrogate_id || "", 1, 50)
    const { data: ipHistory } = useIntendedParentHistory(match?.intended_parent_id || null)

    const { filteredNotes, filteredFiles, filteredTasks, filteredActivity } = useMatchDetailTabData({
        sourceFilter,
        surrogateNotes,
        intendedParentNotes: ipNotes,
        surrogateFiles,
        intendedParentFiles: ipFiles,
        surrogateTasks,
        intendedParentTasks: ipTasks,
        surrogateActivity,
        intendedParentHistory: ipHistory,
        match,
    })

    // Check if user can change surrogate status (case_manager+)
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

    const formatDateTime = (dateStr: string | null | undefined) => {
        if (!dateStr) return "—"
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

    // Handle Accept match
    const handleAcceptMatch = async () => {
        await acceptMatchMutation.mutateAsync({ matchId })
        // Invalidate all related queries to refresh UI
        if (match?.surrogate_id) {
            queryClient.invalidateQueries({ queryKey: surrogateKeys.detail(match.surrogate_id) })
            queryClient.invalidateQueries({ queryKey: surrogateKeys.lists() })
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
        if (match?.surrogate_id) {
            queryClient.invalidateQueries({ queryKey: surrogateKeys.detail(match.surrogate_id) })
        }
        if (match?.intended_parent_id) {
            queryClient.invalidateQueries({ queryKey: intendedParentKeys.detail(match.intended_parent_id) })
        }
        queryClient.invalidateQueries({ queryKey: matchKeys.detail(matchId) })
        queryClient.invalidateQueries({ queryKey: matchKeys.lists() })
    }

    const handleCancelMatch = async (reason?: string) => {
        await cancelMatchMutation.mutateAsync({ matchId, data: reason ? { reason } : {} })
        queryClient.invalidateQueries({ queryKey: matchKeys.detail(matchId) })
        queryClient.invalidateQueries({ queryKey: matchKeys.lists() })
    }

    // Handle Add Note
    const handleAddNote = async (target: "surrogate" | "ip", content: string) => {
        try {
            if (target === "surrogate" && match?.surrogate_id) {
                await createNoteMutation.mutateAsync({ surrogateId: match.surrogate_id, body: content })
            } else if (target === "ip" && match?.intended_parent_id) {
                await createIPNoteMutation.mutateAsync({ id: match.intended_parent_id, data: { content } })
            }
            toast.success("Note added successfully")
        } catch {
            toast.error("Failed to add note")
        }
    }

    // Handle File Upload
    const handleUploadFile = async (target: "surrogate" | "ip", file: File) => {
        try {
            if (target === "surrogate" && match?.surrogate_id) {
                await uploadAttachmentMutation.mutateAsync({ surrogateId: match.surrogate_id, file })
            } else if (target === "ip" && match?.intended_parent_id) {
                await uploadIPAttachmentMutation.mutateAsync({ ipId: match.intended_parent_id, file })
            }
            toast.success("File uploaded successfully")
        } catch {
            toast.error("Failed to upload file")
        }
    }

    // Handle Delete File
    const handleDeleteFile = async (attachmentId: string, source: "surrogate" | "ip") => {
        if (!confirm("Are you sure you want to delete this file?")) return
        try {
            const surrogateId = source === "surrogate" ? match?.surrogate_id : undefined
            await deleteAttachmentMutation.mutateAsync({ attachmentId, surrogateId: surrogateId || "" })
            // Invalidate the appropriate query based on source
            if (source === "surrogate" && match?.surrogate_id) {
                queryClient.invalidateQueries({ queryKey: ["attachments", match.surrogate_id] })
            } else if (source === "ip" && match?.intended_parent_id) {
                queryClient.invalidateQueries({ queryKey: ["ip-attachments", match.intended_parent_id] })
            }
            toast.success("File deleted successfully")
        } catch {
            toast.error("Failed to delete file")
        }
    }

    // Handle Add Task
    const handleAddTask = async (target: "surrogate" | "ip", data: TaskFormData) => {
        try {
            if (target === "surrogate" && match?.surrogate_id) {
                await createTaskMutation.mutateAsync({
                    title: data.title,
                    task_type: data.task_type,
                    surrogate_id: match.surrogate_id,
                    ...(data.description ? { description: data.description } : {}),
                    ...(data.due_date ? { due_date: data.due_date } : {}),
                })
            } else if (target === "ip" && match?.intended_parent_id) {
                await createTaskMutation.mutateAsync({
                    title: data.title,
                    task_type: data.task_type,
                    intended_parent_id: match.intended_parent_id,
                    ...(data.description ? { description: data.description } : {}),
                    ...(data.due_date ? { due_date: data.due_date } : {}),
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
            <NotFoundState
                title="Match not found"
                backUrl="/intended-parents/matches"
            />
        )
    }

    return (
        <>
            <div className="flex min-h-screen flex-col">
                {/* Page Header */}
                <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                    <div className="flex h-14 items-center gap-4 px-6">
                        <Button
                            render={<Link href="/intended-parents/matches" />}
                            variant="ghost"
                            size="sm"
                            className="h-7 text-xs"
                        >
                            <ArrowLeftIcon className="mr-1 size-3" />
                            Matches
                        </Button>
                        <div className="flex-1 flex items-center gap-2">
                            <h1 className="text-xl font-semibold">
                                {match.surrogate_name || "Surrogate"} ↔ {match.ip_name || "Intended Parents"}
                            </h1>
                            <span className="text-sm text-muted-foreground">
                                {match.match_number ? `Match #${match.match_number}` : "—"}
                            </span>
                        {/* Surrogate Stage Badge */}
                            {match.surrogate_stage_label && (
                                <Badge variant="secondary" className="text-xs">
                                    {match.surrogate_stage_label}
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
                        {canChangeStatus && match.status === 'accepted' && (
                            <Button
                                variant="destructive"
                                size="sm"
                                className="h-7 text-xs"
                                onClick={() => setCancelDialogOpen(true)}
                                disabled={cancelMatchMutation.isPending}
                            >
                                {cancelMatchMutation.isPending ? 'Requesting...' : 'Cancel Match'}
                            </Button>
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
                            <div className="grid h-full gap-4 grid-cols-[minmax(0,35fr)_minmax(0,35fr)_minmax(0,30fr)]">
                                {/* Surrogate Column - 35% */}
                                <div className="min-w-0 border rounded-lg p-4 overflow-y-auto">
                                    <div className="flex items-center gap-2 mb-3">
                                        <UserIcon className="size-4 text-purple-500" />
                                        <h2 className="text-sm font-semibold text-purple-500">Surrogate</h2>
                                    </div>

                                    {surrogateLoading ? (
                                        <div className="flex items-center justify-center h-32">
                                            <Loader2Icon className="size-5 animate-spin text-muted-foreground" />
                                        </div>
                                    ) : surrogateData ? (
                                        <div className="space-y-3">
                                            {/* Profile Header */}
                                            <div className="flex items-start gap-3">
                                                <Avatar className="h-10 w-10">
                                                    <AvatarFallback className="bg-purple-500/10 text-purple-500 text-sm">
                                                        {(surrogateData.full_name || "S").charAt(0).toUpperCase()}
                                                    </AvatarFallback>
                                                </Avatar>
                                                <div className="flex-1 min-w-0">
                                                    <h3 className="text-base font-semibold truncate">
                                                        <Link
                                                            href={`/surrogates/${surrogateData.id}`}
                                                            className="hover:underline underline-offset-4"
                                                        >
                                                            {surrogateData.full_name || "Surrogate"}
                                                        </Link>
                                                    </h3>
                                                    <div className="flex items-center gap-1 mt-0.5">
                                                        <Badge variant="outline" className="text-xs px-1.5 py-0">#{surrogateData.surrogate_number}</Badge>
                                                        <Badge variant="secondary" className="text-xs px-1.5 py-0">{surrogateData.status_label}</Badge>
                                                    </div>
                                                </div>
                                            </div>

                                            <Separator />

                                            {/* Contact Info - Compact */}
                                            <div className="space-y-2 text-sm">
                                                <div className="flex items-center gap-2">
                                                    <MailIcon className="size-3.5 text-muted-foreground flex-shrink-0" />
                                                    <span className="truncate">{surrogateData.email || "—"}</span>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <PhoneIcon className="size-3.5 text-muted-foreground flex-shrink-0" />
                                                    <span>{surrogateData.phone || "—"}</span>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <MapPinIcon className="size-3.5 text-muted-foreground flex-shrink-0" />
                                                    <span>{surrogateData.state || "—"}</span>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <CakeIcon className="size-3.5 text-muted-foreground flex-shrink-0" />
                                                    <span>{formatDate(surrogateData.date_of_birth)}</span>
                                                </div>
                                            </div>

                                            <Separator />

                                            {/* Demographics - Compact */}
                                            <div>
                                                <p className="text-xs text-muted-foreground mb-1">Demographics</p>
                                                <div className="grid grid-cols-3 gap-1 text-xs">
                                                    <div><span className="text-muted-foreground">Race:</span> {formatRace(surrogateData.race) || "—"}</div>
                                                    <div><span className="text-muted-foreground">Ht:</span> {formatHeight(surrogateData.height_ft)}</div>
                                                    <div><span className="text-muted-foreground">Wt:</span> {surrogateData.weight_lb ? `${surrogateData.weight_lb}lb` : "—"}</div>
                                                </div>
                                            </div>

                                            <Button
                                                render={<Link href={`/surrogates/${surrogateData.id}`} />}
                                                variant="outline"
                                                size="sm"
                                                className="w-full text-xs h-7"
                                            >
                                                View Full Profile
                                            </Button>
                                        </div>
                                    ) : (
                                        <div className="flex items-center justify-center h-32 text-muted-foreground text-sm">
                                            No surrogate data
                                        </div>
                                    )}
                                </div>

                                {/* Intended Parents Column - 35% */}
                                <div className="min-w-0 border rounded-lg p-4 overflow-y-auto">
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
                                                    <h3 className="text-base font-semibold truncate">
                                                        <Link
                                                            href={`/intended-parents/${ipData.id}`}
                                                            className="hover:underline underline-offset-4"
                                                        >
                                                            {ipData.full_name || "Intended Parent"}
                                                        </Link>
                                                    </h3>
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

                                            <Button
                                                render={<Link href={`/intended-parents/${ipData.id}`} />}
                                                variant="outline"
                                                size="sm"
                                                className="w-full text-xs h-7"
                                            >
                                                View Full Profile
                                            </Button>
                                        </div>
                                    ) : (
                                        <div className="flex items-center justify-center h-32 text-muted-foreground text-sm">
                                            No intended parent data
                                        </div>
                                    )}
                                </div>

                                {/* Notes/Files/Tasks/Activity Column - 30% */}
                                <MatchDetailOverviewTabs
                                    activeTab={activeTab}
                                    sourceFilter={sourceFilter}
                                    filteredNotes={filteredNotes}
                                    filteredFiles={filteredFiles}
                                    filteredTasks={filteredTasks}
                                    filteredActivity={filteredActivity}
                                    onTabChange={handleTabChange}
                                    onSourceFilterChange={handleSourceFilterChange}
                                    onAddNote={() => setAddNoteDialogOpen(true)}
                                    onUploadFile={() => setUploadFileDialogOpen(true)}
                                    onDownloadFile={(attachmentId) => downloadAttachmentMutation.mutate(attachmentId)}
                                    onDeleteFile={handleDeleteFile}
                                    isDownloadPending={downloadAttachmentMutation.isPending}
                                    isDeletePending={deleteAttachmentMutation.isPending}
                                    formatDate={formatDate}
                                    formatDateTime={formatDateTime}
                                />
                            </div>
                        </TabsContent>

                        <TabsContent value="calendar" className="h-[calc(100vh-145px)]">
                            {match && (
                                <MatchTasksCalendar
                                    surrogateId={match.surrogate_id}
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

            <CancelMatchDialog
                open={cancelDialogOpen}
                onOpenChange={setCancelDialogOpen}
                onConfirm={handleCancelMatch}
                isPending={cancelMatchMutation.isPending}
            />

            {/* Add Note Dialog */}
            <AddNoteDialog
                open={addNoteDialogOpen}
                onOpenChange={setAddNoteDialogOpen}
                onSubmit={handleAddNote}
                isPending={createNoteMutation.isPending || createIPNoteMutation.isPending}
                surrogateName={surrogateData?.full_name || "Surrogate"}
                ipName={ipData?.full_name || "Intended Parent"}
            />

            {/* Upload File Dialog */}
            <UploadFileDialog
                open={uploadFileDialogOpen}
                onOpenChange={setUploadFileDialogOpen}
                onUpload={handleUploadFile}
                isPending={uploadAttachmentMutation.isPending || uploadIPAttachmentMutation.isPending}
                surrogateName={surrogateData?.full_name || "Surrogate"}
                ipName={ipData?.full_name || "Intended Parent"}
            />

            {/* Add Task Dialog */}
            <AddTaskDialog
                open={addTaskDialogOpen}
                onOpenChange={setAddTaskDialogOpen}
                onSubmit={handleAddTask}
                isPending={createTaskMutation.isPending}
                surrogateName={surrogateData?.full_name || "Surrogate"}
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
