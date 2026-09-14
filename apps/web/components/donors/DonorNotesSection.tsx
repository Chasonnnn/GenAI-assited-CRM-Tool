"use client"

import { EntityNotes } from "@/components/notes/EntityNotes"
import { Card, CardContent } from "@/components/ui/card"
import { useCreateDonorNote, useDeleteDonorNote, useDonorNotes } from "@/lib/hooks/use-donors"

export function DonorNotesSection({ donorId, canEdit, currentUserId, canDeleteAny, embedded = false }: {
    embedded?: boolean
    donorId: string
    canEdit: boolean
    currentUserId: string | null
    canDeleteAny: boolean
}) {
    const notesQuery = useDonorNotes(donorId)
    const createNote = useCreateDonorNote()
    const deleteNote = useDeleteDonorNote()

    const content = <EntityNotes
        key={donorId}
        notes={notesQuery.data?.map((note) => ({ ...note, body: note.content }))}
        status={notesQuery.isLoading ? "loading" : notesQuery.isError ? "error" : "ready"}
        onRetry={() => { void notesQuery.refetch() }}
        onAddNote={async (content) => { await createNote.mutateAsync({ donorId, data: { content } }) }}
        isSubmitting={createNote.isPending}
        onDeleteNote={async (noteId) => { await deleteNote.mutateAsync({ donorId, noteId }) }}
        canCreate={canEdit}
        canDeleteNote={(note) => canEdit && (canDeleteAny || note.author_id === currentUserId)}
        editorLabel="New donor note"
        listLabel="Donor notes"
    />
    return embedded ? content : <Card><CardContent>{content}</CardContent></Card>
}
