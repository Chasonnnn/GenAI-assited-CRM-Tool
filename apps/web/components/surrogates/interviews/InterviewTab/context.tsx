"use client"

import * as React from "react"
import { createContext, use, useState, useCallback, useMemo, useRef, useEffect } from "react"
import { toast } from "sonner"
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
import { useAuth } from "@/lib/auth-context"
import { isTranscriptEmpty } from "../transcript-utils"
import type {
    InterviewListItem,
    InterviewRead,
    InterviewNoteRead,
    InterviewAttachmentRead,
    InterviewType,
    InterviewStatus,
    TipTapDoc,
} from "@/lib/api/interviews"

// ============================================================================
// Types
// ============================================================================

export type DialogState =
    | { type: "closed" }
    | { type: "editor"; interview: InterviewRead | null }
    | { type: "delete"; interview: InterviewRead }
    | { type: "version_history"; interview: InterviewRead }
    | { type: "attachments" }

export type UploadState =
    | { type: "idle" }
    | { type: "uploading" }
    | { type: "transcribing"; attachmentId: string }
    | { type: "error"; message: string }

export interface FormState {
    type: InterviewType
    date: string
    duration: string
    transcript: TipTapDoc | null
    status: InterviewStatus
}

export interface InterviewTabContextValue {
    // Data
    surrogateId: string
    interviews: InterviewListItem[]
    selectedInterview: InterviewRead | null
    notes: InterviewNoteRead[]
    attachments: InterviewAttachmentRead[]
    isLoading: boolean

    // Selection
    selectedId: string | null
    selectInterview: (id: string | null) => void

    // Dialog state (consolidated from 4+ booleans)
    dialog: DialogState
    openEditor: (interview?: InterviewRead | null) => void
    openDeleteDialog: (interview: InterviewRead) => void
    openVersionHistory: (interview: InterviewRead) => void
    openAttachments: () => void
    closeDialog: () => void

    // Upload state
    upload: UploadState
    uploadInputRef: React.RefObject<HTMLInputElement | null>

    // Form state
    form: FormState
    setFormType: (type: InterviewType) => void
    setFormDate: (date: string) => void
    setFormDuration: (duration: string) => void
    setFormTranscript: (transcript: TipTapDoc | null) => void
    setFormStatus: (status: InterviewStatus) => void

    // Mutations
    createOrUpdateInterview: () => Promise<void>
    deleteInterview: () => Promise<void>
    uploadFiles: (files: FileList | null) => Promise<void>
    requestTranscription: (attachmentId: string) => Promise<void>
    generateAISummary: () => Promise<void>

    // Note mutations
    addNote: (data: { content: string; commentId: string; anchorText: string; parentId?: string }) => Promise<void>
    updateNote: (noteId: string, content: string) => Promise<void>
    deleteNote: (noteId: string) => Promise<void>

    // Loading states
    isCreatePending: boolean
    isUpdatePending: boolean
    isDeletePending: boolean
    isAISummaryPending: boolean

    // Permissions
    canEdit: boolean
    canDelete: boolean
    canEditNotes: boolean
}

// ============================================================================
// Context
// ============================================================================

const InterviewTabContext = createContext<InterviewTabContextValue | null>(null)

export function useInterviewTab() {
    const context = use(InterviewTabContext)
    if (!context) {
        throw new Error("useInterviewTab must be used within an InterviewTabProvider")
    }
    return context
}

// ============================================================================
// Provider
// ============================================================================

interface InterviewTabProviderProps {
    surrogateId: string
    children: React.ReactNode
}

