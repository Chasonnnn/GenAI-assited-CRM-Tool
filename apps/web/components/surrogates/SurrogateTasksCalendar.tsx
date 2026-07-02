"use client"

/**
 * SurrogateTasksCalendar - List/Calendar view for surrogate-specific tasks.
 *
 * Features:
 * - Toggle between list and calendar views (persisted per-surrogate)
 * - List view groups tasks by: Overdue, Today, Upcoming, No Date
 * - Calendar view reuses UnifiedCalendar (same as My Tasks)
 */

import { Loader2Icon } from "lucide-react"

import { UnifiedCalendar } from "@/components/appointments/UnifiedCalendar"
import { Card } from "@/components/ui/card"
import type { TaskListItem } from "@/lib/api/tasks"

import { SurrogateTasksCalendarHeader } from "./SurrogateTasksCalendarHeader"
import { SurrogateTasksEmptyState } from "./SurrogateTasksEmptyState"
import { SurrogateTasksListView } from "./SurrogateTasksListView"
import {
    buildTaskGroups,
    countCompletedTasks,
    getOrphanedCompletedTasks,
} from "./surrogate-task-derivations"
import {
    useSurrogateTaskViewMode,
} from "./use-surrogate-task-view-mode"

interface SurrogateTasksCalendarProps {
    surrogateId: string
    tasks: TaskListItem[]
    isLoading?: boolean
    onTaskToggle: (taskId: string, completed: boolean) => void
    onAddTask: () => void
    onTaskClick?: (task: TaskListItem) => void
}

export function SurrogateTasksCalendar({
    surrogateId,
    tasks,
    isLoading = false,
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
            ) : tasks.length === 0 ? (
                <SurrogateTasksEmptyState onAddTask={onAddTask} />
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
