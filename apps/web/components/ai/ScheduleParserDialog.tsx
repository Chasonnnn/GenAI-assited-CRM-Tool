"use client"

import * as React from "react"
import { useRef } from "react"
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

type ScheduleParserStep = "input" | "review" | "success"

type ScheduleParserMetadata = {
    timezone: string
    refDate: string
}

type ScheduleParserState = {
    scheduleText: string
    errorMessage: string | null
    editableTasks: EditableTask[]
    warnings: string[]
    metadata: ScheduleParserMetadata | null
    step: ScheduleParserStep
}

type ScheduleParserStateAction =
    | { type: "scheduleText"; value: string }
    | { type: "error"; value: string | null }
    | { type: "warningsOnly"; warnings: string[] }
    | { type: "parseSuccess"; tasks: EditableTask[]; warnings: string[]; metadata: ScheduleParserMetadata }
    | { type: "taskChange"; id: string; field: keyof EditableTask; value: EditableTask[keyof EditableTask] }
    | { type: "selectAll"; checked: boolean }
    | { type: "step"; step: ScheduleParserStep }
    | { type: "reset" }

function createInitialScheduleParserState(): ScheduleParserState {
    return {
        scheduleText: "",
        errorMessage: null,
        editableTasks: [],
        warnings: [],
        metadata: null,
        step: "input",
    }
}

function scheduleParserStateReducer(
    state: ScheduleParserState,
    action: ScheduleParserStateAction
): ScheduleParserState {
    switch (action.type) {
        case "scheduleText":
            return { ...state, scheduleText: action.value }
        case "error":
            return { ...state, errorMessage: action.value }
        case "warningsOnly":
            return { ...state, warnings: action.warnings }
        case "parseSuccess":
            return {
                ...state,
                editableTasks: action.tasks,
                warnings: action.warnings,
                metadata: action.metadata,
                step: "review",
            }
        case "taskChange":
            return {
                ...state,
                editableTasks: state.editableTasks.map((task) =>
                    task.id === action.id ? { ...task, [action.field]: action.value } : task
                ),
            }
        case "selectAll":
            return {
                ...state,
                editableTasks: state.editableTasks.map((task) => ({
                    ...task,
                    selected: action.checked,
                })),
            }
        case "step":
            return { ...state, step: action.step }
        case "reset":
            return createInitialScheduleParserState()
        default:
            return state
    }
}

export type EntityType = "surrogate" | "intended_parent" | "match"

export interface ScheduleParserDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    entityType: EntityType
    entityId: string
    entityName?: string
}

function getWarningKey(warning: string) {
    return warning
}

function makeScheduleParserId() {
    // crypto.randomUUID is supported in modern browsers; the fallback keeps tests/older envs happy.
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
        return crypto.randomUUID()
    }
    return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function getConfidenceBadge(confidence: number) {
    if (confidence >= 0.8) return <Badge variant="secondary" className="bg-green-100 text-green-800">High</Badge>
    if (confidence >= 0.5) return <Badge variant="secondary" className="bg-yellow-100 text-yellow-800">Medium</Badge>
    return <Badge variant="secondary" className="bg-red-100 text-red-800">Low</Badge>
}

type ScheduleParserTaskChangeHandler = <K extends keyof EditableTask>(
    id: string,
    field: K,
    value: EditableTask[K]
) => void

function ScheduleParserWarningList({
    warnings,
    destructive = false,
}: {
    warnings: string[]
    destructive?: boolean
}) {
    if (warnings.length === 0) return null

    return (
        <Alert variant={destructive ? "destructive" : "default"}>
            <AlertTriangleIcon className="size-4" />
            <AlertDescription>
                <ul className={`list-disc pl-4${destructive ? "" : " text-sm"}`}>
                    {warnings.map((warning) => (
                        <li key={getWarningKey(warning)}>{warning}</li>
                    ))}
                </ul>
            </AlertDescription>
        </Alert>
    )
}

function ScheduleParserInputStep({
    scheduleText,
    uniqueWarnings,
    onScheduleTextChange,
}: {
    scheduleText: string
    uniqueWarnings: string[]
    onScheduleTextChange: (value: string) => void
}) {
    return (
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
                    onChange={(e) => onScheduleTextChange(e.target.value)}
                    rows={10}
                    className="font-mono text-sm"
                />
            </div>

            <ScheduleParserWarningList warnings={uniqueWarnings} destructive />
        </div>
    )
}

