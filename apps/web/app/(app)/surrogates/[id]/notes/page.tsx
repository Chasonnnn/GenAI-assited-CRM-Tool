"use client"

import { useParams } from "next/navigation"
import { SurrogateNotesTab } from "@/components/surrogates/tabs/SurrogateNotesTab"
import { useNotes, useCreateNote, useDeleteNote } from "@/lib/hooks/use-notes"
import { formatDateTime } from "@/components/surrogates/detail/surrogate-detail-utils"

export default function SurrogateNotesPage() {
    const params = useParams<{ id: string }>()
    const id = params.id
    const { data: notes } = useNotes(id)
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
            notes={notes}
            onAddNote={handleAddNote}
            isSubmitting={createNoteMutation.isPending}
            onDeleteNote={handleDeleteNote}
            formatDateTime={formatDateTime}
        />
    )
}
