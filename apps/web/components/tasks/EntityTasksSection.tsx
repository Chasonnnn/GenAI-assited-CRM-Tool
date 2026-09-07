"use client"

import { useState } from "react"
import { Loader2Icon, PlusIcon } from "lucide-react"

import { AddTaskDialog, type TaskFormData } from "@/components/tasks/AddTaskDialog"
import { TaskDetailDialog } from "@/components/tasks/TaskDetailDialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { toast } from "@/components/ui/toast"
import type { TaskListItem, TaskUpdatePayload } from "@/lib/api/tasks"
import { useAuth } from "@/lib/auth-context"
import { formatDate } from "@/lib/formatters"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"
import { useTasks } from "@/lib/hooks/use-tasks"
import { useTaskActions } from "@/lib/hooks/use-task-actions"
import type { TaskRelatedRecordFields } from "@/lib/task-related-record"

type TaskSubject =
    | { surrogate_id: string; intended_parent_id?: never; donor_id?: never }
    | { intended_parent_id: string; surrogate_id?: never; donor_id?: never }
    | { donor_id: string; surrogate_id?: never; intended_parent_id?: never }

type TaskFilter = "open" | "completed" | "all"

export function EntityTasksSection({
    subject,
    record,
    canView,
    canCreate,
    archived = false,
}: {
    subject: TaskSubject
    record: TaskRelatedRecordFields
    canView: boolean
    canCreate: boolean
    archived?: boolean
}) {
    const { user } = useAuth()
    const permissionsQuery = useEffectivePermissions(user?.user_id ?? null)
    const permissions = permissionsQuery.data?.permissions ?? []
    const isAdmin = user?.role === "developer" || user?.role === "admin"
    const canEdit = user?.role === "developer" || permissions.includes("edit_tasks")
    const [filter, setFilter] = useState<TaskFilter>("open")
    const [page, setPage] = useState(1)
    const [isAddOpen, setIsAddOpen] = useState(false)
    const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null)
    const tasksQuery = useTasks({
        ...subject,
        exclude_approvals: true,
        ...(filter === "all" ? {} : { is_completed: filter === "completed" }),
        page,
        per_page: 10,
    }, { enabled: canView })
    const actions = useTaskActions()
    const canManage = (task: TaskListItem) => isAdmin
        || task.created_by_user_id === user?.user_id
        || (task.owner_type === "user" && task.owner_id === user?.user_id)
    const pages = tasksQuery.data?.pages ?? 1

    const handleCreate = async (formData: TaskFormData) => {
        await actions.create(formData)
        setPage(1)
    }

    const handleToggle = async (task: TaskListItem) => {
        try {
            await actions.toggle(task.id, task.is_completed)
            setPage(1)
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to update task")
        }
    }

    const handleSave = async (taskId: string, data: TaskUpdatePayload) => {
        try {
            await actions.update(taskId, data)
            setPage(1)
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to save task")
            throw error
        }
    }

    const handleDelete = async (taskId: string) => {
        try {
            await actions.remove(taskId)
            setPage(1)
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to delete task")
            throw error
        }
    }

    if (!canView) return null

    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-4">
                <CardTitle><h2>Tasks</h2></CardTitle>
                {canCreate && !archived ? (
                    <Button size="sm" onClick={() => setIsAddOpen(true)}><PlusIcon className="size-4" />Add Task</Button>
                ) : null}
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="flex flex-wrap gap-2" aria-label="Task status">
                    {([['open', 'Open'], ['completed', 'Completed'], ['all', 'All']] as const).map(([value, label]) => (
                        <Button key={value} size="sm" variant={filter === value ? "secondary" : "ghost"} aria-pressed={filter === value} onClick={() => { setFilter(value); setPage(1) }}>
                            {label}
                        </Button>
                    ))}
                </div>
                {tasksQuery.isLoading ? (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground" role="status"><Loader2Icon className="size-4 animate-spin" />Loading tasks…</div>
                ) : tasksQuery.isError ? (
                    <div className="flex items-center justify-between gap-4">
                        <p className="text-sm text-destructive">Failed to load tasks.</p>
                        <Button variant="outline" size="sm" onClick={() => { void tasksQuery.refetch() }}>Retry</Button>
                    </div>
                ) : (tasksQuery.data?.items.length ?? 0) === 0 ? (
                    <p className="text-sm text-muted-foreground">No tasks yet.</p>
                ) : (
                    <ul className="divide-y" aria-label="Record tasks">
                        {tasksQuery.data?.items.map((task) => (
                            <li key={task.id} className="flex items-start gap-3 py-3 first:pt-0 last:pb-0">
                                <Checkbox className="mt-1" checked={task.is_completed} disabled={!canEdit || !canManage(task) || actions.isToggling} aria-label={`${task.is_completed ? "Reopen" : "Complete"} ${task.title}`} onCheckedChange={() => { void handleToggle(task) }} />
                                <div className="min-w-0 flex-1">
                                    <Button unstyled type="button" className="max-w-full [overflow-wrap:anywhere] text-left text-sm font-medium hover:underline focus-visible:underline" onClick={() => setSelectedTaskId(task.id)}>{task.title}</Button>
                                    <p className="text-xs text-muted-foreground">{formatDate(task.due_date, undefined, "No due date")}{task.owner_name ? ` · ${task.owner_name}` : ""}</p>
                                </div>
                            </li>
                        ))}
                    </ul>
                )}
                {(pages > 1 || page > 1) ? (
                    <nav className="flex items-center justify-between gap-2" aria-label="Task pages">
                        <Button size="sm" variant="outline" disabled={page === 1 || tasksQuery.isLoading} onClick={() => setPage(page - 1)}>Previous</Button>
                        <span className="text-sm text-muted-foreground">Page {page} of {Math.max(page, pages)}</span>
                        <Button size="sm" variant="outline" disabled={page >= pages || tasksQuery.isLoading} onClick={() => setPage(page + 1)}>Next</Button>
                    </nav>
                ) : null}
            </CardContent>
            {isAddOpen ? <AddTaskDialog open onOpenChange={setIsAddOpen} onSubmit={handleCreate} isPending={actions.isCreating} initialRelatedRecord={record} /> : null}
            {selectedTaskId ? <TaskDetailDialog taskId={selectedTaskId} onClose={() => setSelectedTaskId(null)} onSave={handleSave} onDelete={handleDelete} isDeleting={actions.isDeleting} /> : null}
        </Card>
    )
}
