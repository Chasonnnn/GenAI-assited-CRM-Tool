"use client"

import { useState } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "@/components/app-link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Textarea } from "@/components/ui/textarea"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { InlineDateField } from "@/components/inline-date-field"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
    ArrowLeftIcon,
    Loader2Icon,
    MoreVerticalIcon,
    MailIcon,
    PhoneIcon,
    MapPinIcon,
    CalendarIcon,
    ArchiveIcon,
    ArchiveRestoreIcon,
    Trash2Icon,
    HeartHandshakeIcon,
    UserIcon,
} from "lucide-react"
import {
    IntendedParentFormFields,
    EMPTY_INTENDED_PARENT_FORM_VALUES,
    buildIntendedParentUpdatePayload,
    type IntendedParentFormValues,
} from "@/components/intended-parents/IntendedParentFormFields"
import { IntendedParentClinicCard } from "@/components/intended-parents/IntendedParentClinicCard"
import { TrustInfoCard } from "@/components/intended-parents/TrustInfoCard"
import { IntendedParentActivityTimeline } from "@/components/intended-parents/IntendedParentActivityTimeline"
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
import { parseDateInput } from "@/lib/utils/date"
import { toast } from "sonner"

export default function IntendedParentDetailPage() {
    const params = useParams<{ id: string }>()
    const router = useRouter()
    const id = params.id

    const [isEditOpen, setIsEditOpen] = useState(false)
    const [newNote, setNewNote] = useState("")
    const [formData, setFormData] = useState<IntendedParentFormValues>(EMPTY_INTENDED_PARENT_FORM_VALUES)
    const [proposeMatchOpen, setProposeMatchOpen] = useState(false)
    const [changeStatusModalOpen, setChangeStatusModalOpen] = useState(false)

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

    const formatDate = (dateStr?: string | null) => {
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

    const handleEdit = () => {
        if (!ip) return
        setFormData({
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
        })
        setIsEditOpen(true)
    }

    const handleSave = async () => {
        await updateMutation.mutateAsync({
            id,
            data: buildIntendedParentUpdatePayload(formData),
        })
        setIsEditOpen(false)
    }

    const updateFormField = <K extends keyof IntendedParentFormValues>(
        field: K,
        value: IntendedParentFormValues[K],
    ) => {
        setFormData((previous) => ({ ...previous, [field]: value }))
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
        setChangeStatusModalOpen(false)

        const response: { status: "applied" | "pending_approval"; request_id?: string } = {
            status: result.status,
        }
        if (result.request_id) response.request_id = result.request_id

        if (result.status === "applied") {
            toast.success(`Stage updated to ${targetLabel}`, {
                action: {
                    label: "Undo (5 min)",
                    onClick: async () => {
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
            router.push("/intended-parents")
        }
    }

    const handleAddNote = async () => {
        if (!newNote.trim()) return
        await createNoteMutation.mutateAsync({ id, data: { content: newNote } })
        setNewNote("")
    }

    if (isLoading) {
        return (
            <div className="flex min-h-screen items-center justify-center">
                <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (!ip) {
        return (
            <div className="flex min-h-screen flex-col items-center justify-center">
                <h1 className="text-2xl font-semibold">Not Found</h1>
                <p className="text-muted-foreground">This intended parent doesn&apos;t exist.</p>
                <Link href="/intended-parents" className="mt-4 inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90">
                    Back to List
                </Link>
            </div>
        )
    }

    const maritalStatusOptions = getMaritalStatusOptions(ip.marital_status)

    return (
        <div className="flex min-h-screen flex-col">
            {/* Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur">
                <div className="flex h-16 items-center justify-between px-6">
                    <div className="flex items-center gap-4">
                        <Link
                            href="/intended-parents"
                            aria-label="Back to intended parents"
                            className="inline-flex items-center justify-center rounded-md border border-input bg-background hover:bg-accent hover:text-accent-foreground size-9"
                        >
                            <ArrowLeftIcon className="size-5" />
                            <span className="sr-only">Back to intended parents</span>
                        </Link>
                        <div>
                            <h1 className="text-2xl font-semibold">{ip.full_name}</h1>
                            <p className="text-sm text-muted-foreground">
                                {ip.intended_parent_number ? `${ip.intended_parent_number} • ` : ""}
                                {ip.email}
                            </p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setProposeMatchOpen(true)}
                            disabled={ip.is_archived}
                        >
                            <HeartHandshakeIcon className="size-4 mr-2" />
                            Propose Match
                        </Button>
                        <Button
                            variant="outline"
                            onClick={() => setChangeStatusModalOpen(true)}
                            disabled={statusMutation.isPending || ip.is_archived}
                        >
                            Change Stage
                        </Button>
                        <Badge
                            variant="outline"
                            style={getIntendedParentStatusStyle(
                                stageOptionsResponse?.statuses,
                                ip.stage_key ?? ip.status,
                            )}
                        >
                            {getIntendedParentStatusLabel(
                                stageOptionsResponse?.statuses,
                                ip.stage_key ?? ip.status,
                                ip.status_label,
                            )}
                        </Badge>
                        <DropdownMenu>
                            <DropdownMenuTrigger
                                aria-label={`Actions for ${ip.full_name}`}
                                className="inline-flex items-center justify-center size-10 rounded-md border border-input bg-background hover:bg-accent hover:text-accent-foreground"
                            >
                                <MoreVerticalIcon className="size-4" />
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                                <DropdownMenuItem onClick={handleEdit}>Edit</DropdownMenuItem>
                                <DropdownMenuSeparator />
                                {!ip.is_archived ? (
                                    <DropdownMenuItem onClick={handleArchive}>
                                        <ArchiveIcon className="mr-2 size-4" /> Archive
                                    </DropdownMenuItem>
                                ) : (
                                    <>
                                        <DropdownMenuItem onClick={handleRestore}>
                                            <ArchiveRestoreIcon className="mr-2 size-4" /> Restore
                                        </DropdownMenuItem>
                                        <DropdownMenuItem onClick={handleDelete} className="text-destructive">
                                            <Trash2Icon className="mr-2 size-4" /> Delete Permanently
                                        </DropdownMenuItem>
                                    </>
                                )}
                            </DropdownMenuContent>
                        </DropdownMenu>
                    </div>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 p-6">
                <div className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-3">
                    {/* Left Column - Details */}
                    <div className="space-y-6 lg:col-span-2">
                        {/* Contact Info */}
                        <Card>
                            <CardHeader>
                                <CardTitle>Contact Information</CardTitle>
                            </CardHeader>
                            <CardContent className="grid gap-4 sm:grid-cols-2">
                                <div className="flex items-center gap-3">
                                    <MailIcon className="size-5 text-muted-foreground" />
                                    <div>
                                        <p className="text-sm text-muted-foreground">Email</p>
                                        <p className="font-medium">{ip.email}</p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3">
                                    <PhoneIcon className="size-5 text-muted-foreground" />
                                    <div>
                                        <p className="text-sm text-muted-foreground">Phone</p>
                                        <p className="font-medium">{ip.phone || "Not provided"}</p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3">
                                    <UserIcon className="size-5 text-muted-foreground" />
                                    <div>
                                        <p className="text-sm text-muted-foreground">Pronouns</p>
                                        <p className="font-medium">{ip.pronouns || "Not provided"}</p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3">
                                    <CalendarIcon className="size-5 text-muted-foreground" />
                                    <div>
                                        <p className="text-sm text-muted-foreground">Date of Birth</p>
                                        <InlineDateField
                                            value={ip.date_of_birth}
                                            onSave={async (value) => {
                                                await updateDetailField({ date_of_birth: value })
                                            }}
                                            placeholder="Not provided"
                                            label="Date of Birth"
                                        />
                                    </div>
                                </div>
                                <div className="flex items-center gap-3">
                                    <MapPinIcon className="size-5 text-muted-foreground" />
                                    <div>
                                        <p className="text-sm text-muted-foreground">Address</p>
                                        <p className="font-medium">
                                            {[ip.address_line1, ip.address_line2, ip.city, ip.state, ip.postal]
                                                .filter(Boolean)
                                                .join(", ") || "Not provided"}
                                        </p>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader>
                                <CardTitle>Marital Status</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <Select
                                    value={ip.marital_status ?? "__none__"}
                                    onValueChange={async (value) => {
                                        await updateDetailField({
                                            marital_status: value === "__none__" ? null : value,
                                        })
                                    }}
                                    disabled={updateMutation.isPending}
                                >
                                    <SelectTrigger aria-label="Marital status" className="w-full sm:w-[240px]">
                                        <SelectValue placeholder="Not provided">
                                            {(value: string | null) =>
                                                maritalStatusOptions.find((option) => option.value === value)?.label ??
                                                "Not provided"
                                            }
                                        </SelectValue>
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="__none__">Not provided</SelectItem>
                                        {maritalStatusOptions.map((option) => (
                                            <SelectItem key={option.value} value={option.value}>
                                                {option.label}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </CardContent>
                        </Card>

                        <TrustInfoCard
                            intendedParent={ip}
                            onUpdate={async (data) => {
                                await updateDetailField(data)
                            }}
                        />

                        {/* Partner Info */}
                        {(ip.partner_name ||
                            ip.partner_email ||
                            ip.partner_pronouns ||
                            ip.partner_date_of_birth) && (
                            <Card>
                                <CardHeader>
                                    <CardTitle>Partner</CardTitle>
                                </CardHeader>
                                <CardContent className="grid gap-4 sm:grid-cols-2">
                                    <div className="flex items-center gap-3">
                                        <UserIcon className="size-5 text-muted-foreground" />
                                        <div>
                                            <p className="text-sm text-muted-foreground">Name</p>
                                            <p className="font-medium">{ip.partner_name || "Not provided"}</p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <MailIcon className="size-5 text-muted-foreground" />
                                        <div>
                                            <p className="text-sm text-muted-foreground">Email</p>
                                            <p className="font-medium">{ip.partner_email || "Not provided"}</p>
                                        </div>
                                    </div>
                                    {ip.partner_pronouns && (
                                        <div className="flex items-center gap-3">
                                            <UserIcon className="size-5 text-muted-foreground" />
                                            <div>
                                                <p className="text-sm text-muted-foreground">Pronouns</p>
                                                <p className="font-medium">{ip.partner_pronouns}</p>
                                            </div>
                                        </div>
                                    )}
                                    <div className="flex items-center gap-3">
                                        <CalendarIcon className="size-5 text-muted-foreground" />
                                        <div>
                                            <p className="text-sm text-muted-foreground">Date of Birth</p>
                                            <InlineDateField
                                                value={ip.partner_date_of_birth}
                                                onSave={async (value) => {
                                                    await updateDetailField({ partner_date_of_birth: value })
                                                }}
                                                placeholder="Not provided"
                                                label="Partner date of birth"
                                            />
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        )}

                        <IntendedParentClinicCard
                            intendedParent={ip}
                            onUpdate={async (data) => {
                                await updateDetailField(data)
                            }}
                        />

                        {/* Notes */}
                        <Card>
                            <CardHeader>
                                <CardTitle>Notes</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="flex gap-2">
                                    <Textarea
                                        placeholder="Add a note..."
                                        value={newNote}
                                        onChange={(e) => setNewNote(e.target.value)}
                                        rows={2}
                                    />
                                    <Button
                                        onClick={handleAddNote}
                                        disabled={!newNote.trim() || createNoteMutation.isPending}
                                        className="bg-teal-600 hover:bg-teal-700"
                                    >
                                        Add
                                    </Button>
                                </div>
                                <Separator />
                                {notes?.length ? (
                                    <div className="space-y-3">
                                        {notes.map((note) => (
                                            <div key={note.id} className="rounded-lg border p-3">
                                                <div
                                                    className="text-sm prose prose-sm max-w-none dark:prose-invert"
                                                    dangerouslySetInnerHTML={{ __html: note.content }}
                                                />
                                                <p className="mt-2 text-xs text-muted-foreground">
                                                    {formatDate(note.created_at)}
                                                </p>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-sm text-muted-foreground">No notes yet.</p>
                                )}
                            </CardContent>
                        </Card>
                    </div>

                    {/* Right Column - History */}
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
                open={changeStatusModalOpen}
                onOpenChange={setChangeStatusModalOpen}
                stages={statusStages}
                currentStageId={ip.stage_id ?? ""}
                currentStageLabel={getIntendedParentStatusLabel(
                    stageOptionsResponse?.statuses,
                    ip.stage_key ?? ip.status,
                    ip.status_label,
                )}
                entityLabel="Stage"
                onSubmit={handleStatusChange}
                isPending={statusMutation.isPending}
            />

            {/* Edit Modal */}
            <Dialog open={isEditOpen} onOpenChange={setIsEditOpen}>
                <DialogContent className="max-w-lg">
                    <DialogHeader>
                        <DialogTitle>Edit Intended Parent</DialogTitle>
                        <DialogDescription>Update the intended parent details</DialogDescription>
                    </DialogHeader>
                    <IntendedParentFormFields
                        values={formData}
                        onChange={updateFormField}
                        idPrefix="edit_"
                        showClinicSection={false}
                        showInternalNotes={false}
                    />
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsEditOpen(false)}>
                            Cancel
                        </Button>
                        <Button
                            className="bg-teal-600 hover:bg-teal-700"
                            onClick={handleSave}
                            disabled={updateMutation.isPending}
                        >
                            {updateMutation.isPending && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                            Save Changes
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Propose Match Dialog */}
            <ProposeMatchFromIPDialog
                open={proposeMatchOpen}
                onOpenChange={setProposeMatchOpen}
                intendedParentId={ip.id}
                ipName={ip.full_name}
            />
        </div>
    )
}
