"use client"

import { EntityNotes } from "@/components/notes/EntityNotes"
import { Card, CardContent } from "@/components/ui/card"
import { useAuth } from "@/lib/auth-context"
import { useCreateIntendedParentNote, useDeleteIntendedParentNote, useIntendedParentNotes } from "@/lib/hooks/use-intended-parents"

export function IntendedParentNotesSection({ intendedParentId, canEdit }: { intendedParentId: string; canEdit: boolean }) {
    const { user } = useAuth()
    const notesQuery = useIntendedParentNotes(intendedParentId)
    const createNote = useCreateIntendedParentNote()
    const deleteNote = useDeleteIntendedParentNote()
    const canDeleteAny = user?.role === "admin" || user?.role === "developer"

    return <Card><CardContent><EntityNotes
        key={intendedParentId}
        notes={notesQuery.data?.map((note) => ({ ...note, body: note.content }))}
        status={notesQuery.isLoading ? "loading" : notesQuery.isError ? "error" : "ready"}
        onRetry={() => { void notesQuery.refetch() }}
        onAddNote={async (content) => { await createNote.mutateAsync({ id: intendedParentId, data: { content } }) }}
        isSubmitting={createNote.isPending}
        onDeleteNote={async (noteId) => { await deleteNote.mutateAsync({ ipId: intendedParentId, noteId }) }}
        canCreate={canEdit}
        canDeleteNote={(note) => canEdit && (canDeleteAny || note.author_id === user?.user_id)}
        {...(user ? { currentUser: { id: user.user_id, name: user.display_name } } : {})}
        editorLabel="New intended parent note"
        listLabel="Intended parent notes"
    /></CardContent></Card>
}
