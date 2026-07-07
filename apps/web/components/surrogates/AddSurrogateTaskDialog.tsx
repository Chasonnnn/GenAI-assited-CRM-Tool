"use client"

/**
 * AddSurrogateTaskDialog - Dialog for creating tasks for a surrogate.
 */

import { useReducer } from "react"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
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
import type { TaskRecurrence } from "@/lib/utils/task-recurrence"

export interface SurrogateTaskFormData {
    title: string
    description?: string
    task_type: "meeting" | "follow_up" | "contact" | "review" | "other"
    due_date?: string
    due_time?: string
    recurrence: TaskRecurrence
    repeat_until?: string
}

interface AddSurrogateTaskDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    onSubmit: (data: SurrogateTaskFormData) => Promise<void>
    isPending: boolean
    surrogateName: string
}

const TASK_TYPES = [
    { value: "meeting", label: "Appointment" },
    { value: "follow_up", label: "Follow Up" },
    { value: "contact", label: "Contact" },
    { value: "review", label: "Review" },
    { value: "other", label: "Other" },
]

type SurrogateTaskFormState = {
    title: string
    description: string
    taskType: SurrogateTaskFormData["task_type"]
    dueDate: string
    dueTime: string
    recurrence: TaskRecurrence
    repeatUntil: string
    error: string
}

type SurrogateTaskFormTextField =
    | "title"
    | "description"
    | "dueDate"
    | "dueTime"
    | "repeatUntil"

type SurrogateTaskFormAction =
    | { type: "field"; field: SurrogateTaskFormTextField; value: string }
    | { type: "taskType"; value: SurrogateTaskFormData["task_type"] }
    | { type: "recurrence"; value: TaskRecurrence }
    | { type: "validationError"; value: string }
    | { type: "reset" }

function createInitialSurrogateTaskFormState(): SurrogateTaskFormState {
    return {
        title: "",
        description: "",
        taskType: "other",
        dueDate: "",
        dueTime: "",
        recurrence: "none",
        repeatUntil: "",
        error: "",
    }
}

function surrogateTaskFormReducer(
    state: SurrogateTaskFormState,
    action: SurrogateTaskFormAction
): SurrogateTaskFormState {
    switch (action.type) {
        case "field":
            return { ...state, [action.field]: action.value }
        case "taskType":
            return { ...state, taskType: action.value }
        case "recurrence":
            return { ...state, recurrence: action.value }
        case "validationError":
            return { ...state, error: action.value }
        case "reset":
            return createInitialSurrogateTaskFormState()
        default:
            return state
    }
}

