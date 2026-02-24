"use client"

import * as React from "react"
import { createContext, use, useState, useCallback, useMemo, useRef, useEffect } from "react"
import { useRouter, useSelectedLayoutSegment } from "next/navigation"
import { toast } from "sonner"
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
import { ROLE_STAGE_VISIBILITY, type StageType } from "@/lib/constants/stages.generated"
import {
    formatMeetingTimeForInvite,
    toLocalIsoDateTime,
} from "../surrogate-detail-utils"
import type { SurrogateRead } from "@/lib/types/surrogate"
import type { PipelineStage } from "@/lib/api/pipelines"
import type { Queue } from "@/lib/hooks/use-queues"

// ============================================================================
// Types
// ============================================================================

export const TAB_VALUES = [
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
export type TabValue = (typeof TAB_VALUES)[number]

export type ActiveDialog =
    | { type: "none" }
    | { type: "edit_surrogate" }
    | { type: "release_queue" }
    | { type: "zoom_meeting" }
    | { type: "email" }
    | { type: "propose_match" }
    | { type: "log_contact" }
    | { type: "log_interview_outcome" }
    | { type: "change_stage" }

export interface ZoomFormState {
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

export interface SurrogateDetailDataContextValue {
    // Core data
    surrogateId: string
    surrogate: SurrogateRead | null
    isLoading: boolean
    error: Error | null

    // Derived data
    stage: PipelineStage | undefined
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

export interface SurrogateDetailTabsContextValue {
    currentTab: TabValue
    allowedTabs: TabValue[]
    setTab: (tab: TabValue) => void
}

export interface SurrogateDetailDialogContextValue {
    activeDialog: ActiveDialog
    openDialog: (dialog: ActiveDialog) => void
    closeDialog: () => void
}

export interface SurrogateDetailQueueContextValue {
    selectedQueueId: string
    setSelectedQueueId: (id: string) => void
}

export interface SurrogateDetailZoomContextValue {
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

export interface SurrogateDetailActionsContextValue {
    changeStatus: (data: {
        stage_id: string
        reason?: string
        effective_at?: string
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

export type SurrogateDetailLayoutContextValue =
    SurrogateDetailDataContextValue &
    SurrogateDetailTabsContextValue &
    SurrogateDetailDialogContextValue &
    SurrogateDetailQueueContextValue &
    SurrogateDetailZoomContextValue &
    SurrogateDetailActionsContextValue

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

// Legacy combined hook for compatibility with existing imports/tests.
export function useSurrogateDetailLayout(): SurrogateDetailLayoutContextValue {
    return {
        ...useSurrogateDetailData(),
        ...useSurrogateDetailTabs(),
        ...useSurrogateDetailDialogs(),
        ...useSurrogateDetailQueue(),
        ...useSurrogateDetailZoom(),
        ...useSurrogateDetailActions(),
    }
}

// ============================================================================
// Provider
// ============================================================================

interface SurrogateDetailLayoutProviderProps {
    surrogateId: string
    children: React.ReactNode
}

export function SurrogateDetailLayoutProvider({ surrogateId, children }: SurrogateDetailLayoutProviderProps) {
    const router = useRouter()
    const segment = useSelectedLayoutSegment()
    const { user } = useAuth()

    // Tab state
    const canViewProfile = user
        ? ["case_manager", "admin", "developer"].includes(user.role)
        : false

    const allowedTabs = useMemo<TabValue[]>(
        () => (canViewProfile ? [...TAB_VALUES] : TAB_VALUES.filter((tab) => tab !== "profile")),
        [canViewProfile]
    )

    const isTabValue = useCallback(
        (value: string | null): value is TabValue =>
            !!value && allowedTabs.includes(value as TabValue),
        [allowedTabs]
    )

    const resolvedTab: TabValue = isTabValue(segment) ? segment : "overview"
    const currentTab: TabValue = resolvedTab

    const handleTabChange = useCallback(
        (value: string) => {
            const nextTab: TabValue = isTabValue(value) ? value : "overview"
            const basePath = `/surrogates/${surrogateId}`
            const nextUrl = nextTab === "overview" ? basePath : `${basePath}/${nextTab}`
            router.replace(nextUrl, { scroll: false })
        },
        [surrogateId, router, isTabValue]
    )

    useEffect(() => {
        if (segment === "overview" || (segment && !isTabValue(segment))) {
            handleTabChange("overview")
        }
    }, [segment, isTabValue, handleTabChange])

    // Dialog state - consolidated from 7+ booleans
    const [activeDialog, setActiveDialog] = useState<ActiveDialog>({ type: "none" })
    const [selectedQueueId, setSelectedQueueId] = useState("")

    // Zoom form state
    const [zoomForm, setZoomForm] = useState<ZoomFormState>({
        topic: "",
        duration: 30,
        startAt: undefined,
        lastMeetingResult: null,
    })
    const zoomIdempotencyKeyRef = useRef<string | null>(null)

    useEffect(() => {
        if (activeDialog.type !== "zoom_meeting") {
            zoomIdempotencyKeyRef.current = null
        }
    }, [activeDialog])

    const timezoneName = useMemo(() => {
        try {
            return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"
        } catch {
            return "UTC"
        }
    }, [])

    // Data fetching
    const { data: surrogateData, isLoading, error } = useSurrogate(surrogateId)
    const { data: defaultPipeline } = useDefaultPipeline()
    const { data: notes } = useNotes(surrogateId)
    const { data: tasksData } = useTasks({ surrogate_id: surrogateId, exclude_approvals: true })
    const { data: queues = [] } = useQueues(false, {
        enabled: !!user?.role && ["case_manager", "admin", "developer"].includes(user.role),
    })
    const { data: assigneesData = [] } = useAssignees()
    const { data: zoomStatus } = useZoomStatus()

    // Derived data
    const stageOptions = useMemo(() => defaultPipeline?.stages || [], [defaultPipeline])
    const stageById = useMemo(
        () => new Map(stageOptions.map((stage) => [stage.id, stage])),
        [stageOptions]
    )
    const visibleStageOptions = useMemo(() => {
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

    const matchedStage = useMemo(
        () => stageOptions.find((stage) => stage.slug === "matched"),
        [stageOptions]
    )

    const canViewJourney = useMemo(() => {
        if (!surrogateData || !matchedStage) return false
        const currentStage = stageById.get(surrogateData.stage_id)
        if (!currentStage) return false
        return currentStage.order >= matchedStage.order
    }, [surrogateData, matchedStage, stageById])

    useEffect(() => {
        if (segment === "journey" && surrogateData && !canViewJourney) {
            handleTabChange("overview")
        }
    }, [segment, surrogateData, canViewJourney, handleTabChange])

    const stage = surrogateData ? stageById.get(surrogateData.stage_id) : undefined
    const statusLabel = surrogateData?.status_label || stage?.label || "Unknown"
    const statusColor = stage?.color || "#6B7280"
    const noteCount = notes?.length ?? 0
    const taskCount = tasksData?.items?.length ?? 0

    // Permissions
    const canManageQueue = user?.role ? ["case_manager", "admin", "developer"].includes(user.role) : false
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
    const isInQueue = surrogateData?.owner_type === "queue"
    const isOwnedByUser = surrogateData?.owner_type === "user"
    const zoomConnected = !!zoomStatus?.connected
    const isUnassignedQueue = !!(
        surrogateData?.owner_type === "queue" &&
        surrogateData.owner_name === "Unassigned"
    )
    const canClaimSurrogate = !!(
        surrogateData &&
        !surrogateData.is_archived &&
        isInQueue &&
        (canManageQueue || (user?.role === "intake_specialist" && isUnassignedQueue))
    )

    // Set AI context
    useSetAIContext(
        surrogateData
            ? {
                entityType: "surrogate",
                entityId: surrogateData.id,
                entityName: `Surrogate #${surrogateData.surrogate_number} - ${surrogateData.full_name}`,
            }
            : null
    )

    // Mutations
    const changeStatusMutation = useChangeSurrogateStatus()
    const archiveMutation = useArchiveSurrogate()
    const restoreMutation = useRestoreSurrogate()
    const updateSurrogateMutation = useUpdateSurrogate()
    const claimSurrogateMutation = useClaimSurrogate()
    const releaseSurrogateMutation = useReleaseSurrogate()
    const assignSurrogateMutation = useAssignSurrogate()
    const createZoomMeetingMutation = useCreateZoomMeeting()
    const sendZoomInviteMutation = useSendZoomInvite()

    // Dialog actions
    const openDialog = useCallback((dialog: ActiveDialog) => {
        setActiveDialog(dialog)
    }, [])

    const closeDialog = useCallback(() => {
        setActiveDialog({ type: "none" })
    }, [])

    // Zoom form setters
    const setZoomTopic = useCallback((topic: string) => {
        setZoomForm(prev => ({ ...prev, topic }))
    }, [])

    const setZoomDuration = useCallback((duration: number) => {
        setZoomForm(prev => ({ ...prev, duration }))
    }, [])

    const setZoomStartAt = useCallback((startAt: Date | undefined) => {
        setZoomForm(prev => ({ ...prev, startAt }))
    }, [])

    const setZoomLastMeetingResult = useCallback((lastMeetingResult: ZoomFormState["lastMeetingResult"]) => {
        setZoomForm(prev => ({ ...prev, lastMeetingResult }))
    }, [])

    // Actions
    const changeStatus = useCallback(async (data: {
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
        } = { stage_id: data.stage_id }
        if (data.reason) payload.reason = data.reason
        if (data.effective_at) payload.effective_at = data.effective_at
        if (data.delivery_baby_gender !== undefined) {
            payload.delivery_baby_gender = data.delivery_baby_gender
        }
        if (data.delivery_baby_weight !== undefined) {
            payload.delivery_baby_weight = data.delivery_baby_weight
        }

        const result = await changeStatusMutation.mutateAsync({
            surrogateId,
            data: payload,
        })
        closeDialog()

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
                                surrogateId,
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
    }, [surrogateData, canChangeStage, stageById, changeStatusMutation, surrogateId, closeDialog])

    const archiveSurrogate = useCallback(async () => {
        await archiveMutation.mutateAsync(surrogateId)
        router.push("/surrogates")
    }, [archiveMutation, surrogateId, router])

    const restoreSurrogate = useCallback(async () => {
        await restoreMutation.mutateAsync(surrogateId)
    }, [restoreMutation, surrogateId])

    const claimSurrogate = useCallback(async () => {
        await claimSurrogateMutation.mutateAsync(surrogateId)
        toast.success("Surrogate claimed")
    }, [claimSurrogateMutation, surrogateId])

    const releaseSurrogate = useCallback(async () => {
        if (!selectedQueueId) return
        await releaseSurrogateMutation.mutateAsync({ surrogateId, queueId: selectedQueueId })
        closeDialog()
        setSelectedQueueId("")
    }, [releaseSurrogateMutation, surrogateId, selectedQueueId, closeDialog])

    const updateSurrogate = useCallback(async (data: Record<string, unknown>) => {
        await updateSurrogateMutation.mutateAsync({ surrogateId, data })
        closeDialog()
    }, [updateSurrogateMutation, surrogateId, closeDialog])

    const assignSurrogate = useCallback(async (ownerId: string | null) => {
        if (!surrogateData) return
        if (ownerId === null) {
            const defaultQueue = queues.find(q => q.name === "Unassigned")
            if (defaultQueue) {
                await releaseSurrogateMutation.mutateAsync({
                    surrogateId: surrogateData.id,
                    queueId: defaultQueue.id,
                })
            }
        } else {
            await assignSurrogateMutation.mutateAsync({
                surrogateId: surrogateData.id,
                owner_type: "user",
                owner_id: ownerId,
            })
        }
    }, [surrogateData, queues, releaseSurrogateMutation, assignSurrogateMutation])

    const createZoomMeeting = useCallback(async () => {
        if (!zoomForm.startAt || !surrogateData) return

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
                contact_name: surrogateData.full_name,
                idempotency_key: zoomIdempotencyKeyRef.current,
            })
            setZoomLastMeetingResult({
                join_url: result.join_url,
                meeting_id: result.meeting_id,
                password: result.password,
                start_time: formatMeetingTimeForInvite(zoomForm.startAt),
            })
            navigator.clipboard.writeText(result.join_url)
        } catch {
            // Error handled by react-query
        }
    }, [zoomForm, surrogateData, createZoomMeetingMutation, surrogateId, timezoneName, setZoomLastMeetingResult])

    const sendZoomInvite = useCallback(async () => {
        if (!surrogateData?.email || !zoomForm.lastMeetingResult) return

        try {
            await sendZoomInviteMutation.mutateAsync({
                recipient_email: surrogateData.email,
                meeting_id: zoomForm.lastMeetingResult.meeting_id,
                join_url: zoomForm.lastMeetingResult.join_url,
                topic: zoomForm.topic,
                duration: zoomForm.duration,
                contact_name: surrogateData.full_name || "there",
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
    }, [surrogateData, zoomForm, sendZoomInviteMutation, surrogateId, closeDialog, setZoomLastMeetingResult])

    const navigateToList = useCallback(() => {
        router.push("/surrogates")
    }, [router])

    const dataValue: SurrogateDetailDataContextValue = useMemo(() => ({
        surrogateId,
        surrogate: surrogateData || null,
        isLoading,
        error: error || null,

        stage,
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
    }), [
        surrogateId,
        surrogateData,
        isLoading,
        error,
        stage,
        statusLabel,
        statusColor,
        stageOptions,
        visibleStageOptions,
        stageById,
        queues,
        assigneesData,
        noteCount,
        taskCount,
        canViewJourney,
        canViewProfile,
        timezoneName,
        canManageQueue,
        canClaimSurrogate,
        canChangeStage,
        isOwnedByCurrentUser,
        isInQueue,
        isOwnedByUser,
        zoomConnected,
        navigateToList,
    ])

    const tabsValue: SurrogateDetailTabsContextValue = useMemo(() => ({
        currentTab,
        allowedTabs,
        setTab: handleTabChange,
    }), [currentTab, allowedTabs, handleTabChange])

    const dialogValue: SurrogateDetailDialogContextValue = useMemo(() => ({
        activeDialog,
        openDialog,
        closeDialog,
    }), [activeDialog, openDialog, closeDialog])

    const queueValue: SurrogateDetailQueueContextValue = useMemo(() => ({
        selectedQueueId,
        setSelectedQueueId,
    }), [selectedQueueId])

    const zoomValue: SurrogateDetailZoomContextValue = useMemo(() => ({
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
    }), [
        zoomForm,
        setZoomTopic,
        setZoomDuration,
        setZoomStartAt,
        setZoomLastMeetingResult,
        zoomIdempotencyKeyRef,
        createZoomMeeting,
        sendZoomInvite,
        createZoomMeetingMutation.isPending,
        sendZoomInviteMutation.isPending,
    ])

    const actionsValue: SurrogateDetailActionsContextValue = useMemo(() => ({
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
    }), [
        changeStatus,
        archiveSurrogate,
        restoreSurrogate,
        claimSurrogate,
        releaseSurrogate,
        updateSurrogate,
        assignSurrogate,
        changeStatusMutation.isPending,
        archiveMutation.isPending,
        restoreMutation.isPending,
        updateSurrogateMutation.isPending,
        claimSurrogateMutation.isPending,
        releaseSurrogateMutation.isPending,
        assignSurrogateMutation.isPending,
    ])

    return (
        <SurrogateDetailDataContext.Provider value={dataValue}>
            <SurrogateDetailTabsContext.Provider value={tabsValue}>
                <SurrogateDetailDialogContext.Provider value={dialogValue}>
                    <SurrogateDetailQueueContext.Provider value={queueValue}>
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
