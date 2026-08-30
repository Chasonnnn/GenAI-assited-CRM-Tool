"use client"

import { useState } from "react"
import { Loader2Icon, Trash2Icon } from "lucide-react"

import { SafeHtmlContent } from "@/components/safe-html-content"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { toast } from "@/components/ui/toast"
import { formatDateTime } from "@/lib/formatters"
import {
    useCreateDonorNote,
    useDeleteDonorNote,
    useDonorNotes,
} from "@/lib/hooks/use-donors"

export function DonorNotesSection({
    donorId,
    canEdit,
    currentUserId,
    canDeleteAny,
}: {
    donorId: string
    canEdit: boolean
    currentUserId: string | null
    canDeleteAny: boolean
}) {
    const [newNote, setNewNote] = useState("")
    const notesQuery = useDonorNotes(donorId)
    const createNote = useCreateDonorNote()
    const deleteNote = useDeleteDonorNote()

    const handleAdd = async () => {
        const content = newNote.trim()
        if (!content) return
        try {
            await createNote.mutateAsync({ donorId, data: { content } })
            setNewNote("")
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to add note")
        }
    }

    const handleDelete = async (noteId: string) => {
        if (!window.confirm("Delete this note?")) return
        try {
            await deleteNote.mutateAsync({ donorId, noteId })
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to delete note")
        }
    }

    return (
        <Card>
            <CardHeader>
                <CardTitle><h2>Notes</h2></CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                {canEdit ? (
                    <form
                        className="flex flex-col gap-2 sm:flex-row sm:items-start"
                        onSubmit={(event) => {
                            event.preventDefault()
                            void handleAdd()
                        }}
                    >
                        <Textarea
                            aria-label="New donor note"
                            placeholder="Add a note..."
                            value={newNote}
                            onChange={(event) => setNewNote(event.target.value)}
                            rows={2}
                        />
                        <Button
                            type="submit"
                            disabled={!newNote.trim() || createNote.isPending}
                        >
                            {createNote.isPending ? (
                                <Loader2Icon className="size-4 animate-spin" />
                            ) : null}
                            Add Note
                        </Button>
                    </form>
                ) : null}

                {notesQuery.isLoading ? (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
                        <Loader2Icon className="size-4 animate-spin" />
                        Loading notes…
                    </div>
                ) : notesQuery.isError ? (
                    <div className="flex items-center justify-between gap-4">
                        <p className="text-sm text-destructive">Failed to load notes.</p>
                        <Button
                            variant="outline"
                            size="sm"
                            aria-label="Retry notes"
                            onClick={() => { void notesQuery.refetch() }}
                        >
                            Retry
                        </Button>
                    </div>
                ) : (notesQuery.data?.length ?? 0) === 0 ? (
                    <p className="text-sm text-muted-foreground">No notes yet.</p>
                ) : (
                    <ul className="space-y-3" aria-label="Donor notes">
                        {notesQuery.data?.map((note) => {
                            const canDelete = canEdit && (
                                canDeleteAny || note.author_id === currentUserId
                            )
                            const createdAt = formatDateTime(note.created_at, "—")
                            return (
                                <li key={note.id} className="rounded-lg border p-3">
                                    <div className="flex items-start gap-3">
                                        <div className="min-w-0 flex-1">
                                            <SafeHtmlContent
                                                html={note.content}
                                                className="prose prose-sm max-w-none text-sm dark:prose-invert"
                                            />
                                            <time
                                                className="mt-2 block text-xs text-muted-foreground"
                                                dateTime={note.created_at}
                                            >
                                                {createdAt}
                                            </time>
                                        </div>
                                        {canDelete ? (
                                            <Button
                                                type="button"
                                                size="icon-sm"
                                                variant="ghost"
                                                className="text-destructive hover:text-destructive"
                                                aria-label={`Delete note from ${createdAt}`}
                                                disabled={deleteNote.isPending}
                                                onClick={() => { void handleDelete(note.id) }}
                                            >
                                                <Trash2Icon className="size-4" />
                                            </Button>
                                        ) : null}
                                    </div>
                                </li>
                            )
                        })}
                    </ul>
                )}
            </CardContent>
        </Card>
    )
}
