"use client"

import { useRef, useState } from "react"
import { DownloadIcon, FileIcon, Loader2Icon, Trash2Icon, UploadIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
    useDeleteDonorAttachment,
    useDonorAttachments,
    useDownloadAttachment,
    useUploadDonorAttachment,
} from "@/lib/hooks/use-attachments"
import type { Donor } from "@/lib/types/donor"

const MAX_FILE_SIZE = 25 * 1024 * 1024

function formatFileSize(bytes: number) {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function getScanLabel(scanStatus: string, quarantined: boolean) {
    if (quarantined) return "Scanning"
    if (scanStatus === "clean") return "Clean"
    if (scanStatus === "infected") return "Infected"
    if (scanStatus === "error") return "Scan Error"
    return "Pending"
}

export function DonorDocumentsSection({ donor, canEdit }: { donor: Donor; canEdit: boolean }) {
    const inputRef = useRef<HTMLInputElement>(null)
    const [uploadError, setUploadError] = useState<string | null>(null)
    const attachmentsQuery = useDonorAttachments(donor.id)
    const uploadAttachment = useUploadDonorAttachment()
    const downloadAttachment = useDownloadAttachment()
    const deleteAttachment = useDeleteDonorAttachment()

    const handleUpload = async (file: File | undefined) => {
        if (!file) return
        setUploadError(null)
        if (file.size > MAX_FILE_SIZE) {
            setUploadError("File exceeds 25 MB limit.")
            return
        }
        try {
            await uploadAttachment.mutateAsync({ donorId: donor.id, file })
        } catch (error) {
            setUploadError(error instanceof Error ? error.message : "Upload failed.")
        }
    }

    const handleDelete = async (attachmentId: string, filename: string) => {
        if (!window.confirm(`Delete ${filename}?`)) return
        await deleteAttachment.mutateAsync({ donorId: donor.id, attachmentId })
    }

    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-4">
                <CardTitle><h2>Documents</h2></CardTitle>
                {canEdit ? (
                    <>
                        <input
                            ref={inputRef}
                            type="file"
                            className="sr-only"
                            aria-label="Upload donor documents"
                            accept=".pdf,.png,.jpg,.jpeg,.doc,.docx,.xls,.xlsx"
                            onChange={(event) => {
                                void handleUpload(event.target.files?.[0])
                                event.target.value = ""
                            }}
                        />
                        <Button
                            size="sm"
                            variant="outline"
                            disabled={uploadAttachment.isPending}
                            onClick={() => inputRef.current?.click()}
                        >
                            {uploadAttachment.isPending ? (
                                <Loader2Icon className="size-4 animate-spin" />
                            ) : (
                                <UploadIcon className="size-4" />
                            )}
                            Upload
                        </Button>
                    </>
                ) : null}
            </CardHeader>
            <CardContent>
                {uploadError ? <p className="mb-4 text-sm text-destructive">{uploadError}</p> : null}
                {attachmentsQuery.isLoading ? (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
                        <Loader2Icon className="size-4 animate-spin" />
                        Loading documents…
                    </div>
                ) : attachmentsQuery.isError ? (
                    <div className="flex items-center justify-between gap-4">
                        <p className="text-sm text-destructive">Failed to load documents.</p>
                        <Button variant="outline" size="sm" onClick={() => { void attachmentsQuery.refetch() }}>
                            Retry
                        </Button>
                    </div>
                ) : (attachmentsQuery.data?.length ?? 0) === 0 ? (
                    <div className="rounded-lg border bg-muted/20 px-4 py-8 text-center">
                        <FileIcon className="mx-auto mb-2 size-7 text-muted-foreground" />
                        <p className="text-sm font-medium text-muted-foreground">No documents yet</p>
                    </div>
                ) : (
                    <ul className="space-y-2" aria-label="Donor documents">
                        {attachmentsQuery.data?.map((attachment) => (
                            <li key={attachment.id} className="flex items-center gap-3 rounded-lg border p-3">
                                <FileIcon className="size-5 shrink-0 text-muted-foreground" />
                                <div className="min-w-0 flex-1">
                                    <p className="truncate text-sm font-medium">{attachment.filename}</p>
                                    <p className="text-xs text-muted-foreground">{formatFileSize(attachment.file_size)}</p>
                                </div>
                                <Badge variant="outline">
                                    {getScanLabel(attachment.scan_status, attachment.quarantined)}
                                </Badge>
                                <Button
                                    size="icon-sm"
                                    variant="ghost"
                                    aria-label={`Download ${attachment.filename}`}
                                    disabled={attachment.quarantined || downloadAttachment.isPending}
                                    onClick={() => downloadAttachment.mutate(attachment.id)}
                                >
                                    <DownloadIcon className="size-4" />
                                </Button>
                                {canEdit ? (
                                    <Button
                                        size="icon-sm"
                                        variant="ghost"
                                        className="text-destructive hover:text-destructive"
                                        aria-label={`Delete ${attachment.filename}`}
                                        disabled={deleteAttachment.isPending}
                                        onClick={() => { void handleDelete(attachment.id, attachment.filename) }}
                                    >
                                        <Trash2Icon className="size-4" />
                                    </Button>
                                ) : null}
                            </li>
                        ))}
                    </ul>
                )}
            </CardContent>
        </Card>
    )
}
