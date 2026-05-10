"use client"

/**
 * AddTaskDialog - Dialog for creating tasks for Surrogate or IP from Match detail page
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
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"

interface AddTaskDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    onSubmit: (target: "match" | "surrogate" | "ip", data: TaskFormData) => Promise<void>
    isPending: boolean
    surrogateName: string
    ipName: string
}

export interface TaskFormData {
    title: string
    description?: string
    task_type: "meeting" | "follow_up" | "contact" | "review" | "other"
    due_date?: string
}

type TaskTarget = "match" | "surrogate" | "ip"

type TaskFormState = {
    target: TaskTarget
    title: string
    description: string
    taskType: TaskFormData["task_type"]
    dueDate: string
}

type TaskFormAction =
    | { type: "set_target"; target: TaskTarget }
    | { type: "set_title"; title: string }
    | { type: "set_description"; description: string }
    | { type: "set_task_type"; taskType: TaskFormData["task_type"] }
    | { type: "set_due_date"; dueDate: string }
    | { type: "reset" }

const INITIAL_TASK_FORM_STATE: TaskFormState = {
    target: "match",
    title: "",
    description: "",
    taskType: "other",
    dueDate: "",
}

function taskFormReducer(state: TaskFormState, action: TaskFormAction): TaskFormState {
    switch (action.type) {
        case "set_target":
            return { ...state, target: action.target }
        case "set_title":
            return { ...state, title: action.title }
        case "set_description":
            return { ...state, description: action.description }
        case "set_task_type":
            return { ...state, taskType: action.taskType }
        case "set_due_date":
            return { ...state, dueDate: action.dueDate }
        case "reset":
            return INITIAL_TASK_FORM_STATE
    }
}

const TASK_TYPES = [
    { value: "meeting", label: "Appointment" },
    { value: "follow_up", label: "Follow Up" },
    { value: "contact", label: "Contact" },
    { value: "review", label: "Review" },
    { value: "other", label: "Other" },
]

export function AddTaskDialog({
    open,
    onOpenChange,
    onSubmit,
    isPending,
    surrogateName,
    ipName,
}: AddTaskDialogProps) {
    const [formState, dispatchForm] = useReducer(taskFormReducer, INITIAL_TASK_FORM_STATE)

    const handleSubmit = async () => {
        const title = formState.title.trim()
        if (!title) return

        const trimmedDescription = formState.description.trim()
        await onSubmit(formState.target, {
            title,
            task_type: formState.taskType,
            ...(trimmedDescription ? { description: trimmedDescription } : {}),
            ...(formState.dueDate ? { due_date: formState.dueDate } : {}),
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
                        Create a task for the full match or assign it to one side only.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    {/* Target selection */}
                    <div className="space-y-2">
                        <Label id="match-task-target-label">Assign to</Label>
                        <RadioGroup
                            value={formState.target}
                            onValueChange={(v) =>
                                dispatchForm({ type: "set_target", target: v as TaskTarget })
                            }
                            aria-labelledby="match-task-target-label"
                            className="flex flex-col gap-3"
                        >
                            <div className="flex items-center gap-2">
                                <RadioGroupItem value="match" id="task-target-match" />
                                <Label htmlFor="task-target-match" className="font-normal cursor-pointer">
                                    Match (both sides)
                                </Label>
                            </div>
                            <div className="flex items-center gap-2">
                                <RadioGroupItem value="surrogate" id="task-target-surrogate" />
                                <Label htmlFor="task-target-surrogate" className="font-normal cursor-pointer">
                                    {surrogateName} (Surrogate)
                                </Label>
                            </div>
                            <div className="flex items-center gap-2">
                                <RadioGroupItem value="ip" id="task-target-ip" />
                                <Label htmlFor="task-target-ip" className="font-normal cursor-pointer">
                                    {ipName} (IP)
                                </Label>
                            </div>
                        </RadioGroup>
                    </div>

                    {/* Title */}
                    <div className="space-y-2">
                        <Label htmlFor="task-title">Title *</Label>
                        <Input
                            id="task-title"
                            value={formState.title}
                            onChange={(e) =>
                                dispatchForm({ type: "set_title", title: e.target.value })
                            }
                            placeholder="Task title..."
                            maxLength={255}
                        />
                    </div>

                    {/* Task Type */}
                    <div className="space-y-2">
                        <Label htmlFor="match-task-type">Type</Label>
                        <Select
                            value={formState.taskType}
                            onValueChange={(v) =>
                                dispatchForm({
                                    type: "set_task_type",
                                    taskType: v as TaskFormData["task_type"],
                                })
                            }
                        >
                            <SelectTrigger id="match-task-type">
                                <SelectValue>
                                    {(value: string | null) => {
                                        const type = TASK_TYPES.find((taskType) => taskType.value === value)
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

                    {/* Due Date */}
                    <div className="space-y-2">
                        <Label htmlFor="task-due-date">Due Date</Label>
                        <Input
                            id="task-due-date"
                            type="date"
                            value={formState.dueDate}
                            onChange={(e) =>
                                dispatchForm({ type: "set_due_date", dueDate: e.target.value })
                            }
                        />
                    </div>

                    {/* Description */}
                    <div className="space-y-2">
                        <Label htmlFor="task-description">Description</Label>
                        <Textarea
                            id="task-description"
                            value={formState.description}
                            onChange={(e) =>
                                dispatchForm({
                                    type: "set_description",
                                    description: e.target.value,
                                })
                            }
                            placeholder="Optional task details..."
                            rows={3}
                            maxLength={2000}
                        />
                    </div>
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
                        disabled={isPending || !formState.title.trim()}
                    >
                        {isPending ? "Creating..." : "Create Task"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
