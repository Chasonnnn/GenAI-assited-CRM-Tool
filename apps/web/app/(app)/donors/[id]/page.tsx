"use client"

import { Suspense, useState } from "react"
import type { Route } from "next"
import { useParams, useRouter, useSearchParams } from "next/navigation"
import { Loader2Icon } from "lucide-react"

import { DonorDetailSections } from "./components/DonorDetailSections"
import { DonorFormFields } from "@/components/donors/DonorFormFields"
import type { DonorFormValues } from "@/components/donors/donor-form-values"
import { QueryErrorState } from "@/components/error-state"
import { ChangeStageModal } from "@/components/surrogates/ChangeStageModal"
import { Button } from "@/components/ui/button"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import {
    Dialog,
    DialogContent,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { toast } from "@/components/ui/toast"
import { useAuth } from "@/lib/auth-context"
import { getActiveDonorStages } from "@/lib/donor-stage-utils"
import {
    useDonor,
    useDonorHistory,
    useArchiveDonor,
    useRestoreDonor,
    useUpdateDonor,
    useUpdateDonorStatus,
} from "@/lib/hooks/use-donors"
import { useDefaultPipeline } from "@/lib/hooks/use-pipelines"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"
import { usePermissionCheck } from "@/lib/hooks/use-permission-check"
import { useEntityActivity } from "@/lib/hooks/use-entity-activity"
import { useTasks } from "@/lib/hooks/use-tasks"
import { getDonorPipelineEntityType, type Donor } from "@/lib/types/donor"

const DEFAULT_DONORS_LIST_PATH = "/donors"

function sanitizeDonorReturnTo(value: string | null): string {
    if (!value || value.startsWith("//")) return DEFAULT_DONORS_LIST_PATH
    if (value === DEFAULT_DONORS_LIST_PATH || value.startsWith(`${DEFAULT_DONORS_LIST_PATH}?`)) {
        return value
    }
    return DEFAULT_DONORS_LIST_PATH
}

function toDonorFormValues(donor: Donor): DonorFormValues {
    return {
        donor_type: donor.donor_type,
        full_name: donor.full_name,
        email: donor.email,
        phone: donor.phone ?? "",
        state: donor.state ?? "",
        education: donor.education ?? "",
    }
}

function LoadedDonorDetail({ donor, returnTo }: { donor: Donor; returnTo: string }) {
    const router = useRouter()
    const { user } = useAuth()
    const permissionsQuery = useEffectivePermissions(user?.user_id ?? null)
    const permissions = permissionsQuery.data?.permissions ?? []
    const isDeveloper = user?.role === "developer"
    const canDeleteAnyNote = isDeveloper || user?.role === "admin"
    const canEdit = isDeveloper || permissions.includes("edit_donors")
    const canArchive = isDeveloper || permissions.includes("archive_donors")
    const canChangeStage = isDeveloper || permissions.includes("change_donor_status")
    const canViewTasks = isDeveloper || permissions.includes("view_tasks")
    const canCreateTasks = isDeveloper || permissions.includes("create_tasks")
    const [isEditOpen, setIsEditOpen] = useState(false)
    const [isStageOpen, setIsStageOpen] = useState(false)
    const [isArchiveConfirmOpen, setIsArchiveConfirmOpen] = useState(false)
    const [formValues, setFormValues] = useState<DonorFormValues>(() => toDonorFormValues(donor))
    const updateDonor = useUpdateDonor()
    const updateStatus = useUpdateDonorStatus()
    const archiveDonor = useArchiveDonor()
    const restoreDonor = useRestoreDonor()
    const historyQuery = useDonorHistory(donor.id)
    const activityQuery = useEntityActivity("donor", donor.id)
    const tasksQuery = useTasks(
        { donor_id: donor.id, exclude_approvals: true, per_page: 100 },
        { enabled: canViewTasks },
    )
    const pipelineEntityType = getDonorPipelineEntityType(donor.donor_type)
    const pipelineQuery = useDefaultPipeline(pipelineEntityType)
    const stages = getActiveDonorStages(pipelineQuery.data?.stages)

    const openEdit = () => {
        setFormValues(toDonorFormValues(donor))
        setIsEditOpen(true)
    }

    const openStage = () => {
        setIsStageOpen(true)
    }

    const handleEdit = async () => {
        try {
            await updateDonor.mutateAsync({
                id: donor.id,
                data: {
                    full_name: formValues.full_name.trim(),
                    email: formValues.email.trim(),
                    phone: formValues.phone.trim() || null,
                    state: formValues.state.trim() || null,
                    education: formValues.education.trim() || null,
                },
            })
            setIsEditOpen(false)
            toast.success("Donor updated successfully")
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to update donor")
        }
    }

    const handleStageChange = async (data: {
        stage_id: string
        reason?: string
        effective_at?: string
    }): Promise<{ status: "applied" | "pending_approval"; request_id?: string }> => {
        const previousStageId = donor.stage_id
        const targetLabel = stages.find((stage) => stage.id === data.stage_id)?.label ?? "Stage"
        const result = await updateStatus.mutateAsync({ id: donor.id, data })
        setIsStageOpen(false)

        if (result.status === "applied") {
            toast.success(`Stage updated to ${targetLabel}`, {
                action: {
                    label: "Undo (5 min)",
                    onClick: () => void (async () => {
                        try {
                            await updateStatus.mutateAsync({
                                id: donor.id,
                                data: { stage_id: previousStageId },
                            })
                            toast.success("Stage change undone")
                        } catch (error) {
                            toast.error(error instanceof Error ? error.message : "Undo failed")
                        }
                    })(),
                },
                duration: 60000,
            })
        } else {
            toast("Stage change request submitted for approval")
        }

        return {
            status: result.status,
            ...(result.request_id ? { request_id: result.request_id } : {}),
        }
    }

    // ConfirmDialog keeps the dialog open while this runs and shows a failure inline.
    const handleArchive = async () => {
        await archiveDonor.mutateAsync(donor.id)
        toast.success("Donor archived")
        router.push(returnTo as Route)
    }

    const handleRestore = async () => {
        try {
            await restoreDonor.mutateAsync(donor.id)
            toast.success("Donor restored")
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to restore donor")
        }
    }

    return (
        <>
            <DonorDetailSections
                donor={donor}
                returnTo={returnTo}
                stages={stages}
                history={historyQuery.data ?? []}
                activities={activityQuery.data?.items ?? []}
                tasks={tasksQuery.data?.items ?? []}
                tasksStatus={
                    !canViewTasks
                        ? "ready"
                        : tasksQuery.isLoading
                          ? "loading"
                          : tasksQuery.isError
                            ? "error"
                            : "ready"
                }
                onRetryTasks={() => { void tasksQuery.refetch() }}
                activityStatus={
                    historyQuery.isLoading || activityQuery.isLoading || pipelineQuery.isLoading
                        ? "loading"
                        : historyQuery.isError || activityQuery.isError || pipelineQuery.isError
                          ? "error"
                          : "ready"
                }
                onRetryActivity={() => {
                    void historyQuery.refetch()
                    void activityQuery.refetch()
                }}
                onEdit={openEdit}
                onChangeStage={openStage}
                onArchive={() => setIsArchiveConfirmOpen(true)}
                archiveStatus={archiveDonor.isPending ? "pending" : "idle"}
                onRestore={() => { void handleRestore() }}
                restoreStatus={restoreDonor.isPending ? "pending" : "idle"}
                access={{
                    edit: canEdit,
                    archive: canArchive,
                    changeStage: canChangeStage,
                    viewTasks: canViewTasks,
                    createTasks: canCreateTasks,
                    deleteAnyNote: canDeleteAnyNote,
                }}
                currentUserId={user?.user_id ?? null}
            />

            <ConfirmDialog
                open={isArchiveConfirmOpen}
                onOpenChange={setIsArchiveConfirmOpen}
                title={`Archive donor ${donor.donor_number}?`}
                confirmLabel="Archive donor"
                errorFallback="Couldn't archive this donor. Try again."
                onConfirm={handleArchive}
            />

            <Dialog open={isEditOpen} onOpenChange={setIsEditOpen}>
                <DialogContent size="lg">
                    <form action={handleEdit}>
                        <DialogHeader><DialogTitle>Edit Donor</DialogTitle></DialogHeader>
                        <div className="py-4">
                            <DonorFormFields
                                values={formValues}
                                idPrefix="edit_donor_"
                                showDonorType={false}
                                onChange={(field, value) => {
                                    setFormValues((current) => ({ ...current, [field]: value }))
                                }}
                            />
                        </div>
                        <DialogFooter>
                            <Button type="button" variant="outline" onClick={() => setIsEditOpen(false)}>
                                Cancel
                            </Button>
                            <Button
                                type="submit"
                                disabled={
                                    updateDonor.isPending ||
                                    !formValues.full_name.trim() ||
                                    !formValues.email.trim()
                                }
                            >
                                {updateDonor.isPending ? <Loader2Icon className="mr-2 size-4 animate-spin" /> : null}
                                Save Changes
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>

            <ChangeStageModal
                open={isStageOpen}
                onOpenChange={setIsStageOpen}
                stages={stages}
                currentStageId={donor.stage_id}
                currentStageLabel={donor.status_label}
                canSelfApproveRegression={["admin", "developer"].includes(user?.role ?? "")}
                onSubmit={handleStageChange}
                isPending={updateStatus.isPending}
            />
        </>
    )
}

function DonorLoadError({
    error,
    onRetry,
    isRetrying,
    returnTo,
}: {
    error: unknown
    onRetry: () => void
    isRetrying: boolean
    returnTo: string
}) {
    const { can } = usePermissionCheck()
    // The donors router requires view_donors, so without it the list is denied too.
    const canViewDonors = can("view_donors")
    return (
        <QueryErrorState
            error={error}
            onRetry={onRetry}
            isRetrying={isRetrying}
            title="Couldn't load donor"
            forbidden={{
                description: "Your account does not have permission to view this donor. Ask an admin to update your role or permissions.",
                secondaryHref: canViewDonors ? DEFAULT_DONORS_LIST_PATH : "/dashboard",
                secondaryLabel: canViewDonors ? "Back to Donors" : "Go to Dashboard",
            }}
            notFound={{ title: "Donor not found", backHref: returnTo, backLabel: "Back to Donors" }}
            headingLevel={1}
        />
    )
}

function DonorDetailPageContent() {
    const params = useParams<{ id: string }>()
    const searchParams = useSearchParams()
    const returnTo = sanitizeDonorReturnTo(searchParams.get("return_to"))
    const donorQuery = useDonor(params.id)
    const donor = donorQuery.data

    if (donorQuery.isLoading) {
        return (
            <div className="flex flex-1 items-center justify-center" role="status">
                <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                <span className="ml-2 text-muted-foreground">Loading donor…</span>
            </div>
        )
    }

    if (donorQuery.isError || !donor) {
        return (
            <DonorLoadError
                error={donorQuery.error}
                onRetry={() => { void donorQuery.refetch() }}
                isRetrying={donorQuery.isFetching}
                returnTo={returnTo}
            />
        )
    }

    return <LoadedDonorDetail donor={donor} returnTo={returnTo} />
}

export default function DonorDetailPage() {
    return (
        <Suspense
            fallback={(
                <div className="flex flex-1 items-center justify-center" role="status">
                    <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                    <span className="ml-2 text-muted-foreground">Loading donor…</span>
                </div>
            )}
        >
            <DonorDetailPageContent />
        </Suspense>
    )
}
