"use client"

import { useReducer } from "react"
import { useParams, useRouter } from "next/navigation"
import {
    EMPTY_INTENDED_PARENT_FORM_VALUES,
    buildIntendedParentUpdatePayload,
    type IntendedParentFormValues,
} from "@/components/intended-parents/IntendedParentFormFields"
import { IntendedParentClinicCard } from "@/components/intended-parents/IntendedParentClinicCard"
import { TrustInfoCard } from "@/components/intended-parents/TrustInfoCard"
import { IntendedParentActivityTimeline } from "@/components/intended-parents/IntendedParentActivityTimeline"
import {
    ContactInformationCard,
    EditIntendedParentDialog,
    IntendedParentHeader,
    IntendedParentLoadingState,
    IntendedParentNotFoundState,
    MaritalStatusCard,
    NotesCard,
    PartnerCard,
} from "./components/IntendedParentDetailSections"
import {
    useIntendedParent,
    useIntendedParentHistory,
    useIntendedParentNotes,
    useUpdateIntendedParent,
    useUpdateIntendedParentStatus,
    useArchiveIntendedParent,
    useRestoreIntendedParent,
    useDeleteIntendedParent,
    useCreateIntendedParentNote,
} from "@/lib/hooks/use-intended-parents"
import { useIntendedParentStatuses } from "@/lib/hooks/use-metadata"
import { useTasks } from "@/lib/hooks/use-tasks"
import { useIPAttachments } from "@/lib/hooks/use-attachments"
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
import { parseDateInput } from "@/lib/utils/date"
import { toast } from "sonner"
import { useAuth } from "@/lib/auth-context"

type IntendedParentDetailState = {
    isEditOpen: boolean
    newNote: string
    formData: IntendedParentFormValues
    proposeMatchOpen: boolean
    changeStatusModalOpen: boolean
}

type IntendedParentDetailAction =
    | { type: "edit.open"; formData: IntendedParentFormValues }
    | { type: "edit.close" }
    | { type: "form.update"; field: keyof IntendedParentFormValues; value: IntendedParentFormValues[keyof IntendedParentFormValues] }
    | { type: "note.update"; value: string }
    | { type: "note.clear" }
    | { type: "proposeMatch.set"; open: boolean }
    | { type: "changeStatus.set"; open: boolean }

const initialDetailState: IntendedParentDetailState = {
    isEditOpen: false,
    newNote: "",
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
        case "note.update":
            return { ...state, newNote: action.value }
        case "note.clear":
            return { ...state, newNote: "" }
        case "proposeMatch.set":
            return { ...state, proposeMatchOpen: action.open }
        case "changeStatus.set":
            return { ...state, changeStatusModalOpen: action.open }
    }
}

function formatDetailDate(dateStr?: string | null) {
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

    // Queries
    const { data: ip, isLoading } = useIntendedParent(id)
    const { data: history } = useIntendedParentHistory(id)
    const { data: notes } = useIntendedParentNotes(id)
    const { data: stageOptionsResponse } = useIntendedParentStatuses()
    const { data: tasksData } = useTasks(
        { intended_parent_id: id, exclude_approvals: true },
        { enabled: !!id },
    )
    const { data: attachments } = useIPAttachments(id)

    // Mutations
    const updateMutation = useUpdateIntendedParent()
    const statusMutation = useUpdateIntendedParentStatus()
    const archiveMutation = useArchiveIntendedParent()
    const restoreMutation = useRestoreIntendedParent()
    const deleteMutation = useDeleteIntendedParent()
    const createNoteMutation = useCreateIntendedParentNote()

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

    const handleAddNote = async () => {
        if (!detailState.newNote.trim()) return
        await createNoteMutation.mutateAsync({ id, data: { content: detailState.newNote } })
        dispatch({ type: "note.clear" })
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

            <div className="flex-1 p-6">
                <div className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-3">
                    <div className="space-y-6 lg:col-span-2">
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

                        <NotesCard
                            notes={notes}
                            newNote={detailState.newNote}
                            isPending={createNoteMutation.isPending}
                            onNewNoteChange={(value) => dispatch({ type: "note.update", value })}
                            onAddNote={handleAddNote}
                            formatDate={formatDetailDate}
                        />
                    </div>

                    <div className="space-y-6">
                        <IntendedParentActivityTimeline
                            currentStageId={ip.stage_id ?? ""}
                            stages={statusStages}
                            history={history ?? []}
                            notes={notes ?? []}
                            attachments={attachments ?? []}
                            tasks={tasksData?.items ?? []}
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
