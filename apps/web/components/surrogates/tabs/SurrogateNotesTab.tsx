"use client"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { TabsContent } from "@/components/ui/tabs"
import { RichTextEditor } from "@/components/rich-text-editor"
import { FileUploadZone } from "@/components/FileUploadZone"
import type { NoteRead } from "@/lib/types/note"
import { TrashIcon } from "lucide-react"

type SurrogateNotesTabProps = {
    surrogateId: string
    notes?: NoteRead[] | undefined
    onAddNote: (html: string) => Promise<void> | void
    isSubmitting: boolean
    onDeleteNote: (noteId: string) => Promise<void> | void
    formatDateTime: (dateString: string) => string
}

export function SurrogateNotesTab({
    surrogateId,
    notes,
    onAddNote,
    isSubmitting,
    onDeleteNote,
    formatDateTime,
}: SurrogateNotesTabProps) {
    const getInitials = (name: string | null): string => {
        if (!name) return "?"
        return name.split(" ").map((part) => part[0]).join("").toUpperCase().slice(0, 2)
    }

    return (
        <TabsContent value="notes">
            <Card>
                <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] divide-y lg:divide-y-0 lg:divide-x divide-border">
                    {/* Notes Column - Left/Main */}
                    <div className="p-6 order-last lg:order-first">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-lg font-semibold">Notes</h3>
                            {notes && notes.length > 0 && (
                                <Badge variant="secondary" className="text-xs">
                                    {notes.length}
                                </Badge>
                            )}
                        </div>

                        {/* Add Note Section */}
                        <div className="rounded-lg border border-border bg-muted/30 p-4 mb-6">
                            <h4 className="text-sm font-medium mb-3 text-muted-foreground">Add a note</h4>
                            <RichTextEditor
                                placeholder="Write your note here..."
                                onSubmit={onAddNote}
                                submitLabel="Add Note"
                                isSubmitting={isSubmitting}
                            />
                        </div>

                        {/* Notes List */}
                        {notes && notes.length > 0 ? (
                            <div className="space-y-3">
                                {notes.map((note) => (
                                    <div
                                        key={note.id}
                                        className="group rounded-lg border border-border bg-card p-4 transition-colors hover:bg-accent/30"
                                    >
                                        <div className="flex items-start gap-3">
                                            <Avatar className="h-9 w-9 flex-shrink-0">
                                                <AvatarFallback className="text-xs bg-primary/10 text-primary">
                                                    {getInitials(note.author_name)}
                                                </AvatarFallback>
                                            </Avatar>
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center justify-between gap-2">
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-sm font-medium">{note.author_name || "Unknown"}</span>
                                                        <span className="text-xs text-muted-foreground">
                                                            {formatDateTime(note.created_at)}
                                                        </span>
                                                    </div>
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity"
                                                        onClick={() => onDeleteNote(note.id)}
                                                    >
                                                        <TrashIcon className="h-3.5 w-3.5 text-muted-foreground hover:text-destructive" />
                                                    </Button>
                                                </div>
                                                <div
                                                    className="mt-2 text-sm prose prose-sm max-w-none dark:prose-invert"
                                                    dangerouslySetInnerHTML={{ __html: note.body }}
                                                />
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-center py-8">
                                <p className="text-sm text-muted-foreground">No notes yet. Add the first note above.</p>
                            </div>
                        )}
                    </div>

                    {/* Attachments Column - Right/Sidebar */}
                    <div className="lg:sticky lg:top-4 lg:self-start p-6 order-first lg:order-last">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-lg font-semibold">Attachments</h3>
                        </div>
                        <FileUploadZone surrogateId={surrogateId} />
                    </div>
                </div>
            </Card>
        </TabsContent>
    )
}
