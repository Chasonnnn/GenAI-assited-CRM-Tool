"use client"

import { useAuth } from "@/lib/auth-context"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"
import { useParams } from "next/navigation"
import { SurrogateNotesTab } from "@/components/surrogates/tabs/SurrogateNotesTab"
import { useNotes, useCreateNote, useDeleteNote } from "@/lib/hooks/use-notes"
import { formatDateTime } from "@/components/surrogates/detail/surrogate-detail-utils"

export default function SurrogateNotesPage() {
    const params = useParams<{ id: string }>()
    const id = params.id
    const { user } = useAuth()
    const permissionsQuery = useEffectivePermissions(user?.user_id ?? null)
    const canEdit = user?.role === "developer" || (permissionsQuery.data?.permissions ?? []).includes("edit_surrogate_notes")
    const canDeleteAny = user?.role === "developer" || user?.role === "admin"
    const notesQuery = useNotes(id)
    const createNoteMutation = useCreateNote()
    const deleteNoteMutation = useDeleteNote()

    const handleAddNote = async (html: string) => {
        if (!html || html === "<p></p>") return
        await createNoteMutation.mutateAsync({ surrogateId: id, body: html })
    }

    const handleDeleteNote = async (noteId: string) => {
        await deleteNoteMutation.mutateAsync({ noteId, surrogateId: id })
    }

    return (
        <SurrogateNotesTab
            surrogateId={id}
            notes={notesQuery.data}
            status={notesQuery.isLoading ? "loading" : notesQuery.isError ? "error" : "ready"}
            onRetry={() => { void notesQuery.refetch() }}
            canCreate={canEdit}
            canDeleteNote={(note) => canEdit && (canDeleteAny || note.author_id === user?.user_id)}
            onAddNote={handleAddNote}
            isSubmitting={createNoteMutation.isPending}
            onDeleteNote={handleDeleteNote}
            formatDateTime={formatDateTime}
        />
    )
}
