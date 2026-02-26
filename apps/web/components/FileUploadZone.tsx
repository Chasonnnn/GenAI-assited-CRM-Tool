"use client"

import { useCallback, useState } from "react"
import { useDropzone } from "react-dropzone"
import { Upload, File, Loader2, X, Download, Trash2, AlertTriangle, CheckCircle2, Clock } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { cn } from "@/lib/utils"
import { useUploadAttachment, useAttachments, useDownloadAttachment, useDeleteAttachment } from "@/lib/hooks/use-attachments"
import type { Attachment } from "@/lib/api/attachments"

interface FileUploadZoneProps {
    surrogateId: string
    className?: string
}

const ALLOWED_EXTENSIONS = ["pdf", "png", "jpg", "jpeg", "doc", "docx", "xls", "xlsx"]
const MAX_FILE_SIZE = 25 * 1024 * 1024 // 25 MB

function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function getScanStatusBadge(status: string, quarantined: boolean) {
    if (quarantined) {
        return (
            <Badge variant="outline" className="text-yellow-600 border-yellow-300 bg-yellow-50">
                <Clock className="size-3 mr-1" aria-hidden="true" />
                Scanning
            </Badge>
        )
    }

    switch (status) {
        case "clean":
            return (
                <Badge variant="outline" className="text-green-600 border-green-300 bg-green-50">
                    <CheckCircle2 className="size-3 mr-1" aria-hidden="true" />
                    Clean
                </Badge>
            )
        case "infected":
            return (
                <Badge variant="destructive">
                    <AlertTriangle className="size-3 mr-1" aria-hidden="true" />
                    Infected
                </Badge>
            )
        case "error":
            return (
                <Badge variant="outline" className="text-orange-600 border-orange-300 bg-orange-50">
                    <AlertTriangle className="size-3 mr-1" aria-hidden="true" />
                    Scan Error
                </Badge>
            )
        default:
            return (
                <Badge variant="outline" className="text-yellow-600 border-yellow-300 bg-yellow-50">
                    <Clock className="size-3 mr-1" aria-hidden="true" />
                    Pending
                </Badge>
            )
    }
}

