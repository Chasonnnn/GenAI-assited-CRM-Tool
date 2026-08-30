"use client"

import { useState } from "react"
import { Loader2Icon, PlusIcon } from "lucide-react"

import { AddTaskDialog, type TaskFormData } from "@/components/tasks/AddTaskDialog"
import { TaskRelatedRecordLinks } from "@/components/tasks/TaskRelatedRecordLinks"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { formatDate } from "@/lib/formatters"
import { useCreateTask, useTasks } from "@/lib/hooks/use-tasks"
import type { Donor } from "@/lib/types/donor"

export function DonorTasksSection({
    donor,
    canView,
    canCreate,
}: {
    donor: Donor
    canView: boolean
    canCreate: boolean
}) {
    const canAddTask = canCreate && !donor.is_archived
    const [isAddOpen, setIsAddOpen] = useState(false)
    const tasksQuery = useTasks(
        { donor_id: donor.id, exclude_approvals: true, is_completed: false, per_page: 10 },
        { enabled: canView },
    )
    const createTask = useCreateTask()

    if (!canView) return null

    const handleCreate = async (formData: TaskFormData) => {
        await createTask.mutateAsync({
            title: formData.title,
            task_type: formData.task_type,
            surrogate_id: formData.surrogate_id,
            intended_parent_id: formData.intended_parent_id,
            donor_id: formData.donor_id,
            ...(formData.description ? { description: formData.description } : {}),
            ...(formData.due_date ? { due_date: formData.due_date } : {}),
            ...(formData.due_time ? { due_time: `${formData.due_time}:00` } : {}),
        })
    }

    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-4">
                <CardTitle><h2>Open Tasks</h2></CardTitle>
                {canAddTask ? (
                    <Button size="sm" onClick={() => setIsAddOpen(true)}>
                        <PlusIcon className="size-4" />
                        Add Task
                    </Button>
                ) : null}
            </CardHeader>
            <CardContent>
                {tasksQuery.isLoading ? (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
                        <Loader2Icon className="size-4 animate-spin" />
                        Loading tasks…
                    </div>
                ) : tasksQuery.isError ? (
                    <div className="flex items-center justify-between gap-4">
                        <p className="text-sm text-destructive">Failed to load tasks.</p>
                        <Button variant="outline" size="sm" onClick={() => { void tasksQuery.refetch() }}>
                            Retry
                        </Button>
                    </div>
                ) : (tasksQuery.data?.items.length ?? 0) === 0 ? (
                    <p className="text-sm text-muted-foreground">No tasks yet.</p>
                ) : (
                    <ul className="divide-y">
                        {tasksQuery.data?.items.map((task) => (
                            <li key={task.id} className="flex flex-col gap-1 py-3 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between">
                                <div className="min-w-0">
                                    <p className="truncate text-sm font-medium">{task.title}</p>
                                    <TaskRelatedRecordLinks task={task} className="text-xs text-muted-foreground" />
                                </div>
                                <span className="shrink-0 text-xs text-muted-foreground">
                                    {formatDate(task.due_date, undefined, "No due date")}
                                </span>
                            </li>
                        ))}
                    </ul>
                )}
            </CardContent>
            {isAddOpen ? (
                <AddTaskDialog
                    open
                    onOpenChange={setIsAddOpen}
                    onSubmit={handleCreate}
                    isPending={createTask.isPending}
                    initialRelatedRecord={{
                        donor_id: donor.id,
                        donor_number: donor.donor_number,
                        donor_type: donor.donor_type,
                        donor_name: donor.full_name,
                    }}
                />
            ) : null}
        </Card>
    )
}
