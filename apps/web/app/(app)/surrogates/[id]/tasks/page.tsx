"use client"

import * as React from "react"
import { useParams } from "next/navigation"
import { format, parseISO } from "date-fns"
import { AddSurrogateTaskDialog, type SurrogateTaskFormData } from "@/components/surrogates/AddSurrogateTaskDialog"
import { SurrogateTasksTab } from "@/components/surrogates/tabs/SurrogateTasksTab"
import { TaskEditModal } from "@/components/tasks/TaskEditModal"
import {
    useTasks,
    useCompleteTask,
    useUncompleteTask,
    useCreateTask,
    useUpdateTask,
    useDeleteTask,
} from "@/lib/hooks/use-tasks"
import { useSurrogate } from "@/lib/hooks/use-surrogates"
import type { TaskListItem } from "@/lib/types/task"
import { buildRecurringDates, MAX_TASK_OCCURRENCES } from "@/lib/utils/task-recurrence"

type TaskEditPayload = {
    id: string
    title: string
    description: string | null
    task_type: string
    due_date: string | null
    due_time: string | null
    is_completed: boolean
    surrogate_id: string | null
}

export default function SurrogateTasksPage() {
    const params = useParams<{ id: string }>()
    const id = params.id
    const { data: surrogateData } = useSurrogate(id)
    const { data: tasksData, isLoading: tasksLoading } = useTasks({
        surrogate_id: id,
        exclude_approvals: true,
    })
    const completeTaskMutation = useCompleteTask()
    const uncompleteTaskMutation = useUncompleteTask()
    const createTaskMutation = useCreateTask()
    const updateTaskMutation = useUpdateTask()
    const deleteTaskMutation = useDeleteTask()

    const [addTaskDialogOpen, setAddTaskDialogOpen] = React.useState(false)
    const [editingTask, setEditingTask] = React.useState<TaskListItem | null>(null)

    const handleTaskToggle = async (taskId: string, isCompleted: boolean) => {
        if (isCompleted) {
            await uncompleteTaskMutation.mutateAsync(taskId)
        } else {
            await completeTaskMutation.mutateAsync(taskId)
        }
    }

    const handleAddTask = async (data: SurrogateTaskFormData) => {
        const dueTime = data.due_time ? `${data.due_time}:00` : undefined
        const buildPayload = (dueDate?: string) => ({
            title: data.title,
            task_type: data.task_type,
            surrogate_id: id,
            ...(data.description ? { description: data.description } : {}),
            ...(dueDate ? { due_date: dueDate } : {}),
            ...(dueTime ? { due_time: dueTime } : {}),
        })

        if (data.recurrence === "none") {
            await createTaskMutation.mutateAsync(buildPayload(data.due_date))
            return
        }

        if (!data.due_date || !data.repeat_until) {
            return
        }

        const start = parseISO(data.due_date)
        const end = parseISO(data.repeat_until)
        const dates = buildRecurringDates(start, end, data.recurrence)

        const lastDate = dates[dates.length - 1]
        if (dates.length >= MAX_TASK_OCCURRENCES && lastDate && end > lastDate) {
            return
        }

        for (const date of dates) {
            await createTaskMutation.mutateAsync(buildPayload(format(date, "yyyy-MM-dd")))
        }
    }

    const handleTaskClick = (task: TaskListItem) => {
        setEditingTask(task)
    }

    const handleSaveTask = async (taskId: string, data: Partial<TaskEditPayload>) => {
        const payload: Record<string, unknown> = {}
        for (const [key, value] of Object.entries(data)) {
            payload[key] = value === null ? undefined : value
        }
        await updateTaskMutation.mutateAsync({ taskId, data: payload })
    }

    const handleDeleteTask = async (taskId: string) => {
        await deleteTaskMutation.mutateAsync(taskId)
        setEditingTask(null)
    }

    return (
        <>
            <SurrogateTasksTab
                surrogateId={id}
                tasks={tasksData?.items || []}
                isLoading={tasksLoading}
                onTaskToggle={handleTaskToggle}
                onAddTask={() => setAddTaskDialogOpen(true)}
                onTaskClick={handleTaskClick}
            />
            <AddSurrogateTaskDialog
                open={addTaskDialogOpen}
                onOpenChange={setAddTaskDialogOpen}
                onSubmit={handleAddTask}
                isPending={createTaskMutation.isPending}
                surrogateName={surrogateData?.full_name || "this surrogate"}
            />
            <TaskEditModal
                task={
                    editingTask
                        ? {
                              id: editingTask.id,
                              title: editingTask.title,
                              description: editingTask.description ?? null,
                              task_type: editingTask.task_type,
                              due_date: editingTask.due_date,
                              due_time: editingTask.due_time ?? null,
                              is_completed: editingTask.is_completed,
                              surrogate_id: editingTask.surrogate_id,
                          }
                        : null
                }
                open={!!editingTask}
                onClose={() => setEditingTask(null)}
                onSave={handleSaveTask}
                onDelete={handleDeleteTask}
                isDeleting={deleteTaskMutation.isPending}
            />
        </>
    )
}