function ScheduleParserReviewStep({
    metadata,
    uniqueWarnings,
    editableTasks,
    selectedCount,
    allSelected,
    onSelectAll,
    onBackToEdit,
    onTaskChange,
}: {
    metadata: ScheduleParserMetadata | null
    uniqueWarnings: string[]
    editableTasks: EditableTask[]
    selectedCount: number
    allSelected: boolean
    onSelectAll: (checked: boolean) => void
    onBackToEdit: () => void
    onTaskChange: ScheduleParserTaskChangeHandler
}) {
    return (
        <div className="space-y-4">
            {metadata && (
                <div className="text-sm text-muted-foreground">
                    Parsed with timezone: {metadata.timezone}, reference date: {metadata.refDate}
                </div>
            )}

            <ScheduleParserWarningList warnings={uniqueWarnings} />

            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Checkbox
                        checked={allSelected}
                        onCheckedChange={(checked) => onSelectAll(!!checked)}
                    />
                    <span className="text-sm">Select all ({selectedCount}/{editableTasks.length})</span>
                </div>
                <Button variant="outline" size="sm" onClick={onBackToEdit}>
                    Back to edit
                </Button>
            </div>

            <ScheduleParserTaskTable tasks={editableTasks} onTaskChange={onTaskChange} />
        </div>
    )
}

function ScheduleParserTaskTable({
    tasks,
    onTaskChange,
}: {
    tasks: EditableTask[]
    onTaskChange: ScheduleParserTaskChangeHandler
}) {
    return (
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
                    {tasks.map((task) => (
                        <ScheduleParserTaskRow
                            key={task.id}
                            task={task}
                            onTaskChange={onTaskChange}
                        />
                    ))}
                </TableBody>
            </Table>
        </div>
    )
}

