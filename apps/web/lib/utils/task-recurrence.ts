import { addDays, addWeeks, addMonths } from "date-fns"

export type TaskRecurrence = "none" | "daily" | "weekly" | "monthly"

export const MAX_TASK_OCCURRENCES = 52

export function buildRecurringDates(
    start: Date,
    end: Date,
    recurrence: TaskRecurrence
): Date[] {
    if (recurrence === "none") return [start]

    const dates: Date[] = []
    let cursor = start

    while (cursor <= end && dates.length < MAX_TASK_OCCURRENCES) {
        dates.push(cursor)
        if (recurrence === "daily") {
            cursor = addDays(cursor, 1)
        } else if (recurrence === "weekly") {
            cursor = addWeeks(cursor, 1)
        } else {
            cursor = addMonths(cursor, 1)
        }
    }

    return dates
}
