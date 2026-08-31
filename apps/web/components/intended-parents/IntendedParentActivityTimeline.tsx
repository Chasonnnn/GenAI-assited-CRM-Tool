"use client"

import { EntityActivityTimeline } from "@/components/activity/EntityActivityTimeline"
import type { Attachment } from "@/lib/api/attachments"
import type { PipelineStage } from "@/lib/api/pipelines"
import type { SurrogateActivity } from "@/lib/api/surrogates"
import type { TaskListItem } from "@/lib/api/tasks"
import { normalizeIntendedParentHistory } from "@/lib/activity-history"
import type {
    EntityNoteListItem,
    IntendedParentStatusHistoryItem,
} from "@/lib/types/intended-parent"

export function IntendedParentActivityTimeline({
    currentStageId,
    stages,
    history,
    notes,
    attachments,
    tasks,
}: {
    currentStageId: string
    stages: PipelineStage[]
    history: IntendedParentStatusHistoryItem[]
    notes: EntityNoteListItem[]
    attachments: Attachment[]
    tasks: TaskListItem[]
}) {
    const noteActivities: SurrogateActivity[] = notes.map((note) => ({
        id: note.id,
        activity_type: "note_added",
        actor_user_id: note.author_id,
        actor_name: null,
        details: { note_id: note.id, preview: note.content },
        created_at: note.created_at,
    }))
    const attachmentActivities: SurrogateActivity[] = attachments.map((attachment) => ({
        id: attachment.id,
        activity_type: "attachment_added",
        actor_user_id: attachment.uploaded_by_user_id,
        actor_name: null,
        details: { attachment_id: attachment.id, filename: attachment.filename },
        created_at: attachment.created_at,
    }))

    return (
        <EntityActivityTimeline
            currentStageId={currentStageId}
            stages={stages}
            stageHistory={normalizeIntendedParentHistory(history)}
            activities={[...noteActivities, ...attachmentActivities]}
            tasks={tasks}
        />
    )
}
