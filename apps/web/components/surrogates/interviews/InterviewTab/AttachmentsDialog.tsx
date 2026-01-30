"use client"

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

interface AttachmentsSectionProps {
    attachments: InterviewAttachmentRead[]
    canUpload: boolean
    onUploadFiles: (files: FileList | null) => void
    uploadError: string | null
    uploadInputRef: React.RefObject<HTMLInputElement | null>
    isUploading: boolean
    onRequestTranscription: (attachmentId: string) => void
    transcribingAttachmentId: string | null
}

function AttachmentsSection({
    attachments,
    canUpload,
    onUploadFiles,
    uploadError,
    uploadInputRef,
    isUploading,
    onRequestTranscription,
    transcribingAttachmentId,
}: AttachmentsSectionProps) {
    return (
        <div className="space-y-3">
            <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-medium">Attachments</div>
                {canUpload && (
                    <>
                        <input
                            ref={uploadInputRef}
                            type="file"
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
                                <Loader2Icon className="h-4 w-4 mr-2 animate-spin" />
                            ) : (
                                <Upload className="h-4 w-4 mr-2" />
                            )}
                            Upload
                        </Button>
                    </>
                )}
            </div>

            {uploadError && (
                <div className="text-sm text-destructive">{uploadError}</div>
            )}

            {attachments.length === 0 ? (
                <div className="text-center py-6">
                    <PaperclipIcon className="h-10 w-10 mx-auto mb-2 text-muted-foreground/50" />
                    <p className="text-sm text-muted-foreground">No attachments</p>
                </div>
            ) : (
                <div className="space-y-2">
                    {attachments.map((att) => {
                        const status = att.transcription_status || "not_started"
                        const isProcessing = status === "pending" || status === "processing"
                        const canTranscribe = att.is_audio_video && !isProcessing && status !== "completed"

                        return (
                            <div
                                key={att.id}
                                className="flex items-start gap-3 p-3 rounded-lg border bg-card hover:bg-accent/30 transition-colors"
                            >
                                <FileTextIcon className="h-8 w-8 text-muted-foreground" />
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
                                                    <Loader2Icon className="h-4 w-4 mr-2 animate-spin" />
                                                ) : (
                                                    <SparklesIcon className="h-4 w-4 mr-2" />
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
    onUploadFiles,
    uploadError,
    uploadInputRef,
    isUploading,
    onRequestTranscription,
    transcribingAttachmentId,
}: AttachmentsDialogProps) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-lg">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <PaperclipIcon className="h-5 w-5" />
                        Attachments
                        {attachments.length > 0 && (
                            <Badge variant="secondary" className="text-xs">{attachments.length}</Badge>
                        )}
                    </DialogTitle>
                </DialogHeader>
                <div className="max-h-[60vh] overflow-auto py-2">
                    <AttachmentsSection
                        attachments={attachments}
                        canUpload={canUpload}
                        onUploadFiles={onUploadFiles}
                        uploadError={uploadError}
                        uploadInputRef={uploadInputRef}
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
