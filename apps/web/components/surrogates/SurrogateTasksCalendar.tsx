"use client"

/**
 * SurrogateTasksCalendar - List/Calendar view for surrogate-specific tasks.
 *
 * Features:
 * - Toggle between list and calendar views (persisted per-surrogate)
 * - List view groups tasks by: Overdue, Today, Upcoming, No Date
 * - Calendar view reuses UnifiedCalendar (same as My Tasks)
 */

import { CalendarCheckIcon, Loader2Icon } from "lucide-react"

import { UnifiedCalendar } from "@/components/appointments/UnifiedCalendar"
import { EmptyState } from "@/components/empty-state"
import { QueryErrorState } from "@/components/error-state"
import { Card } from "@/components/ui/card"
import type { TaskListItem } from "@/lib/api/tasks"

import { SurrogateTasksCalendarHeader } from "./SurrogateTasksCalendarHeader"
import { SurrogateTasksListView } from "./SurrogateTasksListView"
import {
    buildTaskGroups,
    countCompletedTasks,
    getOrphanedCompletedTasks,
} from "./surrogate-task-derivations"
import {
    useSurrogateTaskViewMode,
} from "./use-surrogate-task-view-mode"

export interface SurrogateTasksLoadError {
    error: unknown
    onRetry: () => void
    isRetrying: boolean
}

interface SurrogateTasksCalendarProps {
    surrogateId: string
    tasks: TaskListItem[]
    isLoading?: boolean
    /** Set when the task list failed to load; it replaces the empty state and both views. */
    loadError?: SurrogateTasksLoadError | null | undefined
    onTaskToggle: (taskId: string, completed: boolean) => void
    onAddTask: () => void
    onTaskClick?: (task: TaskListItem) => void
}

export function SurrogateTasksCalendar({
    surrogateId,
    tasks,
    isLoading = false,
    loadError = null,
    onTaskToggle,
    onAddTask,
    onTaskClick,
}: SurrogateTasksCalendarProps) {
    const [viewMode, setViewMode] = useSurrogateTaskViewMode(surrogateId)
    const taskGroups = buildTaskGroups(tasks)
    const orphanedCompletedTasks = getOrphanedCompletedTasks(taskGroups, tasks)
    const completedTaskCount = countCompletedTasks(tasks)

    return (
        <div className="space-y-4">
            <SurrogateTasksCalendarHeader
                taskCount={tasks.length}
                viewMode={viewMode}
                onAddTask={onAddTask}
                onViewModeChange={setViewMode}
            />

            {isLoading ? (
                <Card className="flex items-center justify-center py-12">
                    <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                </Card>
            ) : loadError ? (
                <Card>
                    <QueryErrorState
                        error={loadError.error}
                        onRetry={loadError.onRetry}
                        isRetrying={loadError.isRetrying}
                        title="Couldn't load tasks"
                        className="min-h-0 py-10"
                    />
                </Card>
            ) : tasks.length === 0 ? (
                // The header's Add Task is the create action, so the empty state has none.
                <Card>
                    <EmptyState icon={CalendarCheckIcon} title="No tasks yet" />
                </Card>
            ) : viewMode === "list" ? (
                <SurrogateTasksListView
                    completedTaskCount={completedTaskCount}
                    orphanedCompletedTasks={orphanedCompletedTasks}
                    taskGroups={taskGroups}
                    onTaskToggle={onTaskToggle}
                    {...(onTaskClick ? { onTaskClick } : {})}
                />
            ) : (
                <UnifiedCalendar
                    taskFilter={{ surrogate_id: surrogateId }}
                    includeAppointments={false}
                    includeGoogleEvents={false}
                    {...(onTaskClick ? { onTaskClick } : {})}
                />
            )}
        </div>
    )
}
