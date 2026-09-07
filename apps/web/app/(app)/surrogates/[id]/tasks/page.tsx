"use client"

import * as React from "react"
import { useParams } from "next/navigation"
import { AddSurrogateTaskDialog, type SurrogateTaskFormData } from "@/components/surrogates/AddSurrogateTaskDialog"
import { SurrogateTasksTab } from "@/components/surrogates/tabs/SurrogateTasksTab"
import { TaskDetailDialog } from "@/components/tasks/TaskDetailDialog"
import { useTasks } from "@/lib/hooks/use-tasks"
import { useSurrogate } from "@/lib/hooks/use-surrogates"
import type { TaskListItem } from "@/lib/types/task"
import type { TaskUpdatePayload } from "@/lib/api/tasks"
import { useTaskActions } from "@/lib/hooks/use-task-actions"

export default function SurrogateTasksPage() {
    const params = useParams<{ id: string }>()
    const id = params.id
    const { data: surrogateData } = useSurrogate(id)
    const { data: tasksData, isLoading: tasksLoading } = useTasks({
        surrogate_id: id,
        exclude_approvals: true,
    })
    const taskActions = useTaskActions()

    const [addTaskDialogOpen, setAddTaskDialogOpen] = React.useState(false)
    const [editingTaskId, setEditingTaskId] = React.useState<string | null>(null)

    const handleTaskToggle = async (taskId: string, isCompleted: boolean) => {
        await taskActions.toggle(taskId, isCompleted)
    }

    const handleAddTask = async (data: SurrogateTaskFormData) => {
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
                isLoading={tasksLoading}
                onTaskToggle={handleTaskToggle}
                onAddTask={() => setAddTaskDialogOpen(true)}
                onTaskClick={handleTaskClick}
            />
            <AddSurrogateTaskDialog
                open={addTaskDialogOpen}
                onOpenChange={setAddTaskDialogOpen}
                onSubmit={handleAddTask}
                isPending={taskActions.isCreating}
                surrogateName={surrogateData?.full_name || "this surrogate"}
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
