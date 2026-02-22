"use client"

import { useMemo } from "react"
import type { DataSource, SourceFilter } from "./useMatchDetailTabState"

type SurrogateNoteInput = {
    id: string
    body: string
    created_at: string
    author_name?: string | null
}

type IntendedParentNoteInput = {
    id: string
    content: string
    created_at: string
}

type AttachmentInput = {
    id: string
    filename: string
    file_size: number
    created_at: string
}

type TaskItemInput = {
    id: string
    title: string
    due_date: string | null
    is_completed: boolean
}

type TaskCollectionInput = {
    items: TaskItemInput[]
} | null | undefined

type SurrogateActivityItemInput = {
    id: string
    activity_type: string
    details?: {
        description?: unknown
    } | null
    actor_name: string | null
    created_at: string
}

type SurrogateActivityInput = {
    items: SurrogateActivityItemInput[]
} | null | undefined

type IntendedParentHistoryItemInput = {
    id: string
    old_status?: string | null
    new_status?: string | null
    reason?: string | null
    changed_by_name: string | null
    changed_at: string
}

type MatchTabDataInput = {
    notes?: string | null
    updated_at?: string | null
    created_at?: string | null
    proposed_at?: string | null
} | null | undefined

export type CombinedNote = {
    id: string
    content: string
    created_at: string
    source: DataSource
    author_name?: string
}

export type CombinedFile = {
    id: string
    filename: string
    file_size: number
    created_at: string
    source: DataSource
}

export type CombinedTask = {
    id: string
    title: string
    due_date: string | null
    is_completed: boolean
    source: DataSource
}

export type CombinedActivity = {
    id: string
    event_type: string
    description: string
    actor_name: string | null
    created_at: string
    source: DataSource
}

type UseMatchDetailTabDataParams = {
    sourceFilter: SourceFilter
    surrogateNotes: SurrogateNoteInput[]
    intendedParentNotes: IntendedParentNoteInput[]
    surrogateFiles: AttachmentInput[]
    intendedParentFiles: AttachmentInput[]
    surrogateTasks: TaskCollectionInput
    intendedParentTasks: TaskCollectionInput
    surrogateActivity: SurrogateActivityInput
    intendedParentHistory: IntendedParentHistoryItemInput[] | null | undefined
    match: MatchTabDataInput
}

export const isDeletableSource = (value: DataSource): value is "surrogate" | "ip" =>
    value === "surrogate" || value === "ip"

function filterBySource<T extends { source: DataSource }>(
    items: T[],
    sourceFilter: SourceFilter
): T[] {
    if (sourceFilter === "all") return items
    return items.filter((item) => item.source === sourceFilter)
}

export function useMatchDetailTabData({
    sourceFilter,
    surrogateNotes,
    intendedParentNotes,
    surrogateFiles,
    intendedParentFiles,
    surrogateTasks,
    intendedParentTasks,
    surrogateActivity,
    intendedParentHistory,
    match,
}: UseMatchDetailTabDataParams) {
    const combinedNotes = useMemo<CombinedNote[]>(() => {
        const notes: CombinedNote[] = []

        for (const surrogateNote of surrogateNotes) {
            const note: CombinedNote = {
                id: surrogateNote.id,
                content: surrogateNote.body,
                created_at: surrogateNote.created_at,
                source: "surrogate",
            }
            if (surrogateNote.author_name) {
                note.author_name = surrogateNote.author_name
            }
            notes.push(note)
        }

        for (const intendedParentNote of intendedParentNotes) {
            notes.push({
                id: intendedParentNote.id,
                content: intendedParentNote.content,
                created_at: intendedParentNote.created_at,
                source: "ip",
            })
        }

        if (match?.notes) {
            notes.push({
                id: "match-notes",
                content: match.notes,
                created_at: match.updated_at || match.created_at || "",
                source: "match",
            })
        }

        notes.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        return notes
    }, [intendedParentNotes, match, surrogateNotes])

    const combinedFiles = useMemo<CombinedFile[]>(() => {
        const files: CombinedFile[] = []

        for (const surrogateFile of surrogateFiles) {
            files.push({
                id: surrogateFile.id,
                filename: surrogateFile.filename,
                file_size: surrogateFile.file_size,
                created_at: surrogateFile.created_at,
                source: "surrogate",
            })
        }

        for (const intendedParentFile of intendedParentFiles) {
            files.push({
                id: intendedParentFile.id,
                filename: intendedParentFile.filename,
                file_size: intendedParentFile.file_size,
                created_at: intendedParentFile.created_at,
                source: "ip",
            })
        }

        files.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        return files
    }, [intendedParentFiles, surrogateFiles])

    const combinedTasks = useMemo<CombinedTask[]>(() => {
        const tasks: CombinedTask[] = []

        for (const surrogateTask of surrogateTasks?.items || []) {
            tasks.push({
                id: surrogateTask.id,
                title: surrogateTask.title,
                due_date: surrogateTask.due_date,
                is_completed: surrogateTask.is_completed,
                source: "surrogate",
            })
        }

        for (const intendedParentTask of intendedParentTasks?.items || []) {
            tasks.push({
                id: intendedParentTask.id,
                title: intendedParentTask.title,
                due_date: intendedParentTask.due_date,
                is_completed: intendedParentTask.is_completed,
                source: "ip",
            })
        }

        return tasks
    }, [intendedParentTasks, surrogateTasks])

    const combinedActivity = useMemo<CombinedActivity[]>(() => {
        const activity: CombinedActivity[] = []

        for (const surrogateEvent of surrogateActivity?.items || []) {
            const description =
                typeof surrogateEvent.details?.description === "string"
                    ? surrogateEvent.details.description
                    : surrogateEvent.activity_type
            activity.push({
                id: surrogateEvent.id,
                event_type: surrogateEvent.activity_type,
                description,
                actor_name: surrogateEvent.actor_name,
                created_at: surrogateEvent.created_at,
                source: "surrogate",
            })
        }

        for (const history of intendedParentHistory || []) {
            activity.push({
                id: history.id,
                event_type: "Status Change",
                description: `Status: ${history.old_status || "new"} → ${history.new_status}${history.reason ? ` (${history.reason})` : ""}`,
                actor_name: history.changed_by_name,
                created_at: history.changed_at,
                source: "ip",
            })
        }

        if (match?.proposed_at) {
            activity.push({
                id: "match-proposed",
                event_type: "Match Proposed",
                description: "Match was proposed",
                actor_name: null,
                created_at: match.proposed_at,
                source: "match",
            })
        }

        activity.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        return activity
    }, [intendedParentHistory, match, surrogateActivity])

    const filteredNotes = useMemo(
        () => filterBySource(combinedNotes, sourceFilter),
        [combinedNotes, sourceFilter]
    )
    const filteredFiles = useMemo(
        () => filterBySource(combinedFiles, sourceFilter),
        [combinedFiles, sourceFilter]
    )
    const filteredTasks = useMemo(
        () => filterBySource(combinedTasks, sourceFilter),
        [combinedTasks, sourceFilter]
    )
    const filteredActivity = useMemo(
        () => filterBySource(combinedActivity, sourceFilter),
        [combinedActivity, sourceFilter]
    )

    return {
        filteredNotes,
        filteredFiles,
        filteredTasks,
        filteredActivity,
    }
}