function ScheduleParserTaskRow({
    task,
    onTaskChange,
}: {
    task: EditableTask
    onTaskChange: ScheduleParserTaskChangeHandler
}) {
    return (
        <TableRow className={!task.selected ? "opacity-50" : ""}>
            <TableCell>
                <Checkbox
                    checked={task.selected}
                    onCheckedChange={(checked) => onTaskChange(task.id, "selected", !!checked)}
                />
            </TableCell>
            <TableCell>
                <Input
                    value={task.title}
                    onChange={(e) => onTaskChange(task.id, "title", e.target.value)}
                    className="h-8"
                />
            </TableCell>
            <TableCell>
                <Input
                    type="date"
                    value={task.due_date || ""}
                    onChange={(e) =>
                        onTaskChange(task.id, "due_date", e.target.value || null)
                    }
                    className="h-8"
                />
            </TableCell>
            <TableCell>
                <Input
                    type="time"
                    value={task.due_time || ""}
                    onChange={(e) =>
                        onTaskChange(task.id, "due_time", e.target.value || null)
                    }
                    className="h-8"
                />
            </TableCell>
            <TableCell>
                <Select
                    value={task.task_type}
                    onValueChange={(val) =>
                        onTaskChange(task.id, "task_type", val || task.task_type)
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
    )
}

function ScheduleParserSuccessStep({ selectedCount }: { selectedCount: number }) {
    return (
        <div className="flex flex-col items-center justify-center gap-y-4 py-8">
            <CheckCircle2Icon className="size-16 text-green-600" />
            <h3 className="text-xl font-semibold">Tasks Created Successfully!</h3>
            <p className="text-muted-foreground">
                {selectedCount} tasks have been added.
            </p>
        </div>
    )
}

function ScheduleParserFooter({
    step,
    scheduleText,
    selectedCount,
    parsePending,
    createPending,
    onClose,
    onParse,
    onCreateTasks,
}: {
    step: ScheduleParserStep
    scheduleText: string
    selectedCount: number
    parsePending: boolean
    createPending: boolean
    onClose: () => void
    onParse: () => void
    onCreateTasks: () => void
}) {
    if (step === "input") {
        return (
            <DialogFooter>
                <Button variant="outline" onClick={onClose}>
                    Cancel
                </Button>
                <Button
                    onClick={onParse}
                    disabled={!scheduleText.trim() || parsePending}
                >
                    {parsePending && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                    Parse Schedule
                </Button>
            </DialogFooter>
        )
    }

    if (step === "review") {
        return (
            <DialogFooter>
                <Button variant="outline" onClick={onClose}>
                    Cancel
                </Button>
                <Button
                    onClick={onCreateTasks}
                    disabled={selectedCount === 0 || createPending}
                >
                    {createPending && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                    Create {selectedCount} Task{selectedCount !== 1 ? "s" : ""}
                </Button>
            </DialogFooter>
        )
    }

    return (
        <DialogFooter>
            <Button onClick={onClose}>Close task creator</Button>
        </DialogFooter>
    )
}

export function ScheduleParserDialog({
    open,
    onOpenChange,
    entityType,
    entityId,
    entityName,
}: ScheduleParserDialogProps) {
    const [parserState, dispatchParserState] = React.useReducer(
        scheduleParserStateReducer,
        createInitialScheduleParserState()
    )
    const { scheduleText, errorMessage, editableTasks, warnings, metadata, step } = parserState
    const bulkRequestIdRef = useRef<string | null>(null)

    const parseSchedule = useParseSchedule()
    const createBulkTasks = useCreateBulkTasks()

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
        dispatchParserState({ type: "error", value: null })

        try {
            const result = await parseSchedule.mutateAsync({
                text: scheduleText,
                ...getEntityPayload(),
                user_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            })

            if (result.proposed_tasks.length === 0 && result.warnings.length > 0) {
                dispatchParserState({ type: "warningsOnly", warnings: result.warnings })
                return
            }

            // Convert to editable tasks
            const tasks: EditableTask[] = result.proposed_tasks.map((task) => ({
                ...task,
                selected: true,
                id: makeScheduleParserId(),
            }))

            dispatchParserState({
                type: "parseSuccess",
                tasks,
                warnings: result.warnings,
                metadata: {
                    timezone: result.assumed_timezone,
                    refDate: result.assumed_reference_date,
                },
            })
            bulkRequestIdRef.current = null // new parse = new payload, reset idempotency key
        } catch (e) {
            const message = e instanceof Error ? e.message : "Failed to parse schedule"
            dispatchParserState({
                type: "error",
                value: message || "Failed to parse schedule",
            })
        }
    }

    const handleTaskChange = <K extends keyof EditableTask>(id: string, field: K, value: EditableTask[K]) => {
        bulkRequestIdRef.current = null // task edits change the payload; reset idempotency key
        dispatchParserState({ type: "taskChange", id, field, value })
    }

    const handleSelectAll = (checked: boolean) => {
        bulkRequestIdRef.current = null // selection changes change the payload; reset idempotency key
        dispatchParserState({ type: "selectAll", checked })
    }

    const handleCreateTasks = async () => {
        const selectedTasks = editableTasks.filter((t) => t.selected)
        if (selectedTasks.length === 0) {
            dispatchParserState({
                type: "error",
                value: "Please select at least one task to create",
            })
            return
        }
        dispatchParserState({ type: "error", value: null })

        const requestId = bulkRequestIdRef.current ?? makeScheduleParserId()
        bulkRequestIdRef.current = requestId

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
                dispatchParserState({ type: "step", step: "success" })
            } else {
                dispatchParserState({
                    type: "error",
                    value: result.error || "Failed to create tasks",
                })
            }
        } catch (e) {
            const message = e instanceof Error ? e.message : "Failed to create tasks"
            dispatchParserState({
                type: "error",
                value: message || "Failed to create tasks",
            })
        }
    }

    const handleClose = () => {
        dispatchParserState({ type: "reset" })
        bulkRequestIdRef.current = null
        onOpenChange(false)
    }

    const selectedCount = editableTasks.filter((t) => t.selected).length
    const allSelected = editableTasks.length > 0 && selectedCount === editableTasks.length
    const uniqueWarnings = Array.from(new Set(warnings))

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
                    <ScheduleParserInputStep
                        scheduleText={scheduleText}
                        uniqueWarnings={uniqueWarnings}
                        onScheduleTextChange={(value) =>
                            dispatchParserState({ type: "scheduleText", value })
                        }
                    />
                )}

                {step === "review" && (
                    <ScheduleParserReviewStep
                        metadata={metadata}
                        uniqueWarnings={uniqueWarnings}
                        editableTasks={editableTasks}
                        selectedCount={selectedCount}
                        allSelected={allSelected}
                        onSelectAll={handleSelectAll}
                        onBackToEdit={() =>
                            dispatchParserState({ type: "step", step: "input" })
                        }
                        onTaskChange={handleTaskChange}
                    />
                )}

                {step === "success" && (
                    <ScheduleParserSuccessStep selectedCount={selectedCount} />
                )}

                <ScheduleParserFooter
                    step={step}
                    scheduleText={scheduleText}
                    selectedCount={selectedCount}
                    parsePending={parseSchedule.isPending}
                    createPending={createBulkTasks.isPending}
                    onClose={handleClose}
                    onParse={handleParse}
                    onCreateTasks={handleCreateTasks}
                />
            </DialogContent>
        </Dialog>
    )
}
