"use client"

import { useId } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import {
    PaperclipIcon,
    FileTextIcon,
    Loader2Icon,
    SparklesIcon,
    Upload,
} from "lucide-react"
import type { InterviewAttachmentRead } from "@/lib/api/interviews"

interface AttachmentsUploadButtonProps {
    onUploadFiles: (files: FileList | null) => void
    uploadInputRef: React.RefObject<HTMLInputElement | null>
    isUploading: boolean
}

function AttachmentsUploadButton({ onUploadFiles, uploadInputRef, isUploading }: AttachmentsUploadButtonProps) {
    const uploadInputId = useId()

    return (
        <>
            <input
                id={uploadInputId}
                name="interview_attachments_upload"
                ref={uploadInputRef}
                type="file"
                aria-label="Upload interview attachments"
                className="hidden"
                multiple
                onChange={(event) => onUploadFiles(event.target.files)}
            />
            <Button
                variant="outline"
                size="sm"
                onClick={() => uploadInputRef.current?.click()}
                disabled={isUploading}
            >
                {isUploading ? (
                    <Loader2Icon className="size-4 mr-2 animate-spin" aria-hidden="true" />
                ) : (
                    <Upload className="size-4 mr-2" aria-hidden="true" />
                )}
                Upload
            </Button>
        </>
    )
}

interface AttachmentsSectionProps {
    attachments: InterviewAttachmentRead[]
    canTranscribe?: boolean
    uploadError: string | null
    isUploading: boolean
    onRequestTranscription: (attachmentId: string) => void
    transcribingAttachmentId: string | null
}

function AttachmentsSection({
    attachments,
    canTranscribe: hasTranscriptionPermission = true,
    uploadError,
    isUploading,
    onRequestTranscription,
    transcribingAttachmentId,
}: AttachmentsSectionProps) {
    return (
        <div className="space-y-3">
            {uploadError && (
                <div className="text-sm text-destructive">{uploadError}</div>
            )}

            {attachments.length === 0 ? (
                <div className="text-center py-6">
                    <PaperclipIcon className="size-10 mx-auto mb-2 text-muted-foreground/50" />
                    <p className="text-sm text-muted-foreground">No attachments</p>
                </div>
            ) : (
                <div className="space-y-2">
                    {attachments.map((att) => {
                        const status = att.transcription_status || "not_started"
                        const isProcessing = status === "pending" || status === "processing"
                        const canTranscribe = hasTranscriptionPermission && att.is_audio_video && !isProcessing && status !== "completed"

                        return (
                            <div
                                key={att.id}
                                className="flex items-start gap-3 p-3 rounded-lg border bg-card hover:bg-accent/30 transition-colors"
                            >
                                <FileTextIcon className="size-8 text-muted-foreground" />
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-medium truncate">{att.filename}</p>
                                    <p className="text-xs text-muted-foreground">
                                        {(att.file_size / 1024).toFixed(1)} KB
                                    </p>
                                    {att.is_audio_video && (
                                        <div className="mt-2 flex items-center gap-2 text-xs">
                                            <Badge variant="outline" className="text-xs capitalize">
                                                {status.replace("_", " ")}
                                            </Badge>
                                            {status === "failed" && att.transcription_error && (
                                                <span className="text-destructive line-clamp-1">
                                                    {att.transcription_error}
                                                </span>
                                            )}
                                        </div>
                                    )}
                                </div>
                                {att.is_audio_video && (
                                    <div className="flex flex-col items-end gap-2">
                                        {status === "completed" ? (
                                            <Badge variant="secondary" className="text-xs">
                                                Transcribed
                                            </Badge>
                                        ) : (
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={() => onRequestTranscription(att.attachment_id)}
                                                disabled={!canTranscribe || isUploading || transcribingAttachmentId === att.attachment_id}
                                            >
                                                {transcribingAttachmentId === att.attachment_id ? (
                                                    <Loader2Icon className="size-4 mr-2 animate-spin" />
                                                ) : (
                                                    <SparklesIcon className="size-4 mr-2" />
                                                )}
                                                {status === "failed" ? "Retry" : "Transcribe"}
                                            </Button>
                                        )}
                                    </div>
                                )}
                            </div>
                        )
                    })}
                </div>
            )}
        </div>
    )
}

interface AttachmentsDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    attachments: InterviewAttachmentRead[]
    canUpload: boolean
    canTranscribe?: boolean
    onUploadFiles: (files: FileList | null) => void
    uploadError: string | null
    uploadInputRef: React.RefObject<HTMLInputElement | null>
    isUploading: boolean
    onRequestTranscription: (attachmentId: string) => void
    transcribingAttachmentId: string | null
}

export function AttachmentsDialog({
    open,
    onOpenChange,
    attachments,
    canUpload,
    canTranscribe = true,
    onUploadFiles,
    uploadError,
    uploadInputRef,
    isUploading,
    onRequestTranscription,
    transcribingAttachmentId,
}: AttachmentsDialogProps) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent size="lg">
                <DialogHeader
                    status={
                        canUpload ? (
                            <AttachmentsUploadButton
                                onUploadFiles={onUploadFiles}
                                uploadInputRef={uploadInputRef}
                                isUploading={isUploading}
                            />
                        ) : undefined
                    }
                >
                    <DialogTitle className="flex items-center gap-2">
                        <PaperclipIcon className="size-5" aria-hidden="true" />
                        Attachments
                        {attachments.length > 0 && (
                            <Badge variant="secondary" className="text-xs">{attachments.length}</Badge>
                        )}
                    </DialogTitle>
                </DialogHeader>
                <div className="max-h-[60vh] overflow-auto py-2">
                    <AttachmentsSection
                        attachments={attachments}
                        canTranscribe={canTranscribe}
                        uploadError={uploadError}
                        isUploading={isUploading}
                        onRequestTranscription={onRequestTranscription}
                        transcribingAttachmentId={transcribingAttachmentId}
                    />
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>
                        Close
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
