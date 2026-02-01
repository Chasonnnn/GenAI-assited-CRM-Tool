"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Checkbox } from "@/components/ui/checkbox"
import { ScrollArea } from "@/components/ui/scroll-area"
import { useWorkflowOptions } from "@/lib/hooks/use-workflows"
import {
    useCreatePlatformWorkflowTemplate,
    usePlatformWorkflowTemplate,
    usePublishPlatformWorkflowTemplate,
    useUpdatePlatformWorkflowTemplate,
} from "@/lib/hooks/use-platform-templates"
import type { PlatformWorkflowTemplate } from "@/lib/api/platform"
import type { ActionConfig, Condition } from "@/lib/api/workflows"
import type { JsonObject, JsonValue } from "@/lib/types/json"
import { PublishDialog } from "@/components/ops/templates/PublishDialog"
import { US_STATES } from "@/lib/constants/us-states"
import { NotFoundState } from "@/components/not-found-state"
import {
    ArrowLeftIcon,
    Loader2Icon,
    PlusIcon,
    XIcon,
    GripVerticalIcon,
    ChevronDownIcon,
} from "lucide-react"
import { toast } from "sonner"

type SelectOption = { value: string; label: string }

const triggerLabels: Record<string, string> = {
    surrogate_created: "Surrogate Created",
    status_changed: "Status Changed",
    surrogate_assigned: "Surrogate Assigned",
    surrogate_updated: "Field Updated",
    task_due: "Task Due",
    task_overdue: "Task Overdue",
    scheduled: "Scheduled",
    inactivity: "Inactivity",
    match_proposed: "Match Proposed",
    match_accepted: "Match Accepted",
    match_rejected: "Match Rejected",
    appointment_scheduled: "Appointment Scheduled",
    appointment_completed: "Appointment Completed",
    note_added: "Note Added",
    document_uploaded: "Document Uploaded",
}

const ICON_OPTIONS = ["template", "mail", "clock", "bell", "activity", "alert-circle"]

const conditionFieldLabels: Record<string, string> = {
    status_label: "Stage",
    stage_id: "Stage",
    source: "Source",
    is_priority: "Is Priority",
    is_archived: "Is Archived",
    owner_id: "Assigned User",
    queue_id: "Queue",
    state: "State",
    full_name: "Full Name",
    email: "Email",
    phone: "Phone",
    owner_type: "Owner Type",
    created_at: "Created At",
    date_of_birth: "Date of Birth",
    age: "Age",
    bmi: "BMI",
    height_ft: "Height (ft)",
    weight_lb: "Weight (lb)",
    num_deliveries: "Deliveries",
    num_csections: "C-Sections",
    race: "Race",
    meta_lead_id: "Meta Lead ID",
    meta_ad_external_id: "Meta Ad External ID",
    meta_form_id: "Meta Form ID",
}

const BOOLEAN_FIELDS = new Set([
    "is_priority",
    "has_child",
    "is_citizen_or_pr",
    "is_non_smoker",
    "has_surrogate_experience",
    "is_age_eligible",
])

const NUMBER_FIELDS = new Set([
    "age",
    "bmi",
    "height_ft",
    "weight_lb",
    "num_deliveries",
    "num_csections",
])

const DATE_FIELDS = new Set(["created_at", "date_of_birth"])

const MULTISELECT_FIELDS = new Set([
    "stage_id",
    "status_label",
    "owner_id",
    "owner_type",
    "state",
    "source",
])

const SOURCE_OPTIONS: SelectOption[] = [
    { value: "manual", label: "Manual" },
    { value: "meta", label: "Meta" },
    { value: "website", label: "Website" },
    { value: "referral", label: "Referral" },
    { value: "import", label: "Import" },
    { value: "agency", label: "Agency" },
]

const OWNER_TYPE_OPTIONS: SelectOption[] = [
    { value: "user", label: "User" },
    { value: "queue", label: "Queue" },
]

const LIST_OPERATORS = new Set(["in", "not_in"])
const VALUELESS_OPERATORS = new Set(["is_empty", "is_not_empty"])

const FALLBACK_TRIGGER_TYPES = [
    { value: "surrogate_created", label: "Surrogate Created", description: "When a new case is created" },
    { value: "status_changed", label: "Status Changed", description: "When case status changes" },
    { value: "surrogate_assigned", label: "Surrogate Assigned", description: "When case is assigned" },
    { value: "surrogate_updated", label: "Surrogate Updated", description: "When specific fields change" },
    { value: "task_due", label: "Task Due", description: "Before a task is due" },
    { value: "task_overdue", label: "Task Overdue", description: "When a task becomes overdue" },
    { value: "scheduled", label: "Scheduled", description: "On a recurring schedule" },
    { value: "inactivity", label: "Inactivity", description: "When case has no activity" },
    { value: "match_proposed", label: "Match Proposed", description: "When a match is proposed" },
    { value: "match_accepted", label: "Match Accepted", description: "When a match is accepted" },
    { value: "match_rejected", label: "Match Rejected", description: "When a match is rejected" },
    { value: "appointment_scheduled", label: "Appointment Scheduled", description: "When an appointment is scheduled" },
    { value: "appointment_completed", label: "Appointment Completed", description: "When an appointment is completed" },
    { value: "note_added", label: "Note Added", description: "When a note is added to a case" },
    { value: "document_uploaded", label: "Document Uploaded", description: "When a document is uploaded" },
]

const FALLBACK_ACTION_TYPES = [
    { value: "send_email", label: "Send Email", description: "Send email using template" },
    { value: "create_task", label: "Create Task", description: "Create a task on the case" },
    { value: "assign_surrogate", label: "Assign Surrogate", description: "Assign to user or queue" },
    { value: "send_notification", label: "Send Notification", description: "Send in-app notification" },
    { value: "update_field", label: "Update Field", description: "Update a case field" },
    { value: "add_note", label: "Add Note", description: "Add a note to the case" },
]

const FALLBACK_OPERATORS = [
    { value: "equals", label: "Equals" },
    { value: "not_equals", label: "Does not equal" },
    { value: "contains", label: "Contains" },
    { value: "not_contains", label: "Does not contain" },
    { value: "is_empty", label: "Is empty" },
    { value: "is_not_empty", label: "Is not empty" },
    { value: "in", label: "Is one of" },
    { value: "not_in", label: "Is not one of" },
    { value: "greater_than", label: "Greater than" },
    { value: "less_than", label: "Less than" },
]

function toListArray(value: JsonValue): string[] {
    if (Array.isArray(value)) {
        return value.map((item) => String(item).trim()).filter(Boolean)
    }
    if (typeof value === "string") {
        return value
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean)
    }
    if (value === null || value === undefined) {
        return []
    }
    const asString = String(value).trim()
    return asString ? [asString] : []
}

