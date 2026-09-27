"use client"

import * as React from "react"
import { useParams } from "next/navigation"
import { AddSurrogateTaskDialog, type SurrogateTaskFormData } from "@/components/surrogates/AddSurrogateTaskDialog"
import { SurrogateTasksTab } from "@/components/surrogates/tabs/SurrogateTasksTab"
import { TaskDetailDialog } from "@/components/tasks/TaskDetailDialog"
import { useTasks } from "@/lib/hooks/use-tasks"
import type { TaskListItem } from "@/lib/types/task"
import type { TaskUpdatePayload } from "@/lib/api/tasks"
import { useTaskActions } from "@/lib/hooks/use-task-actions"
import { useAuth } from "@/lib/auth-context"
import { useSurrogateDetailData } from "@/components/surrogates/detail/SurrogateDetailLayout/context"

export default function SurrogateTasksPage() {
    const params = useParams<{ id: string }>()
    const id = params.id
    const tasksQuery = useTasks({
        surrogate_id: id,
        exclude_approvals: true,
    })
    const tasksData = tasksQuery.data
    // A failed background refetch keeps the loaded list; only a failed first load shows the error.
    const tasksLoadError = tasksQuery.isError && !tasksData
        ? {
            error: tasksQuery.error,
            onRetry: () => { void tasksQuery.refetch() },
            isRetrying: tasksQuery.isFetching,
        }
        : null
    const taskActions = useTaskActions()
    const { user } = useAuth()
    const { effectivePermissions } = useSurrogateDetailData()
    const isV2 = effectivePermissions?.policy_version === 2
    const canCreateTask = !isV2 || effectivePermissions.permissions.includes("create_tasks")
    const canToggleTask = (task: TaskListItem) => !isV2 || (
        effectivePermissions.permissions.includes("edit_tasks") && (
            user?.role === "admin" || user?.role === "developer"
            || task.created_by_user_id === user?.user_id
            || (task.owner_type === "user" && task.owner_id === user?.user_id)
        )
    )

    const [addTaskDialogOpen, setAddTaskDialogOpen] = React.useState(false)
    const [editingTaskId, setEditingTaskId] = React.useState<string | null>(null)

    const handleTaskToggle = async (taskId: string, isCompleted: boolean) => {
        const task = tasksData?.items.find((item) => item.id === taskId)
        if (!task || !canToggleTask(task)) return
        await taskActions.toggle(taskId, isCompleted)
    }

    const handleAddTask = async (data: SurrogateTaskFormData) => {
        if (!canCreateTask) return
        await taskActions.create({ ...data, surrogate_id: id, intended_parent_id: null, donor_id: null })
    }

    const handleTaskClick = (task: TaskListItem) => {
        setEditingTaskId(task.id)
    }

    const handleSaveTask = async (taskId: string, data: TaskUpdatePayload) => {
        await taskActions.update(taskId, data)
    }

    const handleDeleteTask = async (taskId: string) => {
        await taskActions.remove(taskId)
        setEditingTaskId(null)
    }

    return (
        <>
            <SurrogateTasksTab
                surrogateId={id}
                tasks={tasksData?.items || []}
                isLoading={tasksQuery.isLoading}
                loadError={tasksLoadError}
                canCreateTask={canCreateTask}
                canToggleTask={canToggleTask}
                onTaskToggle={handleTaskToggle}
                onAddTask={() => setAddTaskDialogOpen(true)}
                onTaskClick={handleTaskClick}
            />
            <AddSurrogateTaskDialog
                open={addTaskDialogOpen && canCreateTask}
                onOpenChange={setAddTaskDialogOpen}
                onSubmit={handleAddTask}
                isPending={taskActions.isCreating}
            />
            {editingTaskId ? <TaskDetailDialog
                taskId={editingTaskId}
                onClose={() => setEditingTaskId(null)}
                onSave={handleSaveTask}
                onDelete={handleDeleteTask}
                isDeleting={taskActions.isDeleting}
            /> : null}
        </>
    )
}
