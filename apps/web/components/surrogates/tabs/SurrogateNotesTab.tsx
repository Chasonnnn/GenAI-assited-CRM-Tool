"use client"

import { Card } from "@/components/ui/card"
import { TabsContent } from "@/components/ui/tabs"
import { FileUploadZone } from "@/components/FileUploadZone"
import { EntityNotes, type EntityNotesProps } from "@/components/notes/EntityNotes"
import type { NoteRead } from "@/lib/types/note"

type SurrogateNotesTabProps = Omit<EntityNotesProps, "notes"> & {
    surrogateId: string
    notes?: NoteRead[] | undefined
}

export function SurrogateNotesTab({ surrogateId, notes, ...props }: SurrogateNotesTabProps) {
    return (
        <TabsContent value="notes">
            <Card>
                <div className="grid grid-cols-1 divide-y divide-border lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:divide-x lg:divide-y-0">
                    <div className="order-last min-w-0 p-6 lg:order-first">
                        <EntityNotes key={surrogateId} notes={notes} editorLabel="New surrogate note" {...props} />
                    </div>
                    <div className="order-first min-w-0 p-6 lg:sticky lg:top-4 lg:self-start lg:order-last">
                        <div className="mb-4 flex items-center justify-between"><h3 className="text-lg font-semibold">Attachments</h3></div>
                        <FileUploadZone surrogateId={surrogateId} />
                    </div>
                </div>
            </Card>
        </TabsContent>
    )
}