function MultiSelect({
    options,
    value,
    onChange,
    placeholder = "Select values",
}: {
    options: SelectOption[]
    value: string[]
    onChange: (next: string[]) => void
    placeholder?: string
}) {
    const selectedValues = new Set(value)
    const selectedLabels = options
        .filter((option) => selectedValues.has(option.value))
        .map((option) => option.label)
    const label = selectedLabels.length > 0 ? `${selectedLabels.length} selected` : placeholder

    return (
        <Popover>
            <PopoverTrigger
                type="button"
                className={buttonVariants({ variant: "outline", className: "flex-1 justify-between" })}
            >
                <span className="truncate">{label}</span>
                <ChevronDownIcon className="size-4 text-muted-foreground" />
            </PopoverTrigger>
            <PopoverContent className="w-72">
                <ScrollArea className="h-48">
                    <div className="space-y-2">
                        {options.map((option) => {
                            const checked = selectedValues.has(option.value)
                            return (
                                <label key={option.value} className="flex items-center gap-2 text-sm">
                                    <Checkbox
                                        checked={checked}
                                        onCheckedChange={(next) => {
                                            const nextChecked = next === true
                                            const updated = new Set(selectedValues)
                                            if (nextChecked) {
                                                updated.add(option.value)
                                            } else {
                                                updated.delete(option.value)
                                            }
                                            onChange(Array.from(updated))
                                        }}
                                    />
                                    <span>{option.label}</span>
                                </label>
                            )
                        })}
                        {options.length === 0 && (
                            <p className="text-xs text-muted-foreground">No options available.</p>
                        )}
                    </div>
                </ScrollArea>
            </PopoverContent>
        </Popover>
    )
}

function normalizeConditionsForUi(conditions: Condition[]): Condition[] {
    return conditions.map((condition) => {
        if (!LIST_OPERATORS.has(condition.operator)) {
            return condition
        }
        if (MULTISELECT_FIELDS.has(condition.field)) {
            if (Array.isArray(condition.value)) {
                return condition
            }
            if (typeof condition.value === "string") {
                const values = condition.value
                    .split(",")
                    .map((value) => value.trim())
                    .filter(Boolean)
                return { ...condition, value: values }
            }
            return { ...condition, value: [] }
        }
        if (Array.isArray(condition.value)) {
            return { ...condition, value: condition.value.join(", ") }
        }
        return condition
    })
}

function normalizeConditionsForSave(conditions: Condition[]): Condition[] {
    return conditions.map((condition) => {
        if (VALUELESS_OPERATORS.has(condition.operator)) {
            return { ...condition, value: null }
        }
        if (LIST_OPERATORS.has(condition.operator)) {
            const raw =
                typeof condition.value === "string"
                    ? condition.value
                    : Array.isArray(condition.value)
                        ? condition.value.join(", ")
                        : ""
            const values = raw
                .split(",")
                .map((value) => value.trim())
                .filter(Boolean)
            return { ...condition, value: values }
        }
        return condition
    })
}

function normalizeActionsForUi(actions: ActionConfig[]): ActionConfig[] {
    return actions.map((action) => {
        const stageId = action["stage_id"]
        if (action.action_type === "update_status" && typeof stageId === "string" && stageId) {
            const normalized: ActionConfig = {
                ...action,
                action_type: "update_field",
                field: "stage_id",
                value: stageId,
            }
            delete normalized["stage_id"]
            return normalized
        }
        return action
    })
}

function normalizeTriggerConfigForUi(
    triggerType: string,
    triggerConfig: JsonObject,
    statuses: { id?: string; value: string; label: string }[],
): JsonObject {
    if (triggerType !== "status_changed") return { ...triggerConfig }
    const next: JsonObject = { ...triggerConfig }
    if (
        (typeof next.to_stage_id !== "string" || !next.to_stage_id) &&
        typeof next.to_status === "string"
    ) {
        const match = statuses.find((status) => status.value === next.to_status)
        if (match?.id) {
            next.to_stage_id = match.id
            delete next.to_status
        }
    }
    if (
        (typeof next.from_stage_id !== "string" || !next.from_stage_id) &&
        typeof next.from_status === "string"
    ) {
        const match = statuses.find((status) => status.value === next.from_status)
        if (match?.id) {
            next.from_stage_id = match.id
            delete next.from_status
        }
    }
    return next
}

