"use client"

import { useCallback, useEffect, useMemo, useReducer, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
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
import { useWorkflowOptions } from "@/lib/hooks/use-workflows"
import {
    useCreatePlatformWorkflowTemplate,
    useDeletePlatformWorkflowTemplate,
    usePlatformWorkflowTemplate,
    usePublishPlatformWorkflowTemplate,
    useUpdatePlatformWorkflowTemplate,
} from "@/lib/hooks/use-platform-templates"
import type { PlatformWorkflowTemplate } from "@/lib/api/platform"
import type { ActionConfig, Condition } from "@/lib/api/workflows"
import type { JsonObject, JsonValue } from "@/lib/types/json"
import { PublishDialog } from "@/components/ops/templates/PublishDialog"
import { getSurrogateFieldLabel } from "@/lib/constants/surrogate-field-labels"
import { US_STATES } from "@/lib/constants/us-states"
import {
    ArrowLeftIcon,
    Loader2Icon,
    PlusIcon,
    Trash2Icon,
    XIcon,
    GripVerticalIcon,
} from "lucide-react"
import { toast } from "sonner"
import {
    areJsonObjectsEqual,
    ConditionValueInput,
    EMAIL_RECIPIENT_OPTIONS,
    FORM_MATCH_STATUS_OPTIONS,
    FORM_SOURCE_MODE_OPTIONS,
    LIST_OPERATORS,
    MULTISELECT_FIELDS,
    OWNER_TYPE_OPTIONS,
    SOURCE_OPTIONS,
    VALUELESS_OPERATORS,
    createClientRowId,
    getEmailRecipientKind,
    getEmailRecipientUserId,
    normalizeEditableActionsForUi as normalizeActionsForUi,
    normalizeEditableConditionsForSave as normalizeConditionsForSave,
    normalizeEditableConditionsForUi as normalizeConditionsForUi,
    toListArray,
    type EditableAction,
    type EditableCondition,
    type SelectOption,
} from "@/components/automation/workflow-editor/shared"

const triggerLabels: Record<string, string> = {
    surrogate_created: "Surrogate Created",
    status_changed: "Status Changed",
    surrogate_assigned: "Surrogate Assigned",
    surrogate_updated: "Field Updated",
    form_started: "Form Started",
    form_submitted: "Application Submitted",
    intake_lead_created: "Intake Lead Created",
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
const ICON_LABELS: Record<string, string> = {
    template: "Template",
    mail: "Mail",
    clock: "Clock",
    bell: "Bell",
    activity: "Activity",
    "alert-circle": "Alert Circle",
}

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
    form_id: "Form",
    created_at: "Created At",
    source_mode: "Submission Source",
    match_status: "Match Status",
    date_of_birth: "Date of Birth",
    age: "Age",
    bmi: "BMI",
    height_ft: "Height (ft)",
    weight_lb: "Weight (lb)",
    journey_timing_preference: "Journey Timing",
    num_deliveries: "Deliveries",
    num_csections: "C-Sections",
    race: "Race",
    meta_lead_id: "Meta Lead ID",
    meta_ad_external_id: "Meta Ad External ID",
    meta_form_id: "Meta Form ID",
}

function getConditionFieldLabel(value: string): string {
    return getSurrogateFieldLabel(value) ?? conditionFieldLabels[value] ?? "Unknown field"
}

const FALLBACK_TRIGGER_TYPES = [
    { value: "surrogate_created", label: "Surrogate Created", description: "When a new case is created" },
    { value: "status_changed", label: "Status Changed", description: "When case status changes" },
    { value: "surrogate_assigned", label: "Surrogate Assigned", description: "When case is assigned" },
    { value: "surrogate_updated", label: "Surrogate Updated", description: "When specific fields change" },
    { value: "form_started", label: "Form Started", description: "When a form draft is started" },
    { value: "form_submitted", label: "Application Submitted", description: "When a form is submitted" },
    { value: "intake_lead_created", label: "Intake Lead Created", description: "When a lead is created from shared intake" },
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
    {
        value: "send_zapier_conversion_event",
        label: "Send Zapier Conversion Event",
        description: "Queue outbound Zapier conversion event for mapped critical stages",
    },
    { value: "update_field", label: "Update Field", description: "Update a case field" },
    { value: "add_note", label: "Add Note", description: "Add a note to the case" },
    { value: "promote_intake_lead", label: "Promote Intake Lead", description: "Promote lead into surrogate case" },
    { value: "auto_match_submission", label: "Auto-Match Submission", description: "Deterministically match submission" },
    { value: "create_intake_lead", label: "Create Intake Lead", description: "Create lead for unmatched submission" },
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

const ZAPIER_CONVERSION_SAMPLE = {
    name: "Meta Conversion Stage Sync (Zapier)",
    description:
        "Queues outbound Zapier stage events for critical conversion buckets based on integration mapping.",
    icon: "activity",
    category: "integrations",
    trigger_type: "status_changed",
    trigger_config: {},
    conditions: [] as Condition[],
    condition_logic: "AND" as const,
    actions: [{ action_type: "send_zapier_conversion_event" }] as ActionConfig[],
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

type WorkflowTemplateEditorState = {
    name: string
    description: string
    icon: string
    category: string
    triggerType: string
    triggerConfig: JsonObject
    conditions: EditableCondition[]
    conditionLogic: "AND" | "OR"
    actions: EditableAction[]
    isPublished: boolean
}

type WorkflowTemplateEditorAction =
    | { type: "hydrateDraft"; templateData: PlatformWorkflowTemplate; statusOptions: { id?: string; value: string; label: string }[] }
    | { type: "loadZapierSample" }
    | { type: "loadSharedIntakeSample" }
    | { type: "setName"; value: string }
    | { type: "setDescription"; value: string }
    | { type: "setIcon"; value: string }
    | { type: "setCategory"; value: string }
    | { type: "setTriggerType"; value: string }
    | { type: "setTriggerConfig"; value: JsonObject }
    | { type: "setConditionLogic"; value: "AND" | "OR" }
    | { type: "setIsPublished"; value: boolean }
    | { type: "addCondition" }
    | { type: "removeCondition"; index: number }
    | { type: "updateCondition"; index: number; updates: Partial<Condition> }
    | { type: "addAction" }
    | { type: "removeAction"; index: number }
    | { type: "updateAction"; index: number; updates: Partial<ActionConfig> }

function createInitialWorkflowTemplateEditorState(): WorkflowTemplateEditorState {
    return {
        name: "",
        description: "",
        icon: "template",
        category: "general",
        triggerType: "",
        triggerConfig: {},
        conditions: [],
        conditionLogic: "AND",
        actions: [],
        isPublished: false,
    }
}

function mergeActionConfig(action: EditableAction, updates: Partial<ActionConfig>): EditableAction {
    const next: EditableAction = { ...action }
    for (const [key, value] of Object.entries(updates)) {
        if (value !== undefined) {
            next[key] = value as JsonValue
        }
    }
    return next
}

function workflowTemplateEditorReducer(
    state: WorkflowTemplateEditorState,
    action: WorkflowTemplateEditorAction
): WorkflowTemplateEditorState {
    switch (action.type) {
        case "hydrateDraft": {
            const draft = action.templateData.draft
            return {
                ...state,
                name: draft.name ?? "",
                description: draft.description ?? "",
                icon: draft.icon ?? "template",
                category: draft.category ?? "general",
                triggerType: draft.trigger_type ?? "",
                triggerConfig: normalizeTriggerConfigForUi(
                    draft.trigger_type ?? "",
                    draft.trigger_config ?? {},
                    action.statusOptions
                ),
                conditions: normalizeConditionsForUi(draft.conditions ?? []),
                conditionLogic: (draft.condition_logic ?? "AND") as "AND" | "OR",
                actions: normalizeActionsForUi(draft.actions ?? []),
                isPublished: (action.templateData.published_version ?? 0) > 0,
            }
        }
        case "loadZapierSample":
            return {
                ...state,
                name: ZAPIER_CONVERSION_SAMPLE.name,
                description: ZAPIER_CONVERSION_SAMPLE.description,
                icon: ZAPIER_CONVERSION_SAMPLE.icon,
                category: ZAPIER_CONVERSION_SAMPLE.category,
                triggerType: ZAPIER_CONVERSION_SAMPLE.trigger_type,
                triggerConfig: ZAPIER_CONVERSION_SAMPLE.trigger_config,
                conditions: normalizeConditionsForUi(ZAPIER_CONVERSION_SAMPLE.conditions),
                conditionLogic: ZAPIER_CONVERSION_SAMPLE.condition_logic,
                actions: normalizeActionsForUi(ZAPIER_CONVERSION_SAMPLE.actions),
            }
        case "loadSharedIntakeSample":
            return {
                ...state,
                name: "Shared Intake Routing: Match Then Lead",
                description:
                    "When a shared application is submitted, auto-match to an existing surrogate first; if no deterministic match exists, create an intake lead.",
                icon: "activity",
                category: "intake",
                triggerType: "form_submitted",
                triggerConfig: {},
                conditions: normalizeConditionsForUi([
                    { field: "source_mode", operator: "equals", value: "shared" },
                ]),
                conditionLogic: "AND",
                actions: normalizeActionsForUi([
                    { action_type: "auto_match_submission" },
                    { action_type: "create_intake_lead", source: "shared_form_workflow" },
                ]),
            }
        case "setName":
            return { ...state, name: action.value }
        case "setDescription":
            return { ...state, description: action.value }
        case "setIcon":
            return { ...state, icon: action.value }
        case "setCategory":
            return { ...state, category: action.value }
        case "setTriggerType":
            return { ...state, triggerType: action.value }
        case "setTriggerConfig":
            return { ...state, triggerConfig: action.value }
        case "setConditionLogic":
            return { ...state, conditionLogic: action.value }
        case "setIsPublished":
            return { ...state, isPublished: action.value }
        case "addCondition":
            return {
                ...state,
                conditions: [
                    ...state.conditions,
                    { clientId: createClientRowId(), field: "", operator: "equals", value: "" },
                ],
            }
        case "removeCondition":
            return {
                ...state,
                conditions: state.conditions.filter((_, index) => index !== action.index),
            }
        case "updateCondition":
            return {
                ...state,
                conditions: state.conditions.map((condition, index) => {
                    if (index !== action.index) return condition
                    const next: EditableCondition = { ...condition, ...action.updates }
                    const fieldChanged =
                        typeof action.updates.field === "string" && action.updates.field !== condition.field
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
                    return next
                }),
            }
        case "addAction":
            return {
                ...state,
                actions: [...state.actions, { clientId: createClientRowId(), action_type: "" }],
            }
        case "removeAction":
            return {
                ...state,
                actions: state.actions.filter((_, index) => index !== action.index),
            }
        case "updateAction":
            return {
                ...state,
                actions: state.actions.map((currentAction, index) =>
                    index === action.index ? mergeActionConfig(currentAction, action.updates) : currentAction
                ),
            }
        default:
            return state
    }
}

type TemplateUserOption = {
    id: string
    display_name: string
}

type TemplateQueueOption = {
    id: string
    name: string
}

type UpdateConditionHandler = (index: number, updates: Partial<Condition>) => void
type UpdateActionHandler = (index: number, updates: Partial<ActionConfig>) => void

type WorkflowTemplateDeleteDialogProps = {
    open: boolean
    onOpenChange: (open: boolean) => void
    onDelete: () => void
    isDeleting: boolean
    name: string
}

function WorkflowTemplateDeleteDialog({
    open,
    onOpenChange,
    onDelete,
    isDeleting,
    name,
}: WorkflowTemplateDeleteDialogProps) {
    return (
        <AlertDialog open={open} onOpenChange={onOpenChange}>
            <AlertDialogContent>
                <AlertDialogHeader>
                    <AlertDialogTitle>Delete template?</AlertDialogTitle>
                    <AlertDialogDescription>
                        This permanently deletes{" "}
                        <span className="font-medium text-foreground">{name || "this template"}</span>. This cannot be undone.
                    </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                    <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
                    <AlertDialogAction
                        onClick={onDelete}
                        disabled={isDeleting}
                        className="bg-destructive text-white hover:bg-destructive/90"
                    >
                        Delete
                    </AlertDialogAction>
                </AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>
    )
}

type WorkflowTemplateHeaderProps = {
    name: string
    setName: (value: string) => void
    isPublished: boolean
    isNew: boolean
    isDeleting: boolean
    isSaving: boolean
    isPublishing: boolean
    onBack: () => void
    onDelete: () => void
    onSave: () => void
    onPublish: () => void
}

function WorkflowTemplateHeader({
    name,
    setName,
    isPublished,
    isNew,
    isDeleting,
    isSaving,
    isPublishing,
    onBack,
    onDelete,
    onSave,
    onPublish,
}: WorkflowTemplateHeaderProps) {
    return (
        <div className="flex h-16 items-center justify-between border-b border-stone-200 bg-white px-6 dark:border-stone-800 dark:bg-stone-900">
            <div className="flex items-center gap-4">
                <Button variant="ghost" size="icon" aria-label="Back to workflow templates" onClick={onBack}>
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
                {!isNew && (
                    <Button
                        variant="destructive"
                        size="sm"
                        onClick={onDelete}
                        disabled={isDeleting || isSaving || isPublishing}
                    >
                        {isDeleting ? <Loader2Icon className="mr-2 size-4 animate-spin" /> : <Trash2Icon className="mr-2 size-4" />}
                        Delete
                    </Button>
                )}
                <Button variant="outline" size="sm" onClick={onSave} disabled={isSaving || isPublishing}>
                    {isSaving && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                    Save Draft
                </Button>
                <Button size="sm" onClick={onPublish} disabled={isSaving || isPublishing}>
                    {isPublishing && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                    Publish
                </Button>
            </div>
        </div>
    )
}

type WorkflowTemplateDetailsSectionProps = {
    description: string
    setDescription: (value: string) => void
    category: string
    setCategory: (value: string) => void
    icon: string
    setIcon: (value: string) => void
    onLoadSharedIntakeSample: () => void
    onLoadZapierSample: () => void
}

function WorkflowTemplateDetailsSection({
    description,
    setDescription,
    category,
    setCategory,
    icon,
    setIcon,
    onLoadSharedIntakeSample,
    onLoadZapierSample,
}: WorkflowTemplateDetailsSectionProps) {
    return (
        <Card>
            <CardHeader>
                <CardTitle>Template Details</CardTitle>
                <CardDescription>Define name, category, and icon for the template.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2">
                <div className="md:col-span-2">
                    <div className="flex flex-wrap gap-2">
                        <Button type="button" variant="outline" size="sm" onClick={onLoadSharedIntakeSample}>
                            Load Shared Intake Sample
                        </Button>
                        <Button type="button" variant="outline" size="sm" onClick={onLoadZapierSample}>
                            Load Zapier Conversion Sample
                        </Button>
                    </div>
                </div>
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
                    <Input value={category} onChange={(event) => setCategory(event.target.value)} placeholder="onboarding" />
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
                                    {ICON_LABELS[iconKey] ?? "Unknown icon"}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
            </CardContent>
        </Card>
    )
}

type WorkflowTemplateStageTriggerFieldsProps = {
    triggerConfig: JsonObject
    setTriggerConfig: (value: JsonObject) => void
    stageIdOptions: SelectOption[]
}

function WorkflowTemplateStageTriggerFields({
    triggerConfig,
    setTriggerConfig,
    stageIdOptions,
}: WorkflowTemplateStageTriggerFieldsProps) {
    return (
        <div className="grid gap-4 md:grid-cols-2">
            <div>
                <Label>To Stage (Optional)</Label>
                <Select
                    value={typeof triggerConfig.to_stage_id === "string" ? triggerConfig.to_stage_id : ""}
                    onValueChange={(value) => setTriggerConfig({ ...triggerConfig, to_stage_id: value })}
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
    )
}

type WorkflowTemplateScheduledTriggerFieldsProps = {
    triggerConfig: JsonObject
    setTriggerConfig: (value: JsonObject) => void
}

function WorkflowTemplateScheduledTriggerFields({
    triggerConfig,
    setTriggerConfig,
}: WorkflowTemplateScheduledTriggerFieldsProps) {
    return (
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
    )
}

type WorkflowTemplateFormTriggerFieldProps = {
    label: string
    placeholder: string
    emptyHint: string
    allowAnyForm: boolean
    formId: string
    formOptions: SelectOption[]
    onChange: (value: string) => void
}

function WorkflowTemplateFormTriggerField({
    label,
    placeholder,
    emptyHint,
    allowAnyForm,
    formId,
    formOptions,
    onChange,
}: WorkflowTemplateFormTriggerFieldProps) {
    return (
        <div>
            <Label>{label}</Label>
            <Select
                value={formId}
                onValueChange={(value) => {
                    if (!value) return
                    onChange(allowAnyForm && value === "__any_form__" ? "" : value)
                }}
            >
                <SelectTrigger className="mt-1.5">
                    <SelectValue placeholder={placeholder}>
                        {(value: string | null) => {
                            if (!value) return placeholder
                            const form = formOptions.find((option) => option.value === value)
                            return form?.label ?? "Unknown form"
                        }}
                    </SelectValue>
                </SelectTrigger>
                <SelectContent>
                    {allowAnyForm && <SelectItem value="__any_form__">{placeholder}</SelectItem>}
                    {formOptions.map((form) => (
                        <SelectItem key={form.value} value={form.value}>
                            {form.label}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
            {formOptions.length === 0 && <p className="mt-2 text-xs text-muted-foreground">{emptyHint}</p>}
        </div>
    )
}

type WorkflowTemplateSurrogateUpdatedTriggerFieldsProps = {
    triggerConfig: JsonObject
    setTriggerConfig: (value: JsonObject) => void
    conditionFields: string[]
}

function WorkflowTemplateSurrogateUpdatedTriggerFields({
    triggerConfig,
    setTriggerConfig,
    conditionFields,
}: WorkflowTemplateSurrogateUpdatedTriggerFieldsProps) {
    const selectedTriggerFields = Array.isArray(triggerConfig.fields)
        ? triggerConfig.fields.filter((field): field is string => typeof field === "string")
        : []

    return (
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
                            {getConditionFieldLabel(field)}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
            {selectedTriggerFields.length > 0 && (
                <div className="flex flex-wrap gap-2">
                    {selectedTriggerFields.map((field) => (
                        <Badge key={field} variant="secondary" className="gap-1">
                            {getConditionFieldLabel(field)}
                            <button
                                type="button"
                                className="ml-1 text-xs"
                                aria-label="Remove field"
                                onClick={() =>
                                    setTriggerConfig({
                                        ...triggerConfig,
                                        fields: selectedTriggerFields.filter((currentField) => currentField !== field),
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
    )
}

type WorkflowTemplateAssignedTriggerFieldsProps = {
    triggerConfig: JsonObject
    setTriggerConfig: (value: JsonObject) => void
    userOptions: TemplateUserOption[]
}

function WorkflowTemplateAssignedTriggerFields({
    triggerConfig,
    setTriggerConfig,
    userOptions,
}: WorkflowTemplateAssignedTriggerFieldsProps) {
    return (
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
    )
}

type WorkflowTemplateTriggerConfigFieldsProps = {
    triggerType: string
    triggerConfig: JsonObject
    setTriggerConfig: (value: JsonObject) => void
    stageIdOptions: SelectOption[]
    formOptions: SelectOption[]
    conditionFields: string[]
    userOptions: TemplateUserOption[]
}

function WorkflowTemplateTriggerConfigFields({
    triggerType,
    triggerConfig,
    setTriggerConfig,
    stageIdOptions,
    formOptions,
    conditionFields,
    userOptions,
}: WorkflowTemplateTriggerConfigFieldsProps) {
    if (triggerType === "status_changed") {
        return (
            <WorkflowTemplateStageTriggerFields
                triggerConfig={triggerConfig}
                setTriggerConfig={setTriggerConfig}
                stageIdOptions={stageIdOptions}
            />
        )
    }

    if (triggerType === "scheduled") {
        return <WorkflowTemplateScheduledTriggerFields triggerConfig={triggerConfig} setTriggerConfig={setTriggerConfig} />
    }

    if (triggerType === "inactivity") {
        return (
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
        )
    }

    if (triggerType === "form_started") {
        return (
            <WorkflowTemplateFormTriggerField
                label="Form *"
                placeholder="Select form"
                emptyHint="Publish a form to use this trigger."
                allowAnyForm={false}
                formId={typeof triggerConfig.form_id === "string" ? triggerConfig.form_id : ""}
                formOptions={formOptions}
                onChange={(value) => value && setTriggerConfig({ ...triggerConfig, form_id: value })}
            />
        )
    }

    if (triggerType === "form_submitted") {
        return (
            <WorkflowTemplateFormTriggerField
                label="Form (optional)"
                placeholder="Any published form"
                emptyHint="Publish a form to use this trigger."
                allowAnyForm
                formId={typeof triggerConfig.form_id === "string" ? triggerConfig.form_id : ""}
                formOptions={formOptions}
                onChange={(value) => setTriggerConfig({ ...triggerConfig, form_id: value })}
            />
        )
    }

    if (triggerType === "intake_lead_created") {
        return (
            <WorkflowTemplateFormTriggerField
                label="Form (optional)"
                placeholder="Any published form"
                emptyHint="Leave blank to apply to all forms in target orgs."
                allowAnyForm
                formId={typeof triggerConfig.form_id === "string" ? triggerConfig.form_id : ""}
                formOptions={formOptions}
                onChange={(value) => setTriggerConfig({ ...triggerConfig, form_id: value })}
            />
        )
    }

    if (triggerType === "task_due") {
        return (
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
        )
    }

    if (triggerType === "surrogate_updated") {
        return (
            <WorkflowTemplateSurrogateUpdatedTriggerFields
                triggerConfig={triggerConfig}
                setTriggerConfig={setTriggerConfig}
                conditionFields={conditionFields}
            />
        )
    }

    if (triggerType === "surrogate_assigned") {
        return (
            <WorkflowTemplateAssignedTriggerFields
                triggerConfig={triggerConfig}
                setTriggerConfig={setTriggerConfig}
                userOptions={userOptions}
            />
        )
    }

    return null
}

type WorkflowTemplateTriggerSectionProps = {
    triggerType: string
    setTriggerType: (value: string) => void
    triggerTypeOptions: SelectOption[]
    triggerConfig: JsonObject
    setTriggerConfig: (value: JsonObject) => void
    stageIdOptions: SelectOption[]
    formOptions: SelectOption[]
    conditionFields: string[]
    userOptions: TemplateUserOption[]
}

function WorkflowTemplateTriggerSection({
    triggerType,
    setTriggerType,
    triggerTypeOptions,
    triggerConfig,
    setTriggerConfig,
    stageIdOptions,
    formOptions,
    conditionFields,
    userOptions,
}: WorkflowTemplateTriggerSectionProps) {
    return (
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
                                    const trigger = triggerTypeOptions.find((option) => option.value === value)
                                    return trigger?.label ?? triggerLabels[value] ?? "Unknown trigger"
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

                <WorkflowTemplateTriggerConfigFields
                    triggerType={triggerType}
                    triggerConfig={triggerConfig}
                    setTriggerConfig={setTriggerConfig}
                    stageIdOptions={stageIdOptions}
                    formOptions={formOptions}
                    conditionFields={conditionFields}
                    userOptions={userOptions}
                />
            </CardContent>
        </Card>
    )
}

type WorkflowTemplateConditionRowProps = {
    condition: EditableCondition
    index: number
    conditionOperators: SelectOption[]
    conditionFields: string[]
    getConditionOptions: (field: string) => SelectOption[] | null
    updateCondition: UpdateConditionHandler
    removeCondition: (index: number) => void
}

function WorkflowTemplateConditionRow({
    condition,
    index,
    conditionOperators,
    conditionFields,
    getConditionOptions,
    updateCondition,
    removeCondition,
}: WorkflowTemplateConditionRowProps) {
    return (
        <Card>
            <CardContent className="space-y-3 p-4">
                <div className="flex items-center gap-3">
                    <Select value={condition.field} onValueChange={(value) => value && updateCondition(index, { field: value })}>
                        <SelectTrigger className="flex-1">
                            <SelectValue placeholder="Field">
                                {(value: string | null) => (value ? getConditionFieldLabel(value) : "Field")}
                            </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                            {conditionFields.map((field) => (
                                <SelectItem key={field} value={field}>
                                    {getConditionFieldLabel(field)}
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
                                    const operator = conditionOperators.find((option) => option.value === value)
                                    return operator?.label ?? "Unknown operator"
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
                    <ConditionValueInput
                        condition={condition}
                        options={getConditionOptions(condition.field)}
                        onChange={(value) => updateCondition(index, { value })}
                    />
                    <Button size="icon" variant="ghost" aria-label="Remove condition" onClick={() => removeCondition(index)}>
                        <XIcon className="size-4" />
                    </Button>
                </div>
            </CardContent>
        </Card>
    )
}

type WorkflowTemplateConditionsSectionProps = {
    conditions: EditableCondition[]
    conditionOperators: SelectOption[]
    conditionFields: string[]
    conditionLogic: "AND" | "OR"
    setConditionLogic: (value: "AND" | "OR") => void
    getConditionOptions: (field: string) => SelectOption[] | null
    addCondition: () => void
    updateCondition: UpdateConditionHandler
    removeCondition: (index: number) => void
}

function WorkflowTemplateConditionsSection({
    conditions,
    conditionOperators,
    conditionFields,
    conditionLogic,
    setConditionLogic,
    getConditionOptions,
    addCondition,
    updateCondition,
    removeCondition,
}: WorkflowTemplateConditionsSectionProps) {
    return (
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
                    <p className="text-sm text-muted-foreground">No conditions - workflow will run for all matching triggers.</p>
                ) : (
                    <>
                        {conditions.map((condition, index) => (
                            <WorkflowTemplateConditionRow
                                key={condition.clientId}
                                condition={condition}
                                index={index}
                                conditionOperators={conditionOperators}
                                conditionFields={conditionFields}
                                getConditionOptions={getConditionOptions}
                                updateCondition={updateCondition}
                                removeCondition={removeCondition}
                            />
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
    )
}

type WorkflowTemplateSendEmailFieldsProps = {
    action: EditableAction
    index: number
    updateAction: UpdateActionHandler
    userOptions: TemplateUserOption[]
}

function WorkflowTemplateSendEmailFields({
    action,
    index,
    updateAction,
    userOptions,
}: WorkflowTemplateSendEmailFieldsProps) {
    return (
        <div className="space-y-3">
            <div className="space-y-2">
                <Label>Email Template ID (optional)</Label>
                <Input
                    placeholder="Leave blank to force selection in each org"
                    value={typeof action.template_id === "string" ? action.template_id : ""}
                    onChange={(event) => updateAction(index, { template_id: event.target.value })}
                />
                <p className="text-xs text-muted-foreground">Use only if every target org has this template ID.</p>
            </div>
            <div className="space-y-2">
                <Label>Recipient</Label>
                <Select
                    value={getEmailRecipientKind(action)}
                    onValueChange={(value) => {
                        if (value === "user") {
                            const currentUser = getEmailRecipientUserId(action)
                            updateAction(index, { recipients: currentUser ? [currentUser] : [] })
                            return
                        }
                        updateAction(index, { recipients: value })
                    }}
                >
                    <SelectTrigger>
                        <SelectValue placeholder="Select recipient" />
                    </SelectTrigger>
                    <SelectContent>
                        {EMAIL_RECIPIENT_OPTIONS.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                                {option.label}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>
            {getEmailRecipientKind(action) === "user" && (
                <Select
                    value={getEmailRecipientUserId(action)}
                    onValueChange={(value) => updateAction(index, { recipients: value ? [value] : [] })}
                >
                    <SelectTrigger>
                        <SelectValue placeholder="Select user">
                            {(value: string | null) => {
                                if (!value) return "Select user"
                                const user = userOptions.find((option) => option.id === value)
                                return user?.display_name ?? "Unknown user"
                            }}
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        {userOptions.map((user) => (
                            <SelectItem key={user.id} value={user.id}>
                                {user.display_name}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            )}
        </div>
    )
}

type WorkflowTemplateCreateTaskFieldsProps = {
    action: EditableAction
    index: number
    updateAction: UpdateActionHandler
    userOptions: TemplateUserOption[]
}

function WorkflowTemplateCreateTaskFields({
    action,
    index,
    updateAction,
    userOptions,
}: WorkflowTemplateCreateTaskFieldsProps) {
    return (
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
                        onChange={(event) => updateAction(index, { due_days: Number(event.target.value) })}
                    />
                    <p className="text-xs text-muted-foreground">0 = due today.</p>
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
    )
}

type WorkflowTemplateSendNotificationFieldsProps = {
    action: EditableAction
    index: number
    updateAction: UpdateActionHandler
    userOptions: TemplateUserOption[]
}

function WorkflowTemplateSendNotificationFields({
    action,
    index,
    updateAction,
    userOptions,
}: WorkflowTemplateSendNotificationFieldsProps) {
    return (
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
                <p className="text-xs text-muted-foreground">Choose a role or a specific user in each org.</p>
            </div>
        </div>
    )
}

type WorkflowTemplateAssignSurrogateFieldsProps = {
    action: EditableAction
    index: number
    updateAction: UpdateActionHandler
    userOptions: TemplateUserOption[]
    queueOptions: TemplateQueueOption[]
}

function WorkflowTemplateAssignSurrogateFields({
    action,
    index,
    updateAction,
    userOptions,
    queueOptions,
}: WorkflowTemplateAssignSurrogateFieldsProps) {
    return (
        <div className="space-y-3">
            <div className="space-y-2">
                <Label>Owner type *</Label>
                <Select
                    value={typeof action.owner_type === "string" ? action.owner_type : "user"}
                    onValueChange={(value) => updateAction(index, { owner_type: value, owner_id: "" })}
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
    )
}

type WorkflowTemplateUpdateFieldFieldsProps = {
    action: EditableAction
    index: number
    updateAction: UpdateActionHandler
    updateFields: string[]
    stageIdOptions: SelectOption[]
    userOptions: TemplateUserOption[]
    queueOptions: TemplateQueueOption[]
}

function WorkflowTemplateUpdateFieldFields({
    action,
    index,
    updateAction,
    updateFields,
    stageIdOptions,
    userOptions,
    queueOptions,
}: WorkflowTemplateUpdateFieldFieldsProps) {
    return (
        <div className="space-y-3">
            <div className="space-y-2">
                <Label>Field *</Label>
                <Select
                    value={typeof action.field === "string" ? action.field : ""}
                    onValueChange={(value) => value && updateAction(index, { field: value, value: "" })}
                >
                    <SelectTrigger>
                        <SelectValue placeholder="Select field" />
                    </SelectTrigger>
                    <SelectContent>
                        {updateFields.map((field) => (
                            <SelectItem key={field} value={field}>
                                {getConditionFieldLabel(field)}
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
                        onValueChange={(value) => updateAction(index, { value: value === "true" })}
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
                    <p className="text-xs text-muted-foreground">Owner IDs are org-specific.</p>
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
    )
}

type WorkflowTemplatePromoteLeadFieldsProps = {
    action: EditableAction
    index: number
    updateAction: UpdateActionHandler
}

function WorkflowTemplatePromoteLeadFields({
    action,
    index,
    updateAction,
}: WorkflowTemplatePromoteLeadFieldsProps) {
    return (
        <div className="space-y-3">
            <Input
                placeholder="Source (optional)"
                value={typeof action.source === "string" ? action.source : ""}
                onChange={(event) => updateAction(index, { source: event.target.value })}
            />
            <div className="flex items-center justify-between rounded-md border p-3">
                <div className="text-sm">Mark as priority</div>
                <Switch
                    checked={typeof action.is_priority === "boolean" ? action.is_priority : false}
                    onCheckedChange={(checked) => updateAction(index, { is_priority: checked })}
                />
            </div>
            <div className="flex items-center justify-between rounded-md border p-3">
                <div className="text-sm">Assign to workflow owner if available</div>
                <Switch
                    checked={typeof action.assign_to_user === "boolean" ? action.assign_to_user : false}
                    onCheckedChange={(checked) => updateAction(index, { assign_to_user: checked })}
                />
            </div>
        </div>
    )
}

type WorkflowTemplateActionFieldsProps = {
    action: EditableAction
    index: number
    updateAction: UpdateActionHandler
    userOptions: TemplateUserOption[]
    queueOptions: TemplateQueueOption[]
    updateFields: string[]
    stageIdOptions: SelectOption[]
}

function WorkflowTemplateActionFields({
    action,
    index,
    updateAction,
    userOptions,
    queueOptions,
    updateFields,
    stageIdOptions,
}: WorkflowTemplateActionFieldsProps) {
    if (action.action_type === "send_email") {
        return (
            <WorkflowTemplateSendEmailFields
                action={action}
                index={index}
                updateAction={updateAction}
                userOptions={userOptions}
            />
        )
    }

    if (action.action_type === "create_task") {
        return (
            <WorkflowTemplateCreateTaskFields
                action={action}
                index={index}
                updateAction={updateAction}
                userOptions={userOptions}
            />
        )
    }

    if (action.action_type === "send_notification") {
        return (
            <WorkflowTemplateSendNotificationFields
                action={action}
                index={index}
                updateAction={updateAction}
                userOptions={userOptions}
            />
        )
    }

    if (action.action_type === "assign_surrogate") {
        return (
            <WorkflowTemplateAssignSurrogateFields
                action={action}
                index={index}
                updateAction={updateAction}
                userOptions={userOptions}
                queueOptions={queueOptions}
            />
        )
    }

    if (action.action_type === "update_field") {
        return (
            <WorkflowTemplateUpdateFieldFields
                action={action}
                index={index}
                updateAction={updateAction}
                updateFields={updateFields}
                stageIdOptions={stageIdOptions}
                userOptions={userOptions}
                queueOptions={queueOptions}
            />
        )
    }

    if (action.action_type === "add_note") {
        return (
            <div className="space-y-2">
                <Label>Note content *</Label>
                <Textarea
                    placeholder="What should be logged in the case notes?"
                    value={typeof action.content === "string" ? action.content : ""}
                    onChange={(event) => updateAction(index, { content: event.target.value })}
                    rows={2}
                />
            </div>
        )
    }

    if (action.action_type === "auto_match_submission") {
        return (
            <p className="rounded-md border p-3 text-sm text-muted-foreground">
                Runs deterministic matching using name + DOB + phone/email and updates the submission to linked or ambiguous review.
            </p>
        )
    }

    if (action.action_type === "create_intake_lead") {
        return (
            <div className="space-y-2">
                <Label>Source (optional)</Label>
                <Input
                    placeholder="shared_form_workflow"
                    value={typeof action.source === "string" ? action.source : ""}
                    onChange={(event) => updateAction(index, { source: event.target.value })}
                />
            </div>
        )
    }

    if (action.action_type === "send_zapier_conversion_event") {
        return (
            <p className="rounded-md border p-3 text-sm text-muted-foreground">
                Queues a Zapier outbound stage update when the current stage maps to Qualified, Converted, Lost, or Not Qualified. Skips automatically if outbound integration is disabled.
            </p>
        )
    }

    if (action.action_type === "promote_intake_lead") {
        return <WorkflowTemplatePromoteLeadFields action={action} index={index} updateAction={updateAction} />
    }

    return null
}

type WorkflowTemplateActionCardProps = {
    action: EditableAction
    index: number
    filteredActionTypes: SelectOption[]
    updateAction: UpdateActionHandler
    removeAction: (index: number) => void
    userOptions: TemplateUserOption[]
    queueOptions: TemplateQueueOption[]
    updateFields: string[]
    stageIdOptions: SelectOption[]
}

function WorkflowTemplateActionCard({
    action,
    index,
    filteredActionTypes,
    updateAction,
    removeAction,
    userOptions,
    queueOptions,
    updateFields,
    stageIdOptions,
}: WorkflowTemplateActionCardProps) {
    return (
        <Card>
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
                                    const actionType = filteredActionTypes.find((option) => option.value === value)
                                    return actionType?.label ?? "Unknown action type"
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
                    <Button size="icon" variant="ghost" aria-label="Remove action" onClick={() => removeAction(index)}>
                        <XIcon className="size-4" />
                    </Button>
                </div>

                <WorkflowTemplateActionFields
                    action={action}
                    index={index}
                    updateAction={updateAction}
                    userOptions={userOptions}
                    queueOptions={queueOptions}
                    updateFields={updateFields}
                    stageIdOptions={stageIdOptions}
                />

                {action.action_type && action.action_type !== "promote_intake_lead" && (
                    <div className="mt-2 flex items-center justify-between border-t pt-2">
                        <div className="flex flex-col">
                            <Label className="text-sm font-medium">Requires Approval</Label>
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
    )
}

type WorkflowTemplateActionsSectionProps = {
    actions: EditableAction[]
    filteredActionTypes: SelectOption[]
    addAction: () => void
    updateAction: UpdateActionHandler
    removeAction: (index: number) => void
    userOptions: TemplateUserOption[]
    queueOptions: TemplateQueueOption[]
    updateFields: string[]
    stageIdOptions: SelectOption[]
}

function WorkflowTemplateActionsSection({
    actions,
    filteredActionTypes,
    addAction,
    updateAction,
    removeAction,
    userOptions,
    queueOptions,
    updateFields,
    stageIdOptions,
}: WorkflowTemplateActionsSectionProps) {
    return (
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
                        <WorkflowTemplateActionCard
                            key={action.clientId}
                            action={action}
                            index={index}
                            filteredActionTypes={filteredActionTypes}
                            updateAction={updateAction}
                            removeAction={removeAction}
                            userOptions={userOptions}
                            queueOptions={queueOptions}
                            updateFields={updateFields}
                            stageIdOptions={stageIdOptions}
                        />
                    ))
                )}
            </CardContent>
        </Card>
    )
}

type WorkflowTemplateSidebarProps = {
    workflowValidationError: string | null
    triggerType: string
    conditionsCount: number
    actionsCount: number
}

function WorkflowTemplateSidebar({
    workflowValidationError,
    triggerType,
    conditionsCount,
    actionsCount,
}: WorkflowTemplateSidebarProps) {
    return (
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
                        <span>{conditionsCount}</span>
                    </div>
                    <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">Actions</span>
                        <span>{actionsCount}</span>
                    </div>
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Hints</CardTitle>
                    <CardDescription>Template best practices.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-2 text-sm text-muted-foreground">
                    <p>Use org-safe defaults (owner/creator/admin) when targeting all orgs.</p>
                    <p>Leave email template IDs blank to force selection when used.</p>
                    <p>Assign actions with org-specific users should be published to selected orgs only.</p>
                </CardContent>
            </Card>
        </div>
    )
}

function useWorkflowTemplatePageState() {
    const router = useRouter()
    const params = useParams()
    const id = params?.id as string
    const isNew = id === "new"
    const templateId = isNew ? null : id

    const { data: templateData, isLoading } = usePlatformWorkflowTemplate(templateId)
    const createTemplate = useCreatePlatformWorkflowTemplate()
    const updateTemplate = useUpdatePlatformWorkflowTemplate()
    const publishTemplate = usePublishPlatformWorkflowTemplate()
    const deleteTemplate = useDeletePlatformWorkflowTemplate()
    const { data: options } = useWorkflowOptions("org")

    const [editorState, dispatchEditor] = useReducer(
        workflowTemplateEditorReducer,
        undefined,
        createInitialWorkflowTemplateEditorState
    )
    const [showPublishDialog, setShowPublishDialog] = useState(false)
    const [showDeleteDialog, setShowDeleteDialog] = useState(false)
    const [isSaving, setIsSaving] = useState(false)
    const [isPublishing, setIsPublishing] = useState(false)

    const {
        name,
        description,
        icon,
        category,
        triggerType,
        triggerConfig,
        conditions,
        conditionLogic,
        actions,
        isPublished,
    } = editorState
    const setName = (value: string) => dispatchEditor({ type: "setName", value })
    const setDescription = (value: string) => dispatchEditor({ type: "setDescription", value })
    const setIcon = (value: string) => dispatchEditor({ type: "setIcon", value })
    const setCategory = (value: string) => dispatchEditor({ type: "setCategory", value })
    const setTriggerType = (value: string) => dispatchEditor({ type: "setTriggerType", value })
    const setTriggerConfig = (value: JsonObject) => dispatchEditor({ type: "setTriggerConfig", value })
    const setConditionLogic = (value: "AND" | "OR") =>
        dispatchEditor({ type: "setConditionLogic", value })
    const setIsPublished = (value: boolean) => dispatchEditor({ type: "setIsPublished", value })

    const statusOptions = useMemo(() => options?.statuses ?? [], [options?.statuses])
    const actionTypeOptions = options?.action_types ?? FALLBACK_ACTION_TYPES
    const triggerTypeOptions = options?.trigger_types ?? FALLBACK_TRIGGER_TYPES
    const updateFields = options?.update_fields ?? ["stage_id", "is_priority", "owner_type", "owner_id"]
    const conditionOperators = options?.condition_operators ?? FALLBACK_OPERATORS
    const conditionFields = options?.condition_fields ?? Object.keys(conditionFieldLabels)
    const userOptions = useMemo(() => options?.users ?? [], [options?.users])
    const queueOptions = useMemo(() => options?.queues ?? [], [options?.queues])
    const formOptions = useMemo<SelectOption[]>(
        () => (options?.forms ?? []).map((form) => ({ value: form.id, label: form.name })),
        [options?.forms],
    )

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

    const applyZapierConversionSample = () => {
        dispatchEditor({ type: "loadZapierSample" })
        toast.success("Loaded Zapier conversion sample workflow")
    }

    useEffect(() => {
        if (!templateData || isNew) return
        dispatchEditor({ type: "hydrateDraft", templateData, statusOptions })
    }, [templateData, isNew, statusOptions])

    useEffect(() => {
        if (!triggerType) return
        const next = { ...triggerConfig }
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
        if (triggerType === "form_started") {
            if (typeof next.form_id !== "string") next.form_id = ""
        }
        if (triggerType === "form_submitted") {
            if (typeof next.form_id !== "string") next.form_id = ""
        }
        if (triggerType === "intake_lead_created") {
            if (typeof next.form_id !== "string") next.form_id = ""
        }
        if (areJsonObjectsEqual(next, triggerConfig)) return
        setTriggerConfig(next)
    }, [triggerConfig, triggerType])

    const addCondition = () => {
        dispatchEditor({ type: "addCondition" })
    }

    const removeCondition = (index: number) => {
        dispatchEditor({ type: "removeCondition", index })
    }

    const updateCondition = (index: number, updates: Partial<Condition>) => {
        dispatchEditor({ type: "updateCondition", index, updates })
    }

    const addAction = () => {
        dispatchEditor({ type: "addAction" })
    }

    const removeAction = (index: number) => {
        dispatchEditor({ type: "removeAction", index })
    }

    const updateAction = (index: number, updates: Partial<ActionConfig>) => {
        dispatchEditor({ type: "updateAction", index, updates })
    }

    const applySharedIntakeSample = () => {
        dispatchEditor({ type: "loadSharedIntakeSample" })
        toast.success("Loaded sample workflow template")
    }

    const getConditionOptions = (field: string): SelectOption[] | null => {
        if (field === "stage_id") return stageIdOptions
        if (field === "status_label") return stageLabelOptions
        if (field === "owner_type") return OWNER_TYPE_OPTIONS
        if (field === "owner_id") return ownerOptions
        if (field === "state") return stateOptions
        if (field === "source") return SOURCE_OPTIONS
        if (field === "source_mode") return FORM_SOURCE_MODE_OPTIONS
        if (field === "match_status") return FORM_MATCH_STATUS_OPTIONS
        return null
    }

    const getTriggerValidationError = (): string | null => {
        if (!triggerType) return "Trigger type is required."
        if (triggerType === "form_started") {
            const formId = triggerConfig.form_id
            if (!formId || typeof formId !== "string") return "Select a form."
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
        if (action.action_type === "send_email") {
            if (Array.isArray(action.recipients) && action.recipients.length === 0) {
                return "Select at least one recipient."
            }
        }
        if (action.action_type === "send_notification" && !title.trim()) {
            return "Notification actions need a title."
        }
        if (action.action_type === "send_notification" && Array.isArray(action.recipients) && action.recipients.length === 0) {
            return "Select at least one recipient."
        }
        if (action.action_type === "send_email" && Array.isArray(action.recipients) && action.recipients.length === 0) {
            return "Select an email recipient."
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
        if (triggerType === "form_submitted") {
            const autoMatchIndex = actions.findIndex(
                (action) => action.action_type === "auto_match_submission"
            )
            const createLeadIndex = actions.findIndex(
                (action) => action.action_type === "create_intake_lead"
            )
            if (autoMatchIndex >= 0 && createLeadIndex >= 0 && autoMatchIndex > createLeadIndex) {
                return "Place Auto-Match Submission before Create Intake Lead for form-submitted templates."
            }
        }
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
        if (triggerType === "form_started") {
            if (typeof next.form_id !== "string" || !next.form_id) delete next.form_id
        }
        if (triggerType === "form_submitted") {
            if (typeof next.form_id !== "string" || !next.form_id) delete next.form_id
        }
        if (triggerType === "intake_lead_created") {
            if (typeof next.form_id !== "string" || !next.form_id) delete next.form_id
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

    const handleDelete = async () => {
        if (isNew || deleteTemplate.isPending) return
        try {
            await deleteTemplate.mutateAsync({ id })
            toast.success("Template deleted")
            setShowDeleteDialog(false)
            router.push("/ops/templates?tab=workflows")
        } catch (err) {
            toast.error(err instanceof Error ? err.message : "Failed to delete template")
        }
    }

    return {
        isNew,
        isLoading,
        templateData,
        name,
        setName,
        description,
        setDescription,
        category,
        setCategory,
        icon,
        setIcon,
        triggerType,
        setTriggerType,
        triggerTypeOptions,
        triggerConfig,
        setTriggerConfig,
        stageIdOptions,
        formOptions,
        conditionFields,
        conditions,
        conditionOperators,
        conditionLogic,
        setConditionLogic,
        actions,
        filteredActionTypes,
        updateFields,
        userOptions,
        queueOptions,
        isPublished,
        isSaving,
        isPublishing,
        isDeleting: deleteTemplate.isPending,
        showPublishDialog,
        setShowPublishDialog,
        showDeleteDialog,
        setShowDeleteDialog,
        workflowValidationError,
        getConditionOptions,
        addCondition,
        updateCondition,
        removeCondition,
        addAction,
        updateAction,
        removeAction,
        applySharedIntakeSample,
        applyZapierConversionSample,
        handleSave,
        handlePublish,
        confirmPublish,
        handleDelete,
        handleBack: () => router.push("/ops/templates?tab=workflows"),
        openDeleteDialog: () => setShowDeleteDialog(true),
    }
}

export default function PlatformWorkflowTemplatePage() {
    const {
        isNew,
        isLoading,
        templateData,
        name,
        setName,
        description,
        setDescription,
        category,
        setCategory,
        icon,
        setIcon,
        triggerType,
        setTriggerType,
        triggerTypeOptions,
        triggerConfig,
        setTriggerConfig,
        stageIdOptions,
        formOptions,
        conditionFields,
        conditions,
        conditionOperators,
        conditionLogic,
        setConditionLogic,
        actions,
        filteredActionTypes,
        updateFields,
        userOptions,
        queueOptions,
        isPublished,
        isSaving,
        isPublishing,
        isDeleting,
        showPublishDialog,
        setShowPublishDialog,
        showDeleteDialog,
        setShowDeleteDialog,
        workflowValidationError,
        getConditionOptions,
        addCondition,
        updateCondition,
        removeCondition,
        addAction,
        updateAction,
        removeAction,
        applySharedIntakeSample,
        applyZapierConversionSample,
        handleSave,
        handlePublish,
        confirmPublish,
        handleDelete,
        handleBack,
        openDeleteDialog,
    } = useWorkflowTemplatePageState()

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

    if (!isNew && !templateData) return null

    return (
        <div className="min-h-screen bg-stone-100 dark:bg-stone-950">
            <WorkflowTemplateDeleteDialog
                open={showDeleteDialog}
                onOpenChange={setShowDeleteDialog}
                onDelete={handleDelete}
                isDeleting={isDeleting}
                name={name}
            />

            <WorkflowTemplateHeader
                name={name}
                setName={setName}
                isPublished={isPublished}
                isNew={isNew}
                isDeleting={isDeleting}
                isSaving={isSaving}
                isPublishing={isPublishing}
                onBack={handleBack}
                onDelete={openDeleteDialog}
                onSave={handleSave}
                onPublish={handlePublish}
            />

            <div className="grid gap-6 p-6 lg:grid-cols-[1fr_320px]">
                <div className="space-y-6">
                    <WorkflowTemplateDetailsSection
                        description={description}
                        setDescription={setDescription}
                        category={category}
                        setCategory={setCategory}
                        icon={icon}
                        setIcon={setIcon}
                        onLoadSharedIntakeSample={applySharedIntakeSample}
                        onLoadZapierSample={applyZapierConversionSample}
                    />

                    <WorkflowTemplateTriggerSection
                        triggerType={triggerType}
                        setTriggerType={setTriggerType}
                        triggerTypeOptions={triggerTypeOptions}
                        triggerConfig={triggerConfig}
                        setTriggerConfig={setTriggerConfig}
                        stageIdOptions={stageIdOptions}
                        formOptions={formOptions}
                        conditionFields={conditionFields}
                        userOptions={userOptions}
                    />

                    <WorkflowTemplateConditionsSection
                        conditions={conditions}
                        conditionOperators={conditionOperators}
                        conditionFields={conditionFields}
                        conditionLogic={conditionLogic}
                        setConditionLogic={setConditionLogic}
                        getConditionOptions={getConditionOptions}
                        addCondition={addCondition}
                        updateCondition={updateCondition}
                        removeCondition={removeCondition}
                    />

                    <WorkflowTemplateActionsSection
                        actions={actions}
                        filteredActionTypes={filteredActionTypes}
                        addAction={addAction}
                        updateAction={updateAction}
                        removeAction={removeAction}
                        userOptions={userOptions}
                        queueOptions={queueOptions}
                        updateFields={updateFields}
                        stageIdOptions={stageIdOptions}
                    />
                </div>

                <WorkflowTemplateSidebar
                    workflowValidationError={workflowValidationError}
                    triggerType={triggerType}
                    conditionsCount={conditions.length}
                    actionsCount={actions.length}
                />
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
