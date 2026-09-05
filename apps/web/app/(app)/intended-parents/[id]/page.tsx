"use client"

import { useReducer } from "react"
import { useParams, useRouter } from "next/navigation"
import {
    EMPTY_INTENDED_PARENT_FORM_VALUES,
    buildIntendedParentUpdatePayload,
    type IntendedParentFormValues,
} from "@/components/intended-parents/intended-parent-form-values"
import { IntendedParentClinicCard } from "@/components/intended-parents/IntendedParentClinicCard"
import { TrustInfoCard } from "@/components/intended-parents/TrustInfoCard"
import { EntityActivityTimeline } from "@/components/activity/EntityActivityTimeline"
import { normalizeIntendedParentHistory } from "@/lib/activity-history"
import {
    ContactInformationCard,
    EditIntendedParentDialog,
    IntendedParentHeader,
    IntendedParentLoadingState,
    IntendedParentNotFoundState,
    MaritalStatusCard,
    PartnerCard,
} from "./components/IntendedParentDetailSections"
import {
    useIntendedParent,
    useIntendedParentHistory,
    useUpdateIntendedParent,
    useUpdateIntendedParentStatus,
    useArchiveIntendedParent,
    useRestoreIntendedParent,
    useDeleteIntendedParent,
} from "@/lib/hooks/use-intended-parents"
import { useIntendedParentStatuses } from "@/lib/hooks/use-metadata"
import { useEntityActivity } from "@/lib/hooks/use-entity-activity"
import { useTasks } from "@/lib/hooks/use-tasks"
import { EntityTasksSection } from "@/components/tasks/EntityTasksSection"
import { useSetAIContext } from "@/lib/context/ai-context"
import { ProposeMatchFromIPDialog } from "@/components/matches/ProposeMatchFromIPDialog"
import { ChangeStageModal } from "@/components/surrogates/ChangeStageModal"
import {
    getIntendedParentStageOptionById,
    getIntendedParentStatusLabel,
    getIntendedParentStatusStyle,
    toPipelineStages,
} from "@/lib/intended-parent-stage-utils"
import { getMaritalStatusOptions } from "@/lib/intended-parent-marital-status"
import type { IntendedParent } from "@/lib/types/intended-parent"
import { toast } from "@/components/ui/toast"
import { useAuth } from "@/lib/auth-context"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"
import { IntendedParentDocumentsSection } from "@/components/intended-parents/IntendedParentDocumentsSection"
import { IntendedParentNotesSection } from "@/components/intended-parents/IntendedParentNotesSection"

type IntendedParentDetailState = {
    isEditOpen: boolean
    formData: IntendedParentFormValues
    proposeMatchOpen: boolean
    changeStatusModalOpen: boolean
}

type IntendedParentDetailAction =
    | { type: "edit.open"; formData: IntendedParentFormValues }
    | { type: "edit.close" }
    | { type: "form.update"; field: keyof IntendedParentFormValues; value: IntendedParentFormValues[keyof IntendedParentFormValues] }
    | { type: "proposeMatch.set"; open: boolean }
    | { type: "changeStatus.set"; open: boolean }

const initialDetailState: IntendedParentDetailState = {
    isEditOpen: false,
    formData: EMPTY_INTENDED_PARENT_FORM_VALUES,
    proposeMatchOpen: false,
    changeStatusModalOpen: false,
}

function intendedParentDetailReducer(
    state: IntendedParentDetailState,
    action: IntendedParentDetailAction,
): IntendedParentDetailState {
    switch (action.type) {
        case "edit.open":
            return { ...state, isEditOpen: true, formData: action.formData }
        case "edit.close":
            return { ...state, isEditOpen: false }
        case "form.update":
            return {
                ...state,
                formData: {
                    ...state.formData,
                    [action.field]: action.value,
                },
            }
        case "proposeMatch.set":
            return { ...state, proposeMatchOpen: action.open }
        case "changeStatus.set":
            return { ...state, changeStatusModalOpen: action.open }
    }
}

function buildEditFormValues(ip: IntendedParent): IntendedParentFormValues {
    return {
        full_name: ip.full_name,
        email: ip.email,
        phone: ip.phone || "",
        pronouns: ip.pronouns || "",
        partner_name: ip.partner_name || "",
        partner_email: ip.partner_email || "",
        partner_pronouns: ip.partner_pronouns || "",
        address_line1: ip.address_line1 || "",
        address_line2: ip.address_line2 || "",
        city: ip.city || "",
        state: ip.state || "",
        postal: ip.postal || "",
        ip_clinic_name: ip.ip_clinic_name || "",
        ip_clinic_address_line1: ip.ip_clinic_address_line1 || "",
        ip_clinic_address_line2: ip.ip_clinic_address_line2 || "",
        ip_clinic_city: ip.ip_clinic_city || "",
        ip_clinic_state: ip.ip_clinic_state || "",
        ip_clinic_postal: ip.ip_clinic_postal || "",
        ip_clinic_phone: ip.ip_clinic_phone || "",
        ip_clinic_fax: ip.ip_clinic_fax || "",
        ip_clinic_email: ip.ip_clinic_email || "",
        notes_internal: ip.notes_internal || "",
    }
}