export default function PlatformWorkflowTemplatePage() {
    const router = useRouter()
    const params = useParams()
    const id = params?.id as string
    const isNew = id === "new"
    const templateId = isNew ? null : id

    const { data: templateData, isLoading } = usePlatformWorkflowTemplate(templateId)
    const createTemplate = useCreatePlatformWorkflowTemplate()
    const updateTemplate = useUpdatePlatformWorkflowTemplate()
    const publishTemplate = usePublishPlatformWorkflowTemplate()
    const { data: options } = useWorkflowOptions("org")

    const [name, setName] = useState("")
    const [description, setDescription] = useState("")
    const [icon, setIcon] = useState("template")
    const [category, setCategory] = useState("general")
    const [triggerType, setTriggerType] = useState("")
    const [triggerConfig, setTriggerConfig] = useState<JsonObject>({})
    const [conditions, setConditions] = useState<Condition[]>([])
    const [conditionLogic, setConditionLogic] = useState<"AND" | "OR">("AND")
    const [actions, setActions] = useState<ActionConfig[]>([])
    const [isPublished, setIsPublished] = useState(false)
    const [showPublishDialog, setShowPublishDialog] = useState(false)
    const [isSaving, setIsSaving] = useState(false)
    const [isPublishing, setIsPublishing] = useState(false)

    const statusOptions = useMemo(() => options?.statuses ?? [], [options?.statuses])
    const actionTypeOptions = options?.action_types ?? FALLBACK_ACTION_TYPES
    const triggerTypeOptions = options?.trigger_types ?? FALLBACK_TRIGGER_TYPES
    const updateFields = options?.update_fields ?? ["stage_id", "is_priority", "owner_type", "owner_id"]
    const conditionOperators = options?.condition_operators ?? FALLBACK_OPERATORS
    const conditionFields = options?.condition_fields ?? Object.keys(conditionFieldLabels)
    const userOptions = useMemo(() => options?.users ?? [], [options?.users])
    const queueOptions = useMemo(() => options?.queues ?? [], [options?.queues])

    const actionTypeValuesForTrigger =
        triggerType && options?.action_types_by_trigger?.[triggerType]
            ? new Set(options.action_types_by_trigger[triggerType])
            : null
    const filteredActionTypes = actionTypeValuesForTrigger
        ? actionTypeOptions.filter((action) => actionTypeValuesForTrigger.has(action.value))
        : actionTypeOptions

    const stageIdOptions = useMemo<SelectOption[]>(
        () =>
            statusOptions.map((status) => ({
                value: status.id ?? status.value,
                label: status.label,
            })),
        [statusOptions]
    )

    const stageLabelOptions = useMemo<SelectOption[]>(
        () => statusOptions.map((status) => ({ value: status.label, label: status.label })),
        [statusOptions]
    )

    const ownerOptions = useMemo<SelectOption[]>(
        () => [
            ...userOptions.map((user) => ({ value: user.id, label: user.display_name })),
            ...queueOptions.map((queue) => ({ value: queue.id, label: `Queue: ${queue.name}` })),
        ],
        [userOptions, queueOptions]
    )

    const stateOptions = useMemo<SelectOption[]>(
        () => US_STATES.map((state) => ({ value: state.value, label: state.label })),
        []
    )

    const selectedTriggerFields = Array.isArray(triggerConfig.fields)
        ? triggerConfig.fields.filter((field): field is string => typeof field === "string")
        : []

    useEffect(() => {
        if (!templateData || isNew) return
        const draft = templateData.draft
        setName(draft.name ?? "")
        setDescription(draft.description ?? "")
        setIcon(draft.icon ?? "template")
        setCategory(draft.category ?? "general")
        setTriggerType(draft.trigger_type ?? "")
        setTriggerConfig(
            normalizeTriggerConfigForUi(draft.trigger_type ?? "", draft.trigger_config ?? {}, statusOptions)
        )
        setConditions(normalizeConditionsForUi(draft.conditions ?? []))
        setConditionLogic((draft.condition_logic ?? "AND") as "AND" | "OR")
        setActions(normalizeActionsForUi(draft.actions ?? []))
        setIsPublished((templateData.published_version ?? 0) > 0)
    }, [templateData, isNew, statusOptions])

    useEffect(() => {
        if (!triggerType) return
        setTriggerConfig((prev) => {
            const next = { ...prev }
            if (triggerType === "status_changed") {
                if (typeof next.to_stage_id !== "string") next.to_stage_id = ""
                if (typeof next.from_stage_id !== "string") next.from_stage_id = ""
            }
            if (triggerType === "scheduled") {
                if (typeof next.cron !== "string") next.cron = ""
                if (typeof next.timezone !== "string") next.timezone = "America/Los_Angeles"
            }
            if (triggerType === "inactivity") {
                if (typeof next.days !== "number") next.days = 7
            }
            if (triggerType === "task_due") {
                if (typeof next.hours_before !== "number") next.hours_before = 24
            }
            if (triggerType === "surrogate_updated") {
                if (!Array.isArray(next.fields)) next.fields = []
            }
            if (triggerType === "surrogate_assigned") {
                if (typeof next.to_user_id !== "string") delete next.to_user_id
            }
            return next
        })
    }, [triggerType])

    const addCondition = () => {
        setConditions([...conditions, { field: "", operator: "equals", value: "" }])
    }

    const removeCondition = (index: number) => {
        setConditions(conditions.filter((_, i) => i !== index))
    }

    const updateCondition = (index: number, updates: Partial<Condition>) => {
        setConditions(
            conditions.map((condition, i) => {
                if (i !== index) return condition
                const next = { ...condition, ...updates }
                const fieldChanged = typeof updates.field === "string" && updates.field !== condition.field
                if (fieldChanged) {
                    next.value = ""
                }
                if (VALUELESS_OPERATORS.has(next.operator)) {
                    next.value = ""
                    return next
                }
                if (LIST_OPERATORS.has(next.operator)) {
                    if (MULTISELECT_FIELDS.has(next.field)) {
                        next.value = toListArray(next.value as JsonValue)
                    } else {
                        if (Array.isArray(next.value)) {
                            next.value = next.value.join(", ")
                        }
                        if (typeof next.value !== "string") {
                            next.value = ""
                        }
                    }
                    return next
                }
                if (Array.isArray(next.value)) {
                    next.value = next.value[0] ?? ""
                }
                if (BOOLEAN_FIELDS.has(next.field) && typeof next.value !== "boolean") {
                    next.value = false
                }
                return next
            })
        )
    }

    const addAction = () => {
        setActions([...actions, { action_type: "" }])
    }

    const removeAction = (index: number) => {
        setActions(actions.filter((_, i) => i !== index))
    }

    const mergeActionConfig = (action: ActionConfig, updates: Partial<ActionConfig>): ActionConfig => {
        const next: ActionConfig = { ...action }
        for (const [key, value] of Object.entries(updates)) {
            if (value !== undefined) {
                next[key] = value as JsonValue
            }
        }
        return next
    }

    const updateAction = (index: number, updates: Partial<ActionConfig>) => {
        setActions(actions.map((action, i) => (i === index ? mergeActionConfig(action, updates) : action)))
    }

    const getConditionOptions = (field: string): SelectOption[] | null => {
        if (field === "stage_id") return stageIdOptions
        if (field === "status_label") return stageLabelOptions
        if (field === "owner_type") return OWNER_TYPE_OPTIONS
        if (field === "owner_id") return ownerOptions
        if (field === "state") return stateOptions
        if (field === "source") return SOURCE_OPTIONS
        return null
    }

    const renderConditionValueInput = (condition: Condition, index: number) => {
        const operator = condition.operator
        const field = condition.field
        const isListOperator = LIST_OPERATORS.has(operator)
        const isValueless = VALUELESS_OPERATORS.has(operator)
        const optionsForField = getConditionOptions(field)

        if (isValueless) {
            return (
                <Input
                    className="flex-1"
                    value=""
                    disabled
                    placeholder="No value needed"
                />
            )
        }

        if (!isListOperator && BOOLEAN_FIELDS.has(field)) {
            const checked = Boolean(condition.value)
            return (
                <div className="flex flex-1 items-center gap-2 rounded-md border px-3 py-2">
                    <Switch checked={checked} onCheckedChange={(next) => updateCondition(index, { value: next })} />
                    <span className="text-sm">{checked ? "Yes" : "No"}</span>
                </div>
            )
        }

        if (!isListOperator && NUMBER_FIELDS.has(field)) {
            return (
                <Input
                    type="number"
                    className="flex-1"
                    value={typeof condition.value === "number" ? condition.value : ""}
                    onChange={(event) => updateCondition(index, { value: Number(event.target.value) })}
                />
            )
        }

        if (!isListOperator && DATE_FIELDS.has(field)) {
            return (
                <Input
                    type="date"
                    className="flex-1"
                    value={typeof condition.value === "string" ? condition.value : ""}
                    onChange={(event) => updateCondition(index, { value: event.target.value })}
                />
            )
        }

        if (isListOperator && optionsForField && MULTISELECT_FIELDS.has(field)) {
            const selectedValues = Array.isArray(condition.value)
                ? condition.value.map((item) => String(item))
                : toListArray(condition.value as JsonValue)
            return (
                <MultiSelect
                    options={optionsForField}
                    value={selectedValues}
                    onChange={(next) => updateCondition(index, { value: next })}
                    placeholder="Select values"
                />
            )
        }

        if (optionsForField && !isListOperator) {
            return (
                <Select
                    value={typeof condition.value === "string" ? condition.value : ""}
                    onValueChange={(value) => updateCondition(index, { value })}
                >
                    <SelectTrigger className="flex-1">
                        <SelectValue placeholder="Select value">
                            {(value: string | null) => {
                                if (!value) return "Select value"
                                const option = optionsForField.find((opt) => opt.value === value)
                                return option?.label ?? value
                            }}
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        {optionsForField.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                                {option.label}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            )
        }

        const inputValue =
            typeof condition.value === "string"
                ? condition.value
                : Array.isArray(condition.value)
                    ? condition.value.join(", ")
                    : ""

        return (
            <Input
                placeholder={isListOperator ? "Comma-separated values" : "Value"}
                className="flex-1"
                value={inputValue}
                onChange={(event) => updateCondition(index, { value: event.target.value })}
            />
        )
    }

    const getTriggerValidationError = (): string | null => {
        if (!triggerType) return "Trigger type is required."
        if (triggerType === "status_changed") {
            const toStage = triggerConfig.to_stage_id
            if (!toStage || typeof toStage !== "string") return "Select a target stage."
        }
        if (triggerType === "scheduled") {
            const cron = triggerConfig.cron
            if (!cron || typeof cron !== "string") return "Cron schedule is required."
        }
        if (triggerType === "inactivity") {
            const days = triggerConfig.days
            if (!days || typeof days !== "number") return "Days inactive is required."
        }
        if (triggerType === "task_due") {
            const hours = triggerConfig.hours_before
            if (!hours || typeof hours !== "number") return "Hours before due is required."
        }
        if (triggerType === "surrogate_updated") {
            const fields = triggerConfig.fields
            if (!Array.isArray(fields) || fields.length === 0) return "Select at least one field."
        }
        return null
    }

    const getActionValidationError = (action: ActionConfig): string | null => {
        const title = typeof action.title === "string" ? action.title : ""
        const content = typeof action.content === "string" ? action.content : ""
        if (!action.action_type) return "Select an action type for each action."
        if (action.action_type === "create_task" && !title.trim()) {
            return "Task actions need a title."
        }
        if (action.action_type === "send_notification" && !title.trim()) {
            return "Notification actions need a title."
        }
        if (action.action_type === "send_notification" && Array.isArray(action.recipients) && action.recipients.length === 0) {
            return "Select at least one recipient."
        }
        if (action.action_type === "assign_surrogate") {
            if (!action.owner_type) return "Assign actions need an owner type."
            if (!action.owner_id) return "Assign actions need a target owner."
        }
        if (action.action_type === "update_field") {
            if (!action.field) return "Select a field to update."
            if (action.value === undefined || action.value === null || action.value === "") {
                return "Update actions need a value."
            }
        }
        if (action.action_type === "add_note" && !content.trim()) {
            return "Note actions need content."
        }
        return null
    }

    const getWorkflowValidationError = (): string | null => {
        if (!name.trim()) return "Template name is required."
        const triggerError = getTriggerValidationError()
        if (triggerError) return triggerError
        if (actions.length === 0) return "Add at least one action."
        for (const action of actions) {
            const error = getActionValidationError(action)
            if (error) return error
        }
        return null
    }

    const workflowValidationError = getWorkflowValidationError()

    const buildTriggerConfig = useCallback((): JsonObject => {
        const next: JsonObject = { ...triggerConfig }
        if (triggerType === "status_changed") {
            if (typeof next.to_stage_id !== "string" || !next.to_stage_id) delete next.to_stage_id
            if (typeof next.from_stage_id !== "string" || !next.from_stage_id) delete next.from_stage_id
            delete next.to_status
            delete next.from_status
        }
        if (triggerType === "scheduled") {
            if (typeof next.cron !== "string") next.cron = ""
            if (typeof next.timezone !== "string") next.timezone = "America/Los_Angeles"
        }
        if (triggerType === "inactivity") {
            const days = Number(next.days)
            next.days = Number.isFinite(days) ? days : 7
        }
        if (triggerType === "task_due") {
            const hours = Number(next.hours_before)
            next.hours_before = Number.isFinite(hours) ? hours : 24
        }
        if (triggerType === "surrogate_updated") {
            if (!Array.isArray(next.fields)) next.fields = []
        }
        if (triggerType === "surrogate_assigned") {
            if (typeof next.to_user_id !== "string") delete next.to_user_id
        }
        return next
    }, [triggerConfig, triggerType])

    const persistTemplate = useCallback(
        async (): Promise<PlatformWorkflowTemplate> => {
            const payload = {
                name: name.trim(),
                description: description.trim() || null,
                icon: icon || "template",
                category: category || "general",
                trigger_type: triggerType,
                trigger_config: buildTriggerConfig(),
                conditions: normalizeConditionsForSave(conditions),
                condition_logic: conditionLogic,
                actions,
            }

            if (isNew) {
                const created = await createTemplate.mutateAsync(payload)
                router.replace(`/ops/templates/workflows/${created.id}`)
                return created
            }

            return updateTemplate.mutateAsync({
                id,
                payload: {
                    ...payload,
                    expected_version: templateData?.published_version ?? null,
                },
            })
        },
        [
            actions,
            buildTriggerConfig,
            category,
            conditionLogic,
            conditions,
            createTemplate,
            description,
            icon,
            id,
            isNew,
            name,
            router,
            templateData?.published_version,
            triggerType,
            updateTemplate,
        ]
    )

    const handleSave = async () => {
        const error = getWorkflowValidationError()
        if (error) {
            toast.error(error)
            return
        }
        setIsSaving(true)
        try {
            const saved = await persistTemplate()
            setIsPublished((saved.published_version ?? 0) > 0)
            toast.success("Template saved")
        } catch (err) {
            toast.error(err instanceof Error ? err.message : "Failed to save template")
        } finally {
            setIsSaving(false)
        }
    }

    const handlePublish = () => {
        const error = getWorkflowValidationError()
        if (error) {
            toast.error(error)
            return
        }
        setShowPublishDialog(true)
    }

    const confirmPublish = async (publishAll: boolean, orgIds: string[]) => {
        setIsPublishing(true)
        try {
            const saved = await persistTemplate()
            await publishTemplate.mutateAsync({
                id: saved.id,
                payload: {
                    publish_all: publishAll,
                    org_ids: publishAll ? null : orgIds,
                },
            })
            setIsPublished(true)
            setShowPublishDialog(false)
            toast.success("Template published")
        } catch (err) {
            toast.error(err instanceof Error ? err.message : "Failed to publish template")
        } finally {
            setIsPublishing(false)
        }
    }

    if (!isNew && isLoading) {
        return (
            <div className="flex h-screen items-center justify-center bg-stone-100 dark:bg-stone-950">
                <div className="flex items-center gap-2 text-stone-600 dark:text-stone-400">
                    <Loader2Icon className="size-5 animate-spin" />
                    <span>Loading template...</span>
                </div>
            </div>
        )
    }

    if (!isNew && !templateData) {
        return (
            <NotFoundState title="Template not found" backUrl="/ops/templates?tab=workflows" />
        )
    }

    return (
        <div className="min-h-screen bg-stone-100 dark:bg-stone-950">
            <div className="flex h-16 items-center justify-between border-b border-stone-200 bg-white px-6 dark:border-stone-800 dark:bg-stone-900">
                <div className="flex items-center gap-4">
                    <Button variant="ghost" size="icon" onClick={() => router.push("/ops/templates?tab=workflows")}>
                        <ArrowLeftIcon className="size-5" />
                    </Button>
                    <Input
                        id="workflow-name"
                        aria-label="Workflow template name"
                        value={name}
                        onChange={(event) => setName(event.target.value)}
                        placeholder="Workflow template name..."
                        className="h-9 w-72 border-none bg-transparent px-0 text-lg font-semibold focus-visible:ring-0"
                    />
                    <Badge variant={isPublished ? "default" : "secondary"} className={isPublished ? "bg-teal-500" : ""}>
                        {isPublished ? "Published" : "Draft"}
                    </Badge>
                </div>
                <div className="flex items-center gap-3">
                    <Button variant="outline" size="sm" onClick={handleSave} disabled={isSaving || isPublishing}>
                        {isSaving && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                        Save Draft
                    </Button>
                    <Button size="sm" onClick={handlePublish} disabled={isSaving || isPublishing}>
                        {isPublishing && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                        Publish
                    </Button>
                </div>
            </div>

            <div className="grid gap-6 p-6 lg:grid-cols-[1fr_320px]">
                <div className="space-y-6">
                    <Card>
                        <CardHeader>
                            <CardTitle>Template Details</CardTitle>
                            <CardDescription>Define name, category, and icon for the template.</CardDescription>
                        </CardHeader>
                        <CardContent className="grid gap-4 md:grid-cols-2">
                            <div className="space-y-2 md:col-span-2">
                                <Label>Description</Label>
                                <Textarea
                                    value={description}
                                    onChange={(event) => setDescription(event.target.value)}
                                    placeholder="Describe what this workflow does"
                                    rows={3}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Category (optional)</Label>
                                <Input
                                    value={category}
                                    onChange={(event) => setCategory(event.target.value)}
                                    placeholder="onboarding"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Icon (optional)</Label>
                                <Select value={icon} onValueChange={(value) => value && setIcon(value)}>
                                    <SelectTrigger>
                                        <SelectValue placeholder="Select icon" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {ICON_OPTIONS.map((iconKey) => (
                                            <SelectItem key={iconKey} value={iconKey}>
                                                {iconKey}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle>Trigger</CardTitle>
                            <CardDescription>Pick a trigger type and configure it.</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div>
                                <Label>Trigger Type *</Label>
                                <Select value={triggerType} onValueChange={(value) => value && setTriggerType(value)}>
                                    <SelectTrigger className="mt-1.5 w-full">
                                        <SelectValue placeholder="Select trigger">
                                            {(value: string | null) => {
                                                if (!value) return "Select trigger"
                                                const trigger = triggerTypeOptions.find((t) => t.value === value)
                                                return trigger?.label ?? value
                                            }}
                                        </SelectValue>
                                    </SelectTrigger>
                                    <SelectContent className="min-w-[320px]">
                                        {triggerTypeOptions.map((trigger) => (
                                            <SelectItem key={trigger.value} value={trigger.value}>
                                                {trigger.label}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>

                            {triggerType === "status_changed" && (
                                <div className="grid gap-4 md:grid-cols-2">
                                    <div>
                                        <Label>To Stage *</Label>
                                        <Select
                                            value={typeof triggerConfig.to_stage_id === "string" ? triggerConfig.to_stage_id : ""}
                                            onValueChange={(value) => value && setTriggerConfig({ ...triggerConfig, to_stage_id: value })}
                                        >
                                            <SelectTrigger className="mt-1.5">
                                                <SelectValue placeholder="Select stage" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {stageIdOptions.map((stage) => (
                                                    <SelectItem key={stage.value} value={stage.value}>
                                                        {stage.label}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div>
                                        <Label>From Stage (Optional)</Label>
                                        <Select
                                            value={typeof triggerConfig.from_stage_id === "string" ? triggerConfig.from_stage_id : ""}
                                            onValueChange={(value) => setTriggerConfig({ ...triggerConfig, from_stage_id: value })}
                                        >
                                            <SelectTrigger className="mt-1.5">
                                                <SelectValue placeholder="Any stage" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="">Any stage</SelectItem>
                                                {stageIdOptions.map((stage) => (
                                                    <SelectItem key={stage.value} value={stage.value}>
                                                        {stage.label}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                </div>
                            )}

                            {triggerType === "scheduled" && (
                                <div className="grid gap-4 md:grid-cols-2">
                                    <div>
                                        <Label>Cron Schedule *</Label>
                                        <Input
                                            placeholder="0 9 * * 1"
                                            className="mt-1.5"
                                            value={typeof triggerConfig.cron === "string" ? triggerConfig.cron : ""}
                                            onChange={(event) => setTriggerConfig({ ...triggerConfig, cron: event.target.value })}
                                        />
                                    </div>
                                    <div>
                                        <Label>Timezone</Label>
                                        <Input
                                            placeholder="America/Los_Angeles"
                                            className="mt-1.5"
                                            value={typeof triggerConfig.timezone === "string" ? triggerConfig.timezone : "America/Los_Angeles"}
                                            onChange={(event) => setTriggerConfig({ ...triggerConfig, timezone: event.target.value })}
                                        />
                                    </div>
                                </div>
                            )}

                            {triggerType === "inactivity" && (
                                <div>
                                    <Label>Days Inactive *</Label>
                                    <Input
                                        type="number"
                                        min={1}
                                        max={90}
                                        className="mt-1.5"
                                        value={typeof triggerConfig.days === "number" ? triggerConfig.days : 7}
                                        onChange={(event) => setTriggerConfig({ ...triggerConfig, days: Number(event.target.value) })}
                                    />
                                </div>
                            )}

                            {triggerType === "task_due" && (
                                <div>
                                    <Label>Hours Before Due *</Label>
                                    <Input
                                        type="number"
                                        min={1}
                                        max={168}
                                        className="mt-1.5"
                                        value={typeof triggerConfig.hours_before === "number" ? triggerConfig.hours_before : 24}
                                        onChange={(event) => setTriggerConfig({ ...triggerConfig, hours_before: Number(event.target.value) })}
                                    />
                                </div>
                            )}

                            {triggerType === "surrogate_updated" && (
                                <div className="space-y-3">
                                    <Label>Fields to Watch *</Label>
                                    <Select
                                        value=""
                                        onValueChange={(value) => {
                                            if (!value || selectedTriggerFields.includes(value)) return
                                            setTriggerConfig({ ...triggerConfig, fields: [...selectedTriggerFields, value] })
                                        }}
                                    >
                                        <SelectTrigger className="flex-1">
                                            <SelectValue placeholder="Select field to add" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {conditionFields.map((field) => (
                                                <SelectItem key={field} value={field}>
                                                    {conditionFieldLabels[field] || field}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                    {selectedTriggerFields.length > 0 && (
                                        <div className="flex flex-wrap gap-2">
                                            {selectedTriggerFields.map((field) => (
                                                <Badge key={field} variant="secondary" className="gap-1">
                                                    {conditionFieldLabels[field] || field}
                                                    <button
                                                        type="button"
                                                        className="ml-1 text-xs"
                                                        aria-label="Remove field"
                                                        onClick={() =>
                                                            setTriggerConfig({
                                                                ...triggerConfig,
                                                                fields: selectedTriggerFields.filter((f) => f !== field),
                                                            })
                                                        }
                                                    >
                                                        <XIcon className="size-3" />
                                                    </button>
                                                </Badge>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}

                            {triggerType === "surrogate_assigned" && (
                                <div>
                                    <Label>Assigned To (Optional)</Label>
                                    <Select
                                        value={typeof triggerConfig.to_user_id === "string" ? triggerConfig.to_user_id : ""}
                                        onValueChange={(value) => setTriggerConfig({ ...triggerConfig, to_user_id: value || null })}
                                    >
                                        <SelectTrigger className="mt-1.5">
                                            <SelectValue placeholder="Any user" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="">Any user</SelectItem>
                                            {userOptions.map((user) => (
                                                <SelectItem key={user.id} value={user.id}>
                                                    {user.display_name}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle>Conditions</CardTitle>
                            <CardDescription>Optional filters that must be true for the workflow to run.</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="flex items-center justify-between">
                                <Label>Conditions</Label>
                                <Button size="sm" variant="outline" onClick={addCondition}>
                                    <PlusIcon className="mr-1 size-3" />
                                    Add Condition
                                </Button>
                            </div>

                            {conditions.length === 0 ? (
                                <p className="text-sm text-muted-foreground">
                                    No conditions - workflow will run for all matching triggers.
                                </p>
                            ) : (
                                <>
                                    {conditions.map((condition, index) => (
                                        <Card key={`condition-${index}`}>
                                            <CardContent className="space-y-3 p-4">
                                                <div className="flex items-center gap-3">
                                                    <Select
                                                        value={condition.field}
                                                        onValueChange={(value) => value && updateCondition(index, { field: value })}
                                                    >
                                                        <SelectTrigger className="flex-1">
                                                            <SelectValue placeholder="Field">
                                                                {(value: string | null) => {
                                                                    if (!value) return "Field"
                                                                    return conditionFieldLabels[value] || value
                                                                }}
                                                            </SelectValue>
                                                        </SelectTrigger>
                                                        <SelectContent>
                                                            {conditionFields.map((field) => (
                                                                <SelectItem key={field} value={field}>
                                                                    {conditionFieldLabels[field] || field}
                                                                </SelectItem>
                                                            ))}
                                                        </SelectContent>
                                                    </Select>
                                                    <Select
                                                        value={condition.operator}
                                                        onValueChange={(value) => value && updateCondition(index, { operator: value })}
                                                    >
                                                        <SelectTrigger className="w-36">
                                                            <SelectValue placeholder="Operator">
                                                                {(value: string | null) => {
                                                                    if (!value) return "Operator"
                                                                    const operator = conditionOperators.find((o) => o.value === value)
                                                                    return operator?.label ?? value
                                                                }}
                                                            </SelectValue>
                                                        </SelectTrigger>
                                                        <SelectContent>
                                                            {conditionOperators.map((operator) => (
                                                                <SelectItem key={operator.value} value={operator.value}>
                                                                    {operator.label}
                                                                </SelectItem>
                                                            ))}
                                                        </SelectContent>
                                                    </Select>
                                                    {renderConditionValueInput(condition, index)}
                                                    <Button
                                                        size="icon"
                                                        variant="ghost"
                                                        aria-label="Remove condition"
                                                        onClick={() => removeCondition(index)}
                                                    >
                                                        <XIcon className="size-4" />
                                                    </Button>
                                                </div>
                                            </CardContent>
                                        </Card>
                                    ))}
                                    {conditions.length > 1 && (
                                        <div className="flex justify-center">
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={() => setConditionLogic(conditionLogic === "AND" ? "OR" : "AND")}
                                            >
                                                {conditionLogic}
                                            </Button>
                                        </div>
                                    )}
                                </>
                            )}
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle>Actions</CardTitle>
                            <CardDescription>Define what happens when the trigger and conditions are met.</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="flex items-center justify-between">
                                <Label>Actions *</Label>
                                <Button size="sm" variant="outline" onClick={addAction}>
                                    <PlusIcon className="mr-1 size-3" />
                                    Add Action
                                </Button>
                            </div>

                            {actions.length === 0 ? (
                                <p className="text-sm text-muted-foreground">Add at least one action.</p>
                            ) : (
                                actions.map((action, index) => (
                                    <Card key={`action-${index}`}>
                                        <CardContent className="space-y-3 p-4">
                                            <div className="flex items-center gap-3">
                                                <GripVerticalIcon className="size-4 text-muted-foreground" />
                                                <Select
                                                    value={action.action_type}
                                                    onValueChange={(value) => value && updateAction(index, { action_type: value })}
                                                >
                                                    <SelectTrigger className="flex-1">
                                                        <SelectValue placeholder="Action type">
                                                            {(value: string | null) => {
                                                                if (!value) return "Action type"
                                                                const actionType = actionTypeOptions.find((a) => a.value === value)
                                                                return actionType?.label ?? value
                                                            }}
                                                        </SelectValue>
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                    {filteredActionTypes.map((actionType) => (
                                                        <SelectItem key={actionType.value} value={actionType.value}>
                                                            {actionType.label}
                                                        </SelectItem>
                                                    ))}
                                                    </SelectContent>
                                                </Select>
                                                <Button
                                                    size="icon"
                                                    variant="ghost"
                                                    aria-label="Remove action"
                                                    onClick={() => removeAction(index)}
                                                >
                                                    <XIcon className="size-4" />
                                                </Button>
                                            </div>

                                            {action.action_type === "send_email" && (
                                                <div className="space-y-2">
                                                    <Label>Email Template ID (optional)</Label>
                                                    <Input
                                                        placeholder="Leave blank to force selection in each org"
                                                        value={typeof action.template_id === "string" ? action.template_id : ""}
                                                        onChange={(event) => updateAction(index, { template_id: event.target.value })}
                                                    />
                                                    <p className="text-xs text-muted-foreground">
                                                        Use only if every target org has this template ID.
                                                    </p>
                                                </div>
                                            )}

                                            {action.action_type === "create_task" && (
                                                <div className="space-y-3">
                                                    <div className="space-y-2">
                                                        <Label>Task title *</Label>
                                                        <Input
                                                            placeholder="e.g. Call surrogate to schedule intake"
                                                            value={typeof action.title === "string" ? action.title : ""}
                                                            onChange={(event) => updateAction(index, { title: event.target.value })}
                                                        />
                                                    </div>
                                                    <div className="space-y-2">
                                                        <Label>Description (optional)</Label>
                                                        <Textarea
                                                            placeholder="Add context or steps for the assignee"
                                                            value={typeof action.description === "string" ? action.description : ""}
                                                            onChange={(event) => updateAction(index, { description: event.target.value })}
                                                            rows={2}
                                                        />
                                                    </div>
                                                    <div className="grid gap-3 md:grid-cols-2">
                                                        <div className="space-y-2">
                                                            <Label>Due in (days)</Label>
                                                            <Input
                                                                type="number"
                                                                min={0}
                                                                max={365}
                                                                placeholder="1"
                                                                value={typeof action.due_days === "number" ? action.due_days : 1}
                                                                onChange={(event) =>
                                                                    updateAction(index, { due_days: Number(event.target.value) })
                                                                }
                                                            />
                                                            <p className="text-xs text-muted-foreground">
                                                                0 = due today.
                                                            </p>
                                                        </div>
                                                        <div className="space-y-2">
                                                            <Label>Assignee</Label>
                                                            <Select
                                                                value={typeof action.assignee === "string" ? action.assignee : "owner"}
                                                                onValueChange={(value) => value && updateAction(index, { assignee: value })}
                                                            >
                                                                <SelectTrigger>
                                                                    <SelectValue placeholder="Assignee" />
                                                                </SelectTrigger>
                                                                <SelectContent>
                                                                    <SelectItem value="owner">Case Owner</SelectItem>
                                                                    <SelectItem value="creator">Creator</SelectItem>
                                                                    <SelectItem value="admin">Admin</SelectItem>
                                                                    {userOptions.map((user) => (
                                                                        <SelectItem key={user.id} value={user.id}>
                                                                            {user.display_name}
                                                                        </SelectItem>
                                                                    ))}
                                                                </SelectContent>
                                                            </Select>
                                                        </div>
                                                    </div>
                                                </div>
                                            )}

                                            {action.action_type === "send_notification" && (
                                                <div className="space-y-3">
                                                    <div className="space-y-2">
                                                        <Label>Notification title *</Label>
                                                        <Input
                                                            placeholder="e.g. Follow up required"
                                                            value={typeof action.title === "string" ? action.title : ""}
                                                            onChange={(event) => updateAction(index, { title: event.target.value })}
                                                        />
                                                    </div>
                                                    <div className="space-y-2">
                                                        <Label>Message (optional)</Label>
                                                        <Textarea
                                                            placeholder="Add extra details for the recipient"
                                                            value={typeof action.body === "string" ? action.body : ""}
                                                            onChange={(event) => updateAction(index, { body: event.target.value })}
                                                            rows={2}
                                                        />
                                                    </div>
                                                    <div className="space-y-2">
                                                        <Label>Recipients *</Label>
                                                        <Select
                                                            value={
                                                                Array.isArray(action.recipients)
                                                                    ? action.recipients[0] ?? "owner"
                                                                    : typeof action.recipients === "string"
                                                                        ? action.recipients
                                                                        : "owner"
                                                            }
                                                            onValueChange={(value) => {
                                                                if (!value) return
                                                                if (value === "owner" || value === "creator" || value === "all_admins") {
                                                                    updateAction(index, { recipients: value })
                                                                    return
                                                                }
                                                                updateAction(index, { recipients: [value] })
                                                            }}
                                                        >
                                                            <SelectTrigger>
                                                                <SelectValue placeholder="Select recipients" />
                                                            </SelectTrigger>
                                                            <SelectContent>
                                                                <SelectItem value="owner">Owner</SelectItem>
                                                                <SelectItem value="creator">Creator</SelectItem>
                                                                <SelectItem value="all_admins">All Admins</SelectItem>
                                                                {userOptions.map((user) => (
                                                                    <SelectItem key={user.id} value={user.id}>
                                                                        {user.display_name}
                                                                    </SelectItem>
                                                                ))}
                                                            </SelectContent>
                                                        </Select>
                                                        <p className="text-xs text-muted-foreground">
                                                            Choose a role or a specific user in each org.
                                                        </p>
                                                    </div>
                                                </div>
                                            )}

                                            {action.action_type === "assign_surrogate" && (
                                                <div className="space-y-3">
                                                    <div className="space-y-2">
                                                        <Label>Owner type *</Label>
                                                        <Select
                                                            value={typeof action.owner_type === "string" ? action.owner_type : "user"}
                                                            onValueChange={(value) =>
                                                                updateAction(index, { owner_type: value, owner_id: "" })
                                                            }
                                                        >
                                                            <SelectTrigger>
                                                                <SelectValue placeholder="Owner type" />
                                                            </SelectTrigger>
                                                            <SelectContent>
                                                                {OWNER_TYPE_OPTIONS.map((option) => (
                                                                    <SelectItem key={option.value} value={option.value}>
                                                                        {option.label}
                                                                    </SelectItem>
                                                                ))}
                                                            </SelectContent>
                                                        </Select>
                                                    </div>
                                                    <div className="space-y-2">
                                                        <Label>Owner *</Label>
                                                        <Select
                                                            value={typeof action.owner_id === "string" ? action.owner_id : ""}
                                                            onValueChange={(value) => value && updateAction(index, { owner_id: value })}
                                                        >
                                                            <SelectTrigger>
                                                                <SelectValue placeholder="Select owner" />
                                                            </SelectTrigger>
                                                            <SelectContent>
                                                                {(action.owner_type === "queue" ? queueOptions : userOptions).map((owner) => (
                                                                    <SelectItem key={owner.id} value={owner.id}>
                                                                        {"name" in owner ? owner.name : owner.display_name}
                                                                    </SelectItem>
                                                                ))}
                                                            </SelectContent>
                                                        </Select>
                                                        <p className="text-xs text-muted-foreground">
                                                            Assigning a specific user should target selected orgs only.
                                                        </p>
                                                    </div>
                                                </div>
                                            )}

                                            {action.action_type === "update_field" && (
                                                <div className="space-y-3">
                                                    <div className="space-y-2">
                                                        <Label>Field *</Label>
                                                        <Select
                                                            value={typeof action.field === "string" ? action.field : ""}
                                                            onValueChange={(value) =>
                                                                value && updateAction(index, { field: value, value: "" })
                                                            }
                                                        >
                                                            <SelectTrigger>
                                                                <SelectValue placeholder="Select field" />
                                                            </SelectTrigger>
                                                            <SelectContent>
                                                                {updateFields.map((field) => (
                                                                    <SelectItem key={field} value={field}>
                                                                        {conditionFieldLabels[field] || field}
                                                                    </SelectItem>
                                                                ))}
                                                            </SelectContent>
                                                        </Select>
                                                    </div>
                                                    {action.field === "stage_id" ? (
                                                        <div className="space-y-2">
                                                            <Label>Value *</Label>
                                                            <Select
                                                                value={typeof action.value === "string" ? action.value : ""}
                                                                onValueChange={(value) => value && updateAction(index, { value })}
                                                            >
                                                                <SelectTrigger>
                                                                    <SelectValue placeholder="Select stage" />
                                                                </SelectTrigger>
                                                                <SelectContent>
                                                                    {stageIdOptions.map((stage) => (
                                                                        <SelectItem key={stage.value} value={stage.value}>
                                                                            {stage.label}
                                                                        </SelectItem>
                                                                    ))}
                                                                </SelectContent>
                                                            </Select>
                                                        </div>
                                                    ) : action.field === "is_priority" ? (
                                                        <div className="space-y-2">
                                                            <Label>Value *</Label>
                                                            <Select
                                                                value={typeof action.value === "boolean" ? String(action.value) : ""}
                                                                onValueChange={(value) =>
                                                                    updateAction(index, { value: value === "true" })
                                                                }
                                                            >
                                                                <SelectTrigger>
                                                                    <SelectValue placeholder="Select priority" />
                                                                </SelectTrigger>
                                                                <SelectContent>
                                                                    <SelectItem value="true">Priority</SelectItem>
                                                                    <SelectItem value="false">Normal</SelectItem>
                                                                </SelectContent>
                                                            </Select>
                                                        </div>
                                                    ) : action.field === "owner_type" ? (
                                                        <div className="space-y-2">
                                                            <Label>Value *</Label>
                                                            <Select
                                                                value={typeof action.value === "string" ? action.value : ""}
                                                                onValueChange={(value) => value && updateAction(index, { value })}
                                                            >
                                                                <SelectTrigger>
                                                                    <SelectValue placeholder="Select owner type" />
                                                                </SelectTrigger>
                                                                <SelectContent>
                                                                    {OWNER_TYPE_OPTIONS.map((option) => (
                                                                        <SelectItem key={option.value} value={option.value}>
                                                                            {option.label}
                                                                        </SelectItem>
                                                                    ))}
                                                                </SelectContent>
                                                            </Select>
                                                        </div>
                                                    ) : action.field === "owner_id" ? (
                                                        <div className="space-y-2">
                                                            <Label>Value *</Label>
                                                            <Select
                                                                value={typeof action.value === "string" ? action.value : ""}
                                                                onValueChange={(value) => value && updateAction(index, { value })}
                                                            >
                                                                <SelectTrigger>
                                                                    <SelectValue placeholder="Select owner" />
                                                                </SelectTrigger>
                                                                <SelectContent>
                                                                    {userOptions.map((user) => (
                                                                        <SelectItem key={user.id} value={user.id}>
                                                                            {user.display_name}
                                                                        </SelectItem>
                                                                    ))}
                                                                    {queueOptions.map((queue) => (
                                                                        <SelectItem key={queue.id} value={queue.id}>
                                                                            {queue.name}
                                                                        </SelectItem>
                                                                    ))}
                                                                </SelectContent>
                                                            </Select>
                                                            <p className="text-xs text-muted-foreground">
                                                                Owner IDs are org-specific.
                                                            </p>
                                                        </div>
                                                    ) : (
                                                        <div className="space-y-2">
                                                            <Label>Value *</Label>
                                                            <Input
                                                                placeholder="Value"
                                                                value={typeof action.value === "string" ? action.value : ""}
                                                                onChange={(event) => updateAction(index, { value: event.target.value })}
                                                            />
                                                        </div>
                                                    )}
                                                </div>
                                            )}

                                            {action.action_type === "add_note" && (
                                                <div className="space-y-2">
                                                    <Label>Note content *</Label>
                                                    <Textarea
                                                        placeholder="What should be logged in the case notes?"
                                                        value={typeof action.content === "string" ? action.content : ""}
                                                        onChange={(event) => updateAction(index, { content: event.target.value })}
                                                        rows={2}
                                                    />
                                                </div>
                                            )}

                                            {action.action_type && (
                                                <div className="flex items-center justify-between pt-2 border-t mt-2">
                                                    <div className="flex flex-col">
                                                        <Label className="text-sm font-medium">
                                                            Requires Approval
                                                        </Label>
                                                        <span className="text-xs text-muted-foreground">
                                                            Surrogate owner must approve before this action runs
                                                        </span>
                                                    </div>
                                                    <Switch
                                                        checked={!!action.requires_approval}
                                                        onCheckedChange={(checked) => updateAction(index, { requires_approval: checked })}
                                                    />
                                                </div>
                                            )}
                                        </CardContent>
                                    </Card>
                                ))
                            )}
                        </CardContent>
                    </Card>
                </div>

                <div className="space-y-4">
                    <Card>
                        <CardHeader>
                            <CardTitle>Workflow Summary</CardTitle>
                            <CardDescription>Snapshot of current configuration.</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-3 text-sm">
                            {workflowValidationError && (
                                <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                                    {workflowValidationError}
                                </div>
                            )}
                            <div className="flex items-center justify-between">
                                <span className="text-muted-foreground">Trigger</span>
                                <Badge variant="secondary">{triggerLabels[triggerType] || triggerType || "—"}</Badge>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-muted-foreground">Conditions</span>
                                <span>{conditions.length}</span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-muted-foreground">Actions</span>
                                <span>{actions.length}</span>
                            </div>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle>Hints</CardTitle>
                            <CardDescription>Template best practices.</CardDescription>
                        </CardHeader>
                        <CardContent className="text-sm text-muted-foreground space-y-2">
                            <p>Use org-safe defaults (owner/creator/admin) when targeting all orgs.</p>
                            <p>Leave email template IDs blank to force selection when used.</p>
                            <p>Assign actions with org-specific users should be published to selected orgs only.</p>
                        </CardContent>
                    </Card>
                </div>
            </div>

            <PublishDialog
                open={showPublishDialog}
                onOpenChange={setShowPublishDialog}
                onPublish={confirmPublish}
                isLoading={isPublishing}
                defaultPublishAll={templateData?.is_published_globally ?? true}
                initialOrgIds={templateData?.target_org_ids ?? []}
            />
        </div>
    )
}
