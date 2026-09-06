import type {
    MatchWork,
    MatchWorkActivity,
    MatchWorkFile,
    MatchWorkNote,
    MatchWorkSource,
    MatchWorkTask,
} from "@/lib/api/matches"
import type { SourceFilter } from "./useMatchDetailTabState"

export type CombinedNote = MatchWorkNote
export type CombinedFile = MatchWorkFile
export type CombinedTask = MatchWorkTask
export type CombinedActivity = MatchWorkActivity

export const isDeletableSource = (value: MatchWorkSource): value is MatchWorkSource =>
    value === "surrogate" || value === "ip" || value === "donor" || value === "match"

export function selectMatchDetailTabData(work: MatchWork | undefined, sourceFilter: SourceFilter) {
    const filter = <T extends { source: MatchWorkSource }>(items: T[] | undefined): T[] =>
        (items ?? []).filter((item) => sourceFilter === "all" || item.source === sourceFilter)
    return {
        filteredNotes: filter(work?.notes),
        filteredFiles: filter(work?.files),
        filteredTasks: filter(work?.tasks),
        filteredActivity: filter(work?.activity),
    }
}
