"use client"

import * as React from "react"
import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import {
    PlusIcon,
    PhoneIcon,
    VideoIcon,
    UsersIcon,
    ClockIcon,
    FileTextIcon,
    MessageSquareIcon,
    PaperclipIcon,
    ChevronLeftIcon,
    MoreVerticalIcon,
    TrashIcon,
    EditIcon,
    HistoryIcon,
    Loader2Icon,
    SparklesIcon,
    Upload,
} from "lucide-react"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import {
    useInterviews,
    useInterview,
    useInterviewNotes,
    useInterviewAttachments,
    useCreateInterview,
    useUpdateInterview,
    useDeleteInterview,
    useCreateInterviewNote,
    useUpdateInterviewNote,
    useDeleteInterviewNote,
    useUploadInterviewAttachment,
    useRequestTranscription,
    useSummarizeInterview,
} from "@/lib/hooks/use-interviews"
import { InterviewVersionHistory } from "./InterviewVersionHistory"
import type {
    InterviewListItem,
    InterviewRead,
    InterviewNoteRead,
    InterviewAttachmentRead,
    InterviewType,
    InterviewStatus,
    TipTapDoc,
} from "@/lib/api/interviews"
import { useAuth } from "@/lib/auth-context"
import { TranscriptEditor, isTranscriptEmpty } from "./TranscriptEditor"
import { InterviewWithComments } from "./InterviewWithComments"

interface SurrogateInterviewTabProps {
    surrogateId: string
}

// Interview type icons
const INTERVIEW_TYPE_ICONS: Record<InterviewType, typeof PhoneIcon> = {
    phone: PhoneIcon,
    video: VideoIcon,
    in_person: UsersIcon,
}

// Interview type colors
const INTERVIEW_TYPE_COLORS: Record<InterviewType, string> = {
    phone: "bg-blue-500/10 text-blue-600 border-blue-500/20",
    video: "bg-purple-500/10 text-purple-600 border-purple-500/20",
    in_person: "bg-green-500/10 text-green-600 border-green-500/20",
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

function formatDate(dateString: string): string {
    const date = new Date(dateString)
    return date.toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
    })
}

