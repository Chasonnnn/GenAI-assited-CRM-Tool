"use client"

import * as React from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { Input } from "@/components/ui/input"
import { Checkbox } from "@/components/ui/checkbox"
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import {
    CopyIcon,
    CheckIcon,
    XIcon,
    ChevronDownIcon,
    ChevronUpIcon,
    FileTextIcon,
    DownloadIcon,
    AlertTriangleIcon,
    SendIcon,
    ClipboardCheckIcon,
    Loader2Icon,
    PencilIcon,
    SaveIcon,
    EditIcon,
    PlusIcon,
    Trash2Icon,
    UploadIcon,
} from "lucide-react"
import { toast } from "sonner"
import {
    useApproveFormSubmission,
    useSurrogateFormSubmission,
    useCreateFormToken,
    useRejectFormSubmission,
    useUpdateSubmissionAnswers,
    useUploadSubmissionFile,
    useDeleteSubmissionFile,
} from "@/lib/hooks/use-forms"
import { exportSubmissionPdf, getSubmissionFileDownloadUrl, type FormSchema } from "@/lib/api/forms"
import { formatLocalDate, parseDateInput } from "@/lib/utils/date"
import { cn } from "@/lib/utils"

interface SurrogateApplicationTabProps {
    surrogateId: string
    formId: string
}

// Format file size for display
function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// Format date for display
function formatDateTime(dateString: string): string {
    const date = new Date(dateString)
    return date.toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    })
}

