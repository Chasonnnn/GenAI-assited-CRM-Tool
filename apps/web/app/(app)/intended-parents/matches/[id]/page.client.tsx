"use client"

import { useState, type ComponentProps } from "react"
import { useParams } from "next/navigation"
import Link from "@/components/app-link"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Separator } from "@/components/ui/separator"
import { PermissionDeniedState } from "@/components/error-state"
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
import type { MatchRead } from "@/lib/api/matches"
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
import { isPermissionError } from "@/lib/error-utils"

const USD_WHOLE_DOLLAR_FORMATTER = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
})
import { formatRace } from "@/lib/formatters"
import { formatHeight } from "@/components/surrogates/detail/surrogate-detail-utils"
import {
    getMatchStatusBadgeClassName,
    getMatchStatusLabel,
} from "@/lib/match-status-definitions"
import { MatchDetailOverviewTabs } from "./components/MatchDetailOverviewTabs"
import { useMatchDetailTabState, type SourceFilter } from "./hooks/useMatchDetailTabState"
import { useMatchDetailTabData } from "./hooks/useMatchDetailTabData"
import type { SurrogateRead } from "@/lib/types/surrogate"
import type { IntendedParent } from "@/lib/types/intended-parent"

function formatMatchDate(dateStr: string | null | undefined) {
    if (!dateStr) return "—"
    const parsed = parseDateInput(dateStr)
    if (Number.isNaN(parsed.getTime())) return "—"
    return parsed.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
    })
}