function toLocalDateTimeInput(dateString: string): string {
    const date = new Date(dateString)
    const pad = (value: number) => value.toString().padStart(2, "0")
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function InterviewTabProvider({ surrogateId, children }: InterviewTabProviderProps) {
    const { user } = useAuth()

    // Selection state
    const [selectedId, setSelectedId] = useState<string | null>(null)

    // Dialog state - consolidated from multiple booleans
    const [dialog, setDialog] = useState<DialogState>({ type: "closed" })

    // Upload state - consolidated
    const [upload, setUpload] = useState<UploadState>({ type: "idle" })
    const uploadInputRef = useRef<HTMLInputElement>(null)

    // Form state
    const [form, setForm] = useState<FormState>({
        type: "phone",
        date: toLocalDateTimeInput(new Date().toISOString()),
        duration: "",
        transcript: null,
        status: "completed",
    })

    // Data fetching
    const { data: interviews = [], isLoading } = useInterviews(surrogateId)
    const { data: selectedInterview, refetch: refetchInterview } = useInterview(selectedId || "")
    const { data: notes = [] } = useInterviewNotes(selectedId || "")
    const { data: attachments = [] } = useInterviewAttachments(selectedId || "")

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

    // Permissions
    const canEdit = user?.role ? ["case_manager", "admin", "developer"].includes(user.role) : false
    const canDelete = user?.role ? ["admin", "developer"].includes(user.role) : false
    const canEditNotes = !!user

    // Poll for transcription status
    useEffect(() => {
        if (!selectedId || !attachments.length) return
        const hasPending = attachments.some((att) =>
            ["pending", "processing"].includes(att.transcription_status || "")
        )
        if (!hasPending) return
        const interval = setInterval(() => {
            refetchInterview()
        }, 5000)
        return () => clearInterval(interval)
    }, [attachments, refetchInterview, selectedId])

    // Reset form when editor opens
    useEffect(() => {
        if (dialog.type === "editor") {
            const interview = dialog.interview
            if (interview) {
                setForm({
                    type: interview.interview_type as InterviewType,
                    date: toLocalDateTimeInput(interview.conducted_at),
                    duration: interview.duration_minutes?.toString() || "",
                    transcript: interview.transcript_json || null,
                    status: interview.status as InterviewStatus,
                })
            } else {
                setForm({
                    type: "phone",
                    date: toLocalDateTimeInput(new Date().toISOString()),
                    duration: "",
                    transcript: null,
                    status: "completed",
                })
            }
        }
    }, [dialog])

    // Selection
    const selectInterview = useCallback((id: string | null) => {
        setSelectedId(id)
    }, [])

    // Dialog actions
    const openEditor = useCallback((interview?: InterviewRead | null) => {
        setDialog({ type: "editor", interview: interview || null })
    }, [])

    const openDeleteDialog = useCallback((interview: InterviewRead) => {
        setDialog({ type: "delete", interview })
    }, [])

    const openVersionHistory = useCallback((interview: InterviewRead) => {
        setDialog({ type: "version_history", interview })
    }, [])

    const openAttachments = useCallback(() => {
        setDialog({ type: "attachments" })
    }, [])

    const closeDialog = useCallback(() => {
        setDialog({ type: "closed" })
    }, [])

    // Form setters
    const setFormType = useCallback((type: InterviewType) => {
        setForm((prev) => ({ ...prev, type }))
    }, [])

    const setFormDate = useCallback((date: string) => {
        setForm((prev) => ({ ...prev, date }))
    }, [])

    const setFormDuration = useCallback((duration: string) => {
        setForm((prev) => ({ ...prev, duration }))
    }, [])

    const setFormTranscript = useCallback((transcript: TipTapDoc | null) => {
        setForm((prev) => ({ ...prev, transcript }))
    }, [])

    const setFormStatus = useCallback((status: InterviewStatus) => {
        setForm((prev) => ({ ...prev, status }))
    }, [])

    // Mutations
    const createOrUpdateInterview = useCallback(async () => {
        if (dialog.type !== "editor") return

        const editingInterview = dialog.interview
        const data = {
            interview_type: form.type,
            conducted_at: new Date(form.date).toISOString(),
            duration_minutes: form.duration ? parseInt(form.duration) : null,
            transcript_json: isTranscriptEmpty(form.transcript) ? null : form.transcript,
            status: form.status,
        }

        try {
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
            closeDialog()
        } catch {
            toast.error(editingInterview ? "Failed to update interview" : "Failed to create interview")
        }
    }, [dialog, form, surrogateId, createInterviewMutation, updateInterviewMutation, closeDialog])

    const deleteInterview = useCallback(async () => {
        if (dialog.type !== "delete") return

        try {
            await deleteInterviewMutation.mutateAsync({
                interviewId: dialog.interview.id,
                surrogateId,
            })
            setSelectedId(null)
            closeDialog()
            toast.success("Interview deleted")
        } catch {
            toast.error("Failed to delete interview")
        }
    }, [dialog, surrogateId, deleteInterviewMutation, closeDialog])

    const uploadFiles = useCallback(async (files: FileList | null) => {
        if (!selectedId || !files?.length) return

        setUpload({ type: "uploading" })

        const allowedExtensions = new Set([
            "pdf", "png", "jpg", "jpeg", "doc", "docx", "xls", "xlsx",
            "aac", "avi", "m4a", "mkv", "mov", "mp3", "mp4", "mpeg", "ogg", "wav", "webm",
        ])
        const maxSize = 25 * 1024 * 1024

        for (const file of Array.from(files)) {
            const ext = file.name.split(".").pop()?.toLowerCase() || ""
            if (!allowedExtensions.has(ext)) {
                setUpload({ type: "error", message: `File type .${ext || "unknown"} not allowed` })
                continue
            }
            if (file.size > maxSize) {
                setUpload({ type: "error", message: "File exceeds 25 MB limit" })
                continue
            }

            try {
                await uploadAttachmentMutation.mutateAsync({ interviewId: selectedId, file })
            } catch (error) {
                setUpload({ type: "error", message: error instanceof Error ? error.message : "Upload failed" })
                break
            }
        }

        if (uploadInputRef.current) {
            uploadInputRef.current.value = ""
        }
        setUpload({ type: "idle" })
    }, [selectedId, uploadAttachmentMutation])

    const requestTranscription = useCallback(async (attachmentId: string) => {
        if (!selectedId) return

        try {
            setUpload({ type: "transcribing", attachmentId })
            await requestTranscriptionMutation.mutateAsync({
                interviewId: selectedId,
                attachmentId,
            })
            toast.success("Transcription started")
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to start transcription")
        } finally {
            setUpload({ type: "idle" })
        }
    }, [selectedId, requestTranscriptionMutation])

    const generateAISummary = useCallback(async () => {
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
    }, [selectedId, summarizeInterviewMutation])

    // Note mutations
    const addNote = useCallback(async (data: {
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
    }, [selectedId, createNoteMutation])

    const updateNote = useCallback(async (noteId: string, content: string) => {
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
    }, [selectedId, updateNoteMutation])

    const deleteNote = useCallback(async (noteId: string) => {
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
    }, [selectedId, deleteNoteMutation])

    const value: InterviewTabContextValue = useMemo(() => ({
        surrogateId,
        interviews,
        selectedInterview: selectedInterview || null,
        notes,
        attachments,
        isLoading,

        selectedId,
        selectInterview,

        dialog,
        openEditor,
        openDeleteDialog,
        openVersionHistory,
        openAttachments,
        closeDialog,

        upload,
        uploadInputRef,

        form,
        setFormType,
        setFormDate,
        setFormDuration,
        setFormTranscript,
        setFormStatus,

        createOrUpdateInterview,
        deleteInterview,
        uploadFiles,
        requestTranscription,
        generateAISummary,

        addNote,
        updateNote,
        deleteNote,

        isCreatePending: createInterviewMutation.isPending,
        isUpdatePending: updateInterviewMutation.isPending,
        isDeletePending: deleteInterviewMutation.isPending,
        isAISummaryPending: summarizeInterviewMutation.isPending,

        canEdit,
        canDelete,
        canEditNotes,
    }), [
        surrogateId,
        interviews,
        selectedInterview,
        notes,
        attachments,
        isLoading,
        selectedId,
        selectInterview,
        dialog,
        openEditor,
        openDeleteDialog,
        openVersionHistory,
        openAttachments,
        closeDialog,
        upload,
        uploadInputRef,
        form,
        setFormType,
        setFormDate,
        setFormDuration,
        setFormTranscript,
        setFormStatus,
        createOrUpdateInterview,
        deleteInterview,
        uploadFiles,
        requestTranscription,
        generateAISummary,
        addNote,
        updateNote,
        deleteNote,
        createInterviewMutation.isPending,
        updateInterviewMutation.isPending,
        deleteInterviewMutation.isPending,
        summarizeInterviewMutation.isPending,
        canEdit,
        canDelete,
        canEditNotes,
    ])

    return (
        <InterviewTabContext.Provider value={value}>
            {children}
        </InterviewTabContext.Provider>
    )
}
