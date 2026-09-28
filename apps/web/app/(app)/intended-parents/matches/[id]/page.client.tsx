"use client"

import { useState, type ComponentProps } from "react"
import { useParams } from "next/navigation"
import Link from "@/components/app-link"
import { toast } from "@/components/ui/toast"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
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
    CircleXIcon,
} from "lucide-react"
import { useMatch, matchKeys, useAcceptMatch, useDeclineMatch, useCancelMatch, useMatchWork, useCreateMatchNote, useUploadMatchFile, matchWorkKeys, useWithdrawMatchCancellation } from "@/lib/hooks/use-matches"
import type { MatchRead, MatchWorkSource } from "@/lib/api/matches"
import { MatchAcceptWarnings, MatchActionControls, MatchConflictBadge, type MatchAction } from "@/components/matches/MatchActionControls"
import { MatchTasksCalendar } from "@/components/matches/MatchTasksCalendar"
import { DeclineMatchDialog } from "@/components/matches/DeclineMatchDialog"
import { CancelMatchDialog } from "@/components/matches/CancelMatchDialog"
import { AddNoteDialog } from "@/components/matches/AddNoteDialog"
import { UploadFileDialog } from "@/components/matches/UploadFileDialog"
import { AddTaskDialog, type TaskFormData } from "@/components/matches/AddTaskDialog"
import { useSurrogate, surrogateKeys } from "@/lib/hooks/use-surrogates"
import { useIntendedParent, intendedParentKeys } from "@/lib/hooks/use-intended-parents"
import { useCreateTask, taskKeys } from "@/lib/hooks/use-tasks"
import { useDeleteAttachment, useDownloadAttachment } from "@/lib/hooks/use-attachments"
import { useAuth } from "@/lib/auth-context"
import { usePermissionCheck } from "@/lib/hooks/use-permission-check"
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
import { AcceptMatchDialog } from "./components/AcceptMatchDialog"
import { MatchDetailOverviewTabs } from "./components/MatchDetailOverviewTabs"
import { useMatchDetailTabState, type SourceFilter } from "./hooks/useMatchDetailTabState"
import { selectMatchDetailTabData } from "./hooks/useMatchDetailTabData"
import { useDonor, donorKeys } from "@/lib/hooks/use-donors"
import type { Donor } from "@/lib/types/donor"
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
    pending,
    onAction,
}: {
    match: MatchRead
    pending: Partial<Record<MatchAction, boolean>>
    onAction: (action: MatchAction) => void
}) {
    return (
        <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="flex min-h-14 flex-wrap items-center gap-3 px-6 py-2">
                <Button
                    render={<Link href="/intended-parents/matches" />}
                    variant="ghost"
                    size="sm"
                >
                    <ArrowLeftIcon className="mr-1 size-4" aria-hidden="true" />
                    Matches
                </Button>
                {/* Full row on phones so the title wraps across the width instead of a narrow column. */}
                <div className="min-w-0 flex-1 basis-full flex flex-wrap items-center gap-2 sm:basis-0">
                    <h1 className="text-xl font-semibold">
                        {(match.match_kind === "donor" ? match.donor_name || "Donor" : match.surrogate_name || "Surrogate")} ↔ {match.ip_name || "Intended Parents"}
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
                <MatchConflictBadge show={match.surrogate_has_accepted_match} />
                <MatchActionControls match={match} pending={pending} onAction={onAction} />
            </div>
        </div>
    )
}

