"use client"

import * as React from "react"
import type { Route } from "next"
import { createContext, use, useState, useRef, useEffect } from "react"
import { redirect, useRouter, useSearchParams, useSelectedLayoutSegment } from "next/navigation"
import { toast } from "@/components/ui/toast"
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
import { useAuth } from "@/lib/auth-context"
import {
    canRoleAccessStage,
    getSurrogateStageContext,
    stageHasCapability,
} from "@/lib/surrogate-stage-context"
import {
    formatMeetingTimeForInvite,
    toLocalIsoDateTime,
} from "../surrogate-detail-utils"
import { trackSurrogateViewed } from "@/lib/workflow-metrics"
import type { SurrogateRead } from "@/lib/types/surrogate"
import type { PipelineStage } from "@/lib/api/pipelines"
import type { Queue } from "@/lib/hooks/use-queues"

// ============================================================================
// Types
// ============================================================================

const TAB_VALUES = [
    "overview",
    "emails",
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

type ActiveDialog =
    | { type: "none" }
    | { type: "edit_surrogate" }
    | { type: "release_queue" }
    | { type: "zoom_meeting" }
    | { type: "email" }
    | { type: "propose_match" }
    | { type: "log_contact" }
    | { type: "log_interview_outcome" }
    | { type: "change_stage" }

interface ZoomFormState {
    topic: string
    duration: number
    startAt: Date | undefined
    lastMeetingResult: {
        join_url: string
        meeting_id: number
        password: string | null
        start_time: string | null
    } | null
}

interface SurrogateDetailDataContextValue {
    // Core data
    surrogateId: string
    surrogate: SurrogateRead | null
    isLoading: boolean
    error: Error | null

    // Derived data
    stage: PipelineStage | undefined
    effectiveStage: PipelineStage | undefined
    pausedFromStage: PipelineStage | undefined
    statusLabel: string
    statusColor: string
    stageOptions: PipelineStage[]
    visibleStageOptions: PipelineStage[]
    stageById: Map<string, PipelineStage>
    queues: Queue[]
    assignees: { id: string; name: string }[]
    noteCount: number
    taskCount: number
    canViewJourney: boolean
    canViewProfile: boolean
    timezoneName: string
    navigateToList: () => void

    // Permissions
    canManageQueue: boolean
    canClaimSurrogate: boolean
    canChangeStage: boolean
    isOwnedByCurrentUser: boolean
    isInQueue: boolean
    isOwnedByUser: boolean
    zoomConnected: boolean
}

interface SurrogateDetailTabsContextValue {
    currentTab: TabValue
    allowedTabs: TabValue[]
    setTab: (tab: TabValue) => void
}

interface SurrogateDetailDialogContextValue {
    activeDialog: ActiveDialog
    openDialog: (dialog: ActiveDialog) => void
    closeDialog: () => void
}

interface SurrogateDetailQueueContextValue {
    selectedQueueId: string
    setSelectedQueueId: (id: string) => void
}

interface SurrogateDetailZoomContextValue {
    zoomForm: ZoomFormState
    setZoomTopic: (topic: string) => void
    setZoomDuration: (duration: number) => void
    setZoomStartAt: (date: Date | undefined) => void
    setZoomLastMeetingResult: (result: ZoomFormState["lastMeetingResult"]) => void
    zoomIdempotencyKeyRef: React.MutableRefObject<string | null>
    createZoomMeeting: () => Promise<void>
    sendZoomInvite: () => Promise<void>
    isCreateZoomPending: boolean
    isSendZoomInvitePending: boolean
}

interface SurrogateDetailActionsContextValue {
    changeStatus: (data: {
        stage_id: string
        reason?: string
        effective_at?: string
        interview_scheduled_at?: string
        on_hold_follow_up_months?: 1 | 3 | 6 | null
        delivery_baby_gender?: string | null
        delivery_baby_weight?: string | null
    }) => Promise<{ status: "applied" | "pending_approval"; request_id?: string }>
    archiveSurrogate: () => Promise<void>
    restoreSurrogate: () => Promise<void>
    claimSurrogate: () => Promise<void>
    releaseSurrogate: () => Promise<void>
    updateSurrogate: (data: Record<string, unknown>) => Promise<void>
    assignSurrogate: (ownerId: string | null) => Promise<void>

    // Loading states
    isChangeStatusPending: boolean
    isArchivePending: boolean
    isRestorePending: boolean
    isUpdatePending: boolean
    isClaimPending: boolean
    isReleasePending: boolean
    isAssignPending: boolean
}

const DEFAULT_SURROGATES_LIST_PATH = "/surrogates"

const sanitizeInternalReturnTo = (value: string | null) => {
    if (!value) return null
    if (!value.startsWith("/") || value.startsWith("//")) return null
    return value
}

const appendSearchToPath = (path: string, search: string) => {
    return search ? `${path}?${search}` : path
}

const EMPTY_STAGES: PipelineStage[] = []

function getLocalTimezoneName() {
    try {
        return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"
    } catch {
        return "UTC"
    }
}

// ============================================================================
// Context
// ============================================================================

const SurrogateDetailDataContext = createContext<SurrogateDetailDataContextValue | null>(null)
const SurrogateDetailTabsContext = createContext<SurrogateDetailTabsContextValue | null>(null)
const SurrogateDetailDialogContext = createContext<SurrogateDetailDialogContextValue | null>(null)
const SurrogateDetailQueueContext = createContext<SurrogateDetailQueueContextValue | null>(null)
const SurrogateDetailZoomContext = createContext<SurrogateDetailZoomContextValue | null>(null)
const SurrogateDetailActionsContext = createContext<SurrogateDetailActionsContextValue | null>(null)

function useRequiredContext<T>(context: React.Context<T | null>, hookName: string): T {
    const value = use(context)
    if (!value) {
        throw new Error(`${hookName} must be used within a SurrogateDetailLayoutProvider`)
    }
    return value
}

export function useSurrogateDetailData() {
    return useRequiredContext(SurrogateDetailDataContext, "useSurrogateDetailData")
}

export function useSurrogateDetailTabs() {
    return useRequiredContext(SurrogateDetailTabsContext, "useSurrogateDetailTabs")
}

export function useSurrogateDetailDialogs() {
    return useRequiredContext(SurrogateDetailDialogContext, "useSurrogateDetailDialogs")
}

export function useSurrogateDetailQueue() {
    return useRequiredContext(SurrogateDetailQueueContext, "useSurrogateDetailQueue")
}

export function useSurrogateDetailZoom() {
    return useRequiredContext(SurrogateDetailZoomContext, "useSurrogateDetailZoom")
}

export function useSurrogateDetailActions() {
    return useRequiredContext(SurrogateDetailActionsContext, "useSurrogateDetailActions")
}

// ============================================================================
// Provider
// ============================================================================

interface SurrogateDetailLayoutProviderProps {
    surrogateId: string
    children: React.ReactNode
}

export function SurrogateDetailLayoutProvider({ surrogateId, children }: SurrogateDetailLayoutProviderProps) {
    return (
        <React.Suspense fallback={null}>
            <SurrogateDetailLayoutProviderContent surrogateId={surrogateId}>
                {children}
            </SurrogateDetailLayoutProviderContent>
        </React.Suspense>
    )
}

type SurrogateDetailAuthUser = ReturnType<typeof useAuth>["user"]
type SurrogateDetailRouterPush = ReturnType<typeof useRouter>["push"]
type ZoomIdempotencyKeyRef = React.MutableRefObject<string | null>

function canUserViewSurrogateProfile(user: SurrogateDetailAuthUser) {
    return user ? ["case_manager", "admin", "developer"].includes(user.role) : false
}

function useSurrogateDetailTabNavigation({
    surrogateId,
    canViewProfile,
}: {
    surrogateId: string
    canViewProfile: boolean
}) {
    const { push, replace } = useRouter()
    const searchParams = useSearchParams()
    const segment = useSelectedLayoutSegment()
    const detailSearch = searchParams.toString()
    const returnTo = sanitizeInternalReturnTo(searchParams.get("return_to")) ?? DEFAULT_SURROGATES_LIST_PATH
    const allowedTabs: TabValue[] = canViewProfile
        ? [...TAB_VALUES]
        : TAB_VALUES.filter((tab) => tab !== "profile")

    const isTabValue = (value: string | null): value is TabValue =>
        !!value && allowedTabs.includes(value as TabValue)
    const basePath = `/surrogates/${surrogateId}`
    const getTabUrl = (tab: TabValue) => {
        const nextPath = tab === "overview" ? basePath : `${basePath}/${tab}`
        return appendSearchToPath(nextPath, detailSearch)
    }

    if (segment === "overview" || (segment && !isTabValue(segment))) {
        redirect(getTabUrl("overview") as Route)
    }

    const handleTabChange = (value: string) => {
        const nextTab: TabValue = isTabValue(value) ? value : "overview"
        const nextUrl = getTabUrl(nextTab)
        replace(nextUrl as Route, { scroll: false })
    }

    const tabsValue: SurrogateDetailTabsContextValue = {
        currentTab: isTabValue(segment) ? segment : "overview",
        allowedTabs,
        setTab: handleTabChange,
    }

    return { push, returnTo, tabsValue }
}

function useSurrogateDetailDataValue({
    surrogateId,
    user,
    canViewProfile,
    push,
    returnTo,
}: {
    surrogateId: string
    user: SurrogateDetailAuthUser
    canViewProfile: boolean
    push: SurrogateDetailRouterPush
    returnTo: string
}) {
    const timezoneName = getLocalTimezoneName()
    const { data: surrogateData, isLoading, error } = useSurrogate(surrogateId)
    const surrogate = surrogateData || null
    const { data: defaultPipeline } = useDefaultPipeline()
    const { data: notes } = useNotes(surrogateId)
    const { data: tasksData } = useTasks({ surrogate_id: surrogateId, exclude_approvals: true })
    const { data: queues = [] } = useQueues(false, {
        enabled: !!user?.role && ["case_manager", "admin", "developer"].includes(user.role),
    })
    const { data: assigneesData = [] } = useAssignees()
    const { data: zoomStatus } = useZoomStatus()
    const stageOptions = defaultPipeline?.stages ?? EMPTY_STAGES
    const stageById = new Map(stageOptions.map((stage) => [stage.id, stage]))
    const visibleStageOptions = (() => {
        if (!user?.role) return stageOptions
        return stageOptions.filter((stage) =>
            canRoleAccessStage(user.role, stage, defaultPipeline?.feature_config, false)
        )
    })()
    const stageContext = getSurrogateStageContext(surrogate, stageById)
    const canViewJourney = (() => {
        if (!stageContext.effectiveStage) return false
        return stageHasCapability(stageContext.effectiveStage, "locks_match_state")
    })()
    const stage = stageContext.currentStage
    const effectiveStage = stageContext.effectiveStage
    const pausedFromStage = stageContext.pausedFromStage
    const statusLabel = surrogate?.status_label || stage?.label || "Unknown"
    const statusColor = stage?.color || "#6B7280"
    const noteCount = notes?.length ?? 0
    const taskCount = tasksData?.items?.length ?? 0
    const canManageQueue = user?.role ? ["case_manager", "admin", "developer"].includes(user.role) : false
    const isOwnedByCurrentUser = !!(
        surrogate?.owner_type === "user" &&
        user?.user_id &&
        surrogate.owner_id === user.user_id
    )
    const canChangeStage = !!(
        surrogate &&
        !surrogate.is_archived &&
        (["admin", "developer"].includes(user?.role || "") ||
            (user?.role === "case_manager" && isOwnedByCurrentUser) ||
            (user?.role === "intake_specialist" && isOwnedByCurrentUser))
    )
    const isInQueue = surrogate?.owner_type === "queue"
    const isOwnedByUser = surrogate?.owner_type === "user"
    const zoomConnected = !!zoomStatus?.connected
    const canClaimSurrogate = !!(
        surrogate &&
        !surrogate.is_archived &&
        isInQueue &&
        canManageQueue
    )

    useEffect(() => {
        if (!surrogate?.id) return
        trackSurrogateViewed(surrogate.id)
    }, [surrogate?.id])

    useSetAIContext(
        surrogate
            ? {
                entityType: "surrogate",
                entityId: surrogate.id,
                entityName: `Surrogate #${surrogate.surrogate_number} - ${surrogate.full_name}`,
            }
            : null
    )

    const navigateToList = () => {
        push(returnTo as Route)
    }

    const dataValue: SurrogateDetailDataContextValue = {
        surrogateId,
        surrogate,
        isLoading,
        error: error || null,
        stage,
        effectiveStage,
        pausedFromStage,
        statusLabel,
        statusColor,
        stageOptions,
        visibleStageOptions,
        stageById,
        queues,
        assignees: assigneesData,
        noteCount,
        taskCount,
        canViewJourney,
        canViewProfile,
        timezoneName,
        navigateToList,
        canManageQueue,
        canClaimSurrogate,
        canChangeStage,
        isOwnedByCurrentUser,
        isInQueue,
        isOwnedByUser,
        zoomConnected,
    }

    return {
        canChangeStage,
        dataValue,
        queues,
        stageById,
        surrogate,
        timezoneName,
    }
}

function useSurrogateDetailDialogState() {
    const [activeDialog, setActiveDialog] = useState<ActiveDialog>({ type: "none" })
    const [selectedQueueId, setSelectedQueueId] = useState("")
    const zoomIdempotencyKeyRef = useRef<string | null>(null)

    const resetZoomIdempotencyKey = () => {
        zoomIdempotencyKeyRef.current = null
    }

    const openDialog = (dialog: ActiveDialog) => {
        if (dialog.type !== "zoom_meeting") {
            resetZoomIdempotencyKey()
        }
        setActiveDialog(dialog)
    }

    const closeDialog = () => {
        resetZoomIdempotencyKey()
        setActiveDialog({ type: "none" })
    }

    const dialogValue: SurrogateDetailDialogContextValue = {
        activeDialog,
        openDialog,
        closeDialog,
    }
    const queueValue: SurrogateDetailQueueContextValue = {
        selectedQueueId,
        setSelectedQueueId,
    }

    return {
        closeDialog,
        dialogValue,
        queueValue,
        selectedQueueId,
        setSelectedQueueId,
        zoomIdempotencyKeyRef,
    }
}

function useSurrogateDetailZoomValue({
    closeDialog,
    surrogate,
    surrogateId,
    timezoneName,
    zoomIdempotencyKeyRef,
}: {
    closeDialog: () => void
    surrogate: SurrogateRead | null
    surrogateId: string
    timezoneName: string
    zoomIdempotencyKeyRef: ZoomIdempotencyKeyRef
}) {
    const [zoomForm, setZoomForm] = useState<ZoomFormState>({
        topic: "",
        duration: 30,
        startAt: undefined,
        lastMeetingResult: null,
    })
    const createZoomMeetingMutation = useCreateZoomMeeting()
    const sendZoomInviteMutation = useSendZoomInvite()
    const setZoomTopic = (topic: string) => {
        setZoomForm((prev) => ({ ...prev, topic }))
    }
    const setZoomDuration = (duration: number) => {
        setZoomForm((prev) => ({ ...prev, duration }))
    }
    const setZoomStartAt = (startAt: Date | undefined) => {
        setZoomForm((prev) => ({ ...prev, startAt }))
    }
    const setZoomLastMeetingResult = (lastMeetingResult: ZoomFormState["lastMeetingResult"]) => {
        setZoomForm((prev) => ({ ...prev, lastMeetingResult }))
    }

    const createZoomMeeting = async () => {
        if (!zoomForm.startAt || !surrogate) return
        try {
            if (!zoomIdempotencyKeyRef.current) {
                zoomIdempotencyKeyRef.current =
                    typeof crypto !== "undefined" && "randomUUID" in crypto
                        ? crypto.randomUUID()
                        : `${Date.now()}-${Math.random().toString(16).slice(2)}`
            }
            const result = await createZoomMeetingMutation.mutateAsync({
                entity_type: "surrogate",
                entity_id: surrogateId,
                topic: zoomForm.topic,
                start_time: toLocalIsoDateTime(zoomForm.startAt),
                timezone: timezoneName,
                duration: zoomForm.duration,
                contact_name: surrogate.full_name,
                idempotency_key: zoomIdempotencyKeyRef.current,
            })
            setZoomLastMeetingResult({
                join_url: result.join_url,
                meeting_id: result.meeting_id,
                password: result.password,
                start_time: formatMeetingTimeForInvite(zoomForm.startAt),
            })
            void navigator.clipboard.writeText(result.join_url)
        } catch {
            // Error handled by react-query
        }
    }

    const sendZoomInvite = async () => {
        if (!surrogate?.email || !zoomForm.lastMeetingResult) return
        try {
            await sendZoomInviteMutation.mutateAsync({
                recipient_email: surrogate.email,
                meeting_id: zoomForm.lastMeetingResult.meeting_id,
                join_url: zoomForm.lastMeetingResult.join_url,
                topic: zoomForm.topic,
                duration: zoomForm.duration,
                contact_name: surrogate.full_name || "there",
                surrogate_id: surrogateId,
                ...(zoomForm.lastMeetingResult.start_time
                    ? { start_time: zoomForm.lastMeetingResult.start_time }
                    : {}),
                ...(zoomForm.lastMeetingResult.password
                    ? { password: zoomForm.lastMeetingResult.password }
                    : {}),
            })
            closeDialog()
            setZoomLastMeetingResult(null)
        } catch {
            // Error handled by react-query
        }
    }

    const zoomValue: SurrogateDetailZoomContextValue = {
        zoomForm,
        setZoomTopic,
        setZoomDuration,
        setZoomStartAt,
        setZoomLastMeetingResult,
        zoomIdempotencyKeyRef,
        createZoomMeeting,
        sendZoomInvite,
        isCreateZoomPending: createZoomMeetingMutation.isPending,
        isSendZoomInvitePending: sendZoomInviteMutation.isPending,
    }

    return zoomValue
}

function useSurrogateDetailActionsValue({
    canChangeStage,
    closeDialog,
    push,
    queues,
    returnTo,
    selectedQueueId,
    setSelectedQueueId,
    stageById,
    surrogate,
    surrogateId,
}: {
    canChangeStage: boolean
    closeDialog: () => void
    push: SurrogateDetailRouterPush
    queues: Queue[]
    returnTo: string
    selectedQueueId: string
    setSelectedQueueId: (id: string) => void
    stageById: Map<string, PipelineStage>
    surrogate: SurrogateRead | null
    surrogateId: string
}) {
    const changeStatusMutation = useChangeSurrogateStatus()
    const archiveMutation = useArchiveSurrogate()
    const restoreMutation = useRestoreSurrogate()
    const updateSurrogateMutation = useUpdateSurrogate()
    const claimSurrogateMutation = useClaimSurrogate()
    const releaseSurrogateMutation = useReleaseSurrogate()
    const assignSurrogateMutation = useAssignSurrogate()

    const changeStatus = async (data: {
        stage_id: string
        reason?: string
        effective_at?: string
        interview_scheduled_at?: string
        on_hold_follow_up_months?: 1 | 3 | 6 | null
        delivery_baby_gender?: string | null
        delivery_baby_weight?: string | null
    }): Promise<{ status: "applied" | "pending_approval"; request_id?: string }> => {
        if (!surrogate || !canChangeStage) {
            return { status: "applied" }
        }
        const previousStageId = surrogate.stage_id
        const targetStageLabel = stageById.get(data.stage_id)?.label || "Stage"
        const payload: {
            stage_id: string
            reason?: string
            effective_at?: string
            interview_scheduled_at?: string
            on_hold_follow_up_months?: 1 | 3 | 6 | null
            delivery_baby_gender?: string | null
            delivery_baby_weight?: string | null
        } = { stage_id: data.stage_id }
        if (data.reason) payload.reason = data.reason
        if (data.effective_at) payload.effective_at = data.effective_at
        if (data.interview_scheduled_at) payload.interview_scheduled_at = data.interview_scheduled_at
        if (data.on_hold_follow_up_months !== undefined) {
            payload.on_hold_follow_up_months = data.on_hold_follow_up_months
        }
        if (data.delivery_baby_gender !== undefined) {
            payload.delivery_baby_gender = data.delivery_baby_gender
        }
        if (data.delivery_baby_weight !== undefined) {
            payload.delivery_baby_weight = data.delivery_baby_weight
        }
        const result = await changeStatusMutation.mutateAsync({ surrogateId, data: payload })
        closeDialog()
        const response: { status: "applied" | "pending_approval"; request_id?: string } = {
            status: result.status,
        }
        if (result.request_id) response.request_id = result.request_id
        if (result.status === "applied") {
            toast.success(`Stage updated to ${targetStageLabel}`, {
                action: {
                    label: "Undo (5 min)",
                    onClick: () => void (async () => {
                        try {
                            await changeStatusMutation.mutateAsync({
                                surrogateId,
                                data: { stage_id: previousStageId },
                            })
                            toast.success("Stage change undone")
                        } catch (error) {
                            const message = error instanceof Error ? error.message : "Undo failed"
                            toast.error(message)
                        }
                    })(),
                },
                duration: 60000,
            })
        } else {
            toast("Stage change request submitted for approval")
        }
        return response
    }

    const archiveSurrogate = async () => {
        await archiveMutation.mutateAsync(surrogateId)
        push(returnTo as Route)
    }
    const restoreSurrogate = async () => {
        await restoreMutation.mutateAsync(surrogateId)
    }
    const claimSurrogate = async () => {
        await claimSurrogateMutation.mutateAsync(surrogateId)
        toast.success("Surrogate claimed")
    }
    const releaseSurrogate = async () => {
        if (!selectedQueueId) return
        await releaseSurrogateMutation.mutateAsync({ surrogateId, queueId: selectedQueueId })
        closeDialog()
        setSelectedQueueId("")
    }
    const updateSurrogate = async (data: Record<string, unknown>) => {
        await updateSurrogateMutation.mutateAsync({ surrogateId, data })
        closeDialog()
    }
    const assignSurrogate = async (ownerId: string | null) => {
        if (!surrogate) return
        if (ownerId === null) {
            const defaultQueue = queues.find((queue) => queue.name === "Unassigned")
            if (defaultQueue) {
                await releaseSurrogateMutation.mutateAsync({
                    surrogateId: surrogate.id,
                    queueId: defaultQueue.id,
                })
            }
        } else {
            await assignSurrogateMutation.mutateAsync({
                surrogateId: surrogate.id,
                owner_type: "user",
                owner_id: ownerId,
            })
        }
    }

    const actionsValue: SurrogateDetailActionsContextValue = {
        changeStatus,
        archiveSurrogate,
        restoreSurrogate,
        claimSurrogate,
        releaseSurrogate,
        updateSurrogate,
        assignSurrogate,
        isChangeStatusPending: changeStatusMutation.isPending,
        isArchivePending: archiveMutation.isPending,
        isRestorePending: restoreMutation.isPending,
        isUpdatePending: updateSurrogateMutation.isPending,
        isClaimPending: claimSurrogateMutation.isPending,
        isReleasePending: releaseSurrogateMutation.isPending,
        isAssignPending: assignSurrogateMutation.isPending,
    }

    return actionsValue
}

function SurrogateDetailLayoutProviderContent({ surrogateId, children }: SurrogateDetailLayoutProviderProps) {
    const { user } = useAuth()
    const canViewProfile = canUserViewSurrogateProfile(user)
    const navigation = useSurrogateDetailTabNavigation({ surrogateId, canViewProfile })
    const data = useSurrogateDetailDataValue({
        surrogateId,
        user,
        canViewProfile,
        push: navigation.push,
        returnTo: navigation.returnTo,
    })
    const dialogs = useSurrogateDetailDialogState()
    const zoomValue = useSurrogateDetailZoomValue({
        closeDialog: dialogs.closeDialog,
        surrogate: data.surrogate,
        surrogateId,
        timezoneName: data.timezoneName,
        zoomIdempotencyKeyRef: dialogs.zoomIdempotencyKeyRef,
    })
    const actionsValue = useSurrogateDetailActionsValue({
        canChangeStage: data.canChangeStage,
        closeDialog: dialogs.closeDialog,
        push: navigation.push,
        queues: data.queues,
        returnTo: navigation.returnTo,
        selectedQueueId: dialogs.selectedQueueId,
        setSelectedQueueId: dialogs.setSelectedQueueId,
        stageById: data.stageById,
        surrogate: data.surrogate,
        surrogateId,
    })

    return (
        <SurrogateDetailDataContext.Provider value={data.dataValue}>
            <SurrogateDetailTabsContext.Provider value={navigation.tabsValue}>
                <SurrogateDetailDialogContext.Provider value={dialogs.dialogValue}>
                    <SurrogateDetailQueueContext.Provider value={dialogs.queueValue}>
                        <SurrogateDetailZoomContext.Provider value={zoomValue}>
                            <SurrogateDetailActionsContext.Provider value={actionsValue}>
                                {children}
                            </SurrogateDetailActionsContext.Provider>
                        </SurrogateDetailZoomContext.Provider>
                    </SurrogateDetailQueueContext.Provider>
                </SurrogateDetailDialogContext.Provider>
            </SurrogateDetailTabsContext.Provider>
        </SurrogateDetailDataContext.Provider>
    )
}