function toLocalDateTimeInput(dateString: string): string {
    const date = new Date(dateString)
    const pad = (value: number) => value.toString().padStart(2, "0")
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

// Format interview type for display
function formatInterviewType(type: InterviewType): string {
    const labels: Record<InterviewType, string> = {
        phone: "Phone",
        video: "Video",
        in_person: "In-Person",
    }
    return labels[type]
}

export function SurrogateInterviewTab({ surrogateId }: SurrogateInterviewTabProps) {
    const { user } = useAuth()
    const [selectedId, setSelectedId] = React.useState<string | null>(null)
    const [editorOpen, setEditorOpen] = React.useState(false)
    const [editingInterview, setEditingInterview] = React.useState<InterviewRead | null>(null)
    const [deleteDialogOpen, setDeleteDialogOpen] = React.useState(false)
    const [interviewToDelete, setInterviewToDelete] = React.useState<InterviewRead | null>(null)
    const [versionHistoryOpen, setVersionHistoryOpen] = React.useState(false)
    const [attachmentsDialogOpen, setAttachmentsDialogOpen] = React.useState(false)

    // Form state
    const [formType, setFormType] = React.useState<InterviewType>("phone")
    const [formDate, setFormDate] = React.useState("")
    const [formDuration, setFormDuration] = React.useState<string>("")
    const [formTranscript, setFormTranscript] = React.useState<TipTapDoc | null>(null)
    const [formStatus, setFormStatus] = React.useState<InterviewStatus>("completed")

    // Fetch data
    const { data: interviews, isLoading: interviewsLoading } = useInterviews(surrogateId)
    const { data: selectedInterview, refetch: refetchInterview } = useInterview(selectedId || "")
    const { data: notes } = useInterviewNotes(selectedId || "")
    const { data: attachments } = useInterviewAttachments(selectedId || "")

    // Mutations
    const createInterviewMutation = useCreateInterview()
    const updateInterviewMutation = useUpdateInterview()
    const deleteInterviewMutation = useDeleteInterview()
    const createNoteMutation = useCreateInterviewNote()
    const updateNoteMutation = useUpdateInterviewNote()
    const deleteNoteMutation = useDeleteInterviewNote()
    const uploadAttachmentMutation = useUploadInterviewAttachment()
    const requestTranscriptionMutation = useRequestTranscription()
    const summarizeInterviewMutation = useSummarizeInterview()

    // User permissions
    const canEdit = user?.role && ["case_manager", "admin", "developer"].includes(user.role)
    const canDelete = user?.role && ["admin", "developer"].includes(user.role)
    const canEditNotes = !!user

    const [uploadError, setUploadError] = React.useState<string | null>(null)
    const [transcribingAttachmentId, setTranscribingAttachmentId] = React.useState<string | null>(null)
    const uploadInputRef = React.useRef<HTMLInputElement | null>(null)

    // Reset form when dialog opens/closes
    React.useEffect(() => {
        if (editorOpen) {
            if (editingInterview) {
                setFormType(editingInterview.interview_type as InterviewType)
                setFormDate(toLocalDateTimeInput(editingInterview.conducted_at))
                setFormDuration(editingInterview.duration_minutes?.toString() || "")
                setFormTranscript(editingInterview.transcript_json || null)
                setFormStatus(editingInterview.status as InterviewStatus)
            } else {
                setFormType("phone")
                setFormDate(toLocalDateTimeInput(new Date().toISOString()))
                setFormDuration("")
                setFormTranscript(null)
                setFormStatus("completed")
            }
        }
    }, [editorOpen, editingInterview])

    React.useEffect(() => {
        if (!selectedId || !attachments?.length) return
        const hasPending = attachments.some((att) =>
            ["pending", "processing"].includes(att.transcription_status || "")
        )
        if (!hasPending) return
        const interval = setInterval(() => {
            refetchInterview()
        }, 5000)
        return () => clearInterval(interval)
    }, [attachments, refetchInterview, selectedId])

    const handleCreateOrUpdate = async () => {
        try {
            const data = {
                interview_type: formType,
                conducted_at: new Date(formDate).toISOString(),
                duration_minutes: formDuration ? parseInt(formDuration) : null,
                transcript_json: isTranscriptEmpty(formTranscript) ? null : formTranscript,
                status: formStatus,
            }

            if (editingInterview) {
                await updateInterviewMutation.mutateAsync({
                    interviewId: editingInterview.id,
                    data: {
                        ...data,
                        expected_version: editingInterview.transcript_version,
                    },
                })
                toast.success("Interview updated")
            } else {
                const newInterview = await createInterviewMutation.mutateAsync({
                    surrogateId,
                    data,
                })
                setSelectedId(newInterview.id)
                toast.success("Interview created")
            }
            setEditorOpen(false)
            setEditingInterview(null)
        } catch {
            toast.error(editingInterview ? "Failed to update interview" : "Failed to create interview")
        }
    }

    const handleDelete = async () => {
        if (!interviewToDelete) return
        try {
            await deleteInterviewMutation.mutateAsync({
                interviewId: interviewToDelete.id,
                surrogateId,
            })
            setSelectedId(null)
            setDeleteDialogOpen(false)
            setInterviewToDelete(null)
            toast.success("Interview deleted")
        } catch {
            toast.error("Failed to delete interview")
        }
    }

    // Note handlers for InterviewWithComments
    const handleAddComment = async (data: {
        content: string
        commentId: string
        anchorText: string
        parentId?: string
    }) => {
        if (!selectedId) return
        try {
            await createNoteMutation.mutateAsync({
                interviewId: selectedId,
                data: {
                    content: data.content,
                    ...(data.commentId ? { comment_id: data.commentId } : {}),
                    ...(data.anchorText ? { anchor_text: data.anchorText } : {}),
                    ...(data.parentId ? { parent_id: data.parentId } : {}),
                },
            })
            toast.success(data.commentId ? "Comment added" : "Note added")
        } catch {
            toast.error("Failed to add comment")
        }
    }

    const handleUpdateNote = async (noteId: string, content: string) => {
        if (!selectedId) return
        try {
            await updateNoteMutation.mutateAsync({
                interviewId: selectedId,
                noteId,
                data: { content },
            })
            toast.success("Note updated")
        } catch {
            toast.error("Failed to update note")
        }
    }

    const handleDeleteNote = async (noteId: string) => {
        if (!selectedId) return
        try {
            await deleteNoteMutation.mutateAsync({
                interviewId: selectedId,
                noteId,
            })
            toast.success("Note deleted")
        } catch {
            toast.error("Failed to delete note")
        }
    }

    const handleUploadFiles = async (files: FileList | null) => {
        if (!selectedId || !files?.length) return
        setUploadError(null)

        const allowedExtensions = new Set([
            "pdf", "png", "jpg", "jpeg", "doc", "docx", "xls", "xlsx",
            "aac", "avi", "m4a", "mkv", "mov", "mp3", "mp4", "mpeg", "ogg", "wav", "webm",
        ])
        const maxSize = 25 * 1024 * 1024

        for (const file of Array.from(files)) {
            const ext = file.name.split(".").pop()?.toLowerCase() || ""
            if (!allowedExtensions.has(ext)) {
                setUploadError(`File type .${ext || "unknown"} not allowed`)
                continue
            }
            if (file.size > maxSize) {
                setUploadError("File exceeds 25 MB limit")
                continue
            }

            try {
                await uploadAttachmentMutation.mutateAsync({ interviewId: selectedId, file })
            } catch (error) {
                setUploadError(error instanceof Error ? error.message : "Upload failed")
                break
            }
        }

        if (uploadInputRef.current) {
            uploadInputRef.current.value = ""
        }
    }

    const handleRequestTranscription = async (attachmentId: string) => {
        if (!selectedId) return
        try {
            setTranscribingAttachmentId(attachmentId)
            await requestTranscriptionMutation.mutateAsync({
                interviewId: selectedId,
                attachmentId,
            })
            toast.success("Transcription started")
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to start transcription")
        } finally {
            setTranscribingAttachmentId(null)
        }
    }

    const handleAISummary = async () => {
        if (!selectedId) return
        try {
            const result = await summarizeInterviewMutation.mutateAsync(selectedId)
            toast.success("AI Summary Generated", {
                description: result.summary.slice(0, 100) + (result.summary.length > 100 ? "..." : ""),
                duration: 8000,
            })
        } catch (error) {
            const message = error instanceof Error ? error.message : "Failed to generate summary"
            if (message.toLowerCase().includes("consent")) {
                toast.error("AI Consent Required", {
                    description: "Please accept AI terms in Settings before using AI features.",
                })
            } else if (message.toLowerCase().includes("not enabled")) {
                toast.error("AI Not Available", {
                    description: "AI features are not enabled for your organization.",
                })
            } else {
                toast.error(message)
            }
        }
    }

    // Loading state
    if (interviewsLoading) {
        return (
            <Card>
                <CardContent className="flex items-center justify-center py-16">
                    <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                    <span className="ml-2 text-muted-foreground">Loading interviews...</span>
                </CardContent>
            </Card>
        )
    }

    // Empty state
    if (!interviews || interviews.length === 0) {
        return (
            <Card>
                <CardContent className="flex flex-col items-center justify-center py-16 text-center">
                    <FileTextIcon className="h-16 w-16 text-muted-foreground mb-4" />
                    <h3 className="text-lg font-semibold mb-2">No Interviews</h3>
                    <p className="text-sm text-muted-foreground mb-6 max-w-md">
                        Document phone calls, video interviews, and in-person meetings with this candidate.
                    </p>
                    {canEdit && (
                        <Button onClick={() => setEditorOpen(true)}>
                            <PlusIcon className="h-4 w-4 mr-2" />
                            Add Interview
                        </Button>
                    )}

                    {/* Create Dialog */}
                    <InterviewEditorDialog
                        open={editorOpen}
                        onOpenChange={(open) => {
                            setEditorOpen(open)
                            if (!open) setEditingInterview(null)
                        }}
                        isEditing={false}
                        isPending={createInterviewMutation.isPending}
                        formType={formType}
                        setFormType={setFormType}
                        formDate={formDate}
                        setFormDate={setFormDate}
                        formDuration={formDuration}
                        setFormDuration={setFormDuration}
                        formTranscript={formTranscript}
                        setFormTranscript={setFormTranscript}
                        formStatus={formStatus}
                        setFormStatus={setFormStatus}
                        onSubmit={handleCreateOrUpdate}
                    />
                </CardContent>
            </Card>
        )
    }

    // Desktop layout: List on left, detail on right
    // Mobile layout: List or detail view with back button
    return (
        <div className="space-y-4">
            {/* Desktop Layout */}
            <div className="hidden lg:grid lg:grid-cols-[320px_1fr] gap-4 h-[calc(100vh-280px)]">
                {/* Interview List */}
                <Card className="overflow-hidden flex flex-col">
                    <CardHeader className="flex flex-row items-center justify-between py-3 px-4 border-b shrink-0">
                        <CardTitle className="text-base">Interviews ({interviews.length})</CardTitle>
                        {canEdit && (
                            <Button size="sm" onClick={() => setEditorOpen(true)}>
                                <PlusIcon className="h-4 w-4" />
                            </Button>
                        )}
                    </CardHeader>
                    <div className="flex-1 overflow-auto">
                        {interviews.map((interview) => (
                            <InterviewListItemComponent
                                key={interview.id}
                                interview={interview}
                                isSelected={selectedId === interview.id}
                                onClick={() => setSelectedId(interview.id)}
                            />
                        ))}
                    </div>
                </Card>

                {/* Detail View */}
                <Card className="overflow-hidden flex flex-col">
                    {selectedId && selectedInterview ? (
                        <InterviewDetailView
                            interview={selectedInterview}
                            notes={notes || []}
                            attachments={attachments || []}
                            onEdit={() => {
                                setEditingInterview(selectedInterview)
                                setEditorOpen(true)
                            }}
                            onDelete={() => {
                                setInterviewToDelete(selectedInterview)
                                setDeleteDialogOpen(true)
                            }}
                            onVersionHistory={() => setVersionHistoryOpen(true)}
                            onAttachments={() => setAttachmentsDialogOpen(true)}
                            onAISummary={handleAISummary}
                            isAISummaryPending={summarizeInterviewMutation.isPending}
                            onAddNote={handleAddComment}
                            onUpdateNote={handleUpdateNote}
                            onDeleteNote={handleDeleteNote}
                            canEdit={!!canEdit}
                            canEditNotes={canEditNotes}
                            canDelete={!!canDelete}
                            canUpload={!!canEdit}
                            onUploadFiles={handleUploadFiles}
                            uploadError={uploadError}
                            uploadInputRef={uploadInputRef}
                            isUploading={uploadAttachmentMutation.isPending}
                            onRequestTranscription={handleRequestTranscription}
                            transcribingAttachmentId={transcribingAttachmentId}
                            attachmentsDialogOpen={attachmentsDialogOpen}
                            onAttachmentsDialogOpenChange={setAttachmentsDialogOpen}
                        />
                    ) : (
                        <div className="flex-1 flex items-center justify-center text-muted-foreground">
                            <div className="text-center">
                                <FileTextIcon className="h-12 w-12 mx-auto mb-3 opacity-50" />
                                <p>Select an interview to view details</p>
                            </div>
                        </div>
                    )}
                </Card>
            </div>

            {/* Mobile Layout */}
            <div className="lg:hidden">
                {selectedId ? (
                    <Card className="overflow-hidden">
                        <div className="p-2 border-b flex items-center justify-between">
                            <Button variant="ghost" size="sm" onClick={() => setSelectedId(null)}>
                                <ChevronLeftIcon className="h-4 w-4 mr-1" />
                                Back to list
                            </Button>
                            {selectedInterview && (
                                <InterviewHeaderActions
                                    interview={selectedInterview}
                                    onEdit={() => {
                                        setEditingInterview(selectedInterview)
                                        setEditorOpen(true)
                                    }}
                                    onDelete={() => {
                                        setInterviewToDelete(selectedInterview)
                                        setDeleteDialogOpen(true)
                                    }}
                                    onVersionHistory={() => setVersionHistoryOpen(true)}
                                    canEdit={!!canEdit}
                                    canDelete={!!canDelete}
                                />
                            )}
                        </div>
                        {selectedInterview && (
                            <div className="h-[calc(100vh-200px)]">
                                <InterviewWithComments
                                    interview={selectedInterview}
                                    notes={notes || []}
                                    onAddNote={handleAddComment}
                                    onUpdateNote={handleUpdateNote}
                                    onDeleteNote={handleDeleteNote}
                                    canEdit={canEditNotes}
                                />
                            </div>
                        )}
                    </Card>
                ) : (
                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between py-3 px-4 border-b">
                            <CardTitle className="text-base">Interviews ({interviews.length})</CardTitle>
                            {canEdit && (
                                <Button size="sm" onClick={() => setEditorOpen(true)}>
                                    <PlusIcon className="h-4 w-4 mr-1" />
                                    Add
                                </Button>
                            )}
                        </CardHeader>
                        <CardContent className="p-0">
                            {interviews.map((interview) => (
                                <InterviewListItemComponent
                                    key={interview.id}
                                    interview={interview}
                                    isSelected={false}
                                    onClick={() => setSelectedId(interview.id)}
                                />
                            ))}
                        </CardContent>
                    </Card>
                )}
            </div>

            {/* Editor Dialog */}
            <InterviewEditorDialog
                open={editorOpen}
                onOpenChange={(open) => {
                    setEditorOpen(open)
                    if (!open) setEditingInterview(null)
                }}
                isEditing={!!editingInterview}
                isPending={createInterviewMutation.isPending || updateInterviewMutation.isPending}
                formType={formType}
                setFormType={setFormType}
                formDate={formDate}
                setFormDate={setFormDate}
                formDuration={formDuration}
                setFormDuration={setFormDuration}
                formTranscript={formTranscript}
                setFormTranscript={setFormTranscript}
                formStatus={formStatus}
                setFormStatus={setFormStatus}
                onSubmit={handleCreateOrUpdate}
            />

            {/* Delete Dialog */}
            <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Delete Interview</DialogTitle>
                    </DialogHeader>
                    <p className="text-sm text-muted-foreground">
                        Are you sure you want to delete this interview? This action cannot be undone.
                    </p>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
                            Cancel
                        </Button>
                        <Button
                            variant="destructive"
                            onClick={handleDelete}
                            disabled={deleteInterviewMutation.isPending}
                        >
                            {deleteInterviewMutation.isPending ? "Deleting..." : "Delete"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Version History Dialog */}
            {selectedInterview && (
                <InterviewVersionHistory
                    interviewId={selectedInterview.id}
                    currentVersion={selectedInterview.transcript_version}
                    open={versionHistoryOpen}
                    onOpenChange={setVersionHistoryOpen}
                    canRestore={canEdit || false}
                />
            )}
        </div>
    )
}

// =============================================================================
// Sub-components
// =============================================================================

interface InterviewListItemComponentProps {
    interview: InterviewListItem
    isSelected: boolean
    onClick: () => void
}

function InterviewListItemComponent({ interview, isSelected, onClick }: InterviewListItemComponentProps) {
    const Icon = INTERVIEW_TYPE_ICONS[interview.interview_type as InterviewType]
    const colorClass = INTERVIEW_TYPE_COLORS[interview.interview_type as InterviewType]

    return (
        <div
            className={cn(
                "p-4 border-b cursor-pointer transition-colors",
                isSelected ? "bg-primary/5" : "hover:bg-muted/50"
            )}
            onClick={onClick}
        >
            <div className="flex items-start gap-3">
                <div className={cn("p-2 rounded-lg", colorClass)}>
                    <Icon className="h-4 w-4" />
                </div>
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-sm">
                            {formatInterviewType(interview.interview_type as InterviewType)}
                        </span>
                        {interview.status === "draft" && (
                            <Badge variant="secondary" className="text-xs">Draft</Badge>
                        )}
                    </div>
                    <div className="text-xs text-muted-foreground">
                        {formatDate(interview.conducted_at)} with {interview.conducted_by_name}
                    </div>
                    <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                        {interview.duration_minutes && (
                            <span className="flex items-center gap-1">
                                <ClockIcon className="h-3 w-3" />
                                {interview.duration_minutes}m
                            </span>
                        )}
                        <span className="flex items-center gap-1">
                            <MessageSquareIcon className="h-3 w-3" />
                            {interview.notes_count}
                        </span>
                        <span className="flex items-center gap-1">
                            <PaperclipIcon className="h-3 w-3" />
                            {interview.attachments_count}
                        </span>
                    </div>
                </div>
            </div>
        </div>
    )
}

interface InterviewDetailViewProps {
    interview: InterviewRead
    notes: InterviewNoteRead[]
    attachments: InterviewAttachmentRead[]
    onEdit: () => void
    onDelete: () => void
    onVersionHistory: () => void
    onAttachments: () => void
    onAISummary: () => void
    isAISummaryPending: boolean
    onAddNote: (data: { content: string; commentId: string; anchorText: string; parentId?: string }) => Promise<void>
    onUpdateNote: (noteId: string, content: string) => Promise<void>
    onDeleteNote: (noteId: string) => Promise<void>
    canEdit: boolean
    canEditNotes: boolean
    canDelete: boolean
    canUpload: boolean
    onUploadFiles: (files: FileList | null) => void
    uploadError: string | null
    uploadInputRef: React.RefObject<HTMLInputElement | null>
    isUploading: boolean
    onRequestTranscription: (attachmentId: string) => void
    transcribingAttachmentId: string | null
    attachmentsDialogOpen: boolean
    onAttachmentsDialogOpenChange: (open: boolean) => void
}

function InterviewDetailView({
    interview,
    notes,
    attachments,
    onEdit,
    onDelete,
    onVersionHistory,
    onAttachments,
    onAISummary,
    isAISummaryPending,
    onAddNote,
    onUpdateNote,
    onDeleteNote,
    canEdit,
    canEditNotes,
    canDelete,
    canUpload,
    onUploadFiles,
    uploadError,
    uploadInputRef,
    isUploading,
    onRequestTranscription,
    transcribingAttachmentId,
    attachmentsDialogOpen,
    onAttachmentsDialogOpenChange,
}: InterviewDetailViewProps) {
    return (
        <div className="flex flex-col h-full">
            {/* Header */}
            <div className="p-4 border-b shrink-0">
                <InterviewHeader
                    interview={interview}
                    attachmentsCount={attachments.length}
                    onEdit={onEdit}
                    onDelete={onDelete}
                    onVersionHistory={onVersionHistory}
                    onAttachments={onAttachments}
                    onAISummary={onAISummary}
                    isAISummaryPending={isAISummaryPending}
                    canEdit={canEdit}
                    canDelete={canDelete}
                />
            </div>

            {/* Content - Interview with comments */}
            <div className="flex-1 overflow-hidden">
                <InterviewWithComments
                    interview={interview}
                    notes={notes}
                    onAddNote={onAddNote}
                    onUpdateNote={onUpdateNote}
                    onDeleteNote={onDeleteNote}
                    canEdit={canEditNotes}
                    className="h-full"
                />
            </div>

            {/* Attachments Dialog */}
            <AttachmentsDialog
                open={attachmentsDialogOpen}
                onOpenChange={onAttachmentsDialogOpenChange}
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
    )
}

interface InterviewHeaderProps {
    interview: InterviewRead
    attachmentsCount: number
    onEdit: () => void
    onDelete: () => void
    onVersionHistory: () => void
    onAttachments: () => void
    onAISummary: () => void
    isAISummaryPending: boolean
    canEdit: boolean
    canDelete: boolean
}

function InterviewHeader({ interview, attachmentsCount, onEdit, onDelete, onVersionHistory, onAttachments, onAISummary, isAISummaryPending, canEdit, canDelete }: InterviewHeaderProps) {
    const Icon = INTERVIEW_TYPE_ICONS[interview.interview_type as InterviewType]
    const colorClass = INTERVIEW_TYPE_COLORS[interview.interview_type as InterviewType]

    return (
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
                        <DropdownMenuItem onClick={onEdit}>
                            <EditIcon className="h-4 w-4 mr-2" />
                            Edit
                        </DropdownMenuItem>
                    )}
                    <DropdownMenuItem onClick={onAttachments}>
                        <PaperclipIcon className="h-4 w-4 mr-2" />
                        Attachments
                        {attachmentsCount > 0 && (
                            <Badge variant="secondary" className="ml-auto text-xs px-1.5 py-0">
                                {attachmentsCount}
                            </Badge>
                        )}
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={onVersionHistory}>
                        <HistoryIcon className="h-4 w-4 mr-2" />
                        Version History
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={onAISummary} disabled={isAISummaryPending}>
                        <SparklesIcon className="h-4 w-4 mr-2" />
                        {isAISummaryPending ? "Generating..." : "AI Summary"}
                    </DropdownMenuItem>
                    {canDelete && (
                        <DropdownMenuItem onClick={onDelete} className="text-destructive">
                            <TrashIcon className="h-4 w-4 mr-2" />
                            Delete
                        </DropdownMenuItem>
                    )}
                </DropdownMenuContent>
            </DropdownMenu>
        </div>
    )
}

