"use client"

import { TaskEditModal } from "@/components/tasks/TaskEditModal"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import type { TaskUpdatePayload } from "@/lib/api/tasks"
import { useAuth } from "@/lib/auth-context"
import { formatDate } from "@/lib/formatters"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"
import { useTask } from "@/lib/hooks/use-tasks"

export function TaskDetailDialog({ taskId, onClose, onSave, onDelete, isDeleting }: {
    taskId: string
    onClose: () => void
    onSave: (taskId: string, data: TaskUpdatePayload) => Promise<void>
    onDelete: (taskId: string) => Promise<void>
    isDeleting: boolean
}) {
    const query = useTask(taskId)
    const { user } = useAuth()
    const permissionsQuery = useEffectivePermissions(user?.user_id ?? null)
    const permissions = permissionsQuery.data?.permissions ?? []
    const task = query.data
    const canManage = task && (
        user?.role === "developer" || user?.role === "admin"
        || task.created_by_user_id === user?.user_id
        || (task.owner_type === "user" && task.owner_id === user?.user_id)
    )
    const canEdit = user?.role === "developer" || permissions.includes("edit_tasks")
    const canDelete = user?.role === "developer" || permissions.includes("delete_tasks")

    if (task && !query.isError && canManage && canEdit) {
        return <TaskEditModal
            key={task.id}
            task={task}
            open
            onClose={onClose}
            onSave={onSave}
            {...(canDelete ? { onDelete } : {})}
            isDeleting={isDeleting}
        />
    }

    return (
        <Dialog open onOpenChange={(open) => { if (!open) onClose() }}>
            <DialogContent>
                <DialogHeader><DialogTitle>{query.isError || !task ? "Task" : task.title}</DialogTitle></DialogHeader>
                {query.isError ? (
                    <div className="space-y-3">
                        <p role="alert" className="text-sm text-destructive">Failed to load task.</p>
                        <Button variant="outline" onClick={() => { void query.refetch() }}>Retry task</Button>
                    </div>
                ) : !task || permissionsQuery.isLoading ? (
                    <p role="status" className="text-sm text-muted-foreground">Loading task…</p>
                ) : (
                    <>
                        <p className="whitespace-pre-wrap text-sm">{task.description || "No description"}</p>
                        <p className="text-sm text-muted-foreground">{formatDate(task.due_date, undefined, "No due date")}</p>
                    </>
                )}
            </DialogContent>
        </Dialog>
    )
}
