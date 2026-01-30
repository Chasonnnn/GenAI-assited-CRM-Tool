"use client"

import * as React from "react"
import { useParams, useRouter, useSelectedLayoutSegment } from "next/navigation"
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
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
    MoreVerticalIcon,
    CheckIcon,
    XIcon,
    Loader2Icon,
    SparklesIcon,
    MailIcon,
    HeartHandshakeIcon,
    PhoneIcon,
    VideoIcon,
} from "lucide-react"
import {
    useSurrogate,
    useChangeSurrogateStatus,
    useArchiveSurrogate,
    useRestoreSurrogate,
    useUpdateSurrogate,
    useAssignSurrogate,
    useAssignees,
} from "@/lib/hooks/use-surrogates"
import { useQueues, useClaimSurrogate, useReleaseSurrogate } from "@/lib/hooks/use-queues"
import { useDefaultPipeline } from "@/lib/hooks/use-pipelines"
import { useNotes } from "@/lib/hooks/use-notes"
import { useTasks } from "@/lib/hooks/use-tasks"
import {
    useZoomStatus,
    useCreateZoomMeeting,
    useSendZoomInvite,
} from "@/lib/hooks/use-user-integrations"
import { useSetAIContext } from "@/lib/context/ai-context"
import { EmailComposeDialog } from "@/components/email/EmailComposeDialog"
import { ProposeMatchDialog } from "@/components/matches/ProposeMatchDialog"
import { LogContactAttemptDialog } from "@/components/surrogates/LogContactAttemptDialog"
import { ChangeStageModal } from "@/components/surrogates/ChangeStageModal"
import { SurrogateDetailHeader } from "@/components/surrogates/detail/SurrogateDetailHeader"
import { SurrogateDetailProvider } from "@/components/surrogates/detail/SurrogateDetailContext"
import { useAuth } from "@/lib/auth-context"
import { ROLE_STAGE_VISIBILITY, type StageType } from "@/lib/constants/stages.generated"
import { cn } from "@/lib/utils"
import {
    formatMeetingTimeForInvite,
    toLocalIsoDateTime,
} from "@/components/surrogates/detail/surrogate-detail-utils"
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

type SurrogateDetailLayoutClientProps = {
    children: React.ReactNode
}

