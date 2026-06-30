"use client"

import { useState, type FormEvent } from "react"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { Calendar } from "@/components/ui/calendar"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { CalendarIcon, Loader2 } from "lucide-react"
import { format, parseISO } from "date-fns"
import { cn } from "@/lib/utils"

interface Task {
    id: string
    title: string
    description: string | null
    task_type: string
    due_date: string | null
    due_time: string | null
    is_completed: boolean
    surrogate_id: string | null
}

interface TaskEditModalProps {
    task: Task | null
    open: boolean
    onClose: () => void
    onSave: (taskId: string, data: Partial<Task>) => Promise<void>
    onDelete?: (taskId: string) => Promise<void>
    isDeleting?: boolean
}

type TaskEditDraft = {
    taskId: string | null
    title: string
    description: string
    taskType: string
    dueDate: Date | undefined
    dueTime: string
}

const TASK_TYPES = [
    { value: "meeting", label: "Meeting" },
    { value: "follow_up", label: "Follow Up" },
    { value: "contact", label: "Contact" },
    { value: "review", label: "Review" },
    { value: "medication", label: "Medication" },
    { value: "exam", label: "Exam" },
    { value: "appointment", label: "Appointment" },
    { value: "other", label: "Other" },
]

function createTaskEditDraft(task: Task | null): TaskEditDraft {
    if (!task) {
        return {
            taskId: null,
            title: "",
            description: "",
            taskType: "other",
            dueDate: undefined,
            dueTime: "",
        }
    }
    return {
        taskId: task.id,
        title: task.title,
        description: task.description || "",
        taskType: task.task_type,
        dueDate: task.due_date ? parseISO(task.due_date) : undefined,
        dueTime: task.due_time?.slice(0, 5) || "",
    }
}

export function TaskEditModal({
    task,
    open,
    onClose,
    onSave,
    onDelete,
    isDeleting = false,
}: TaskEditModalProps) {
    const activeTaskId = task?.id ?? null
    const [draft, setDraft] = useState<TaskEditDraft>(() => createTaskEditDraft(task))
    const [isSaving, setIsSaving] = useState(false)
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)

    if (draft.taskId !== activeTaskId) {
        setDraft(createTaskEditDraft(task))
    }

    const updateDraft = (updates: Partial<Omit<TaskEditDraft, "taskId">>) => {
        setDraft((current) => ({ ...current, ...updates }))
    }

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault()
        if (!task) return

        setIsSaving(true)
        try {
            await onSave(task.id, {
                title: draft.title,
                description: draft.description || null,
                task_type: draft.taskType,
                due_date: draft.dueDate ? format(draft.dueDate, "yyyy-MM-dd") : null,
                due_time: draft.dueTime ? `${draft.dueTime}:00` : null,
            })
        } catch (error) {
            console.error("Failed to save task:", error)
            setIsSaving(false)
            return
        }
        setIsSaving(false)
        onClose()
    }

    const handleDelete = () => {
        if (!task || !onDelete) return
        setDeleteDialogOpen(true)
    }

    const confirmDelete = async () => {
        if (!task || !onDelete) return
        await onDelete(task.id)
        setDeleteDialogOpen(false)
        onClose()
    }

    return (
        <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
            <DialogContent className="sm:max-w-[500px]">
                <form onSubmit={handleSubmit}>
                    <DialogHeader>
                        <DialogTitle>Edit Task</DialogTitle>
                        <DialogDescription>
                            Update task details and schedule.
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4 py-4">
                        {/* Title */}
                        <div className="space-y-2">
                            <Label htmlFor="title">Title</Label>
                            <Input
                                id="title"
                                name="title"
                                value={draft.title}
                                onChange={(e) => updateDraft({ title: e.target.value })}
                                placeholder="Task title"
                                required
                                autoComplete="off"
                            />
                        </div>

                        {/* Description */}
                        <div className="space-y-2">
                            <Label htmlFor="description">Description</Label>
                            <Textarea
                                id="description"
                                value={draft.description}
                                onChange={(e) => updateDraft({ description: e.target.value })}
                                placeholder="Optional description"
                                rows={3}
                            />
                        </div>

                        {/* Task Type */}
                        <div className="space-y-2">
                            <Label htmlFor="task-type">Type</Label>
                            <Select value={draft.taskType} onValueChange={(v) => v && updateDraft({ taskType: v })}>
                                <SelectTrigger id="task-type">
                                    <SelectValue>
                                        {(value: string | null) => {
                                            const type = TASK_TYPES.find(t => t.value === value)
                                            return type?.label ?? "Select type"
                                        }}
                                    </SelectValue>
                                </SelectTrigger>
                                <SelectContent>
                                    {TASK_TYPES.map((type) => (
                                        <SelectItem key={type.value} value={type.value}>
                                            {type.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        {/* Due Date & Time */}
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="due-date-picker">Due Date</Label>
                                <Popover>
                                    <PopoverTrigger render={
                                        <Button
                                            id="due-date-picker"
                                            variant="outline"
                                            className={cn(
                                                "w-full justify-start text-left font-normal",
                                                !draft.dueDate && "text-muted-foreground"
                                            )}
                                        >
                                            <CalendarIcon className="mr-2 size-4" />
                                            {draft.dueDate ? format(draft.dueDate, "PPP") : "Select date"}
                                        </Button>
                                    } />
                                    <PopoverContent className="w-auto p-0" align="start">
                                        <Calendar
                                            mode="single"
                                            selected={draft.dueDate}
                                            onSelect={(nextDate) => updateDraft({ dueDate: nextDate })}
                                        />
                                    </PopoverContent>
                                </Popover>
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="due-time">Due Time</Label>
                                <Input
                                    id="due-time"
                                    type="time"
                                    value={draft.dueTime}
                                    onChange={(e) => updateDraft({ dueTime: e.target.value })}
                                />
                            </div>
                        </div>
                    </div>

                    <DialogFooter>
                        {onDelete && (
                            <Button
                                type="button"
                                variant="destructive"
                                onClick={handleDelete}
                                disabled={isSaving || isDeleting}
                            >
                                {isDeleting && <Loader2 className="mr-2 size-4 animate-spin" />}
                                Delete Task
                            </Button>
                        )}
                        <Button type="button" variant="outline" onClick={onClose} disabled={isSaving || isDeleting}>
                            Cancel
                        </Button>
                        <Button type="submit" disabled={isSaving || isDeleting || !draft.title.trim()}>
                            {isSaving && <Loader2 className="mr-2 size-4 animate-spin" />}
                            Save Changes
                        </Button>
                    </DialogFooter>
                </form>

                {/* Delete Confirmation Dialog */}
                <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
                    <AlertDialogContent>
                        <AlertDialogHeader>
                            <AlertDialogTitle>Delete Task</AlertDialogTitle>
                            <AlertDialogDescription>
                                This action cannot be undone. This will permanently delete the task.
                            </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
                            <AlertDialogAction
                                onClick={confirmDelete}
                                disabled={isDeleting}
                                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                            >
                                {isDeleting && <Loader2 className="mr-2 size-4 animate-spin" />}
                                Delete
                            </AlertDialogAction>
                        </AlertDialogFooter>
                    </AlertDialogContent>
                </AlertDialog>
            </DialogContent>
        </Dialog>
    )
}
