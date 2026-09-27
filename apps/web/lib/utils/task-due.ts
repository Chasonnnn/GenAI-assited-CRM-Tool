import { format } from "date-fns"

import { parseDateInput, startOfLocalDay } from "@/lib/utils/date"

export type DueCategory = "overdue" | "today" | "tomorrow" | "this-week" | "later" | "no-date"

function isOverdue(dueDate: string | null): boolean {
    if (!dueDate) return false
    return parseDateInput(dueDate) < startOfLocalDay()
}

function isDueToday(dueDate: string | null): boolean {
    if (!dueDate) return false
    const due = parseDateInput(dueDate)
    const today = startOfLocalDay()
    return due.getTime() === today.getTime()
}

function isDueTomorrow(dueDate: string | null): boolean {
    if (!dueDate) return false
    const due = parseDateInput(dueDate)
    const tomorrow = startOfLocalDay()
    tomorrow.setDate(tomorrow.getDate() + 1)
    return due.getTime() === tomorrow.getTime()
}

function isDueThisWeek(dueDate: string | null): boolean {
    if (!dueDate) return false
    const due = parseDateInput(dueDate)
    const today = startOfLocalDay()
    const endOfWeek = new Date(today)
    endOfWeek.setDate(today.getDate() + 7)
    return due > today && due <= endOfWeek && !isDueToday(dueDate) && !isDueTomorrow(dueDate)
}

/**
 * Orders tasks by due date, then due time, with untimed tasks after timed ones on the same day
 * and undated tasks last. Matches the API's list order.
 */
export function compareTasksByDueTime(
    a: { due_date: string | null; due_time: string | null },
    b: { due_date: string | null; due_time: string | null },
): number {
    const dateOrder = (a.due_date ?? "9999-99-99").localeCompare(b.due_date ?? "9999-99-99")
    if (dateOrder !== 0) return dateOrder
    return (a.due_time ?? "99:99:99").localeCompare(b.due_time ?? "99:99:99")
}

/** Formats an API due time ("HH:MM[:SS]") as "h:mm a". */
export function formatDueTime(dueTime: string): string {
    const [hours = 0, minutes = 0] = dueTime.split(":").map(Number)
    return format(new Date(2000, 0, 1, hours, minutes), "h:mm a")
}

export function getDueCategory(task: { due_date: string | null }): DueCategory {
    if (!task.due_date) return "no-date"
    if (isOverdue(task.due_date)) return "overdue"
    if (isDueToday(task.due_date)) return "today"
    if (isDueTomorrow(task.due_date)) return "tomorrow"
    if (isDueThisWeek(task.due_date)) return "this-week"
    return "later"
}

export const categoryLabels: Record<DueCategory, string> = {
    overdue: "Overdue",
    today: "Today",
    tomorrow: "Tomorrow",
    "this-week": "This Week",
    later: "Later",
    "no-date": "No Due Date",
}

export const categoryColors: Record<DueCategory, { text: string; badge: string }> = {
    overdue: { text: "text-destructive", badge: "bg-destructive/10 text-destructive border-destructive/20" },
    today: { text: "text-amber-500", badge: "bg-amber-500/10 text-amber-500 border-amber-500/20" },
    tomorrow: { text: "text-blue-500", badge: "bg-blue-500/10 text-blue-500 border-blue-500/20" },
    "this-week": { text: "text-muted-foreground", badge: "bg-muted-foreground/10 text-muted-foreground border-muted-foreground/20" },
    later: { text: "text-muted-foreground", badge: "bg-muted-foreground/10 text-muted-foreground border-muted-foreground/20" },
    "no-date": { text: "text-muted-foreground", badge: "bg-muted-foreground/10 text-muted-foreground border-muted-foreground/20" },
}