export function SurrogateDetailLayoutClient({ children }: SurrogateDetailLayoutClientProps) {
    const params = useParams<{ id: string }>()
    const id = params.id
    const router = useRouter()
    const segment = useSelectedLayoutSegment()
    const { user } = useAuth()
    const canViewProfile = user
        ? ["case_manager", "admin", "developer"].includes(user.role)
        : false
    const allowedTabs = React.useMemo<TabValue[]>(
        () => (canViewProfile ? [...TAB_VALUES] : TAB_VALUES.filter((tab) => tab !== "profile")),
        [canViewProfile]
    )
    const isTabValue = React.useCallback(
        (value: string | null): value is TabValue =>
            !!value && allowedTabs.includes(value as TabValue),
        [allowedTabs]
    )
    const resolvedTab: TabValue = isTabValue(segment) ? segment : "overview"
    const [currentTab, setCurrentTab] = React.useState<TabValue>(resolvedTab)

    const handleTabChange = React.useCallback(
        (value: string) => {
            const nextTab: TabValue = isTabValue(value) ? value : "overview"
            setCurrentTab(nextTab)
            const basePath = `/surrogates/${id}`
            const nextUrl = nextTab === "overview" ? basePath : `${basePath}/${nextTab}`
            router.replace(nextUrl, { scroll: false })
        },
        [id, router, isTabValue]
    )

    React.useEffect(() => {
        setCurrentTab(resolvedTab)
    }, [resolvedTab])

    React.useEffect(() => {
        if (segment === "overview" || (segment && !isTabValue(segment))) {
            handleTabChange("overview")
        }
    }, [segment, isTabValue, handleTabChange])

    const { data: defaultPipeline } = useDefaultPipeline()
    const stageOptions = React.useMemo(() => defaultPipeline?.stages || [], [defaultPipeline])
    const stageById = React.useMemo(
        () => new Map(stageOptions.map((stage) => [stage.id, stage])),
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
    const matchedStage = React.useMemo(
        () => stageOptions.find((stage) => stage.slug === "matched"),
        [stageOptions]
    )

    const { data: surrogateData, isLoading, error } = useSurrogate(id)
    const canViewJourney = React.useMemo(() => {
        if (!surrogateData || !matchedStage) return false
        const currentStage = stageById.get(surrogateData.stage_id)
        if (!currentStage) return false
        return currentStage.order >= matchedStage.order
    }, [surrogateData, matchedStage, stageById])

    React.useEffect(() => {
        if (segment === "journey" && surrogateData && !canViewJourney) {
            handleTabChange("overview")
        }
    }, [segment, surrogateData, canViewJourney, handleTabChange])

    const { data: notes } = useNotes(id)
    const { data: tasksData } = useTasks({ surrogate_id: id, exclude_approvals: true })

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
    const [emailDialogOpen, setEmailDialogOpen] = React.useState(false)
    const [proposeMatchOpen, setProposeMatchOpen] = React.useState(false)
    const [contactAttemptDialogOpen, setContactAttemptDialogOpen] = React.useState(false)
    const [changeStageModalOpen, setChangeStageModalOpen] = React.useState(false)

    const timezoneName = React.useMemo(() => {
        try {
            return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"
        } catch {
            return "UTC"
        }
    }, [])

    React.useEffect(() => {
        if (!zoomDialogOpen) {
            zoomIdempotencyKeyRef.current = null
        }
    }, [zoomDialogOpen])

    const changeStatusMutation = useChangeSurrogateStatus()
    const archiveMutation = useArchiveSurrogate()
    const restoreMutation = useRestoreSurrogate()
    const updateSurrogateMutation = useUpdateSurrogate()
    const claimSurrogateMutation = useClaimSurrogate()
    const releaseSurrogateMutation = useReleaseSurrogate()
    const createZoomMeetingMutation = useCreateZoomMeeting()
    const sendZoomInviteMutation = useSendZoomInvite()
    const assignSurrogateMutation = useAssignSurrogate()
    const { data: assignees } = useAssignees()

    const { data: zoomStatus } = useZoomStatus()

    useSetAIContext(
        surrogateData
            ? {
                  entityType: "surrogate",
                  entityId: surrogateData.id,
                  entityName: `Surrogate #${surrogateData.surrogate_number} - ${surrogateData.full_name}`,
              }
            : null
    )

    const canManageQueue =
        user?.role && ["case_manager", "admin", "developer"].includes(user.role)
    const { data: queues } = useQueues()
    const isOwnedByCurrentUser = !!(
        surrogateData?.owner_type === "user" &&
        user?.user_id &&
        surrogateData.owner_id === user.user_id
    )
    const canChangeStage = !!(
        surrogateData &&
        !surrogateData.is_archived &&
        (["admin", "developer"].includes(user?.role || "") ||
            (user?.role === "case_manager" && isOwnedByCurrentUser) ||
            (user?.role === "intake_specialist" && isOwnedByCurrentUser))
    )

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
                            const message = error instanceof Error ? error.message : "Undo failed"
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
        router.push("/surrogates")
    }

    const handleRestore = async () => {
        await restoreMutation.mutateAsync(id)
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

    const isInQueue = surrogateData?.owner_type === "queue"
    const isOwnedByUser = surrogateData?.owner_type === "user"

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
                    <p className="text-destructive">
                        Error loading surrogate: {error?.message || "Not found"}
                    </p>
                    <Button
                        variant="outline"
                        className="mt-4"
                        onClick={() => router.push("/surrogates")}
                    >
                        Back to Surrogates
                    </Button>
                </Card>
            </div>
        )
    }

    const stage = stageById.get(surrogateData.stage_id)
    const statusLabel = surrogateData.status_label || stage?.label || "Unknown"
    const statusColor = stage?.color || "#6B7280"
    const noteCount = notes?.length ?? 0
    const taskCount = tasksData?.items?.length ?? 0

    return (
        <div className="flex flex-1 flex-col">
            <SurrogateDetailHeader
                surrogateNumber={surrogateData.surrogate_number}
                statusLabel={statusLabel}
                statusColor={statusColor}
                isArchived={surrogateData.is_archived}
                onBack={() => router.push("/surrogates")}
            >
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setChangeStageModalOpen(true)}
                    disabled={surrogateData.is_archived || !canChangeStage}
                >
                    Change Stage
                </Button>

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

                {(() => {
                    const currentStage = stageById.get(surrogateData.stage_id)
                    const contactedStage = stageOptions.find((stage) => stage.slug === "contacted")
                    const isIntakeStage = currentStage?.stage_type === "intake"
                    const isBeforeContacted = !!(
                        currentStage &&
                        contactedStage &&
                        currentStage.order < contactedStage.order
                    )
                    const isAssignee = !!(
                        user?.user_id && surrogateData.owner_id === user.user_id
                    )
                    const canLogContact =
                        surrogateData.owner_type === "user" &&
                        (isAssignee || canManageQueue) &&
                        isIntakeStage &&
                        isBeforeContacted &&
                        !surrogateData.is_archived
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

                {canManageQueue && isInQueue && (
                    <Button
                        variant="default"
                        size="sm"
                        onClick={handleClaimSurrogate}
                        disabled={claimSurrogateMutation.isPending || surrogateData.is_archived}
                    >
                        {claimSurrogateMutation.isPending ? "Claiming..." : "Claim Surrogate"}
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

                {(() => {
                    const currentStage = stageById.get(surrogateData.stage_id)
                    const isReadyToMatchStage = currentStage?.slug === "ready_to_match"
                    const isManagerRole =
                        user?.role && ["case_manager", "admin", "developer"].includes(user.role)
                    const canProposeMatch =
                        isManagerRole && isReadyToMatchStage && !surrogateData.is_archived

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

                {user?.role &&
                    ["case_manager", "admin", "developer"].includes(user.role) &&
                    !surrogateData.is_archived && (
                        <DropdownMenu>
                            <DropdownMenuTrigger
                                className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
                                disabled={assignSurrogateMutation.isPending}
                            >
                                {assignSurrogateMutation.isPending ? (
                                    <Loader2Icon className="size-4 mr-2 animate-spin" />
                                ) : null}
                                Assign
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                                {surrogateData.owner_type === "user" &&
                                    surrogateData.owner_id &&
                                    (() => {
                                        const defaultQueue = queues?.find(
                                            (queue) => queue.name === "Unassigned"
                                        )
                                        if (!defaultQueue) return null
                                        return (
                                            <>
                                                <DropdownMenuItem
                                                    onClick={() =>
                                                        releaseSurrogateMutation.mutate({
                                                            surrogateId: surrogateData.id,
                                                            queueId: defaultQueue.id,
                                                        })
                                                    }
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
                                        onClick={() =>
                                            assignSurrogateMutation.mutate({
                                                surrogateId: surrogateData.id,
                                                owner_type: "user",
                                                owner_id: assignee.id,
                                            })
                                        }
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
                    <DropdownMenuTrigger
                        className={cn(buttonVariants({ variant: "ghost", size: "icon-sm" }))}
                    >
                        <span className="inline-flex items-center justify-center">
                            <MoreVerticalIcon className="h-4 w-4" />
                        </span>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => setEditDialogOpen(true)}>
                            Edit
                        </DropdownMenuItem>
                        {surrogateData.is_archived ? (
                            <DropdownMenuItem onClick={handleRestore}>Restore</DropdownMenuItem>
                        ) : (
                            <DropdownMenuItem onClick={handleArchive}>Archive</DropdownMenuItem>
                        )}
                    </DropdownMenuContent>
                </DropdownMenu>
            </SurrogateDetailHeader>

            <div className="flex flex-1 flex-col gap-4 p-4 md:p-6">
                <Tabs value={currentTab} onValueChange={handleTabChange} className="w-full">
                    <TabsList className="mb-4 overflow-x-auto print:hidden">
                        <TabsTrigger value="overview">Overview</TabsTrigger>
                        <TabsTrigger value="notes">
                            Notes {noteCount > 0 && `(${noteCount})`}
                        </TabsTrigger>
                        <TabsTrigger value="tasks">
                            Tasks {taskCount > 0 && `(${taskCount})`}
                        </TabsTrigger>
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
                    {!canViewJourney && (
                        <p className="mt-1 text-xs text-muted-foreground">
                            Journey available after Match Confirmed
                        </p>
                    )}

                    <SurrogateDetailProvider surrogate={surrogateData}>
                        {children}
                    </SurrogateDetailProvider>
                </Tabs>
            </div>

            <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
                <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle>Edit Surrogate: #{surrogateData?.surrogate_number}</DialogTitle>
                    </DialogHeader>
                    <form
                        onSubmit={async (event: React.FormEvent<HTMLFormElement>) => {
                            event.preventDefault()
                            const form = event.currentTarget
                            const formData = new FormData(form)
                            const data: Record<string, unknown> = {}
                            const getString = (key: string) => {
                                const value = formData.get(key)
                                return typeof value === "string" ? value : ""
                            }

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

                            const heightFt = getString("height_ft")
                            data.height_ft = heightFt ? parseFloat(heightFt) : null
                            const weightLb = getString("weight_lb")
                            data.weight_lb = weightLb ? parseFloat(weightLb) : null
                            const numDeliveries = getString("num_deliveries")
                            data.num_deliveries = numDeliveries ? parseInt(numDeliveries, 10) : null
                            const numCsections = getString("num_csections")
                            data.num_csections = numCsections ? parseInt(numCsections, 10) : null

                            data.is_age_eligible = formData.get("is_age_eligible") === "on"
                            data.is_citizen_or_pr = formData.get("is_citizen_or_pr") === "on"
                            data.has_child = formData.get("has_child") === "on"
                            data.is_non_smoker = formData.get("is_non_smoker") === "on"
                            data.has_surrogate_experience =
                                formData.get("has_surrogate_experience") === "on"
                            data.is_priority = formData.get("is_priority") === "on"

                            await updateSurrogateMutation.mutateAsync({ surrogateId: id, data })
                            setEditDialogOpen(false)
                        }}
                    >
                        <div className="grid gap-4 py-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="full_name">Full Name *</Label>
                                    <Input
                                        id="full_name"
                                        name="full_name"
                                        defaultValue={surrogateData?.full_name}
                                        required
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="email">Email *</Label>
                                    <Input
                                        id="email"
                                        name="email"
                                        type="email"
                                        defaultValue={surrogateData?.email}
                                        required
                                    />
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="phone">Phone</Label>
                                    <Input
                                        id="phone"
                                        name="phone"
                                        defaultValue={surrogateData?.phone ?? ""}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="state">State</Label>
                                    <Input
                                        id="state"
                                        name="state"
                                        defaultValue={surrogateData?.state ?? ""}
                                    />
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="date_of_birth">Date of Birth</Label>
                                    <Input
                                        id="date_of_birth"
                                        name="date_of_birth"
                                        type="date"
                                        defaultValue={surrogateData?.date_of_birth ?? ""}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="race">Race</Label>
                                    <Input
                                        id="race"
                                        name="race"
                                        defaultValue={surrogateData?.race ?? ""}
                                    />
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="height_ft">Height (ft)</Label>
                                    <Input
                                        id="height_ft"
                                        name="height_ft"
                                        type="number"
                                        step="0.1"
                                        defaultValue={surrogateData?.height_ft ?? ""}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="weight_lb">Weight (lb)</Label>
                                    <Input
                                        id="weight_lb"
                                        name="weight_lb"
                                        type="number"
                                        defaultValue={surrogateData?.weight_lb ?? ""}
                                    />
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="num_deliveries">Number of Deliveries</Label>
                                    <Input
                                        id="num_deliveries"
                                        name="num_deliveries"
                                        type="number"
                                        min="0"
                                        max="20"
                                        defaultValue={surrogateData?.num_deliveries ?? ""}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="num_csections">Number of C-Sections</Label>
                                    <Input
                                        id="num_csections"
                                        name="num_csections"
                                        type="number"
                                        min="0"
                                        max="10"
                                        defaultValue={surrogateData?.num_csections ?? ""}
                                    />
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-4 pt-2">
                                <div className="flex items-center gap-2">
                                    <Checkbox
                                        id="is_priority"
                                        name="is_priority"
                                        defaultChecked={surrogateData?.is_priority}
                                    />
                                    <Label htmlFor="is_priority">Priority Surrogate</Label>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Checkbox
                                        id="is_age_eligible"
                                        name="is_age_eligible"
                                        defaultChecked={surrogateData?.is_age_eligible ?? false}
                                    />
                                    <Label htmlFor="is_age_eligible">Age Eligible</Label>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Checkbox
                                        id="is_citizen_or_pr"
                                        name="is_citizen_or_pr"
                                        defaultChecked={surrogateData?.is_citizen_or_pr ?? false}
                                    />
                                    <Label htmlFor="is_citizen_or_pr">US Citizen/PR</Label>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Checkbox
                                        id="has_child"
                                        name="has_child"
                                        defaultChecked={surrogateData?.has_child ?? false}
                                    />
                                    <Label htmlFor="has_child">Has Child</Label>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Checkbox
                                        id="is_non_smoker"
                                        name="is_non_smoker"
                                        defaultChecked={surrogateData?.is_non_smoker ?? false}
                                    />
                                    <Label htmlFor="is_non_smoker">Non-Smoker</Label>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Checkbox
                                        id="has_surrogate_experience"
                                        name="has_surrogate_experience"
                                        defaultChecked={
                                            surrogateData?.has_surrogate_experience ?? false
                                        }
                                    />
                                    <Label htmlFor="has_surrogate_experience">
                                        Surrogate Experience
                                    </Label>
                                </div>
                            </div>
                        </div>
                        <DialogFooter>
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => setEditDialogOpen(false)}
                            >
                                Cancel
                            </Button>
                            <Button type="submit" disabled={updateSurrogateMutation.isPending}>
                                {updateSurrogateMutation.isPending ? "Saving..." : "Save Changes"}
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>

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
                            onChange={(event) => setSelectedQueueId(event.target.value)}
                            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 mt-2"
                        >
                            <option value="">Select a queue...</option>
                            {queues?.map((queue) => (
                                <option key={queue.id} value={queue.id}>
                                    {queue.name}
                                </option>
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
                            {releaseSurrogateMutation.isPending ? "Releasing..." : "Release"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

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
                                onChange={(event) => setZoomTopic(event.target.value)}
                                placeholder="Appointment topic"
                                className="mt-2"
                                disabled={!!lastMeetingResult}
                            />
                        </div>
                        <div>
                            <Label>When</Label>
                            <div className="mt-2">
                                <DateTimePicker
                                    value={zoomStartAt}
                                    onChange={setZoomStartAt}
                                    disabled={!!lastMeetingResult}
                                />
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
                                onChange={(event) => setZoomDuration(Number(event.target.value))}
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
                                                contact_name: surrogateData.full_name || "there",
                                                surrogate_id: id,
                                                ...(lastMeetingResult.start_time
                                                    ? { start_time: lastMeetingResult.start_time }
                                                    : {}),
                                                ...(lastMeetingResult.password
                                                    ? { password: lastMeetingResult.password }
                                                    : {}),
                                            })
                                            setZoomDialogOpen(false)
                                            setLastMeetingResult(null)
                                        } catch {
                                            // Error handled by react-query
                                        }
                                    }}
                                    disabled={sendZoomInviteMutation.isPending || !surrogateData?.email}
                                >
                                    {sendZoomInviteMutation.isPending ? "Sending..." : "Send Invite"}
                                </Button>
                            </>
                        ) : (
                            <Button
                                onClick={async () => {
                                    if (!zoomStartAt) return
                                    try {
                                        if (!zoomIdempotencyKeyRef.current) {
                                            zoomIdempotencyKeyRef.current =
                                                typeof crypto !== "undefined" && "randomUUID" in crypto
                                                    ? crypto.randomUUID()
                                                    : `${Date.now()}-${Math.random()
                                                          .toString(16)
                                                          .slice(2)}`
                                        }
                                        const result = await createZoomMeetingMutation.mutateAsync({
                                            entity_type: "surrogate",
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
                                disabled={
                                    !zoomTopic ||
                                    !zoomStartAt ||
                                    createZoomMeetingMutation.isPending
                                }
                            >
                                {createZoomMeetingMutation.isPending
                                    ? "Creating..."
                                    : "Create Appointment"}
                            </Button>
                        )}
                    </DialogFooter>
                </DialogContent>
            </Dialog>

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

            <ProposeMatchDialog
                open={proposeMatchOpen}
                onOpenChange={setProposeMatchOpen}
                surrogateId={surrogateData.id}
                surrogateName={surrogateData.full_name}
            />

            <LogContactAttemptDialog
                open={contactAttemptDialogOpen}
                onOpenChange={setContactAttemptDialogOpen}
                surrogateId={surrogateData.id}
                surrogateName={surrogateData.full_name}
            />

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
