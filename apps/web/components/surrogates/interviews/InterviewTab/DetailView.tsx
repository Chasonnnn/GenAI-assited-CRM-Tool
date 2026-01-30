"use client"

import { Badge } from "@/components/ui/badge"
import { buttonVariants } from "@/components/ui/button"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
    PhoneIcon,
    VideoIcon,
    UsersIcon,
    ClockIcon,
    MoreVerticalIcon,
    EditIcon,
    PaperclipIcon,
    HistoryIcon,
    SparklesIcon,
    TrashIcon,
    FileTextIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { InterviewWithComments } from "../InterviewWithComments"
import { useInterviewTab } from "./context"
import { AttachmentsDialog } from "./AttachmentsDialog"
import type { InterviewType } from "@/lib/api/interviews"

const INTERVIEW_TYPE_ICONS: Record<InterviewType, typeof PhoneIcon> = {
    phone: PhoneIcon,
    video: VideoIcon,
    in_person: UsersIcon,
}

const INTERVIEW_TYPE_COLORS: Record<InterviewType, string> = {
    phone: "bg-blue-500/10 text-blue-600 border-blue-500/20",
    video: "bg-purple-500/10 text-purple-600 border-purple-500/20",
    in_person: "bg-green-500/10 text-green-600 border-green-500/20",
}

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

function formatInterviewType(type: InterviewType): string {
    const labels: Record<InterviewType, string> = {
        phone: "Phone",
        video: "Video",
        in_person: "In-Person",
    }
    return labels[type]
}

export function DetailView() {
    const {
        selectedInterview,
        notes,
        attachments,
        openEditor,
        openDeleteDialog,
        openVersionHistory,
        openAttachments,
        generateAISummary,
        isAISummaryPending,
        addNote,
        updateNote,
        deleteNote,
        canEdit,
        canDelete,
        canEditNotes,
        dialog,
        closeDialog,
        upload,
        uploadInputRef,
        uploadFiles,
        requestTranscription,
    } = useInterviewTab()

    if (!selectedInterview) {
        return (
            <div className="flex-1 flex items-center justify-center text-muted-foreground">
                <div className="text-center">
                    <FileTextIcon className="h-12 w-12 mx-auto mb-3 opacity-50" />
                    <p>Select an interview to view details</p>
                </div>
            </div>
        )
    }

    const interview = selectedInterview
    const Icon = INTERVIEW_TYPE_ICONS[interview.interview_type as InterviewType]
    const colorClass = INTERVIEW_TYPE_COLORS[interview.interview_type as InterviewType]

    return (
        <div className="flex flex-col h-full">
            {/* Header */}
            <div className="p-4 border-b shrink-0">
                <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3">
                        <div className={cn("p-2 rounded-lg", colorClass)}>
                            <Icon className="h-5 w-5" />
                        </div>
                        <div>
                            <div className="flex items-center gap-2">
                                <h3 className="font-semibold">
                                    {formatInterviewType(interview.interview_type as InterviewType)} Interview
                                </h3>
                                {interview.status === "draft" && (
                                    <Badge variant="secondary">Draft</Badge>
                                )}
                                <Badge variant="outline" className="text-xs">v{interview.transcript_version}</Badge>
                            </div>
                            <div className="text-sm text-muted-foreground mt-1">
                                {formatDateTime(interview.conducted_at)} with {interview.conducted_by_name}
                            </div>
                            {interview.duration_minutes && (
                                <div className="text-sm text-muted-foreground flex items-center gap-1">
                                    <ClockIcon className="h-3 w-3" />
                                    {interview.duration_minutes} minutes
                                </div>
                            )}
                        </div>
                    </div>
                    <DropdownMenu>
                        <DropdownMenuTrigger
                            className={buttonVariants({ variant: "ghost", size: "icon", className: "h-8 w-8" })}
                        >
                            <MoreVerticalIcon className="h-4 w-4" />
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                            {canEdit && (
                                <DropdownMenuItem onClick={() => openEditor(interview)}>
                                    <EditIcon className="h-4 w-4 mr-2" />
                                    Edit
                                </DropdownMenuItem>
                            )}
                            <DropdownMenuItem onClick={openAttachments}>
                                <PaperclipIcon className="h-4 w-4 mr-2" />
                                Attachments
                                {attachments.length > 0 && (
                                    <Badge variant="secondary" className="ml-auto text-xs px-1.5 py-0">
                                        {attachments.length}
                                    </Badge>
                                )}
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => openVersionHistory(interview)}>
                                <HistoryIcon className="h-4 w-4 mr-2" />
                                Version History
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={generateAISummary} disabled={isAISummaryPending}>
                                <SparklesIcon className="h-4 w-4 mr-2" />
                                {isAISummaryPending ? "Generating..." : "AI Summary"}
                            </DropdownMenuItem>
                            {canDelete && (
                                <DropdownMenuItem onClick={() => openDeleteDialog(interview)} className="text-destructive">
                                    <TrashIcon className="h-4 w-4 mr-2" />
                                    Delete
                                </DropdownMenuItem>
                            )}
                        </DropdownMenuContent>
                    </DropdownMenu>
                </div>
            </div>

            {/* Content - Interview with comments */}
            <div className="flex-1 overflow-hidden">
                <InterviewWithComments
                    interview={interview}
                    notes={notes}
                    onAddNote={addNote}
                    onUpdateNote={updateNote}
                    onDeleteNote={deleteNote}
                    canEdit={canEditNotes}
                    className="h-full"
                />
            </div>

            {/* Attachments Dialog */}
            <AttachmentsDialog
                open={dialog.type === "attachments"}
                onOpenChange={(open) => !open && closeDialog()}
                attachments={attachments}
                canUpload={canEdit}
                onUploadFiles={uploadFiles}
                uploadError={upload.type === "error" ? upload.message : null}
                uploadInputRef={uploadInputRef}
                isUploading={upload.type === "uploading"}
                onRequestTranscription={requestTranscription}
                transcribingAttachmentId={upload.type === "transcribing" ? upload.attachmentId : null}
            />
        </div>
    )
}
