"use client"

import * as React from "react"
import { AlertTriangleIcon, CheckCircle2Icon, ClockIcon, Loader2Icon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import type { Attachment } from "@/lib/api/attachments"
import { useAttachments, useUploadAttachment } from "@/lib/hooks/use-attachments"

const EMAIL_ATTACHMENTS_MAX_COUNT = 10
const EMAIL_ATTACHMENTS_MAX_TOTAL_BYTES = 18 * 1024 * 1024

const MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024
const ALLOWED_EXTENSIONS = new Set(["pdf", "png", "jpg", "jpeg", "doc", "docx", "xls", "xlsx"])

const ACCEPTED_FILE_TYPES: Record<string, string[]> = {
    "application/pdf": [".pdf"],
    "image/png": [".png"],
    "image/jpeg": [".jpg", ".jpeg"],
    "application/msword": [".doc"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
    "application/vnd.ms-excel": [".xls"],
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
}

export interface EmailAttachmentSelectionState {
    selectedAttachmentIds: string[]
    hasBlockingAttachments: boolean
    totalBytes: number
    errorMessage: string | null
}

interface EmailAttachmentsPanelProps {
    surrogateId: string
    onSelectionChange: (state: EmailAttachmentSelectionState) => void
    hideUI?: boolean
    ref?: React.Ref<EmailAttachmentsPanelHandle>
}

export interface EmailAttachmentsPanelHandle {
    uploadFiles: (files: File[]) => Promise<void>
}

function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function getScanBadge(attachment: Attachment) {
    if (attachment.quarantined || attachment.scan_status === "pending") {
        return (
            <Badge variant="outline" className="text-yellow-700 border-yellow-300 bg-yellow-50">
                <ClockIcon className="size-3 mr-1" />
                Scanning
            </Badge>
        )
    }

    if (attachment.scan_status === "clean") {
        return (
            <Badge variant="outline" className="text-green-700 border-green-300 bg-green-50">
                <CheckCircle2Icon className="size-3 mr-1" />
                Clean
            </Badge>
        )
    }

    return (
        <Badge variant="destructive">
            <AlertTriangleIcon className="size-3 mr-1" />
            {attachment.scan_status === "infected" ? "Infected" : "Scan Error"}
        </Badge>
    )
}

export function EmailAttachmentsPanel({
    surrogateId,
    onSelectionChange,
    hideUI = false,
    ref,
}: EmailAttachmentsPanelProps) {
    const { data: attachments = [], isLoading } = useAttachments(surrogateId)
    const uploadMutation = useUploadAttachment()
    const fileInputRef = React.useRef<HTMLInputElement | null>(null)
    const fileInputId = React.useId()

    const [selectedAttachmentIds, setSelectedAttachmentIds] = React.useState<string[]>([])
    const [uploadError, setUploadError] = React.useState<string | null>(null)
    const onSelectionChangeRef = React.useRef(onSelectionChange)
    onSelectionChangeRef.current = onSelectionChange

    const selectedAttachmentIdSet = React.useMemo(
        () => new Set(selectedAttachmentIds),
        [selectedAttachmentIds],
    )

    const selectedAttachments = React.useMemo(
        () => attachments.filter((attachment) => selectedAttachmentIdSet.has(attachment.id)),
        [attachments, selectedAttachmentIdSet]
    )

    const totalBytes = React.useMemo(
        () => selectedAttachments.reduce((sum, attachment) => sum + attachment.file_size, 0),
        [selectedAttachments]
    )

    const hasPendingOrUnsafeSelection = React.useMemo(
        () =>
            selectedAttachments.some(
                (attachment) => attachment.quarantined || attachment.scan_status !== "clean"
            ),
        [selectedAttachments]
    )

    const overCountLimit = selectedAttachmentIds.length > EMAIL_ATTACHMENTS_MAX_COUNT
    const overSizeLimit = totalBytes > EMAIL_ATTACHMENTS_MAX_TOTAL_BYTES
    const hasBlockingAttachments = hasPendingOrUnsafeSelection || overCountLimit || overSizeLimit

    const constraintError = React.useMemo(() => {
        if (overCountLimit) {
            return `You can attach at most ${EMAIL_ATTACHMENTS_MAX_COUNT} files.`
        }
        if (overSizeLimit) {
            return `Total attachment size exceeds ${(EMAIL_ATTACHMENTS_MAX_TOTAL_BYTES / (1024 * 1024)).toFixed(0)} MiB.`
        }
        if (hasPendingOrUnsafeSelection) {
            return "All selected attachments must be clean before sending."
        }
        return null
    }, [hasPendingOrUnsafeSelection, overCountLimit, overSizeLimit])

    const visibleError = uploadError || constraintError

    React.useEffect(() => {
        onSelectionChangeRef.current({
            selectedAttachmentIds,
            hasBlockingAttachments,
            totalBytes,
            errorMessage: visibleError,
        })
    }, [selectedAttachmentIds, hasBlockingAttachments, totalBytes, visibleError])

    const toggleSelection = React.useCallback((attachmentId: string, checked: boolean) => {
        setSelectedAttachmentIds((current) => {
            if (checked) {
                return Array.from(new Set([...current, attachmentId]))
            }
            return current.filter((id) => id !== attachmentId)
        })
    }, [])

    const uploadFiles = React.useCallback(
        async (incomingFiles: File[]) => {
            setUploadError(null)
            const validFiles: File[] = []
            const validationErrors: string[] = []

            for (const file of incomingFiles) {
                const ext = file.name.split(".").pop()?.toLowerCase() ?? ""
                if (!ALLOWED_EXTENSIONS.has(ext)) {
                    validationErrors.push(`File type .${ext || "unknown"} is not allowed.`)
                    continue
                }
                if (file.size > MAX_UPLOAD_SIZE_BYTES) {
                    validationErrors.push("File exceeds 25 MB limit.")
                    continue
                }

                validFiles.push(file)
            }

            if (validationErrors.length > 0) {
                setUploadError(validationErrors[0] ?? "One or more files could not be uploaded.")
            }

            const uploadResults = await Promise.all(
                validFiles.map(async (file) => {
                    try {
                        const uploaded = await uploadMutation.mutateAsync({ surrogateId, file })
                        return { id: uploaded.id, error: null }
                    } catch (error) {
                        return {
                            id: null,
                            error: error instanceof Error ? error.message : "Upload failed.",
                        }
                    }
                }),
            )

            const uploadedIds: string[] = []
            for (const result of uploadResults) {
                if (result.id) uploadedIds.push(result.id)
            }
            const firstUploadError = uploadResults.find((result) => result.error)?.error

            if (firstUploadError) {
                setUploadError(firstUploadError)
            }

            if (uploadedIds.length > 0) {
                setSelectedAttachmentIds((current) => Array.from(new Set([...current, ...uploadedIds])))
            }
        },
        [surrogateId, uploadMutation]
    )

    React.useImperativeHandle(
        ref,
        () => ({
            uploadFiles,
        }),
        [uploadFiles]
    )

    const handlePickFiles = React.useCallback(() => {
        fileInputRef.current?.click()
    }, [])

    const handleInputChange = React.useCallback(
        (event: React.ChangeEvent<HTMLInputElement>) => {
            const files = event.target.files ? Array.from(event.target.files) : []
            if (files.length > 0) {
                void uploadFiles(files)
            }
            event.target.value = ""
        },
        [uploadFiles]
    )

    if (hideUI) {
        return null
    }

    return (
        <div className="grid gap-3">
            <div className="flex items-start justify-between gap-3">
                <div>
                    <Label htmlFor={fileInputId}>Attachments</Label>
                    <p className="text-xs text-muted-foreground mt-1">
                        Drag files into the message body, or pick files from your device.
                    </p>
                </div>
                <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={handlePickFiles}
                    disabled={uploadMutation.isPending}
                >
                    Attach files
                </Button>
                <input
                    id={fileInputId}
                    name="email_attachments"
                    ref={fileInputRef}
                    type="file"
                    multiple
                    className="sr-only"
                    onChange={handleInputChange}
                    accept={Object.values(ACCEPTED_FILE_TYPES)
                        .flat()
                        .join(",")}
                />
            </div>
            <p className="text-xs text-muted-foreground">
                Allowed: PDF, images, Word, and Excel files (max 25 MB each).
            </p>

            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span>{selectedAttachmentIds.length} selected</span>
                <span>&#8226;</span>
                <span>{formatFileSize(totalBytes)}</span>
                {uploadMutation.isPending && (
                    <>
                        <span>&#8226;</span>
                        <span className="inline-flex items-center gap-1">
                            <Loader2Icon className="size-3 animate-spin" />
                            Uploading&hellip;
                        </span>
                    </>
                )}
            </div>

            {visibleError && (
                <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive inline-flex items-center gap-2">
                    <AlertTriangleIcon className="size-3.5" />
                    {visibleError}
                </div>
            )}

            {isLoading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2Icon className="size-4 animate-spin" />
                    Loading attachments&hellip;
                </div>
            ) : attachments.length === 0 ? (
                <p className="text-sm text-muted-foreground">No attachments yet.</p>
            ) : (
                <div className="max-h-44 overflow-y-auto rounded-md border">
                    {attachments.map((attachment) => {
                        const checked = selectedAttachmentIdSet.has(attachment.id)
                        const inputId = `email-attachment-${attachment.id}`
                        return (
                            <div
                                key={attachment.id}
                                className="flex items-center gap-3 border-b last:border-b-0 px-3 py-2"
                            >
                                <Checkbox
                                    id={inputId}
                                    checked={checked}
                                    onCheckedChange={(next) => toggleSelection(attachment.id, Boolean(next))}
                                    aria-label={`Select ${attachment.filename}`}
                                />
                                <Label htmlFor={inputId} className="flex-1 cursor-pointer">
                                    <span className="block text-sm font-medium truncate">{attachment.filename}</span>
                                    <span className="block text-xs text-muted-foreground">
                                        {formatFileSize(attachment.file_size)}
                                    </span>
                                </Label>
                                {getScanBadge(attachment)}
                            </div>
                        )
                    })}
                </div>
            )}
        </div>
    )
}