export function FileUploadZone({ surrogateId, className }: FileUploadZoneProps) {
    const [uploadProgress, setUploadProgress] = useState<number | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [deleteTarget, setDeleteTarget] = useState<string | null>(null)

    const { data: attachments = [], isLoading } = useAttachments(surrogateId)
    const uploadMutation = useUploadAttachment()
    const downloadMutation = useDownloadAttachment()
    const deleteMutation = useDeleteAttachment()

    const onDrop = useCallback(
        async (acceptedFiles: File[]) => {
            setError(null)

            for (const file of acceptedFiles) {
                // Validate extension
                const ext = file.name.split(".").pop()?.toLowerCase()
                if (!ext || !ALLOWED_EXTENSIONS.includes(ext)) {
                    setError(`File type .${ext} not allowed`)
                    continue
                }

                // Validate size
                if (file.size > MAX_FILE_SIZE) {
                    setError("File exceeds 25 MB limit")
                    continue
                }

                try {
                    setUploadProgress(0)
                    await uploadMutation.mutateAsync({ surrogateId, file })
                    setUploadProgress(100)
                    setTimeout(() => setUploadProgress(null), 1000)
                } catch (err) {
                    setError(err instanceof Error ? err.message : "Upload failed")
                    setUploadProgress(null)
                }
            }
        },
        [surrogateId, uploadMutation]
    )

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: {
            "application/pdf": [".pdf"],
            "image/*": [".png", ".jpg", ".jpeg"],
            "application/msword": [".doc"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
            "application/vnd.ms-excel": [".xls"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
        },
        maxSize: MAX_FILE_SIZE,
    })

    const handleDownload = (attachmentId: string) => {
        downloadMutation.mutate(attachmentId)
    }

    const handleDelete = (attachmentId: string) => {
        setDeleteTarget(attachmentId)
    }

    const confirmDelete = () => {
        if (deleteTarget) {
            deleteMutation.mutate(
                { attachmentId: deleteTarget, surrogateId },
                { onSuccess: () => setDeleteTarget(null) }
            )
        }
    }

    return (
        <div className={cn("space-y-4", className)}>
            {/* Upload Zone */}
            <div
                {...getRootProps({
                    role: "button",
                    "aria-label": "Upload attachments",
                })}
                className={cn(
                    "border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors",
                    isDragActive
                        ? "border-primary bg-primary/5"
                        : "border-muted-foreground/25 hover:border-primary/50"
                )}
            >
                <input {...getInputProps()} />
                <Upload className="size-8 mx-auto mb-2 text-muted-foreground" aria-hidden="true" />
                {isDragActive ? (
                    <p className="text-sm text-primary">Drop files here...</p>
                ) : (
                    <>
                        <p className="text-sm text-muted-foreground">
                            Drag & drop files here, or click to select
                        </p>
                        <p className="text-xs text-muted-foreground mt-1">
                            PDF, images, Word, Excel • Max 25 MB
                        </p>
                    </>
                )}
            </div>

            {/* Upload Progress */}
            {uploadProgress !== null && (
                <div className="flex items-center gap-3">
                    <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                    <Progress value={uploadProgress} className="flex-1" />
                    <span className="text-sm text-muted-foreground">{uploadProgress}%</span>
                </div>
            )}

            {/* Error */}
            {error && (
                <div className="flex items-center gap-2 text-sm text-destructive">
                    <AlertTriangle className="size-4" aria-hidden="true" />
                    {error}
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setError(null)}
                        aria-label="Dismiss upload error"
                    >
                        <X className="size-4" aria-hidden="true" />
                    </Button>
                </div>
            )}

            {/* Attachments List */}
            {isLoading ? (
                <div className="flex justify-center py-4">
                    <Loader2 className="size-6 animate-spin text-muted-foreground" aria-hidden="true" />
                </div>
            ) : attachments.length > 0 ? (
                <ul className="space-y-2" aria-label="Attachments">
                    {attachments.map((attachment: Attachment) => (
                        <li
                            key={attachment.id}
                            className="flex items-center gap-3 p-3 rounded-lg border bg-card"
                        >
                            <File className="size-5 text-muted-foreground shrink-0" aria-hidden="true" />

                            <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium truncate">{attachment.filename}</p>
                                <p className="text-xs text-muted-foreground">
                                    {formatFileSize(attachment.file_size)}
                                </p>
                            </div>

                            {getScanStatusBadge(attachment.scan_status, attachment.quarantined)}

                            <div className="flex items-center gap-1">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => handleDownload(attachment.id)}
                                    disabled={attachment.quarantined || downloadMutation.isPending}
                                    title={attachment.quarantined ? "Pending virus scan" : "Download"}
                                    aria-label={`Download ${attachment.filename}`}
                                >
                                    <Download className="size-4" aria-hidden="true" />
                                </Button>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => handleDelete(attachment.id)}
                                    disabled={deleteMutation.isPending}
                                    className="text-destructive hover:text-destructive"
                                    aria-label={`Delete ${attachment.filename}`}
                                >
                                    <Trash2 className="size-4" aria-hidden="true" />
                                </Button>
                            </div>
                        </li>
                    ))}
                </ul>
            ) : (
                <p className="text-sm text-muted-foreground text-center py-4">
                    No attachments yet
                </p>
            )}

            {/* Delete Confirmation Dialog */}
            <AlertDialog open={deleteTarget !== null} onOpenChange={(open) => !open && setDeleteTarget(null)}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Delete Attachment</AlertDialogTitle>
                        <AlertDialogDescription>
                            Are you sure you want to delete <span className="font-medium text-foreground">{attachments.find((a) => a.id === deleteTarget)?.filename}</span>? This will permanently delete this file.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={deleteMutation.isPending}>Cancel</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={confirmDelete}
                            disabled={deleteMutation.isPending}
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        >
                            {deleteMutation.isPending && (
                                <Loader2 className="mr-2 size-4 animate-spin" aria-hidden="true" />
                            )}
                            Delete
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    )
}