export function SurrogateApplicationTab({
    surrogateId,
    formId,
}: SurrogateApplicationTabProps) {
    const [baseUrl, setBaseUrl] = React.useState("")

    React.useEffect(() => {
        if (typeof window !== "undefined") {
            setBaseUrl(window.location.origin)
        }
    }, [])

    const {
        data: submission,
        isLoading,
        error: submissionError,
    } = useSurrogateFormSubmission(formId, surrogateId)
    const createTokenMutation = useCreateFormToken()
    const approveMutation = useApproveFormSubmission()
    const rejectMutation = useRejectFormSubmission()
    const updateAnswersMutation = useUpdateSubmissionAnswers()
    const uploadFileMutation = useUploadSubmissionFile()
    const deleteFileMutation = useDeleteSubmissionFile()
    const fileInputRef = React.useRef<HTMLInputElement>(null)
    const [deletingFileId, setDeletingFileId] = React.useState<string | null>(null)
    const [isEditMode, setIsEditMode] = React.useState(false)
    const [isExporting, setIsExporting] = React.useState(false)

    // Section collapse state
    const [sectionOpen, setSectionOpen] = React.useState<Record<number, boolean>>({})
    const [filesOpen, setFilesOpen] = React.useState(true)

    // Inline editing state
    const [editingField, setEditingField] = React.useState<string | null>(null)
    const [editedValues, setEditedValues] = React.useState<Record<string, unknown>>({})

    // Modal state
    const [rejectModalOpen, setRejectModalOpen] = React.useState(false)
    const [approveModalOpen, setApproveModalOpen] = React.useState(false)
    const [sendFormModalOpen, setSendFormModalOpen] = React.useState(false)

    // Form state
    const [rejectReason, setRejectReason] = React.useState("")
    const [approveNotes, setApproveNotes] = React.useState("")
    const [formLinkCopied, setFormLinkCopied] = React.useState(false)
    const [formLink, setFormLink] = React.useState("")

    // Loading state for actions
    const [isApproving, setIsApproving] = React.useState(false)
    const [isRejecting, setIsRejecting] = React.useState(false)
    const [isGeneratingLink, setIsGeneratingLink] = React.useState(false)

    React.useEffect(() => {
        if (!submission?.schema_snapshot?.pages) return
        const initialState: Record<number, boolean> = {}
        submission.schema_snapshot.pages.forEach((_page, index) => {
            initialState[index] = true
        })
        setSectionOpen(initialState)
    }, [submission?.schema_snapshot])

    const copyFormLink = async () => {
        if (!formLink) {
            toast.error("Generate a form link first")
            return
        }
        await navigator.clipboard.writeText(formLink)
        setFormLinkCopied(true)
        toast.success("Form link copied to clipboard")
        setTimeout(() => setFormLinkCopied(false), 2000)
    }

    const handleApprove = async () => {
        if (!submission) return
        setIsApproving(true)
        try {
            await approveMutation.mutateAsync({
                submissionId: submission.id,
                reviewNotes: approveNotes.trim() || null,
            })
            toast.success("Application approved and surrogate updated")
            setApproveModalOpen(false)
            setApproveNotes("")
        } catch {
            toast.error("Failed to approve application")
        } finally {
            setIsApproving(false)
        }
    }

    const handleReject = async () => {
        if (!rejectReason.trim() || !submission) return
        setIsRejecting(true)
        try {
            await rejectMutation.mutateAsync({
                submissionId: submission.id,
                reviewNotes: rejectReason.trim(),
            })
            toast.success("Application rejected")
            setRejectModalOpen(false)
            setRejectReason("")
        } catch {
            toast.error("Failed to reject application")
        } finally {
            setIsRejecting(false)
        }
    }

    const handleGenerateFormLink = async () => {
        setIsGeneratingLink(true)
        try {
            const token = await createTokenMutation.mutateAsync({
                formId,
                surrogateId,
                expiresInDays: 14,
            })
            const link = baseUrl ? `${baseUrl}/apply/${token.token}` : `/apply/${token.token}`
            setFormLink(link)
            setFormLinkCopied(false)
            setSendFormModalOpen(true)
        } catch {
            toast.error("Failed to generate form link")
        } finally {
            setIsGeneratingLink(false)
        }
    }

    const hasEdits = Object.keys(editedValues).length > 0

    const handleSaveEdits = async () => {
        if (!submission || !hasEdits) return
        try {
            const updates = Object.entries(editedValues).map(([field_key, value]) => ({
                field_key,
                value,
            }))
            const result = await updateAnswersMutation.mutateAsync({
                submissionId: submission.id,
                updates,
            })
            toast.success(
                result.surrogate_updates.length > 0
                    ? `Saved changes (updated ${result.surrogate_updates.length} surrogate fields)`
                    : "Saved changes"
            )
            setEditedValues({})
            setEditingField(null)
        } catch {
            toast.error("Failed to save changes")
        }
    }

    const handleCancelEdits = () => {
        setEditedValues({})
        setEditingField(null)
        setIsEditMode(false)
    }

    const handleFieldChange = (fieldKey: string, value: unknown) => {
        setEditedValues(prev => ({ ...prev, [fieldKey]: value }))
    }

    const cancelEditing = () => {
        setEditingField(null)
        // Remove the edited value for this field
        if (editingField) {
            setEditedValues(prev => {
                const next = { ...prev }
                delete next[editingField]
                return next
            })
        }
    }

    const handleExport = async () => {
        if (!submission) return
        setIsExporting(true)
        try {
            await exportSubmissionPdf(submission.id)
            toast.success("Application exported as PDF")
        } catch {
            toast.error("Failed to export application")
        } finally {
            setIsExporting(false)
        }
    }

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (!file || !submission) return

        try {
            await uploadFileMutation.mutateAsync({
                submissionId: submission.id,
                file,
                formId: submission.form_id,
                surrogateId: submission.surrogate_id,
            })
            toast.success(`Uploaded: ${file.name}`)
        } catch {
            toast.error("Failed to upload file")
        } finally {
            if (fileInputRef.current) {
                fileInputRef.current.value = ""
            }
        }
    }

    const handleDeleteFile = async (fileId: string, filename: string) => {
        if (!submission) return

        setDeletingFileId(fileId)
        try {
            await deleteFileMutation.mutateAsync({
                submissionId: submission.id,
                fileId,
                formId: submission.form_id,
                surrogateId: submission.surrogate_id,
            })
            toast.success(`Deleted: ${filename}`)
        } catch {
            toast.error("Failed to delete file")
        } finally {
            setDeletingFileId(null)
        }
    }

    const renderEditField = (
        field: FormSchema["pages"][number]["fields"][number],
        value: unknown,
    ) => {
        if (field.type === "textarea") {
            return (
                <Textarea
                    value={typeof value === "string" ? value : ""}
                    onChange={(e) => handleFieldChange(field.key, e.target.value)}
                    className="min-h-20 text-sm"
                />
            )
        }

        if (field.type === "date") {
            const dateValue = typeof value === "string" ? value : ""
            return (
                <Input
                    type="date"
                    value={dateValue}
                    onChange={(e) => handleFieldChange(field.key, e.target.value)}
                    className="h-8 text-sm"
                />
            )
        }

        if (field.type === "select" || field.type === "radio") {
            return (
                <NativeSelect
                    value={typeof value === "string" ? value : ""}
                    onChange={(e) => handleFieldChange(field.key, e.target.value)}
                    size="sm"
                    className="w-48"
                >
                    <NativeSelectOption value="">Select</NativeSelectOption>
                    {(field.options || []).map((option) => (
                        <NativeSelectOption key={option.value} value={option.value}>
                            {option.label}
                        </NativeSelectOption>
                    ))}
                </NativeSelect>
            )
        }

        if (field.type === "multiselect" || field.type === "checkbox") {
            const selectedValues = Array.isArray(value) ? value : []
            return (
                <div className="flex flex-col gap-2">
                    {(field.options || []).map((option) => {
                        const checked = selectedValues.includes(option.value)
                        return (
                            <label key={option.value} className="flex items-center gap-2 text-sm">
                                <Checkbox
                                    checked={checked}
                                    onCheckedChange={(nextChecked) => {
                                        const isChecked = nextChecked === true
                                        const next = isChecked
                                            ? [...selectedValues, option.value]
                                            : selectedValues.filter((item) => item !== option.value)
                                        handleFieldChange(field.key, next)
                                    }}
                                />
                                <span>{option.label}</span>
                            </label>
                        )
                    })}
                </div>
            )
        }

        const inputType =
            field.type === "email"
                ? "email"
                : field.type === "phone"
                    ? "tel"
                    : field.type === "number"
                        ? "number"
                        : "text"

        return (
            <Input
                type={inputType}
                value={
                    typeof value === "string"
                        ? value
                        : value !== null && value !== undefined
                            ? String(value)
                            : ""
                }
                onChange={(e) => handleFieldChange(field.key, e.target.value)}
                className="h-8 text-sm"
            />
        )
    }

    // Loading state
    if (isLoading) {
        return (
            <Card>
                <CardContent className="flex items-center justify-center py-16">
                    <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                    <span className="ml-2 text-muted-foreground">Loading application...</span>
                </CardContent>
            </Card>
        )
    }

    if (submissionError) {
        return (
            <Card>
                <CardContent className="flex flex-col items-center justify-center py-16 text-center">
                    <AlertTriangleIcon className="h-12 w-12 text-amber-500 mb-4" />
                    <h3 className="text-lg font-semibold mb-2">Unable to load application</h3>
                    <p className="text-sm text-muted-foreground max-w-md">
                        Please refresh the page or try again later.
                    </p>
                </CardContent>
            </Card>
        )
    }

    // Empty state - no submission
    if (!submission) {
        return (
            <Card>
                <CardContent className="flex flex-col items-center justify-center py-16 text-center">
                    <FileTextIcon className="h-16 w-16 text-muted-foreground mb-4" />
                    <h3 className="text-lg font-semibold mb-2">No Application Submitted</h3>
                    <p className="text-sm text-muted-foreground mb-6 max-w-md">
                        This candidate has not yet submitted their application form. Send them a secure form link to get started.
                    </p>
                    <Button
                        className="bg-teal-500 hover:bg-teal-600"
                        onClick={handleGenerateFormLink}
                        disabled={isGeneratingLink}
                    >
                        {isGeneratingLink ? (
                            <Loader2Icon className="h-4 w-4 mr-2 animate-spin" />
                        ) : (
                            <SendIcon className="h-4 w-4 mr-2" />
                        )}
                        Send Form Link
                    </Button>

                    {/* Send Form Modal */}
                    <Dialog open={sendFormModalOpen} onOpenChange={setSendFormModalOpen}>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>Send Application Form</DialogTitle>
                                <DialogDescription>
                                    Generate and copy a secure, unique link for this candidate to complete their application.
                                </DialogDescription>
                            </DialogHeader>
                            <div className="space-y-4">
                                <div className="rounded-lg border p-4 bg-muted/50">
                                    <p className="text-sm font-mono break-all">
                                        {formLink || `${baseUrl || ""}/apply/[token]`}
                                    </p>
                                </div>
                                <div className="flex items-start gap-2 text-sm text-muted-foreground">
                                    <AlertTriangleIcon className="h-4 w-4 mt-0.5 shrink-0" />
                                    <p>
                                        This link is unique to this surrogate and expires in 14 days. The candidate can save their progress
                                        and return later.
                                    </p>
                                </div>
                            </div>
                            <DialogFooter>
                                <Button variant="outline" onClick={() => setSendFormModalOpen(false)}>
                                    Close
                                </Button>
                                <Button onClick={copyFormLink} disabled={!formLink}>
                                    {formLinkCopied ? (
                                        <>
                                            <CheckIcon className="h-4 w-4 mr-2" />
                                            Copied!
                                        </>
                                    ) : (
                                        <>
                                            <CopyIcon className="h-4 w-4 mr-2" />
                                            Copy Link
                                        </>
                                    )}
                                </Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
                </CardContent>
            </Card>
        )
    }

    // Has submission - show application details
    const status = submission.status
    const isPending = status === "pending_review"
    const schema = submission.schema_snapshot as FormSchema | null
    const pages = schema?.pages || []
    const previewFields = pages
        .flatMap((page) => page.fields)
        .filter((field) => field.type !== "file")
        .slice(0, 3)

    const renderFieldValue = (
        field: FormSchema["pages"][number]["fields"][number],
        value: unknown,
    ) => {
        if (value === null || value === undefined || value === "") {
            return <span className="text-sm text-muted-foreground">—</span>
        }
        if (field.type === "date" && typeof value === "string") {
            return <span className="text-sm text-right">{formatLocalDate(parseDateInput(value))}</span>
        }
        if (typeof value === "boolean") {
            return value ? (
                <Badge variant="default" className="bg-green-500 hover:bg-green-500/80">
                    Yes
                </Badge>
            ) : (
                <Badge variant="secondary">No</Badge>
            )
        }
        if (Array.isArray(value)) {
            return value.length ? (
                <span className="text-sm text-right">{value.join(", ")}</span>
            ) : (
                <span className="text-sm text-muted-foreground">—</span>
            )
        }
        return <span className="text-sm text-right">{String(value)}</span>
    }

    const handleDownloadFile = async (fileId: string) => {
        try {
            const response = await getSubmissionFileDownloadUrl(submission.id, fileId)
            window.open(response.download_url, "_blank", "noopener,noreferrer")
        } catch {
            toast.error("Failed to download file")
        }
    }

    return (
        <div className="space-y-4">
            {/* Header Section */}
            <div className="flex items-center justify-between">
                <div className="space-y-1">
                    <div className="flex items-center gap-3">
                        <h2 className="text-xl font-semibold">Application</h2>
                        {status === "pending_review" && (
                            <Badge variant="default" className="bg-amber-500 hover:bg-amber-500/80">
                                Pending Review
                            </Badge>
                        )}
                        {status === "approved" && (
                            <Badge variant="default" className="bg-green-500 hover:bg-green-500/80">
                                Approved
                            </Badge>
                        )}
                        {status === "rejected" && <Badge variant="destructive">Rejected</Badge>}
                    </div>
                    <p className="text-sm text-muted-foreground">
                        Submitted {formatDateTime(submission.submitted_at)}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <Button
                        variant="outline"
                        onClick={handleExport}
                        disabled={isExporting}
                    >
                        {isExporting ? (
                            <Loader2Icon className="h-4 w-4 animate-spin mr-2" />
                        ) : (
                            <DownloadIcon className="h-4 w-4 mr-2" />
                        )}
                        Export
                    </Button>

                    {isEditMode ? (
                        <>
                            <Button variant="ghost" onClick={handleCancelEdits}>
                                Cancel
                            </Button>
                            <Button
                                onClick={handleSaveEdits}
                                disabled={!hasEdits || updateAnswersMutation.isPending}
                                className="bg-primary"
                            >
                                {updateAnswersMutation.isPending ? (
                                    <Loader2Icon className="h-4 w-4 animate-spin mr-2" />
                                ) : (
                                    <SaveIcon className="h-4 w-4 mr-2" />
                                )}
                                Save Changes
                                {hasEdits && (
                                    <Badge variant="secondary" className="ml-2">
                                        {Object.keys(editedValues).length}
                                    </Badge>
                                )}
                            </Button>
                        </>
                    ) : (
                        <Button onClick={() => setIsEditMode(true)}>
                            <EditIcon className="h-4 w-4 mr-2" />
                            Edit
                        </Button>
                    )}
                </div>
            </div>

            {/* Main Content - Collapsible Sections */}
            <div className="grid gap-4 md:grid-cols-2">
                {pages.length === 0 ? (
                    <Card>
                        <CardContent className="py-8 text-center text-sm text-muted-foreground">
                            No schema snapshot available for this submission.
                        </CardContent>
                    </Card>
                ) : (
                    pages.map((page, index) => {
                        const pageTitle = page.title || `Page ${index + 1}`
                        const fields = page.fields.filter((field) => field.type !== "file")
                        const isOpen = sectionOpen[index] ?? true
                        return (
                            <Card key={`${pageTitle}-${index}`}>
                                <Collapsible
                                    open={isOpen}
                                    onOpenChange={(open) =>
                                        setSectionOpen((prev) => ({ ...prev, [index]: open }))
                                    }
                                >
                                    <CardHeader className="pb-3">
                                        <CollapsibleTrigger className="flex items-center justify-between w-full hover:opacity-70 transition-opacity">
                                            <CardTitle>{pageTitle}</CardTitle>
                                            {isOpen ? (
                                                <ChevronUpIcon className="h-4 w-4 text-muted-foreground" />
                                            ) : (
                                                <ChevronDownIcon className="h-4 w-4 text-muted-foreground" />
                                            )}
                                        </CollapsibleTrigger>
                                    </CardHeader>
                                    <CollapsibleContent>
                                        <CardContent className="space-y-3">
                                            {fields.length === 0 ? (
                                                <p className="text-sm text-muted-foreground">
                                                    No fields on this page.
                                                </p>
                                            ) : (
                                                fields.map((field) => {
                                                    const originalValue = submission.answers[field.key]
                                                    const editedValue = editedValues[field.key]
                                                    const isEditing = isEditMode && editingField === field.key
                                                    const hasEdit = editedValue !== undefined
                                                    const displayValue = hasEdit ? editedValue : originalValue

                                                    return (
                                                        <div key={field.key} className="flex justify-between items-start gap-4 group py-1">
                                                            <span className="text-sm text-muted-foreground flex-shrink-0">
                                                                {field.label}
                                                            </span>
                                                            <div className="flex items-center gap-2">
                                                                {isEditing ? (
                                                                    <div className="flex items-center gap-2">
                                                                        {renderEditField(field, editedValue ?? originalValue)}
                                                                        <Button
                                                                            size="sm"
                                                                            variant="ghost"
                                                                            className="h-7 w-7 p-0"
                                                                            onClick={cancelEditing}
                                                                        >
                                                                            <XIcon className="h-3.5 w-3.5" />
                                                                        </Button>
                                                                    </div>
                                                                ) : (
                                                                    <>
                                                                        <span className={cn(
                                                                            hasEdit && "bg-yellow-100 dark:bg-yellow-900/30 px-1.5 py-0.5 rounded"
                                                                        )}>
                                                                            {renderFieldValue(field, displayValue)}
                                                                        </span>
                                                                        {isEditMode && (
                                                                            <Button
                                                                                size="sm"
                                                                                variant="ghost"
                                                                                className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                                                                                onClick={() => setEditingField(field.key)}
                                                                            >
                                                                                <PencilIcon className="h-3 w-3" />
                                                                            </Button>
                                                                        )}
                                                                    </>
                                                                )}
                                                            </div>
                                                        </div>
                                                    )
                                                })
                                            )}
                                        </CardContent>
                                    </CollapsibleContent>
                                </Collapsible>
                            </Card>
                        )
                    })
                )}

                {/* Uploaded Files */}
                <Card>
                    <Collapsible open={filesOpen} onOpenChange={setFilesOpen}>
                        <CardHeader className="pb-3">
                            <div className="flex items-center justify-between w-full">
                                <CollapsibleTrigger className="flex items-center gap-2 hover:opacity-70 transition-opacity">
                                    <CardTitle>Uploaded Files ({submission.files.length})</CardTitle>
                                    {filesOpen ? (
                                        <ChevronUpIcon className="h-4 w-4 text-muted-foreground" />
                                    ) : (
                                        <ChevronDownIcon className="h-4 w-4 text-muted-foreground" />
                                    )}
                                </CollapsibleTrigger>

                                {isEditMode && (
                                    <>
                                        <input
                                            ref={fileInputRef}
                                            type="file"
                                            className="hidden"
                                            onChange={handleFileUpload}
                                            accept="*/*"
                                        />
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="h-8 gap-1.5 text-xs border-dashed border-primary/50 text-primary hover:bg-primary/5 hover:border-primary"
                                            onClick={() => fileInputRef.current?.click()}
                                            disabled={uploadFileMutation.isPending}
                                        >
                                            {uploadFileMutation.isPending ? (
                                                <Loader2Icon className="h-3.5 w-3.5 animate-spin" />
                                            ) : (
                                                <PlusIcon className="h-3.5 w-3.5" />
                                            )}
                                            Upload File
                                        </Button>
                                    </>
                                )}
                            </div>
                        </CardHeader>
                        <CollapsibleContent>
                            <CardContent className="space-y-3">
                                {submission.files.length === 0 ? (
                                    <div className="py-6 text-center">
                                        <UploadIcon className="h-8 w-8 mx-auto mb-2 text-muted-foreground/40" />
                                        <p className="text-sm text-muted-foreground">No files uploaded</p>
                                        {isEditMode && (
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                className="mt-2 text-primary hover:text-primary/80"
                                                onClick={() => fileInputRef.current?.click()}
                                            >
                                                <PlusIcon className="h-4 w-4 mr-1" />
                                                Add a file
                                            </Button>
                                        )}
                                    </div>
                                ) : (
                                    submission.files.map((file) => {
                                        const isDeleting = deletingFileId === file.id
                                        return (
                                            <div
                                                key={file.id}
                                                className={cn(
                                                    "flex items-center justify-between p-3 rounded-lg border transition-all",
                                                    file.quarantined
                                                        ? "border-amber-500/50 bg-amber-500/10"
                                                        : "bg-card hover:bg-accent/50",
                                                    isDeleting && "opacity-50"
                                                )}
                                            >
                                                <div className="flex items-center gap-3 min-w-0 flex-1">
                                                    {file.quarantined ? (
                                                        <AlertTriangleIcon className="h-8 w-8 text-amber-500 shrink-0" />
                                                    ) : (
                                                        <FileTextIcon className="h-8 w-8 text-muted-foreground shrink-0" />
                                                    )}
                                                    <div className="min-w-0">
                                                        <p className="text-sm font-medium truncate">{file.filename}</p>
                                                        <p
                                                            className={cn(
                                                                "text-xs",
                                                                file.quarantined ? "text-amber-600" : "text-muted-foreground"
                                                            )}
                                                        >
                                                            {file.quarantined ? "Virus scan pending..." : formatFileSize(file.file_size)}
                                                        </p>
                                                    </div>
                                                </div>

                                                <div className="flex items-center gap-1 shrink-0">
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-8 w-8"
                                                        disabled={file.quarantined}
                                                        onClick={() => handleDownloadFile(file.id)}
                                                    >
                                                        <DownloadIcon className="h-4 w-4" />
                                                    </Button>

                                                    {isEditMode && (
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                                                            onClick={() => handleDeleteFile(file.id, file.filename)}
                                                            disabled={isDeleting}
                                                        >
                                                            {isDeleting ? (
                                                                <Loader2Icon className="h-4 w-4 animate-spin" />
                                                            ) : (
                                                                <Trash2Icon className="h-4 w-4" />
                                                            )}
                                                        </Button>
                                                    )}
                                                </div>
                                            </div>
                                        )
                                    })
                                )}
                            </CardContent>
                        </CollapsibleContent>
                    </Collapsible>
                </Card>
            </div>

            {/* Action Footer - Only show for Pending Review */}
            {isPending && (
                <div className="sticky bottom-0 border-t bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 p-4 -mx-4 md:-mx-6">
                    <div className="flex items-center justify-end gap-3">
                        {/* Reject Button */}
                        <Button
                            variant="outline"
                            className="text-destructive hover:text-destructive bg-transparent"
                            onClick={() => setRejectModalOpen(true)}
                        >
                            <XIcon className="h-4 w-4 mr-2" />
                            Reject
                        </Button>

                        {/* Approve Button */}
                        <Button
                            className="bg-teal-500 hover:bg-teal-600"
                            onClick={() => setApproveModalOpen(true)}
                        >
                            <ClipboardCheckIcon className="h-4 w-4 mr-2" />
                            Approve & Update Surrogate
                        </Button>
                    </div>
                </div>
            )}

            {/* Reject Modal */}
            <Dialog open={rejectModalOpen} onOpenChange={setRejectModalOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Reject Application</DialogTitle>
                        <DialogDescription>
                            Please provide a reason for rejecting this application.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                        <div>
                            <Label htmlFor="reject-reason">Rejection Reason *</Label>
                            <Textarea
                                id="reject-reason"
                                placeholder="Explain why this application is being rejected..."
                                className="mt-2 min-h-24"
                                value={rejectReason}
                                onChange={(e) => setRejectReason(e.target.value)}
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setRejectModalOpen(false)} disabled={isRejecting}>
                            Cancel
                        </Button>
                        <Button variant="destructive" disabled={!rejectReason.trim() || isRejecting} onClick={handleReject}>
                            {isRejecting && <Loader2Icon className="h-4 w-4 mr-2 animate-spin" />}
                            Reject Application
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Approve Modal */}
            <Dialog open={approveModalOpen} onOpenChange={setApproveModalOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Approve Application</DialogTitle>
                        <DialogDescription>
                            The following Surrogate fields will be updated with information from this application:
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                        <div className="rounded-lg border p-4 space-y-2 text-sm">
                            {previewFields.length === 0 ? (
                                <p className="text-muted-foreground">
                                    Surrogate fields will be updated based on configured mappings.
                                </p>
                            ) : (
                                previewFields.map((field) => (
                                    <div key={field.key} className="flex justify-between">
                                        <span className="text-muted-foreground">{field.label}</span>
                                        {renderFieldValue(field, submission.answers[field.key])}
                                    </div>
                                ))
                            )}
                        </div>
                        <div>
                            <Label htmlFor="approve-notes">Optional Notes</Label>
                            <Textarea
                                id="approve-notes"
                                placeholder="Add any notes about this approval..."
                                className="mt-2 min-h-20"
                                value={approveNotes}
                                onChange={(e) => setApproveNotes(e.target.value)}
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setApproveModalOpen(false)} disabled={isApproving}>
                            Cancel
                        </Button>
                        <Button className="bg-teal-500 hover:bg-teal-600" onClick={handleApprove} disabled={isApproving}>
                            {isApproving && <Loader2Icon className="h-4 w-4 mr-2 animate-spin" />}
                            Approve & Update
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}
