"use client"

import * as React from "react"
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
import { Textarea } from "@/components/ui/textarea"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Loader2Icon, SparklesIcon, AlertTriangleIcon, CheckCircle2Icon } from "lucide-react"
import { useParseSchedule, useCreateBulkTasks } from "@/lib/hooks/use-schedule-parser"
import type { ProposedTask } from "@/lib/api/schedule-parser"

const TASK_TYPES = [
    { value: "medication", label: "Medication" },
    { value: "exam", label: "Exam" },
    { value: "appointment", label: "Appointment" },
    { value: "follow_up", label: "Follow-up" },
    { value: "meeting", label: "Appointment (Zoom)" },
    { value: "contact", label: "Contact" },
    { value: "review", label: "Review" },
    { value: "other", label: "Other" },
]

interface EditableTask extends ProposedTask {
    selected: boolean
    id: string // Local ID for React key
}

export type EntityType = "surrogate" | "intended_parent" | "match"

interface ScheduleParserDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    entityType: EntityType
    entityId: string
    entityName?: string
}

export function ScheduleParserDialog({
    open,
    onOpenChange,
    entityType,
    entityId,
    entityName,
}: ScheduleParserDialogProps) {
    const [scheduleText, setScheduleText] = useState("")
    const [errorMessage, setErrorMessage] = useState<string | null>(null)
    const [editableTasks, setEditableTasks] = useState<EditableTask[]>([])
    const [warnings, setWarnings] = useState<string[]>([])
    const [metadata, setMetadata] = useState<{ timezone: string; refDate: string } | null>(null)
    const [step, setStep] = useState<"input" | "review" | "success">("input")
    const [bulkRequestId, setBulkRequestId] = useState<string | null>(null)

    const parseSchedule = useParseSchedule()
    const createBulkTasks = useCreateBulkTasks()

    const makeId = () => {
        // crypto.randomUUID is supported in modern browsers; the fallback keeps tests/older envs happy.
        if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
            return crypto.randomUUID()
        }
        return `${Date.now()}-${Math.random().toString(16).slice(2)}`
    }

    // Build entity ID payload based on type
    const getEntityPayload = () => {
        switch (entityType) {
            case "surrogate": return { surrogate_id: entityId }
            case "intended_parent": return { intended_parent_id: entityId }
            case "match": return { match_id: entityId }
        }
    }

    const handleParse = async () => {
        if (!scheduleText.trim()) return
        setErrorMessage(null)

        try {
            const result = await parseSchedule.mutateAsync({
                text: scheduleText,
                ...getEntityPayload(),
                user_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            })

            if (result.proposed_tasks.length === 0 && result.warnings.length > 0) {
                setWarnings(result.warnings)
                return
            }

            // Convert to editable tasks
            const tasks: EditableTask[] = result.proposed_tasks.map((task) => ({
                ...task,
                selected: true,
                id: makeId(),
            }))

            setEditableTasks(tasks)
            setWarnings(result.warnings)
            setMetadata({
                timezone: result.assumed_timezone,
                refDate: result.assumed_reference_date,
            })
            setBulkRequestId(null) // new parse = new payload, reset idempotency key
            setStep("review")
        } catch (e) {
            const message = e instanceof Error ? e.message : "Failed to parse schedule"
            setErrorMessage(message || "Failed to parse schedule")
        }
    }

    const handleTaskChange = <K extends keyof EditableTask>(id: string, field: K, value: EditableTask[K]) => {
        setBulkRequestId(null) // task edits change the payload; reset idempotency key
        setEditableTasks((prev) =>
            prev.map((task) => (task.id === id ? { ...task, [field]: value } : task))
        )
    }

    const handleSelectAll = (checked: boolean) => {
        setBulkRequestId(null) // selection changes change the payload; reset idempotency key
        setEditableTasks((prev) => prev.map((task) => ({ ...task, selected: checked })))
    }

    const handleCreateTasks = async () => {
        const selectedTasks = editableTasks.filter((t) => t.selected)
        if (selectedTasks.length === 0) {
            setErrorMessage("Please select at least one task to create")
            return
        }
        setErrorMessage(null)

        const requestId = bulkRequestId ?? makeId()
        if (!bulkRequestId) setBulkRequestId(requestId)

        try {
            const result = await createBulkTasks.mutateAsync({
                request_id: requestId,
                ...getEntityPayload(),
                tasks: selectedTasks.map((t) => ({
                    title: t.title,
                    description: t.description,
                    due_date: t.due_date,
                    due_time: t.due_time,
                    task_type: t.task_type,
                    dedupe_key: t.dedupe_key,
                })),
            })

            if (result.success) {
                setStep("success")
            } else {
                setErrorMessage(result.error || "Failed to create tasks")
            }
        } catch (e) {
            const message = e instanceof Error ? e.message : "Failed to create tasks"
            setErrorMessage(message || "Failed to create tasks")
        }
    }

    const handleClose = () => {
        setScheduleText("")
        setEditableTasks([])
        setWarnings([])
        setMetadata(null)
        setStep("input")
        setErrorMessage(null)
        setBulkRequestId(null)
        onOpenChange(false)
    }

    const selectedCount = editableTasks.filter((t) => t.selected).length
    const allSelected = editableTasks.length > 0 && selectedCount === editableTasks.length

    const getConfidenceBadge = (confidence: number) => {
        if (confidence >= 0.8) return <Badge variant="secondary" className="bg-green-100 text-green-800">High</Badge>
        if (confidence >= 0.5) return <Badge variant="secondary" className="bg-yellow-100 text-yellow-800">Medium</Badge>
        return <Badge variant="secondary" className="bg-red-100 text-red-800">Low</Badge>
    }

    return (
        <Dialog
            open={open}
            onOpenChange={(nextOpen) => {
                if (!nextOpen) handleClose()
            }}
        >
            <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <SparklesIcon className="size-5 text-purple-600" />
                        AI Schedule Parser
                    </DialogTitle>
                    <DialogDescription>
                        {entityName && (
                            <span>Creating tasks for <strong>{entityName}</strong></span>
                        )}
                    </DialogDescription>
                </DialogHeader>

                {errorMessage && (
                    <Alert variant="destructive">
                        <AlertTriangleIcon className="size-4" />
                        <AlertDescription>{errorMessage}</AlertDescription>
                    </Alert>
                )}

                {step === "input" && (
                    <div className="space-y-4">
                        <div className="space-y-2">
                            <Label>Paste medication schedule, exam dates, or appointments</Label>
                            <Textarea
                                placeholder="Example:
Medication Schedule:
- Estrace 2mg: Start Dec 26, take twice daily
- PIO injections: Start Dec 28, every night at 9pm
- Transfer date: January 5th at 10am at ABC Clinic"
                                value={scheduleText}
                                onChange={(e) => setScheduleText(e.target.value)}
                                rows={10}
                                className="font-mono text-sm"
                            />
                        </div>

                        {warnings.length > 0 && (
                            <Alert variant="destructive">
                                <AlertTriangleIcon className="size-4" />
                                <AlertDescription>
                                    <ul className="list-disc pl-4">
                                        {warnings.map((w, i) => (
                                            <li key={i}>{w}</li>
                                        ))}
                                    </ul>
                                </AlertDescription>
                            </Alert>
                        )}
                    </div>
                )}

                {step === "review" && (
                    <div className="space-y-4">
                        {metadata && (
                            <div className="text-sm text-muted-foreground">
                                Parsed with timezone: {metadata.timezone}, reference date: {metadata.refDate}
                            </div>
                        )}

                        {warnings.length > 0 && (
                            <Alert>
                                <AlertTriangleIcon className="size-4" />
                                <AlertDescription>
                                    <ul className="list-disc pl-4 text-sm">
                                        {warnings.map((w, i) => (
                                            <li key={i}>{w}</li>
                                        ))}
                                    </ul>
                                </AlertDescription>
                            </Alert>
                        )}

                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <Checkbox
                                    checked={allSelected}
                                    onCheckedChange={(checked) => handleSelectAll(!!checked)}
                                />
                                <span className="text-sm">Select all ({selectedCount}/{editableTasks.length})</span>
                            </div>
                            <Button variant="outline" size="sm" onClick={() => setStep("input")}>
                                Back to edit
                            </Button>
                        </div>

                        <div className="border rounded-md overflow-x-auto">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead className="w-10"></TableHead>
                                        <TableHead>Title</TableHead>
                                        <TableHead className="w-32">Date</TableHead>
                                        <TableHead className="w-24">Time</TableHead>
                                        <TableHead className="w-32">Type</TableHead>
                                        <TableHead className="w-20">Confidence</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {editableTasks.map((task) => (
                                        <TableRow key={task.id} className={!task.selected ? "opacity-50" : ""}>
                                            <TableCell>
                                                <Checkbox
                                                    checked={task.selected}
                                                    onCheckedChange={(checked) =>
                                                        handleTaskChange(task.id, "selected", !!checked)
                                                    }
                                                />
                                            </TableCell>
                                            <TableCell>
                                                <Input
                                                    value={task.title}
                                                    onChange={(e) =>
                                                        handleTaskChange(task.id, "title", e.target.value)
                                                    }
                                                    className="h-8"
                                                />
                                            </TableCell>
                                            <TableCell>
                                                <Input
                                                    type="date"
                                                    value={task.due_date || ""}
                                                    onChange={(e) =>
                                                        handleTaskChange(task.id, "due_date", e.target.value || null)
                                                    }
                                                    className="h-8"
                                                />
                                            </TableCell>
                                            <TableCell>
                                                <Input
                                                    type="time"
                                                    value={task.due_time || ""}
                                                    onChange={(e) =>
                                                        handleTaskChange(task.id, "due_time", e.target.value || null)
                                                    }
                                                    className="h-8"
                                                />
                                            </TableCell>
                                            <TableCell>
                                                <Select
                                                    value={task.task_type}
                                                    onValueChange={(val) =>
                                                        handleTaskChange(task.id, "task_type", val || task.task_type)
                                                    }
                                                >
                                                    <SelectTrigger className="h-8">
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
                                            </TableCell>
                                            <TableCell>{getConfidenceBadge(task.confidence)}</TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    </div>
                )}

                {step === "success" && (
                    <div className="flex flex-col items-center justify-center py-8 space-y-4">
                        <CheckCircle2Icon className="size-16 text-green-600" />
                        <h3 className="text-xl font-semibold">Tasks Created Successfully!</h3>
                        <p className="text-muted-foreground">
                            {editableTasks.filter((t) => t.selected).length} tasks have been added.
                        </p>
                    </div>
                )}

                <DialogFooter>
                    {step === "input" && (
                        <>
                            <Button variant="outline" onClick={handleClose}>
                                Cancel
                            </Button>
                            <Button
                                onClick={handleParse}
                                disabled={!scheduleText.trim() || parseSchedule.isPending}
                            >
                                {parseSchedule.isPending && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                                Parse Schedule
                            </Button>
                        </>
                    )}

                    {step === "review" && (
                        <>
                            <Button variant="outline" onClick={handleClose}>
                                Cancel
                            </Button>
                            <Button
                                onClick={handleCreateTasks}
                                disabled={selectedCount === 0 || createBulkTasks.isPending}
                            >
                                {createBulkTasks.isPending && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                                Create {selectedCount} Task{selectedCount !== 1 ? "s" : ""}
                            </Button>
                        </>
                    )}

                    {step === "success" && (
                        <Button onClick={handleClose}>Done</Button>
                    )}
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