interface InterviewHeaderActionsProps {
    interview: InterviewRead
    onEdit: () => void
    onDelete: () => void
    onVersionHistory: () => void
    canEdit: boolean
    canDelete: boolean
}

function InterviewHeaderActions({ onEdit, onDelete, onVersionHistory, canEdit, canDelete }: InterviewHeaderActionsProps) {
    return (
        <DropdownMenu>
            <DropdownMenuTrigger
                className={buttonVariants({ variant: "ghost", size: "icon", className: "h-8 w-8" })}
            >
                <MoreVerticalIcon className="h-4 w-4" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
                {canEdit && (
                    <DropdownMenuItem onClick={onEdit}>
                        <EditIcon className="h-4 w-4 mr-2" />
                        Edit
                    </DropdownMenuItem>
                )}
                <DropdownMenuItem onClick={onVersionHistory}>
                    <HistoryIcon className="h-4 w-4 mr-2" />
                    Version History
                </DropdownMenuItem>
                {canDelete && (
                    <DropdownMenuItem onClick={onDelete} className="text-destructive">
                        <TrashIcon className="h-4 w-4 mr-2" />
                        Delete
                    </DropdownMenuItem>
                )}
            </DropdownMenuContent>
        </DropdownMenu>
    )
}

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

function AttachmentsDialog({
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

interface InterviewEditorDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    isEditing: boolean
    isPending: boolean
    formType: InterviewType
    setFormType: (type: InterviewType) => void
    formDate: string
    setFormDate: (date: string) => void
    formDuration: string
    setFormDuration: (duration: string) => void
    formTranscript: TipTapDoc | null
    setFormTranscript: (transcript: TipTapDoc | null) => void
    formStatus: InterviewStatus
    setFormStatus: (status: InterviewStatus) => void
    onSubmit: () => void
}

function InterviewEditorDialog({
    open,
    onOpenChange,
    isEditing,
    isPending,
    formType,
    setFormType,
    formDate,
    setFormDate,
    formDuration,
    setFormDuration,
    formTranscript,
    setFormTranscript,
    formStatus,
    setFormStatus,
    onSubmit,
}: InterviewEditorDialogProps) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>{isEditing ? "Edit Interview" : "Add Interview"}</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-4">
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label htmlFor="interview-type">Interview Type</Label>
                            <NativeSelect
                                id="interview-type"
                                value={formType}
                                onChange={(e) => setFormType(e.target.value as InterviewType)}
                            >
                                <NativeSelectOption value="phone">Phone Call</NativeSelectOption>
                                <NativeSelectOption value="video">Video Call</NativeSelectOption>
                                <NativeSelectOption value="in_person">In-Person</NativeSelectOption>
                            </NativeSelect>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="interview-status">Status</Label>
                            <NativeSelect
                                id="interview-status"
                                value={formStatus}
                                onChange={(e) => setFormStatus(e.target.value as InterviewStatus)}
                            >
                                <NativeSelectOption value="completed">Completed</NativeSelectOption>
                                <NativeSelectOption value="draft">Draft</NativeSelectOption>
                            </NativeSelect>
                        </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label htmlFor="interview-date">Date & Time</Label>
                            <Input
                                id="interview-date"
                                type="datetime-local"
                                value={formDate}
                                onChange={(e) => setFormDate(e.target.value)}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="interview-duration">Duration (minutes)</Label>
                            <Input
                                id="interview-duration"
                                type="number"
                                min="1"
                                max="480"
                                placeholder="30"
                                value={formDuration}
                                onChange={(e) => setFormDuration(e.target.value)}
                            />
                        </div>
                    </div>
                    <div className="space-y-2">
                        <Label>Transcript</Label>
                        <TranscriptEditor
                            content={formTranscript}
                            onChange={setFormTranscript}
                            placeholder="Start typing or paste content from Word, Google Docs..."
                            minHeight="200px"
                            maxHeight="400px"
                        />
                        <p className="text-xs text-muted-foreground">
                            Paste formatted text from Word or Google Docs to preserve formatting.
                            You can also upload audio/video files for AI transcription after creating the interview.
                        </p>
                    </div>
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>
                        Cancel
                    </Button>
                    <Button onClick={onSubmit} disabled={isPending || !formDate}>
                        {isPending ? (
                            <>
                                <Loader2Icon className="h-4 w-4 mr-2 animate-spin" />
                                {isEditing ? "Saving..." : "Creating..."}
                            </>
                        ) : (
                            isEditing ? "Save Changes" : "Create Interview"
                        )}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
