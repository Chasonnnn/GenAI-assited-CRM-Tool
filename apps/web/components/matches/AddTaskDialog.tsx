"use client"

/**
 * AddTaskDialog - Dialog for creating tasks for Case or IP from Match detail page
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
    onSubmit: (target: "case" | "ip", data: TaskFormData) => Promise<void>
    isPending: boolean
    caseName: string
    ipName: string
}

export interface TaskFormData {
    title: string
    description?: string
    task_type: "meeting" | "follow_up" | "contact" | "review" | "other"
    due_date?: string
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
    caseName,
    ipName,
}: AddTaskDialogProps) {
    const [target, setTarget] = useState<"case" | "ip">("case")
    const [title, setTitle] = useState("")
    const [description, setDescription] = useState("")
    const [taskType, setTaskType] = useState<TaskFormData["task_type"]>("other")
    const [dueDate, setDueDate] = useState("")

    const handleSubmit = async () => {
        if (!title.trim()) return

        await onSubmit(target, {
            title: title.trim(),
            description: description.trim() || undefined,
            task_type: taskType,
            due_date: dueDate || undefined,
        })

        // Reset form
        setTitle("")
        setDescription("")
        setTaskType("other")
        setDueDate("")
        setTarget("case")
        onOpenChange(false)
    }

    const handleClose = (isOpen: boolean) => {
        if (!isOpen) {
            setTitle("")
            setDescription("")
            setTaskType("other")
            setDueDate("")
            setTarget("case")
        }
        onOpenChange(isOpen)
    }

    return (
        <Dialog open={open} onOpenChange={handleClose}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>Add Task</DialogTitle>
                    <DialogDescription>
                        Create a new task for the Case or Intended Parent.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    {/* Target selection */}
                    <div className="space-y-2">
                        <Label>Assign to</Label>
                        <RadioGroup
                            value={target}
                            onValueChange={(v) => setTarget(v as "case" | "ip")}
                            className="flex gap-4"
                        >
                            <div className="flex items-center space-x-2">
                                <RadioGroupItem value="case" id="task-target-case" />
                                <Label htmlFor="task-target-case" className="font-normal cursor-pointer">
                                    {caseName} (Case)
                                </Label>
                            </div>
                            <div className="flex items-center space-x-2">
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
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            placeholder="Task title..."
                            maxLength={255}
                        />
                    </div>

                    {/* Task Type */}
                    <div className="space-y-2">
                        <Label>Type</Label>
                        <Select value={taskType} onValueChange={(v) => setTaskType(v as TaskFormData["task_type"])}>
                            <SelectTrigger>
                                <SelectValue />
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
                            value={dueDate}
                            onChange={(e) => setDueDate(e.target.value)}
                        />
                    </div>

                    {/* Description */}
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
