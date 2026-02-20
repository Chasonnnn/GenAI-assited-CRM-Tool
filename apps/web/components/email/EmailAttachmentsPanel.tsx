"use client"

import * as React from "react"
import { useDropzone } from "react-dropzone"
import { AlertTriangleIcon, CheckCircle2Icon, ClockIcon, Loader2Icon, UploadIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"
import type { Attachment } from "@/lib/api/attachments"
import { useAttachments, useUploadAttachment } from "@/lib/hooks/use-attachments"

export const EMAIL_ATTACHMENTS_MAX_COUNT = 10
export const EMAIL_ATTACHMENTS_MAX_TOTAL_BYTES = 18 * 1024 * 1024

const MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024
const ALLOWED_EXTENSIONS = ["pdf", "png", "jpg", "jpeg", "doc", "docx", "xls", "xlsx"]

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

export function EmailAttachmentsPanel({ surrogateId, onSelectionChange }: EmailAttachmentsPanelProps) {
    const { data: attachments = [], isLoading } = useAttachments(surrogateId)
    const uploadMutation = useUploadAttachment()

    const [selectedAttachmentIds, setSelectedAttachmentIds] = React.useState<string[]>([])
    const [uploadError, setUploadError] = React.useState<string | null>(null)

    React.useEffect(() => {
        setSelectedAttachmentIds((current) =>
            current.filter((attachmentId) => attachments.some((attachment) => attachment.id === attachmentId))
        )
    }, [attachments])

    const selectedAttachments = React.useMemo(
        () => attachments.filter((attachment) => selectedAttachmentIds.includes(attachment.id)),
        [attachments, selectedAttachmentIds]
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
        onSelectionChange({
            selectedAttachmentIds,
            hasBlockingAttachments,
            totalBytes,
            errorMessage: visibleError,
        })
    }, [selectedAttachmentIds, hasBlockingAttachments, totalBytes, visibleError, onSelectionChange])

    const toggleSelection = React.useCallback((attachmentId: string, checked: boolean) => {
        setSelectedAttachmentIds((current) => {
            if (checked) {
                return Array.from(new Set([...current, attachmentId]))
            }
            return current.filter((id) => id !== attachmentId)
        })
    }, [])

    const onDrop = React.useCallback(
        async (acceptedFiles: File[]) => {
            setUploadError(null)
            const uploadedIds: string[] = []

            for (const file of acceptedFiles) {
                const ext = file.name.split(".").pop()?.toLowerCase() ?? ""
                if (!ALLOWED_EXTENSIONS.includes(ext)) {
                    setUploadError(`File type .${ext || "unknown"} is not allowed.`)
                    continue
                }
                if (file.size > MAX_UPLOAD_SIZE_BYTES) {
                    setUploadError("File exceeds 25 MB limit.")
                    continue
                }

                try {
                    const uploaded = await uploadMutation.mutateAsync({ surrogateId, file })
                    uploadedIds.push(uploaded.id)
                } catch (error) {
                    setUploadError(error instanceof Error ? error.message : "Upload failed.")
                }
            }

            if (uploadedIds.length > 0) {
                setSelectedAttachmentIds((current) => Array.from(new Set([...current, ...uploadedIds])))
            }
        },
        [surrogateId, uploadMutation]
    )

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        maxSize: MAX_UPLOAD_SIZE_BYTES,
        accept: ACCEPTED_FILE_TYPES,
    })

    return (
        <div className="grid gap-3">
            <div>
                <Label>Attachments</Label>
                <p className="text-xs text-muted-foreground mt-1">
                    Drag and drop files like Gmail, or pick from existing surrogate attachments.
                </p>
            </div>

            <div
                {...getRootProps()}
                className={cn(
                    "rounded-lg border-2 border-dashed p-4 text-center transition-colors cursor-pointer",
                    isDragActive
                        ? "border-primary bg-primary/5"
                        : "border-muted-foreground/25 hover:border-primary/50"
                )}
                aria-label="Attachment upload dropzone"
            >
                <input {...getInputProps()} />
                <UploadIcon className="mx-auto mb-2 size-5 text-muted-foreground" />
                {isDragActive ? (
                    <p className="text-sm text-primary">Drop files to attach...</p>
                ) : (
                    <p className="text-sm text-muted-foreground">
                        Drop files here or click to upload (PDF, image, Word, Excel; max 25 MB)
                    </p>
                )}
            </div>

            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span>{selectedAttachmentIds.length} selected</span>
                <span>&#8226;</span>
                <span>{formatFileSize(totalBytes)}</span>
                {uploadMutation.isPending && (
                    <>
                        <span>&#8226;</span>
                        <span className="inline-flex items-center gap-1">
                            <Loader2Icon className="size-3 animate-spin" />
                            Uploading...
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
                    Loading attachments...
                </div>
            ) : attachments.length === 0 ? (
                <p className="text-sm text-muted-foreground">No attachments yet.</p>
            ) : (
                <div className="max-h-44 overflow-y-auto rounded-md border">
                    {attachments.map((attachment) => {
                        const checked = selectedAttachmentIds.includes(attachment.id)
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
