"use client"

import { useState, useEffect } from "react"
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
    case_id: string | null
}

interface TaskEditModalProps {
    task: Task | null
    open: boolean
    onClose: () => void
    onSave: (taskId: string, data: Partial<Task>) => Promise<void>
}

const TASK_TYPES = [
    { value: "call", label: "Call" },
    { value: "email", label: "Email" },
    { value: "meeting", label: "Meeting" },
    { value: "follow_up", label: "Follow Up" },
    { value: "other", label: "Other" },
]

export function TaskEditModal({ task, open, onClose, onSave }: TaskEditModalProps) {
    const [title, setTitle] = useState("")
    const [description, setDescription] = useState("")
    const [taskType, setTaskType] = useState("other")
    const [dueDate, setDueDate] = useState<Date | undefined>(undefined)
    const [dueTime, setDueTime] = useState("")
    const [isSaving, setIsSaving] = useState(false)

    // Populate form when task changes
    useEffect(() => {
        if (task) {
            setTitle(task.title)
            setDescription(task.description || "")
            setTaskType(task.task_type)
            setDueDate(task.due_date ? parseISO(task.due_date) : undefined)
            setDueTime(task.due_time?.slice(0, 5) || "") // HH:MM format
        } else {
            // Reset form
            setTitle("")
            setDescription("")
            setTaskType("other")
            setDueDate(undefined)
            setDueTime("")
        }
    }, [task])

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!task) return

        setIsSaving(true)
        try {
            await onSave(task.id, {
                title,
                description: description || null,
                task_type: taskType,
                due_date: dueDate ? format(dueDate, "yyyy-MM-dd") : null,
                due_time: dueTime ? `${dueTime}:00` : null, // Add seconds
            })
            onClose()
        } catch (error) {
            console.error("Failed to save task:", error)
        } finally {
            setIsSaving(false)
        }
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
                                value={title}
                                onChange={(e) => setTitle(e.target.value)}
                                placeholder="Task title"
                                required
                            />
                        </div>

                        {/* Description */}
                        <div className="space-y-2">
                            <Label htmlFor="description">Description</Label>
                            <Textarea
                                id="description"
                                value={description}
                                onChange={(e) => setDescription(e.target.value)}
                                placeholder="Optional description"
                                rows={3}
                            />
                        </div>

                        {/* Task Type */}
                        <div className="space-y-2">
                            <Label htmlFor="task-type">Type</Label>
                            <Select value={taskType} onValueChange={setTaskType}>
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

                        {/* Due Date & Time */}
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label>Due Date</Label>
                                <Popover>
                                    <PopoverTrigger asChild>
                                        <Button
                                            variant="outline"
                                            className={cn(
                                                "w-full justify-start text-left font-normal",
                                                !dueDate && "text-muted-foreground"
                                            )}
                                        >
                                            <CalendarIcon className="mr-2 size-4" />
                                            {dueDate ? format(dueDate, "PPP") : "Select date"}
                                        </Button>
                                    </PopoverTrigger>
                                    <PopoverContent className="w-auto p-0" align="start">
                                        <Calendar
                                            mode="single"
                                            selected={dueDate}
                                            onSelect={setDueDate}
                                            initialFocus
                                        />
                                    </PopoverContent>
                                </Popover>
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="due-time">Due Time</Label>
                                <Input
                                    id="due-time"
                                    type="time"
                                    value={dueTime}
                                    onChange={(e) => setDueTime(e.target.value)}
                                />
                            </div>
                        </div>
                    </div>

                    <DialogFooter>
                        <Button type="button" variant="outline" onClick={onClose}>
                            Cancel
                        </Button>
                        <Button type="submit" disabled={isSaving || !title.trim()}>
                            {isSaving && <Loader2 className="mr-2 size-4 animate-spin" />}
                            Save Changes
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    )
}