function formatMatchDateTime(dateStr: string | null | undefined) {
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

type MatchDetailOverviewTabsProps = ComponentProps<typeof MatchDetailOverviewTabs>

function MatchDetailHeader({
    match,
    canChangeStatus,
    acceptPending,
    rejectPending,
    cancelPending,
    onAcceptMatch,
    onRejectClick,
    onCancelClick,
}: {
    match: MatchRead
    canChangeStatus: boolean
    acceptPending: boolean
    rejectPending: boolean
    cancelPending: boolean
    onAcceptMatch: () => void
    onRejectClick: () => void
    onCancelClick: () => void
}) {
    return (
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
                    {match.surrogate_stage_label && (
                        <Badge variant="secondary" className="text-xs">
                            {match.surrogate_stage_label}
                        </Badge>
                    )}
                </div>
                <Badge className={getMatchStatusBadgeClassName(match.status)}>
                    {getMatchStatusLabel(match.status)}
                </Badge>
                {canChangeStatus && (match.status === "proposed" || match.status === "reviewing") && (
                    <>
                        <Button
                            variant="default"
                            size="sm"
                            className="h-7 text-xs bg-green-600 hover:bg-green-700"
                            onClick={onAcceptMatch}
                            disabled={acceptPending}
                        >
                            {acceptPending ? "Accepting..." : "Accept Match"}
                        </Button>
                        <Button
                            variant="destructive"
                            size="sm"
                            className="h-7 text-xs"
                            onClick={onRejectClick}
                            disabled={rejectPending}
                        >
                            {rejectPending ? "Rejecting..." : "Reject"}
                        </Button>
                    </>
                )}
                {canChangeStatus && match.status === "accepted" && (
                    <Button
                        variant="destructive"
                        size="sm"
                        className="h-7 text-xs"
                        onClick={onCancelClick}
                        disabled={cancelPending}
                    >
                        {cancelPending ? "Requesting..." : "Cancel Match"}
                    </Button>
                )}
            </div>
        </div>
    )
}

function MatchDetailMainTabs({
    userAiEnabled,
    surrogateId,
    intendedParentId,
    surrogateData,
    surrogateLoading,
    intendedParentData,
    intendedParentLoading,
    overviewTabsProps,
    onShowScheduleParser,
    onAddTask,
}: {
    userAiEnabled: boolean
    surrogateId: string
    intendedParentId: string
    surrogateData: SurrogateRead | undefined
    surrogateLoading: boolean
    intendedParentData: IntendedParent | undefined
    intendedParentLoading: boolean
    overviewTabsProps: MatchDetailOverviewTabsProps
    onShowScheduleParser: () => void
    onAddTask: () => void
}) {
    return (
        <div className="flex-1 p-4">
            <Tabs defaultValue="overview" className="w-full">
                <div className="flex items-center justify-between mb-3">
                    <TabsList>
                        <TabsTrigger value="overview">Overview</TabsTrigger>
                        <TabsTrigger value="calendar">Calendar</TabsTrigger>
                    </TabsList>
                    {userAiEnabled && (
                        <Button
                            variant="outline"
                            size="sm"
                            className="h-7 text-xs gap-1"
                            onClick={onShowScheduleParser}
                        >
                            <CalendarPlusIcon className="size-3" />
                            Parse Schedule
                        </Button>
                    )}
                </div>

                <TabsContent value="overview" className="h-[calc(100vh-145px)]">
                    <div className="grid h-full gap-4 grid-cols-[minmax(0,35fr)_minmax(0,35fr)_minmax(0,30fr)]">
                        <SurrogateProfileColumn
                            surrogateData={surrogateData}
                            isLoading={surrogateLoading}
                        />
                        <IntendedParentProfileColumn
                            intendedParentData={intendedParentData}
                            isLoading={intendedParentLoading}
                        />
                        <MatchDetailOverviewTabs {...overviewTabsProps} />
                    </div>
                </TabsContent>

                <TabsContent value="calendar" className="h-[calc(100vh-145px)]">
                    <MatchTasksCalendar
                        surrogateId={surrogateId}
                        ipId={intendedParentId}
                        onAddTask={onAddTask}
                    />
                </TabsContent>
            </Tabs>
        </div>
    )
}

function SurrogateProfileColumn({
    surrogateData,
    isLoading,
}: {
    surrogateData: SurrogateRead | undefined
    isLoading: boolean
}) {
    return (
        <div className="min-w-0 border rounded-lg p-4 overflow-y-auto">
            <div className="flex items-center gap-2 mb-3">
                <UserIcon className="size-4 text-purple-500" />
                <h2 className="text-sm font-semibold text-purple-500">Surrogate</h2>
            </div>

            {isLoading ? (
                <div className="flex items-center justify-center h-32">
                    <Loader2Icon className="size-5 animate-spin text-muted-foreground" />
                </div>
            ) : surrogateData ? (
                <div className="space-y-3">
                    <div className="flex items-start gap-3">
                        <Avatar className="size-10">
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
                            <span>{formatMatchDate(surrogateData.date_of_birth)}</span>
                        </div>
                    </div>

                    <Separator />

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
    )
}

function IntendedParentProfileColumn({
    intendedParentData,
    isLoading,
}: {
    intendedParentData: IntendedParent | undefined
    isLoading: boolean
}) {
    return (
        <div className="min-w-0 border rounded-lg p-4 overflow-y-auto">
            <div className="flex items-center gap-2 mb-3">
                <UsersIcon className="size-4 text-green-500" />
                <h2 className="text-sm font-semibold text-green-500">Intended Parents</h2>
            </div>

            {isLoading ? (
                <div className="flex items-center justify-center h-32">
                    <Loader2Icon className="size-5 animate-spin text-muted-foreground" />
                </div>
            ) : intendedParentData ? (
                <div className="space-y-3">
                    <div className="flex items-start gap-3">
                        <Avatar className="size-10">
                            <AvatarFallback className="bg-green-500/10 text-green-500 text-sm">
                                {(intendedParentData.full_name || "IP").charAt(0).toUpperCase()}
                            </AvatarFallback>
                        </Avatar>
                        <div className="flex-1 min-w-0">
                            <h3 className="text-base font-semibold truncate">
                                <Link
                                    href={`/intended-parents/${intendedParentData.id}`}
                                    className="hover:underline underline-offset-4"
                                >
                                    {intendedParentData.full_name || "Intended Parent"}
                                </Link>
                            </h3>
                            <Badge variant="secondary" className="text-xs px-1.5 py-0 mt-0.5">
                                {intendedParentData.status_label || intendedParentData.status || "—"}
                            </Badge>
                        </div>
                    </div>

                    <Separator />

                    <div className="space-y-2 text-sm">
                        <div className="flex items-center gap-2">
                            <MailIcon className="size-3.5 text-muted-foreground flex-shrink-0" />
                            <span className="truncate">{intendedParentData.email || "—"}</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <PhoneIcon className="size-3.5 text-muted-foreground flex-shrink-0" />
                            <span>{intendedParentData.phone || "—"}</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <MapPinIcon className="size-3.5 text-muted-foreground flex-shrink-0" />
                            <span>{intendedParentData.state || "—"}</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <DollarSignIcon className="size-3.5 text-muted-foreground flex-shrink-0" />
                            <span>
                                {intendedParentData.budget
                                    ? USD_WHOLE_DOLLAR_FORMATTER.format(intendedParentData.budget)
                                    : "—"}
                            </span>
                        </div>
                    </div>

                    {intendedParentData.notes_internal && (
                        <>
                            <Separator />
                            <div>
                                <p className="text-xs text-muted-foreground mb-1">Notes</p>
                                <p className="text-xs line-clamp-2">{intendedParentData.notes_internal}</p>
                            </div>
                        </>
                    )}

                    <Button
                        render={<Link href={`/intended-parents/${intendedParentData.id}`} />}
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
    )
}

function MatchDetailDialogs({
    rejectDialogOpen,
    cancelDialogOpen,
    addNoteDialogOpen,
    uploadFileDialogOpen,
    addTaskDialogOpen,
    showScheduleParser,
    matchId,
    matchName,
    surrogateName,
    intendedParentName,
    rejectPending,
    cancelPending,
    addNotePending,
    uploadFilePending,
    addTaskPending,
    onRejectOpenChange,
    onCancelOpenChange,
    onAddNoteOpenChange,
    onUploadFileOpenChange,
    onAddTaskOpenChange,
    onScheduleParserOpenChange,
    onReject,
    onCancel,
    onAddNote,
    onUploadFile,
    onAddTask,
}: {
    rejectDialogOpen: boolean
    cancelDialogOpen: boolean
    addNoteDialogOpen: boolean
    uploadFileDialogOpen: boolean
    addTaskDialogOpen: boolean
    showScheduleParser: boolean
    matchId: string
    matchName: string
    surrogateName: string
    intendedParentName: string
    rejectPending: boolean
    cancelPending: boolean
    addNotePending: boolean
    uploadFilePending: boolean
    addTaskPending: boolean
    onRejectOpenChange: (open: boolean) => void
    onCancelOpenChange: (open: boolean) => void
    onAddNoteOpenChange: (open: boolean) => void
    onUploadFileOpenChange: (open: boolean) => void
    onAddTaskOpenChange: (open: boolean) => void
    onScheduleParserOpenChange: (open: boolean) => void
    onReject: (reason: string) => Promise<void>
    onCancel: (reason?: string) => Promise<void>
    onAddNote: (target: "surrogate" | "ip", content: string) => Promise<void>
    onUploadFile: (target: "surrogate" | "ip", file: File) => Promise<void>
    onAddTask: (target: "match" | "surrogate" | "ip", data: TaskFormData) => Promise<void>
}) {
    return (
        <>
            <RejectMatchDialog
                open={rejectDialogOpen}
                onOpenChange={onRejectOpenChange}
                onConfirm={onReject}
                isPending={rejectPending}
            />

            <CancelMatchDialog
                open={cancelDialogOpen}
                onOpenChange={onCancelOpenChange}
                onConfirm={onCancel}
                isPending={cancelPending}
            />

            <AddNoteDialog
                open={addNoteDialogOpen}
                onOpenChange={onAddNoteOpenChange}
                onSubmit={onAddNote}
                isPending={addNotePending}
                surrogateName={surrogateName}
                ipName={intendedParentName}
            />

            <UploadFileDialog
                open={uploadFileDialogOpen}
                onOpenChange={onUploadFileOpenChange}
                onUpload={onUploadFile}
                isPending={uploadFilePending}
                surrogateName={surrogateName}
                ipName={intendedParentName}
            />

            <AddTaskDialog
                open={addTaskDialogOpen}
                onOpenChange={onAddTaskOpenChange}
                onSubmit={onAddTask}
                isPending={addTaskPending}
                surrogateName={surrogateName}
                ipName={intendedParentName}
            />

            {showScheduleParser && (
                <ScheduleParserDialog
                    open={showScheduleParser}
                    onOpenChange={onScheduleParserOpenChange}
                    entityType="match"
                    entityId={matchId}
                    entityName={matchName}
                />
            )}
        </>
    )
}

function useMatchDetailRelatedData(match: MatchRead | undefined, sourceFilter: SourceFilter) {
    const { data: surrogateData, isLoading: surrogateLoading } = useSurrogate(match?.surrogate_id || "")
    const { data: ipData, isLoading: ipLoading } = useIntendedParent(match?.intended_parent_id || "")

    const { data: surrogateNotes = [] } = useNotes(match?.surrogate_id || "")
    const { data: ipNotes = [] } = useIntendedParentNotes(match?.intended_parent_id || "")
    const { data: surrogateFiles = [] } = useAttachments(match?.surrogate_id || null)
    const { data: ipFiles = [] } = useIPAttachments(match?.intended_parent_id || null)
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

    return {
        surrogateData,
        surrogateLoading,
        ipData,
        ipLoading,
        filteredNotes,
        filteredFiles,
        filteredTasks,
        filteredActivity,
    }
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

    const {
        data: match,
        isLoading: matchLoading,
        isError: matchIsError,
        error: matchError,
        refetch: refetchMatch,
    } = useMatch(matchId)
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

    const {
        surrogateData,
        surrogateLoading,
        ipData,
        ipLoading,
        filteredNotes,
        filteredFiles,
        filteredTasks,
        filteredActivity,
    } = useMatchDetailRelatedData(match, sourceFilter)

    // Check if user can change surrogate status (case_manager+)
    const canChangeStatus = !!user?.role && ['case_manager', 'admin', 'developer'].includes(user.role)

    const invalidateMatchSourceQueries = (
        entityIds?: {
            surrogate_id?: string | null
            intended_parent_id?: string | null
        } | null,
    ) => {
        const surrogateId = entityIds?.surrogate_id ?? match?.surrogate_id
        const intendedParentId = entityIds?.intended_parent_id ?? match?.intended_parent_id

        if (surrogateId) {
            void queryClient.invalidateQueries({ queryKey: surrogateKeys.detail(surrogateId) })
            void queryClient.invalidateQueries({ queryKey: surrogateKeys.lists() })
            void queryClient.invalidateQueries({
                queryKey: [...surrogateKeys.detail(surrogateId), "activity"],
            })
            void queryClient.invalidateQueries({
                queryKey: [...surrogateKeys.detail(surrogateId), "history"],
            })
        }

        if (intendedParentId) {
            void queryClient.invalidateQueries({ queryKey: intendedParentKeys.detail(intendedParentId) })
            void queryClient.invalidateQueries({ queryKey: intendedParentKeys.lists() })
            void queryClient.invalidateQueries({ queryKey: intendedParentKeys.history(intendedParentId) })
        }
    }

    // Handle Accept match
    const handleAcceptMatch = async () => {
        const updatedMatch = await acceptMatchMutation.mutateAsync({ matchId })
        invalidateMatchSourceQueries(updatedMatch)
        void queryClient.invalidateQueries({ queryKey: matchKeys.detail(matchId) })
    }

    // Handle Reject match
    const handleRejectMatch = async (reason: string) => {
        const updatedMatch = await rejectMatchMutation.mutateAsync({
            matchId,
            data: { rejection_reason: reason },
        })
        invalidateMatchSourceQueries(updatedMatch)
        void queryClient.invalidateQueries({ queryKey: matchKeys.detail(matchId) })
        void queryClient.invalidateQueries({ queryKey: matchKeys.lists() })
    }

    const handleCancelMatch = async (reason?: string) => {
        const updatedMatch = await cancelMatchMutation.mutateAsync({
            matchId,
            data: reason ? { reason } : {},
        })
        invalidateMatchSourceQueries(updatedMatch)
        void queryClient.invalidateQueries({ queryKey: matchKeys.detail(matchId) })
        void queryClient.invalidateQueries({ queryKey: matchKeys.lists() })
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
                void queryClient.invalidateQueries({ queryKey: ["attachments", match.surrogate_id] })
            } else if (source === "ip" && match?.intended_parent_id) {
                void queryClient.invalidateQueries({ queryKey: ["ip-attachments", match.intended_parent_id] })
            }
            toast.success("File deleted successfully")
        } catch {
            toast.error("Failed to delete file")
        }
    }

    // Handle Add Task
    const handleAddTask = async (target: "match" | "surrogate" | "ip", data: TaskFormData) => {
        try {
            if (target === "match") {
                await createTaskMutation.mutateAsync({
                    title: data.title,
                    task_type: data.task_type,
                    match_id: matchId,
                    ...(data.description ? { description: data.description } : {}),
                    ...(data.due_date ? { due_date: data.due_date } : {}),
                })
            } else if (target === "surrogate" && match?.surrogate_id) {
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
            void queryClient.invalidateQueries({ queryKey: taskKeys.lists() })
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

    if (matchIsError && isPermissionError(matchError)) {
        return (
            <PermissionDeniedState
                className="min-h-screen"
                description="Your account does not have permission to view this match. Ask an admin to update your role or permissions."
                onRetry={() => refetchMatch()}
                secondaryHref="/intended-parents/matches"
                secondaryLabel="Back to matches"
            />
        )
    }

    if (!match) return null

    return (
        <>
            <div className="flex min-h-screen flex-col">
                <MatchDetailHeader
                    match={match}
                    canChangeStatus={canChangeStatus}
                    acceptPending={acceptMatchMutation.isPending}
                    rejectPending={rejectMatchMutation.isPending}
                    cancelPending={cancelMatchMutation.isPending}
                    onAcceptMatch={handleAcceptMatch}
                    onRejectClick={() => setRejectDialogOpen(true)}
                    onCancelClick={() => setCancelDialogOpen(true)}
                />

                <MatchDetailMainTabs
                    userAiEnabled={!!user?.ai_enabled}
                    surrogateId={match.surrogate_id}
                    intendedParentId={match.intended_parent_id}
                    surrogateData={surrogateData}
                    surrogateLoading={surrogateLoading}
                    intendedParentData={ipData}
                    intendedParentLoading={ipLoading}
                    overviewTabsProps={{
                        activeTab,
                        sourceFilter,
                        filteredNotes,
                        filteredFiles,
                        filteredTasks,
                        filteredActivity,
                        onTabChange: handleTabChange,
                        onSourceFilterChange: handleSourceFilterChange,
                        onAddTask: () => setAddTaskDialogOpen(true),
                        onAddNote: () => setAddNoteDialogOpen(true),
                        onUploadFile: () => setUploadFileDialogOpen(true),
                        onDownloadFile: (attachmentId) => downloadAttachmentMutation.mutate(attachmentId),
                        onDeleteFile: (attachmentId, source) => {
                            void handleDeleteFile(attachmentId, source)
                        },
                        isDownloadPending: downloadAttachmentMutation.isPending,
                        isDeletePending: deleteAttachmentMutation.isPending,
                        formatDate: formatMatchDate,
                        formatDateTime: formatMatchDateTime,
                    }}
                    onShowScheduleParser={() => setShowScheduleParser(true)}
                    onAddTask={() => setAddTaskDialogOpen(true)}
                />
            </div>

            <MatchDetailDialogs
                rejectDialogOpen={rejectDialogOpen}
                cancelDialogOpen={cancelDialogOpen}
                addNoteDialogOpen={addNoteDialogOpen}
                uploadFileDialogOpen={uploadFileDialogOpen}
                addTaskDialogOpen={addTaskDialogOpen}
                showScheduleParser={showScheduleParser}
                matchId={matchId}
                matchName={matchName}
                surrogateName={surrogateData?.full_name || "Surrogate"}
                intendedParentName={ipData?.full_name || "Intended Parent"}
                rejectPending={rejectMatchMutation.isPending}
                cancelPending={cancelMatchMutation.isPending}
                addNotePending={createNoteMutation.isPending || createIPNoteMutation.isPending}
                uploadFilePending={uploadAttachmentMutation.isPending || uploadIPAttachmentMutation.isPending}
                addTaskPending={createTaskMutation.isPending}
                onRejectOpenChange={setRejectDialogOpen}
                onCancelOpenChange={setCancelDialogOpen}
                onAddNoteOpenChange={setAddNoteDialogOpen}
                onUploadFileOpenChange={setUploadFileDialogOpen}
                onAddTaskOpenChange={setAddTaskDialogOpen}
                onScheduleParserOpenChange={setShowScheduleParser}
                onReject={handleRejectMatch}
                onCancel={handleCancelMatch}
                onAddNote={handleAddNote}
                onUploadFile={handleUploadFile}
                onAddTask={handleAddTask}
            />
        </>
    )
}
