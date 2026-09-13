"use client"

import { TabsContent } from "@/components/ui/tabs"
import { SurrogateTasksCalendar } from "@/components/surrogates/SurrogateTasksCalendar"
import type { TaskListItem } from "@/lib/types/task"

type SurrogateTasksTabProps = {
    canCreateTask?: boolean
    canToggleTask?: (task: TaskListItem) => boolean
    surrogateId: string
    tasks: TaskListItem[]
    isLoading: boolean
    onTaskToggle: (taskId: string, isCompleted: boolean) => Promise<void> | void
    onAddTask: () => void
    onTaskClick: (task: TaskListItem) => void
}

export function SurrogateTasksTab({
    canCreateTask = true,
    canToggleTask = () => true,
    surrogateId,
    tasks,
    isLoading,
    onTaskToggle,
    onAddTask,
    onTaskClick,
}: SurrogateTasksTabProps) {
    return (
        <TabsContent value="tasks" className="space-y-4">
            <SurrogateTasksCalendar
                canCreateTask={canCreateTask}
                canToggleTask={canToggleTask}
                surrogateId={surrogateId}
                tasks={tasks}
                isLoading={isLoading}
                onTaskToggle={onTaskToggle}
                onAddTask={onAddTask}
                onTaskClick={onTaskClick}
            />
        </TabsContent>
    )
}