export function AddSurrogateTaskDialog({
    open,
    onOpenChange,
    onSubmit,
    isPending,
    surrogateName,
}: AddSurrogateTaskDialogProps) {
    const [formState, dispatchForm] = useReducer(
        surrogateTaskFormReducer,
        createInitialSurrogateTaskFormState()
    )
    const { title, description, taskType, dueDate, dueTime, recurrence, repeatUntil, error } =
        formState

    const handleSubmit = async () => {
        if (!title.trim()) return
        dispatchForm({ type: "validationError", value: "" })

        if (recurrence !== "none") {
            if (!dueDate) {
                dispatchForm({
                    type: "validationError",
                    value: "Recurring tasks require a due date.",
                })
                return
            }
            if (!repeatUntil) {
                dispatchForm({
                    type: "validationError",
                    value: "Please select a repeat until date.",
                })
                return
            }
            if (repeatUntil < dueDate) {
                dispatchForm({
                    type: "validationError",
                    value: "Repeat until date must be after the due date.",
                })
                return
            }
        }

        const trimmedDescription = description.trim()
        await onSubmit({
            title: title.trim(),
            task_type: taskType,
            recurrence,
            ...(trimmedDescription ? { description: trimmedDescription } : {}),
            ...(dueDate ? { due_date: dueDate } : {}),
            ...(dueTime ? { due_time: dueTime } : {}),
            ...(repeatUntil ? { repeat_until: repeatUntil } : {}),
        })

        dispatchForm({ type: "reset" })
        onOpenChange(false)
    }

    const handleClose = (isOpen: boolean) => {
        if (!isOpen) {
            dispatchForm({ type: "reset" })
        }
        onOpenChange(isOpen)
    }

    return (
        <Dialog open={open} onOpenChange={handleClose}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>Add Task</DialogTitle>
                    <DialogDescription>
                        Create a new task for {surrogateName}.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    <div className="space-y-2">
                        <Label htmlFor="task-title">Title *</Label>
                        <Input
                            id="task-title"
                            value={title}
                            onChange={(e) =>
                                dispatchForm({
                                    type: "field",
                                    field: "title",
                                    value: e.target.value,
                                })
                            }
                            placeholder="Task title..."
                            maxLength={255}
                        />
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="surrogate-task-type">Type</Label>
                        <Select
                            value={taskType}
                            onValueChange={(v) =>
                                dispatchForm({
                                    type: "taskType",
                                    value: v as SurrogateTaskFormData["task_type"],
                                })
                            }
                        >
                            <SelectTrigger id="surrogate-task-type">
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

                    <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-2">
                            <Label htmlFor="task-due-date">Due Date</Label>
                            <Input
                                id="task-due-date"
                                type="date"
                                value={dueDate}
                                onChange={(e) =>
                                    dispatchForm({
                                        type: "field",
                                        field: "dueDate",
                                        value: e.target.value,
                                    })
                                }
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="task-due-time">Due Time</Label>
                            <Input
                                id="task-due-time"
                                type="time"
                                value={dueTime}
                                onChange={(e) =>
                                    dispatchForm({
                                        type: "field",
                                        field: "dueTime",
                                        value: e.target.value,
                                    })
                                }
                            />
                        </div>
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="surrogate-task-repeat">Repeat</Label>
                        <Select
                            value={recurrence}
                            onValueChange={(v) =>
                                dispatchForm({
                                    type: "recurrence",
                                    value: v as SurrogateTaskFormData["recurrence"],
                                })
                            }
                        >
                            <SelectTrigger id="surrogate-task-repeat">
                                <SelectValue>
                                    {(value: string | null) => {
                                        const labels: Record<string, string> = {
                                            none: "Does not repeat",
                                            daily: "Daily",
                                            weekly: "Weekly",
                                            monthly: "Monthly",
                                        }
                                        return labels[value ?? "none"] ?? "Select recurrence"
                                    }}
                                </SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="none">Does not repeat</SelectItem>
                                <SelectItem value="daily">Daily</SelectItem>
                                <SelectItem value="weekly">Weekly</SelectItem>
                                <SelectItem value="monthly">Monthly</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>

                    {recurrence !== "none" && (
                        <div className="space-y-2">
                            <Label htmlFor="task-repeat-until">Repeat Until</Label>
                            <Input
                                id="task-repeat-until"
                                type="date"
                                value={repeatUntil}
                                onChange={(e) =>
                                    dispatchForm({
                                        type: "field",
                                        field: "repeatUntil",
                                        value: e.target.value,
                                    })
                                }
                            />
                        </div>
                    )}

                    <div className="space-y-2">
                        <Label htmlFor="task-description">Description</Label>
                        <Textarea
                            id="task-description"
                            value={description}
                            onChange={(e) =>
                                dispatchForm({
                                    type: "field",
                                    field: "description",
                                    value: e.target.value,
                                })
                            }
                            placeholder="Optional task details..."
                            rows={3}
                            maxLength={2000}
                        />
                    </div>

                    {error && (
                        <p className="text-xs text-destructive">{error}</p>
                    )}
                </div>

                <DialogFooter>
                    <Button
                        variant="outline"
                        onClick={() => handleClose(false)}
                        disabled={isPending}
                    >
                        Cancel
                    </Button>
                    <Button
                        onClick={handleSubmit}
                        disabled={isPending || !title.trim()}
                    >
                        {isPending ? "Creating..." : "Create Task"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