function MatchDetailMainTabs({
    userAiEnabled,
    matchId,
    participantKind,
    donorData,
    donorLoading,
    donorError,
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
    matchId: string
    participantKind: "surrogate" | "donor"
    donorData: Donor | undefined
    donorLoading: boolean
    donorError: boolean
    surrogateId: string | null
    intendedParentId: string
    surrogateData: SurrogateRead | undefined
    surrogateLoading: boolean
    intendedParentData: IntendedParent | undefined
    intendedParentLoading: boolean
    overviewTabsProps: MatchDetailOverviewTabsProps
    onShowScheduleParser: () => void
    onAddTask?: (() => void) | undefined
}) {
    return (
        <div className="flex-1 p-4">
            <Tabs defaultValue="overview" className="w-full">
                <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                    <TabsList>
                        <TabsTrigger value="overview">Overview</TabsTrigger>
                        <TabsTrigger value="calendar">Calendar</TabsTrigger>
                    </TabsList>
                    {userAiEnabled && participantKind === "surrogate" && (
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
                    {/* Below xl the case work column is too narrow for its four tabs, so it spans both card columns. */}
                    <div className="grid h-full gap-4 grid-cols-1 lg:grid-cols-2 xl:grid-cols-[minmax(0,35fr)_minmax(0,35fr)_minmax(0,30fr)]">
                        {participantKind === "donor" ? <DonorProfileColumn donor={donorData} isLoading={donorLoading} isError={donorError} /> : <SurrogateProfileColumn
                            surrogateData={surrogateData}
                            isLoading={surrogateLoading}
                        />}
                        <IntendedParentProfileColumn
                            intendedParentData={intendedParentData}
                            isLoading={intendedParentLoading}
                        />
                        <MatchDetailOverviewTabs {...overviewTabsProps} className="lg:col-span-2 xl:col-span-1" />
                    </div>
                </TabsContent>

                <TabsContent value="calendar" className="h-[calc(100vh-145px)]">
                    <MatchTasksCalendar
                        matchId={matchId}
                        participantKind={participantKind}
                        surrogateId={surrogateId ?? ""}
                        ipId={intendedParentId}
                        {...(onAddTask ? { onAddTask } : {})}
                    />
                </TabsContent>
            </Tabs>
        </div>
    )
}

function DonorProfileColumn({ donor, isLoading, isError }: { donor: Donor | undefined; isLoading: boolean; isError: boolean }) {
    return <div className="min-w-0 border rounded-lg p-4 overflow-y-auto">
        <div className="flex items-center gap-2 mb-3"><UserIcon className="size-4 text-purple-500" /><h2 className="text-sm font-semibold text-purple-500">Donor</h2></div>
        {isLoading ? <div role="status" className="flex justify-center h-32 items-center"><Loader2Icon className="size-5 animate-spin" /></div> : isError ? <p role="alert" className="text-sm text-muted-foreground">Unable to load donor profile</p> : donor ? <div className="space-y-3">
            <div className="flex items-start gap-3">
                <Avatar className="size-10"><AvatarFallback className="bg-purple-500/10 text-purple-500 text-sm">{donor.full_name.charAt(0).toUpperCase()}</AvatarFallback></Avatar>
                <div className="min-w-0"><h3 className="text-base font-semibold truncate"><Link href={`/donors/${donor.id}`} className="hover:underline">{donor.full_name}</Link></h3><div className="flex flex-wrap gap-1 mt-0.5"><Badge variant="outline" className="text-xs px-1.5 py-0">#{donor.donor_number}</Badge><Badge variant="secondary" className="text-xs px-1.5 py-0">{donor.status_label}</Badge></div></div>
            </div>
            <Separator />
            <div className="space-y-2 text-sm">
                <div className="flex items-center gap-2"><MailIcon className="size-3.5 shrink-0 text-muted-foreground" /><span className="[overflow-wrap:anywhere]">{donor.email}</span></div>
                {donor.phone && <div className="flex items-center gap-2"><PhoneIcon className="size-3.5 text-muted-foreground" /><span>{donor.phone}</span></div>}
                {donor.state && <div className="flex items-center gap-2"><MapPinIcon className="size-3.5 text-muted-foreground" /><span>{donor.state}</span></div>}
                <p>{donor.donor_type === "egg" ? "Egg Donor" : "Sperm Donor"}</p>
                {donor.education && <p>{donor.education}</p>}
            </div>
            <Button render={<Link href={`/donors/${donor.id}`} />} variant="outline" size="sm" className="w-full text-xs h-7">View Full Profile</Button>
        </div> : <p className="text-sm text-muted-foreground">No donor data</p>}
    </div>
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
    declineDialogOpen,
    cancelDialogOpen,
    addNoteDialogOpen,
    uploadFileDialogOpen,
    addTaskDialogOpen,
    showScheduleParser,
    matchId,
    matchName,
    surrogateName,
    participantKind,
    intendedParentName,
    declinePending,
    cancelPending,
    addNotePending,
    uploadFilePending,
    addTaskPending,
    onDeclineOpenChange,
    onCancelOpenChange,
    onAddNoteOpenChange,
    onUploadFileOpenChange,
    onAddTaskOpenChange,
    onScheduleParserOpenChange,
    onDecline,
    onCancel,
    onAddNote,
    onUploadFile,
    onAddTask,
}: {
    declineDialogOpen: boolean
    cancelDialogOpen: boolean
    addNoteDialogOpen: boolean
    uploadFileDialogOpen: boolean
    addTaskDialogOpen: boolean
    showScheduleParser: boolean
    matchId: string
    matchName: string
    surrogateName: string
    participantKind: "surrogate" | "donor"
    intendedParentName: string
    declinePending: boolean
    cancelPending: boolean
    addNotePending: boolean
    uploadFilePending: boolean
    addTaskPending: boolean
    onDeclineOpenChange: (open: boolean) => void
    onCancelOpenChange: (open: boolean) => void
    onAddNoteOpenChange: (open: boolean) => void
    onUploadFileOpenChange: (open: boolean) => void
    onAddTaskOpenChange: (open: boolean) => void
    onScheduleParserOpenChange: (open: boolean) => void
    onDecline: (reason: string) => Promise<void>
    onCancel: (reason: string) => Promise<void>
    onAddNote: (target: MatchWorkSource, content: string) => Promise<void>
    onUploadFile: (target: MatchWorkSource, file: File) => Promise<void>
    onAddTask: (target: MatchWorkSource, data: TaskFormData) => Promise<void>
}) {
    return (
        <>
            <DeclineMatchDialog
                open={declineDialogOpen}
                onOpenChange={onDeclineOpenChange}
                onConfirm={onDecline}
                isPending={declinePending}
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
                participantKind={participantKind}
                ipName={intendedParentName}
            />

            <UploadFileDialog
                open={uploadFileDialogOpen}
                onOpenChange={onUploadFileOpenChange}
                onUpload={onUploadFile}
                isPending={uploadFilePending}
                surrogateName={surrogateName}
                participantKind={participantKind}
                ipName={intendedParentName}
            />

            <AddTaskDialog
                participantKind={participantKind}
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

function useMatchDetailRelatedData(match: MatchRead | undefined, sourceFilter: SourceFilter, workPage = 1) {
    const { data: surrogateData, isLoading: surrogateLoading } = useSurrogate(match?.surrogate_id || "")
    const { data: ipData, isLoading: ipLoading } = useIntendedParent(match?.intended_parent_id || "")
    const donorQuery = useDonor(match?.donor_id ?? null)
    const work = useMatchWork(match?.id ?? "", workPage)
    return {
        surrogateData, surrogateLoading, ipData, ipLoading,
        donorData: donorQuery.data, donorLoading: donorQuery.isLoading, donorError: donorQuery.isError,
        hasMoreWork: work.data?.has_more ?? false,
        canViewNotes: work.data?.can_view_notes ?? true, canViewTasks: work.data?.can_view_tasks ?? true,
        workLoading: work.isLoading, workError: work.error, refetchWork: work.refetch,
        ...selectMatchDetailTabData(work.data, sourceFilter),
    }
}

function MatchDetailPageContent({ matchId }: { matchId: string }) {

    const { activeTab, sourceFilter, handleTabChange, handleSourceFilterChange } =
        useMatchDetailTabState(matchId)
    const [acceptDialogOpen, setAcceptDialogOpen] = useState(false)
    const [actionError, setActionError] = useState<string | null>(null)
    const [workPage, setWorkPage] = useState(1)
    const [declineDialogOpen, setDeclineDialogOpen] = useState(false)
    const [cancelDialogOpen, setCancelDialogOpen] = useState(false)
    const [addNoteDialogOpen, setAddNoteDialogOpen] = useState(false)
    const [uploadFileDialogOpen, setUploadFileDialogOpen] = useState(false)
    const [addTaskDialogOpen, setAddTaskDialogOpen] = useState(false)
    const [pendingDeleteFile, setPendingDeleteFile] = useState<{ id: string; filename: string } | null>(null)
    const [showScheduleParser, setShowScheduleParser] = useState(false)
    const { user } = useAuth()
    const { can } = usePermissionCheck()
    const queryClient = useQueryClient()

    const {
        data: match,
        isLoading: matchLoading,
        isError: matchIsError,
        error: matchError,
    } = useMatch(matchId)
    const acceptMatchMutation = useAcceptMatch()
    const declineMatchMutation = useDeclineMatch()
    const cancelMatchMutation = useCancelMatch()
    const withdrawCancellationMutation = useWithdrawMatchCancellation()
    const createNoteMutation = useCreateMatchNote(matchId)
    const uploadAttachmentMutation = useUploadMatchFile(matchId)
    const deleteAttachmentMutation = useDeleteAttachment()
    const downloadAttachmentMutation = useDownloadAttachment()
    const createTaskMutation = useCreateTask()

    // Set AI context for this page.
    // NOTE: The chat API currently supports surrogate/task/global. For match pages, we attach AI to the surrogate.
    const matchName = match ? `${match.match_kind === "donor" ? match.donor_name : match.surrogate_name} & ${match.ip_name}` : ""
    useSetAIContext(match?.surrogate_id ? { entityType: "surrogate", entityId: match.surrogate_id, entityName: matchName } : null)

    const {
        surrogateData,
        surrogateLoading,
        donorData, donorLoading, donorError, workLoading, workError, refetchWork, hasMoreWork, canViewNotes, canViewTasks,
        ipData,
        ipLoading,
        filteredNotes,
        filteredFiles,
        filteredTasks,
        filteredActivity,
    } = useMatchDetailRelatedData(match, sourceFilter, workPage)

    // Completed matches accept postpartum work; the backend rejects work on the other closed statuses.
    const canCreateWork = match?.status === "under_review" || match?.status === "accepted" || match?.status === "completed"

    const invalidateMatchSourceQueries = (
        entityIds?: {
            surrogate_id?: string | null
            donor_id?: string | null
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

        const donorId = entityIds?.donor_id ?? match?.donor_id
        if (donorId) { void queryClient.invalidateQueries({ queryKey: donorKeys.detail(donorId) }) }
        if (intendedParentId) {
            void queryClient.invalidateQueries({ queryKey: intendedParentKeys.detail(intendedParentId) })
            void queryClient.invalidateQueries({ queryKey: intendedParentKeys.lists() })
            void queryClient.invalidateQueries({ queryKey: intendedParentKeys.history(intendedParentId) })
        }
    }

    // Handle Accept match. Failures surface inline in the confirm dialog.
    const handleAcceptMatch = async () => {
        const updatedMatch = await acceptMatchMutation.mutateAsync({ matchId })
        invalidateMatchSourceQueries(updatedMatch)
        void queryClient.invalidateQueries({ queryKey: matchKeys.detail(matchId) })
    }

    // Handle decline match
    const handleDeclineMatch = async (reason: string) => {
        const updatedMatch = await declineMatchMutation.mutateAsync({
            matchId,
            data: { reason },
        })
        invalidateMatchSourceQueries(updatedMatch)
        void queryClient.invalidateQueries({ queryKey: matchKeys.detail(matchId) })
        void queryClient.invalidateQueries({ queryKey: matchKeys.lists() })
    }

    const handleCancelMatch = async (reason: string) => {
        const updatedMatch = await cancelMatchMutation.mutateAsync({
            matchId,
            data: { reason },
        })
        invalidateMatchSourceQueries(updatedMatch)
        void queryClient.invalidateQueries({ queryKey: matchKeys.detail(matchId) })
        void queryClient.invalidateQueries({ queryKey: matchKeys.lists() })
    }

    const handleWithdrawCancellation = async () => {
        setActionError(null)
        const requestId = match?.pending_cancellation_request_id
        if (!requestId) {
            setActionError("No pending cancellation request exists for this match")
            return
        }
        try {
            await withdrawCancellationMutation.mutateAsync({ matchId, requestId })
            invalidateMatchSourceQueries()
        } catch (error) { setActionError(error instanceof Error ? error.message : "Unable to withdraw cancellation") }
    }

    const handleMatchAction = (action: MatchAction) => {
        if (action === "accept") setAcceptDialogOpen(true)
        else if (action === "decline") setDeclineDialogOpen(true)
        else if (action === "request_cancel") setCancelDialogOpen(true)
        else void handleWithdrawCancellation()
    }

    const handleAddNote = async (source: MatchWorkSource, content: string) => {
        try {
            await createNoteMutation.mutateAsync({ source, content })
            toast.success("Note added successfully")
        } catch (error) { toast.error("Failed to add note"); throw error }
    }
    const handleUploadFile = async (source: MatchWorkSource, file: File) => {
        try {
            await uploadAttachmentMutation.mutateAsync({ source, file })
            toast.success("File uploaded successfully")
        } catch (error) { toast.error("Failed to upload file"); throw error }
    }
    // Runs from ConfirmDialog, which stays open while it runs and shows a failure inline.
    const handleDeleteFile = async (attachmentId: string) => {
        await deleteAttachmentMutation.mutateAsync({ attachmentId, surrogateId: match?.surrogate_id || "" })
        void queryClient.invalidateQueries({ queryKey: matchWorkKeys.all(matchId) })
        toast.success("File deleted successfully")
    }
    const handleAddTask = async (target: MatchWorkSource, data: TaskFormData) => {
        try {
            await createTaskMutation.mutateAsync({ ...data, match_id: matchId, work_source: target })
            void queryClient.invalidateQueries({ queryKey: taskKeys.lists() })
            void queryClient.invalidateQueries({ queryKey: matchWorkKeys.all(matchId) })
            toast.success("Task created successfully")
        } catch (error) { toast.error("Failed to create task"); throw error }
    }

    if (matchLoading) {
        return (
            <div className="flex min-h-screen items-center justify-center">
                <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (matchIsError && isPermissionError(matchError)) {
        // Without view_matches the Matches list is denied too, so point back to Dashboard.
        const canViewMatches = can("view_matches")
        return (
            <PermissionDeniedState
                className="min-h-screen"
                description="Your account does not have permission to view this match. Ask an admin to update your role or permissions."
                secondaryHref={canViewMatches ? "/intended-parents/matches" : "/dashboard"}
                secondaryLabel={canViewMatches ? "Back to matches" : "Go to Dashboard"}
            />
        )
    }

    if (!match) return null

    return (
        <>
            <div className="flex min-h-screen flex-col">
                <MatchDetailHeader
                    match={match}
                    pending={{
                        accept: acceptMatchMutation.isPending,
                        decline: declineMatchMutation.isPending,
                        request_cancel: cancelMatchMutation.isPending,
                        withdraw_cancel: withdrawCancellationMutation.isPending,
                    }}
                    onAction={handleMatchAction}
                />
                <MatchAcceptWarnings warnings={match.accept_eligibility_warnings} />

                {actionError && <p role="alert" className="px-6 py-2 text-sm text-destructive">{actionError}</p>}
                {match.status === "declined" && match.decline_reason ? (
                    <div
                        data-slot="match-decline-reason"
                        className="flex items-start gap-2.5 border-b bg-destructive/10 px-6 py-3 text-sm"
                    >
                        <CircleXIcon className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
                        <p className="min-w-0 break-words">
                            <span className="font-medium">Decline reason: </span>
                            {match.decline_reason}
                            {match.reviewed_at ? (
                                <span className="text-muted-foreground"> · {formatMatchDateTime(match.reviewed_at)}</span>
                            ) : null}
                        </p>
                    </div>
                ) : null}
                {match.outcome && <div className="px-6 py-2 text-sm border-b"><span className="font-medium">Outcome: </span>{match.outcome}{match.closed_at && <span className="text-muted-foreground"> · {formatMatchDate(match.closed_at)}</span>}</div>}
                <MatchDetailMainTabs
                    matchId={matchId}
                    participantKind={match.match_kind ?? "surrogate"}
                    donorData={donorData}
                    donorLoading={donorLoading}
                    donorError={donorError}
                    userAiEnabled={!!user?.ai_enabled && canCreateWork}
                    surrogateId={match.surrogate_id}
                    intendedParentId={match.intended_parent_id}
                    surrogateData={surrogateData}
                    surrogateLoading={surrogateLoading}
                    intendedParentData={ipData}
                    intendedParentLoading={ipLoading}
                    overviewTabsProps={{
                        participantKind: match.match_kind ?? "surrogate",
                        hasMore: hasMoreWork,
                        page: workPage, onPageChange: setWorkPage,
                        canViewNotes, canViewTasks,
                        isLoading: workLoading,
                        error: workError ? "Unable to load case work" : null,
                        onRetry: () => { void refetchWork() },
                        activeTab,
                        sourceFilter,
                        filteredNotes,
                        filteredFiles,
                        filteredTasks,
                        filteredActivity,
                        onTabChange: handleTabChange,
                        onSourceFilterChange: handleSourceFilterChange,
                        onAddTask: canCreateWork ? () => setAddTaskDialogOpen(true) : undefined,
                        onAddNote: canCreateWork ? () => setAddNoteDialogOpen(true) : undefined,
                        onUploadFile: canCreateWork ? () => setUploadFileDialogOpen(true) : undefined,
                        onDownloadFile: (attachmentId) => downloadAttachmentMutation.mutate(attachmentId),
                        onDeleteFile: (attachmentId) => {
                            const file = filteredFiles.find((item) => item.id === attachmentId)
                            setPendingDeleteFile({ id: attachmentId, filename: file?.filename ?? "this file" })
                        },
                        isDownloadPending: downloadAttachmentMutation.isPending,
                        isDeletePending: deleteAttachmentMutation.isPending,
                        formatDate: formatMatchDate,
                        formatDateTime: formatMatchDateTime,
                    }}
                    onShowScheduleParser={() => setShowScheduleParser(true)}
                    onAddTask={canCreateWork ? () => setAddTaskDialogOpen(true) : undefined}
                />
            </div>

            <ConfirmDialog
                open={pendingDeleteFile !== null}
                onOpenChange={(open) => { if (!open) setPendingDeleteFile(null) }}
                title={`Delete ${pendingDeleteFile?.filename ?? "this file"}?`}
                confirmLabel="Delete file"
                errorFallback="Couldn't delete this file. Try again."
                onConfirm={() => (pendingDeleteFile ? handleDeleteFile(pendingDeleteFile.id) : undefined)}
            />
            {acceptDialogOpen ? (
                <AcceptMatchDialog
                    match={match}
                    intendedParent={ipData}
                    open={acceptDialogOpen}
                    onOpenChange={setAcceptDialogOpen}
                    onConfirm={handleAcceptMatch}
                />
            ) : null}
            <MatchDetailDialogs
                declineDialogOpen={declineDialogOpen}
                cancelDialogOpen={cancelDialogOpen}
                addNoteDialogOpen={addNoteDialogOpen && canCreateWork}
                uploadFileDialogOpen={uploadFileDialogOpen && canCreateWork}
                addTaskDialogOpen={addTaskDialogOpen && canCreateWork}
                showScheduleParser={showScheduleParser && canCreateWork}
                matchId={matchId}
                matchName={matchName}
                surrogateName={match.match_kind === "donor" ? donorData?.full_name || "Donor" : surrogateData?.full_name || "Surrogate"}
                participantKind={match.match_kind ?? "surrogate"}
                intendedParentName={ipData?.full_name || "Intended Parent"}
                declinePending={declineMatchMutation.isPending}
                cancelPending={cancelMatchMutation.isPending}
                addNotePending={createNoteMutation.isPending}
                uploadFilePending={uploadAttachmentMutation.isPending}
                addTaskPending={createTaskMutation.isPending}
                onDeclineOpenChange={setDeclineDialogOpen}
                onCancelOpenChange={setCancelDialogOpen}
                onAddNoteOpenChange={setAddNoteDialogOpen}
                onUploadFileOpenChange={setUploadFileDialogOpen}
                onAddTaskOpenChange={setAddTaskDialogOpen}
                onScheduleParserOpenChange={setShowScheduleParser}
                onDecline={handleDeclineMatch}
                onCancel={handleCancelMatch}
                onAddNote={handleAddNote}
                onUploadFile={handleUploadFile}
                onAddTask={handleAddTask}
            />
        </>
    )
}

export default function MatchDetailPage() {
    const params = useParams<{ id: string }>()
    return <MatchDetailPageContent key={params.id} matchId={params.id} />
}