export default function IntendedParentDetailPage() {
    const params = useParams<{ id: string }>()
    const { push } = useRouter()
    const id = params.id

    const [detailState, dispatch] = useReducer(intendedParentDetailReducer, initialDetailState)
    const { user } = useAuth()
    const permissionsQuery = useEffectivePermissions(user?.user_id ?? null)
    const canEdit = user?.role === "developer" || (permissionsQuery.data?.permissions ?? []).includes("edit_intended_parents")

    const canViewTasks = user?.role === "developer" || (permissionsQuery.data?.permissions ?? []).includes("view_tasks")
    const canCreateTasks = user?.role === "developer" || (permissionsQuery.data?.permissions ?? []).includes("create_tasks")

    // Queries
    const { data: ip, isLoading } = useIntendedParent(id)
    const historyQuery = useIntendedParentHistory(id)
    const activityQuery = useEntityActivity("intended_parent", id)
    const stageOptionsQuery = useIntendedParentStatuses()
    const stageOptionsResponse = stageOptionsQuery.data
    const tasksQuery = useTasks(
        { intended_parent_id: id, exclude_approvals: true },
        { enabled: !!id && canViewTasks },
    )

    // Mutations
    const updateMutation = useUpdateIntendedParent()
    const statusMutation = useUpdateIntendedParentStatus()
    const archiveMutation = useArchiveIntendedParent()
    const restoreMutation = useRestoreIntendedParent()
    const deleteMutation = useDeleteIntendedParent()

    // Set AI context for this intended parent
    useSetAIContext(
        ip
            ? {
                entityType: "intended-parent",
                entityId: ip.id,
                entityName: `Intended Parent: ${ip.full_name}`,
            }
            : null
    )

    const statusStages = toPipelineStages(stageOptionsResponse?.statuses)

    const handleEdit = () => {
        if (!ip) return
        dispatch({
            type: "edit.open",
            formData: buildEditFormValues(ip),
        })
    }

    const handleSave = async () => {
        await updateMutation.mutateAsync({
            id,
            data: buildIntendedParentUpdatePayload(detailState.formData),
        })
        dispatch({ type: "edit.close" })
    }

    const updateFormField = <K extends keyof IntendedParentFormValues>(
        field: K,
        value: IntendedParentFormValues[K],
    ) => {
        dispatch({ type: "form.update", field, value })
    }

    const updateDetailField = async (data: Parameters<typeof updateMutation.mutateAsync>[0]["data"]) => {
        await updateMutation.mutateAsync({ id, data })
    }

    const handleStatusChange = async (data: {
        stage_id: string
        reason?: string
        effective_at?: string
        on_hold_follow_up_months?: 1 | 3 | 6 | null
    }): Promise<{ status: "applied" | "pending_approval"; request_id?: string }> => {
        if (!ip) {
            return { status: "applied" }
        }
        const previousStageId = ip.stage_id
        const targetStage = getIntendedParentStageOptionById(
            stageOptionsResponse?.statuses,
            data.stage_id,
        )
        const targetLabel = targetStage?.label ?? "Stage"
        const payload: { stage_id: string; reason?: string; effective_at?: string } = {
            stage_id: data.stage_id,
        }
        if (data.reason) payload.reason = data.reason
        if (data.effective_at) payload.effective_at = data.effective_at

        const result = await statusMutation.mutateAsync({ id, data: payload })
        dispatch({ type: "changeStatus.set", open: false })

        const response: { status: "applied" | "pending_approval"; request_id?: string } = {
            status: result.status,
        }
        if (result.request_id) response.request_id = result.request_id

        if (result.status === "applied") {
            toast.success(`Stage updated to ${targetLabel}`, {
                action: {
                    label: "Undo (5 min)",
                    onClick: () => void (async () => {
                        if (!previousStageId) {
                            toast.error("Undo failed")
                            return
                        }
                        try {
                            await statusMutation.mutateAsync({
                                id,
                                data: { stage_id: previousStageId },
                            })
                            toast.success("Stage change undone")
                        } catch (error) {
                            const message =
                                error instanceof Error ? error.message : "Undo failed"
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

    const handleArchive = async () => {
        if (confirm("Are you sure you want to archive this intended parent?")) {
            await archiveMutation.mutateAsync(id)
        }
    }

    const handleRestore = async () => {
        await restoreMutation.mutateAsync(id)
    }

    const handleDelete = async () => {
        if (confirm("This will permanently delete this intended parent. Are you sure?")) {
            await deleteMutation.mutateAsync(id)
            push("/intended-parents")
        }
    }


    if (isLoading) {
        return <IntendedParentLoadingState />
    }

    if (!ip) {
        return <IntendedParentNotFoundState />
    }

    const maritalStatusOptions = getMaritalStatusOptions(ip.marital_status)
    const currentStageLabel = getIntendedParentStatusLabel(
        stageOptionsResponse?.statuses,
        ip.stage_key ?? ip.status,
        ip.status_label,
    )

    return (
        <div className="flex min-h-screen flex-col">
            <IntendedParentHeader
                intendedParent={ip}
                statusLabel={currentStageLabel}
                statusStyle={getIntendedParentStatusStyle(
                    stageOptionsResponse?.statuses,
                    ip.stage_key ?? ip.status,
                )}
                isStatusPending={statusMutation.isPending}
                onProposeMatch={() => dispatch({ type: "proposeMatch.set", open: true })}
                onChangeStage={() => dispatch({ type: "changeStatus.set", open: true })}
                onEdit={handleEdit}
                onArchive={handleArchive}
                onRestore={handleRestore}
                onDelete={handleDelete}
            />

            <div className="min-w-0 flex-1 p-6">
                <div className="mx-auto grid min-w-0 max-w-6xl grid-cols-1 gap-6 lg:grid-cols-3">
                    <div className="min-w-0 space-y-6 lg:col-span-2">
                        <ContactInformationCard
                            intendedParent={ip}
                            onDateOfBirthChange={async (value) => {
                                await updateDetailField({ date_of_birth: value })
                            }}
                        />

                        <PartnerCard
                            intendedParent={ip}
                            onPartnerDateOfBirthChange={async (value) => {
                                await updateDetailField({ partner_date_of_birth: value })
                            }}
                        />

                        <MaritalStatusCard
                            value={ip.marital_status}
                            options={maritalStatusOptions}
                            disabled={updateMutation.isPending}
                            onChange={async (value) => {
                                await updateDetailField({ marital_status: value })
                            }}
                        />

                        <TrustInfoCard
                            intendedParent={ip}
                            onUpdate={async (data) => {
                                await updateDetailField(data)
                            }}
                        />

                        <IntendedParentClinicCard
                            intendedParent={ip}
                            onUpdate={async (data) => {
                                await updateDetailField(data)
                            }}
                        />

                        <IntendedParentNotesSection intendedParentId={id} canEdit={canEdit} />
                        <EntityTasksSection key={id} subject={{ intended_parent_id: id }} record={{ intended_parent_id: id }} canView={canViewTasks} canCreate={canCreateTasks} archived={ip.is_archived} />
                        <IntendedParentDocumentsSection intendedParentId={id} canEdit={canEdit} />
                    </div>

                    <div className="min-w-0 space-y-6">
                        <EntityActivityTimeline
                            currentStageId={ip.stage_id ?? ""}
                            stages={statusStages}
                            stageHistory={normalizeIntendedParentHistory(historyQuery.data ?? [])}
                            activities={activityQuery.data?.items ?? []}
                            tasks={tasksQuery.data?.items ?? []}
                            tasksStatus={
                                tasksQuery.isLoading ? "loading" : tasksQuery.isError ? "error" : "ready"
                            }
                            onRetryTasks={() => { void tasksQuery.refetch() }}
                            status={
                                historyQuery.isLoading || activityQuery.isLoading || stageOptionsQuery.isLoading
                                    ? "loading"
                                    : historyQuery.isError || activityQuery.isError || stageOptionsQuery.isError
                                      ? "error"
                                      : "ready"
                            }
                            onRetry={() => {
                                void historyQuery.refetch()
                                void activityQuery.refetch()
                            }}
                            historyHref={`/intended-parents/${id}/history`}
                        />
                    </div>
                </div>
            </div>

            <ChangeStageModal
                open={detailState.changeStatusModalOpen}
                onOpenChange={(open) => dispatch({ type: "changeStatus.set", open })}
                stages={statusStages}
                currentStageId={ip.stage_id ?? ""}
                currentStageLabel={currentStageLabel}
                entityLabel="Stage"
                canSelfApproveRegression={["admin", "developer"].includes(user?.role ?? "")}
                onSubmit={handleStatusChange}
                isPending={statusMutation.isPending}
            />

            <EditIntendedParentDialog
                open={detailState.isEditOpen}
                values={detailState.formData}
                isPending={updateMutation.isPending}
                onOpenChange={(open) => dispatch(open ? { type: "edit.open", formData: detailState.formData } : { type: "edit.close" })}
                onChange={updateFormField}
                onSave={handleSave}
            />

            <ProposeMatchFromIPDialog
                open={detailState.proposeMatchOpen}
                onOpenChange={(open) => dispatch({ type: "proposeMatch.set", open })}
                intendedParentId={ip.id}
                ipName={ip.full_name}
            />
        </div>
    )
}
