"use client"

/**
 * AddTaskDialog - Dialog for creating tasks from My Tasks page.
 */

import { useState } from "react"
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

export interface TaskFormData {
    title: string
    description?: string
    task_type: "meeting" | "follow_up" | "contact" | "review" | "medication" | "exam" | "appointment" | "other"
    due_date?: string
    due_time?: string
    recurrence: TaskRecurrence
    repeat_until?: string
}

interface AddTaskDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    onSubmit: (data: TaskFormData) => Promise<void>
    isPending: boolean
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

export function AddTaskDialog({
    open,
    onOpenChange,
    onSubmit,
    isPending,
}: AddTaskDialogProps) {
    const [title, setTitle] = useState("")
    const [description, setDescription] = useState("")
    const [taskType, setTaskType] = useState<TaskFormData["task_type"]>("other")
    const [dueDate, setDueDate] = useState("")
    const [dueTime, setDueTime] = useState("")
    const [recurrence, setRecurrence] = useState<TaskRecurrence>("none")
    const [repeatUntil, setRepeatUntil] = useState("")
    const [error, setError] = useState("")

    const handleSubmit = async () => {
        if (!title.trim()) return
        setError("")

        if (recurrence !== "none") {
            if (!dueDate) {
                setError("Recurring tasks require a due date.")
                return
            }
            if (!repeatUntil) {
                setError("Please select a repeat until date.")
                return
            }
            if (repeatUntil < dueDate) {
                setError("Repeat until date must be after the due date.")
                return
            }
        }

        await onSubmit({
            title: title.trim(),
            description: description.trim() || undefined,
            task_type: taskType,
            due_date: dueDate || undefined,
            due_time: dueTime || undefined,
            recurrence,
            repeat_until: repeatUntil || undefined,
        })

        setTitle("")
        setDescription("")
        setTaskType("other")
        setDueDate("")
        setDueTime("")
        setRecurrence("none")
        setRepeatUntil("")
        setError("")
        onOpenChange(false)
    }

    const handleClose = (isOpen: boolean) => {
        if (!isOpen) {
            setTitle("")
            setDescription("")
            setTaskType("other")
            setDueDate("")
            setDueTime("")
            setRecurrence("none")
            setRepeatUntil("")
            setError("")
        }
        onOpenChange(isOpen)
    }

    return (
        <Dialog open={open} onOpenChange={handleClose}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>Add Task</DialogTitle>
                    <DialogDescription>
                        Create a new task for your list.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    <div className="space-y-2">
                        <Label htmlFor="task-title">Title *</Label>
                        <Input
                            id="task-title"
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            placeholder="Task title..."
                            maxLength={255}
                        />
                    </div>

                    <div className="space-y-2">
                        <Label>Type</Label>
                        <Select value={taskType} onValueChange={(v) => setTaskType(v as TaskFormData["task_type"])}>
                            <SelectTrigger>
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
                                onChange={(e) => setDueDate(e.target.value)}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="task-due-time">Due Time</Label>
                            <Input
                                id="task-due-time"
                                type="time"
                                value={dueTime}
                                onChange={(e) => setDueTime(e.target.value)}
                            />
                        </div>
                    </div>

                    <div className="space-y-2">
                        <Label>Repeat</Label>
                        <Select value={recurrence} onValueChange={(v) => setRecurrence(v as TaskRecurrence)}>
                            <SelectTrigger>
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
                                onChange={(e) => setRepeatUntil(e.target.value)}
                            />
                        </div>
                    )}

                    <div className="space-y-2">
                        <Label htmlFor="task-description">Description</Label>
                        <Textarea
                            id="task-description"
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
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
