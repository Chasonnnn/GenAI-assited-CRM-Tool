"use client"

import { useState } from "react"
import { Loader2Icon, TrashIcon } from "lucide-react"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { RichTextEditor } from "@/components/rich-text-editor"
import { RichTextPreview } from "@/components/rich-text-preview"
import { formatDateTime as defaultFormatDateTime } from "@/lib/formatters"

export interface EntityNoteItem {
    id: string
    body: string
    author_id: string | null
    author_name?: string | null
    created_at: string
}

export interface EntityNotesProps {
    notes?: EntityNoteItem[] | undefined
    status?: "loading" | "error" | "ready"
    onRetry?: (() => void) | undefined
    onAddNote: (html: string) => Promise<void> | void
    isSubmitting: boolean
    onDeleteNote: (noteId: string) => Promise<void> | void
    canCreate?: boolean
    canDeleteNote?: ((note: EntityNoteItem) => boolean) | undefined
    currentUser?: { id: string; name?: string | null } | undefined
    editorLabel?: string
    listLabel?: string
    formatDateTime?: (dateString: string) => string
}

export function EntityNotes({
    notes,
    status = "ready",
    onRetry,
    onAddNote,
    isSubmitting,
    onDeleteNote,
    canCreate = true,
    canDeleteNote = () => true,
    currentUser,
    editorLabel = "New note",
    listLabel = "Notes",
    formatDateTime = (value) => defaultFormatDateTime(value, "—"),
}: EntityNotesProps) {
    const [draft, setDraft] = useState("")
    const [error, setError] = useState<string | null>(null)
    const [deletingNote, setDeletingNote] = useState<EntityNoteItem | null>(null)
    const [isDeleting, setIsDeleting] = useState(false)
    const hasContent = Boolean(draft.replace(/<[^>]*>/g, "").replace(/&nbsp;/g, " ").trim())
    const authorName = (note: EntityNoteItem) => note.author_name
        || (note.author_id === currentUser?.id ? currentUser?.name : null)
        || "Unknown"

    const handleAdd = async () => {
        if (!hasContent || isSubmitting) return
        setError(null)
        try {
            await onAddNote(draft.trim())
            setDraft("")
        } catch (error) {
            setError(error instanceof Error ? error.message : "Failed to add note")
        }
    }

    const handleDelete = async () => {
        if (!deletingNote || isDeleting) return
        setIsDeleting(true)
        setError(null)
        try {
            await onDeleteNote(deletingNote.id)
            setDeletingNote(null)
        } catch (error) {
            setError(error instanceof Error ? error.message : "Failed to delete note")
        } finally {
            setIsDeleting(false)
        }
    }

    return (
        <div className="min-w-0 space-y-4">
            <div className="flex items-center gap-2"><h3 className="text-lg font-semibold">Notes</h3>{notes?.length ? <Badge variant="secondary">{notes.length}</Badge> : null}</div>
            {canCreate ? (
                <div className="min-w-0 space-y-3 rounded-lg border border-border bg-muted/30 p-4">
                    <RichTextEditor content={draft} onChange={setDraft} placeholder="Add a note..." ariaLabel={editorLabel} enableEmojiPicker />
                    <Button onClick={() => { void handleAdd() }} disabled={!hasContent || isSubmitting}>{isSubmitting ? <Loader2Icon className="size-4 animate-spin" /> : null}Add Note</Button>
                </div>
            ) : null}
            {error && !deletingNote ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
            {status === "loading" ? <p role="status" className="text-sm text-muted-foreground">Loading notes…</p>
                : status === "error" ? <div className="space-y-3"><p className="text-sm text-destructive">Failed to load notes.</p><Button variant="outline" size="sm" aria-label="Retry notes" onClick={onRetry}>Retry</Button></div>
                : !notes?.length ? <p className="text-sm text-muted-foreground">No notes yet.</p>
                : <ul className="space-y-3" aria-label={listLabel}>
                    {notes.map((note) => {
                        const name = authorName(note)
                        return <li key={note.id} className="group rounded-lg border border-border bg-card p-4">
                            <div className="flex items-start gap-3">
                                <Avatar className="size-9 shrink-0"><AvatarFallback className="bg-primary/10 text-xs text-primary">{name === "Unknown" ? "?" : name.split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase()}</AvatarFallback></Avatar>
                                <div className="min-w-0 flex-1">
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                        <div className="flex flex-wrap items-center gap-2"><span className="text-sm font-medium">{name}</span><time className="text-xs text-muted-foreground" dateTime={note.created_at}>{formatDateTime(note.created_at)}</time></div>
                                        {canDeleteNote(note) ? <Button variant="ghost" size="icon-sm" aria-label={`Delete note by ${name}`} onClick={() => { setError(null); setDeletingNote(note) }}><TrashIcon className="size-3.5 text-muted-foreground" /></Button> : null}
                                    </div>
                                    <RichTextPreview html={note.body} className="mt-2 [overflow-wrap:anywhere] text-sm" />
                                </div>
                            </div>
                        </li>
                    })}
                </ul>}
            <Dialog open={Boolean(deletingNote)} onOpenChange={(open) => { if (!open && !isDeleting) { setDeletingNote(null); setError(null) } }}>
                <DialogContent>
                    <DialogHeader><DialogTitle>Delete note?</DialogTitle></DialogHeader>
                    {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
                    <DialogFooter>
                        <Button variant="outline" disabled={isDeleting} onClick={() => { setDeletingNote(null); setError(null) }}>Cancel</Button>
                        <Button variant="destructive" disabled={isDeleting} onClick={() => { void handleDelete() }}>{isDeleting ? "Deleting…" : "Delete Note"}</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}
