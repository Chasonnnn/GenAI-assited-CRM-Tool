import { format, parseISO } from "date-fns"
import type { TaskFormData } from "@/lib/types/task"
import type { TaskUpdatePayload } from "@/lib/api/tasks"
import { useCompleteTask, useCreateTask, useCreateTaskBatch, useDeleteTask, useUncompleteTask, useUpdateTask } from "@/lib/hooks/use-tasks"
import { buildRecurringDates, MAX_TASK_OCCURRENCES } from "@/lib/utils/task-recurrence"

export function useTaskActions() {
    const createTask = useCreateTask()
    const createTaskBatch = useCreateTaskBatch()
    const updateTask = useUpdateTask()
    const completeTask = useCompleteTask()
    const uncompleteTask = useUncompleteTask()
    const deleteTask = useDeleteTask()

    const create = async (formData: TaskFormData) => {
        const payload = {
            title: formData.title,
            task_type: formData.task_type,
            surrogate_id: formData.surrogate_id,
            intended_parent_id: formData.intended_parent_id,
            donor_id: formData.donor_id,
            ...(formData.description ? { description: formData.description } : {}),
            ...(formData.due_time ? { due_time: `${formData.due_time}:00` } : {}),
        }
        if (formData.recurrence === "none") {
            await createTask.mutateAsync({ ...payload, ...(formData.due_date ? { due_date: formData.due_date } : {}) })
            return
        }
        if (!formData.due_date || !formData.repeat_until) throw new Error("Choose a start and end date.")
        const end = parseISO(formData.repeat_until)
        const dates = buildRecurringDates(parseISO(formData.due_date), end, formData.recurrence)
        const lastDate = dates.at(-1)
        if (dates.length >= MAX_TASK_OCCURRENCES && lastDate && end > lastDate) {
            throw new Error(`Limit recurring tasks to ${MAX_TASK_OCCURRENCES} occurrences.`)
        }
        await createTaskBatch.mutateAsync(dates.map((date) => ({ ...payload, due_date: format(date, "yyyy-MM-dd") })))
    }

    return {
        create,
        update: (taskId: string, data: TaskUpdatePayload) => updateTask.mutateAsync({ taskId, data }),
        toggle: (taskId: string, isCompleted: boolean) => (isCompleted ? uncompleteTask : completeTask).mutateAsync(taskId),
        remove: (taskId: string) => deleteTask.mutateAsync(taskId),
        isCreating: createTask.isPending || createTaskBatch.isPending,
        isToggling: completeTask.isPending || uncompleteTask.isPending,
        isDeleting: deleteTask.isPending,
    }
}
