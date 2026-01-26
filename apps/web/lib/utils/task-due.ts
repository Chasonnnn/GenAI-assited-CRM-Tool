import { parseDateInput, startOfLocalDay } from "@/lib/utils/date"

export type DueCategory = "overdue" | "today" | "tomorrow" | "this-week" | "later" | "no-date"

export function isOverdue(dueDate: string | null): boolean {
    if (!dueDate) return false
    return parseDateInput(dueDate) < startOfLocalDay()
}

export function isDueToday(dueDate: string | null): boolean {
    if (!dueDate) return false
    const due = parseDateInput(dueDate)
    const today = startOfLocalDay()
    return due.getTime() === today.getTime()
}

export function isDueTomorrow(dueDate: string | null): boolean {
    if (!dueDate) return false
    const due = parseDateInput(dueDate)
    const tomorrow = startOfLocalDay()
    tomorrow.setDate(tomorrow.getDate() + 1)
    return due.getTime() === tomorrow.getTime()
}

export function isDueThisWeek(dueDate: string | null): boolean {
    if (!dueDate) return false
    const due = parseDateInput(dueDate)
    const today = startOfLocalDay()
    const endOfWeek = new Date(today)
    endOfWeek.setDate(today.getDate() + 7)
    return due > today && due <= endOfWeek && !isDueToday(dueDate) && !isDueTomorrow(dueDate)
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
