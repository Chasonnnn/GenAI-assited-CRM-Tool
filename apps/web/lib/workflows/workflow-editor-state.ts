/**
 * Pure state, labels, and validation for the workflow editor. React-free so the reducer
 * and save normalization can be unit tested and shared by the editor page and the list page.
 */

import { ApiError } from "@/lib/api"
import type { ActionConfig, Condition, WorkflowCreate, WorkflowScope, WorkflowSubjectType } from "@/lib/api/workflows"
import { getSurrogateFieldLabel } from "@/lib/constants/surrogate-field-labels"
import { DONOR_SOURCE_LABELS } from "@/lib/donor-source-labels"
import { isPermissionError } from "@/lib/error-utils"
import { createSelectLabelGetter, toSelectOptions } from "@/lib/select-labels"
import type { JsonObject, JsonValue } from "@/lib/types/json"
import {
    FORM_TRIGGER_TYPES,
    INTAKE_LEAD_KIND_CONFIG_KEYS,
    LIST_OPERATORS,
    MULTISELECT_FIELDS,
    VALUELESS_OPERATORS,
    createClientRowId,
    normalizeEditableActionsForUi,
    normalizeEditableConditionsForUi,
    toListArray,
    type EditableAction,
    type EditableCondition,
    type SelectOption,
} from "@/components/automation/workflow-editor/shared"

export type StatusOption = { id?: string; value: string; label: string; is_active?: boolean }

export const WORKFLOW_SUBJECT_LABELS: Record<WorkflowSubjectType, string> = {
    surrogate: "Surrogate",
    form_submission: "Form Submission",
    intake_lead: "Intake Lead",
    match: "Match",
    appointment: "Appointment",
    egg_donor: "Egg Donor",
    sperm_donor: "Sperm Donor",
}

export const WORKFLOW_SUBJECT_PLURAL_LABELS: Record<WorkflowSubjectType, string> = {
    surrogate: "Surrogates",
    form_submission: "Form Submissions",
    intake_lead: "Intake Leads",
    match: "Matches",
    appointment: "Appointments",
    egg_donor: "Egg Donors",
    sperm_donor: "Sperm Donors",
}

export type CreateWorkflowSubjectType = Extract<WorkflowSubjectType, "surrogate" | "egg_donor" | "sperm_donor">

export const CREATE_WORKFLOW_SUBJECT_OPTIONS: Array<{ value: CreateWorkflowSubjectType; label: string }> = [
    { value: "surrogate", label: WORKFLOW_SUBJECT_LABELS.surrogate },
    { value: "egg_donor", label: WORKFLOW_SUBJECT_LABELS.egg_donor },
    { value: "sperm_donor", label: WORKFLOW_SUBJECT_LABELS.sperm_donor },
]

/** The record an appointment workflow acts on (mirrors AppointmentTriggerConfig.record_type). */
export function getAppointmentRecordType(triggerConfig: JsonObject): CreateWorkflowSubjectType {
    const value = triggerConfig.record_type
    return CREATE_WORKFLOW_SUBJECT_OPTIONS.find((option) => option.value === value)?.value ?? "surrogate"
}

export function getAppointmentTypeNames(triggerConfig: JsonObject): string[] {
    return Array.isArray(triggerConfig.appointment_type_names)
        ? triggerConfig.appointment_type_names.filter((name): name is string => typeof name === "string")
        : []
}

// Mirrors workflow_service.LEGACY_TRIGGER_SUBJECT_TYPES; the engine matches on subject_type.
export const FIXED_TRIGGER_SUBJECT_TYPES: Partial<Record<string, WorkflowSubjectType>> = {
    form_submitted: "form_submission",
    form_submission_approved: "form_submission",
    form_submission_rejected: "form_submission",
    intake_lead_created: "intake_lead",
    match_proposed: "match",
    match_accepted: "match",
    match_declined: "match",
    match_cancelled: "match",
    appointment_scheduled: "appointment",
    appointment_completed: "appointment",
    appointment_cancelled: "appointment",
    appointment_no_show: "appointment",
    appointment_requested: "appointment",
    appointment_rescheduled: "appointment",
    appointment_expired: "appointment",
}

export const TRIGGER_LABELS: Record<string, string> = {
    surrogate_created: "Surrogate Created",
    status_changed: "Status Changed",
    surrogate_assigned: "Surrogate Assigned",
    surrogate_updated: "Surrogate Updated",
    form_submitted: "Application Submitted",
    form_submission_approved: "Application Approved",
    form_submission_rejected: "Application Rejected",
    intake_lead_created: "Intake Lead Created",
    task_due: "Task Due",
    task_overdue: "Task Overdue",
    scheduled: "Scheduled",
    inactivity: "Inactivity",
    match_proposed: "Match Proposed",
    match_accepted: "Match Accepted",
    match_declined: "Match Declined",
    match_cancelled: "Match Cancelled",
    appointment_scheduled: "Appointment Scheduled",
    appointment_completed: "Appointment Completed",
    appointment_cancelled: "Appointment Cancelled",
    appointment_no_show: "Appointment No-Show",
    appointment_requested: "Appointment Requested",
    appointment_rescheduled: "Appointment Rescheduled",
    appointment_expired: "Appointment Request Expired",
    note_added: "Note Added",
    document_uploaded: "Document Uploaded",
    donor_created: "Donor Created",
    donor_stage_changed: "Donor Stage Changed",
    donor_assigned: "Donor Assigned",
    donor_updated: "Donor Updated",
}

export function getTriggerLabel(triggerType: string): string {
    return TRIGGER_LABELS[triggerType] ?? triggerType
}

// Update Field writes only canonical donor sources; the backend rejects anything else.
export const UPDATE_SOURCE_OPTIONS = toSelectOptions(DONOR_SOURCE_LABELS)
export const getUpdateSourceLabel = createSelectLabelGetter(DONOR_SOURCE_LABELS, {
    emptyLabel: "Select source",
    unknownLabel: "Unknown source",
})

export const DONOR_TYPE_OPTIONS: SelectOption[] = [
    { value: "egg", label: "Egg Donor" },
    { value: "sperm", label: "Sperm Donor" },
]

export const CONDITION_FIELD_LABELS: Record<string, string> = {
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
    status: "Status",
    source_mode: "Submission Source",
    lead_kind: "Applicant Type",
    match_status: "Match Status",
    created_at: "Created At",
    date_of_birth: "Date of Birth",
    height_ft: "Height (ft)",
    weight_lb: "Weight (lb)",
    journey_timing_preference: "Journey Timing",
    num_deliveries: "Deliveries",
    num_csections: "C-Sections",
    race: "Race",
    meta_lead_id: "Meta Lead ID",
    meta_ad_external_id: "Meta Ad External ID",
    meta_form_id: "Meta Form ID",
    education: "Education",
    donor_type: "Donor Type",
    donor_number: "Donor Number",
    marital_status: "Marital Status",
    contact_status: "Contact Status",
    last_contacted_at: "Last Contacted",
    assigned_at: "Assigned At",
    embryo_stage: "Embryo Stage",
    pregnancy_due_date: "Due Date",
    actual_delivery_date: "Delivery Date",
    college: "College",
    nicotine: "Nicotine",
    cannabis: "Cannabis",
    infectious_disease: "Infectious Disease",
    previous_donation: "Previous Donation",
    submitted_at: "Submitted At",
    match_kind: "Match Type",
    outcome: "Outcome",
    appointment_type_id: "Appointment Type",
    meeting_mode: "Meeting Mode",
    scheduled_start: "Scheduled Start",
}

export function getConditionFieldLabel(value: string): string {
    return getSurrogateFieldLabel(value) ?? CONDITION_FIELD_LABELS[value] ?? "Unknown field"
}

export function isDonorSubject(
    subjectType: WorkflowSubjectType,
): subjectType is Extract<WorkflowSubjectType, "egg_donor" | "sperm_donor"> {
    return subjectType === "egg_donor" || subjectType === "sperm_donor"
}

// Mirrors workflow_service.SHARED_DONOR_STAGE_ERROR.
export const SHARED_DONOR_STAGE_ERROR = "Stage references need a form for one donor type."

// The applicant type belongs to the previous form; the backend rejects a lead kind that does
// not match the selected form.
export function withIntakeTriggerForm(triggerType: string, config: JsonObject, formId: string | null): JsonObject {
    if (config.form_id === formId) return config
    const next: JsonObject = { ...config, form_id: formId }
    const leadKindKey = INTAKE_LEAD_KIND_CONFIG_KEYS[triggerType]
    if (leadKindKey) delete next[leadKindKey]
    return next
}

export function normalizeTriggerConfigForUi(
    triggerType: string,
    triggerConfig: JsonObject,
    statuses: StatusOption[],
): JsonObject {
    const next: JsonObject = { ...triggerConfig }
    if (triggerType === "status_changed" || triggerType === "donor_stage_changed") {
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
        if (typeof next.to_stage_id !== "string") next.to_stage_id = ""
        if (typeof next.from_stage_id !== "string") delete next.from_stage_id
    }
    if (triggerType === "scheduled") {
        if (typeof next.cron !== "string") next.cron = ""
        if (typeof next.timezone !== "string") next.timezone = "America/Los_Angeles"
    }
    if (triggerType === "inactivity") {
        if (typeof next.days === "string") {
            const parsed = Number(next.days)
            next.days = Number.isFinite(parsed) ? parsed : 7
        } else if (typeof next.days !== "number") {
            next.days = 7
        }
    }
    if (triggerType === "task_due") {
        if (typeof next.hours_before === "string") {
            const parsed = Number(next.hours_before)
            next.hours_before = Number.isFinite(parsed) ? parsed : 24
        } else if (typeof next.hours_before !== "number") {
            next.hours_before = 24
        }
    }
    if (FORM_TRIGGER_TYPES.has(triggerType)) {
        if (typeof next.form_id !== "string") next.form_id = ""
    }
    if (triggerType === "surrogate_updated" || triggerType === "donor_updated") {
        if (!Array.isArray(next.fields)) next.fields = []
    }
    if (triggerType === "surrogate_assigned" || triggerType === "donor_assigned") {
        if (typeof next.to_user_id !== "string") delete next.to_user_id
    }
    return next
}

/** Trigger config as the API expects it: blank optional keys removed, numbers coerced. */
export function buildTriggerConfigForSave(triggerType: string, triggerConfig: JsonObject): JsonObject {
    const next: JsonObject = { ...triggerConfig }
    if (triggerType === "status_changed" || triggerType === "donor_stage_changed") {
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
    if (FORM_TRIGGER_TYPES.has(triggerType)) {
        if (typeof next.form_id !== "string" || !next.form_id) delete next.form_id
    }
    if (triggerType === "surrogate_updated" || triggerType === "donor_updated") {
        if (!Array.isArray(next.fields)) next.fields = []
    }
    if (triggerType === "surrogate_assigned" || triggerType === "donor_assigned") {
        if (typeof next.to_user_id !== "string") delete next.to_user_id
    }
    return next
}

export function getTriggerConfigValidationError(triggerType: string, triggerConfig: JsonObject): string | null {
    if (triggerType === "scheduled") {
        const cron = triggerConfig.cron
        if (!cron || typeof cron !== "string") return "Cron schedule is required."
    }
    if (triggerType === "inactivity") {
        const days = triggerConfig.days
        if (!days || typeof days !== "number") return "Inactivity days are required."
    }
    if (triggerType === "task_due") {
        const hours = triggerConfig.hours_before
        if (!hours || typeof hours !== "number") return "Hours before due is required."
    }
    if (FORM_TRIGGER_TYPES.has(triggerType)) {
        const formId = triggerConfig.form_id
        if (!formId || typeof formId !== "string") return "Select a form."
    }
    if (triggerType === "surrogate_updated" || triggerType === "donor_updated") {
        const fields = triggerConfig.fields
        if (!Array.isArray(fields) || fields.length === 0) return "Select at least one field to watch."
    }
    return null
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function getActionValidationError(action: ActionConfig): string | null {
    const title = typeof action.title === "string" ? action.title : ""
    const content = typeof action.content === "string" ? action.content : ""
    if (!action.action_type) return "Select an action type for each action."
    if (action.action_type === "send_email" && !action.template_id) {
        return "Select an email template for all email actions."
    }
    if (
        action.action_type === "send_email" &&
        Array.isArray(action.recipients) &&
        action.recipients.length === 0
    ) {
        return "Select at least one email recipient."
    }
    if (action.action_type === "send_email" && action.recipients === "queue" && !action.recipient_queue_id) {
        return "Select a queue for queue email recipients."
    }
    if (action.action_type === "send_email" && action.recipients === "role" && !action.recipient_role) {
        return "Select a role for role email recipients."
    }
    if (action.action_type === "send_email" && action.recipients === "custom") {
        const emails = Array.isArray(action.recipient_emails) ? action.recipient_emails : []
        if (emails.length === 0) return "Enter at least one email address."
        if (emails.length > 10) return "Enter at most 10 email addresses."
        if (emails.some((email) => typeof email !== "string" || !EMAIL_PATTERN.test(email))) {
            return "Enter valid email addresses."
        }
    }
    if (action.action_type === "send_message" && !action.purpose) {
        return "Select a message purpose for all messaging actions."
    }
    if (action.action_type === "send_message" && !action.message_template_version_id) {
        return "Select a message template for all messaging actions."
    }
    if (action.action_type === "create_task" && !title.trim()) {
        return "Task actions need a title."
    }
    if (action.action_type === "send_notification" && !title.trim()) {
        return "Notification actions need a title."
    }
    if (action.action_type === "send_notification" && Array.isArray(action.recipients) && action.recipients.length === 0) {
        return "Select at least one recipient."
    }
    if (action.action_type === "assign_surrogate" || action.action_type === "assign_donor") {
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

export function getActionsValidationError(triggerType: string, actions: ActionConfig[]): string | null {
    if (actions.length === 0) return "Add at least one action."
    if (triggerType === "form_submitted") {
        const autoMatchIndex = actions.findIndex((action) => action.action_type === "auto_match_submission")
        const createLeadIndex = actions.findIndex((action) => action.action_type === "create_intake_lead")
        if (autoMatchIndex >= 0 && createLeadIndex >= 0 && autoMatchIndex > createLeadIndex) {
            return "Place Auto-Match Submission before Create Intake Lead for form-submitted workflows."
        }
    }
    for (const action of actions) {
        const error = getActionValidationError(action)
        if (error) return error
    }
    return null
}

export function parseServerErrors(
    error: unknown,
    { forbiddenMessage }: { forbiddenMessage: string },
): string[] {
    // A 403 detail names internal permission keys; show one plain sentence instead.
    if (isPermissionError(error)) return [forbiddenMessage]
    if (error instanceof ApiError) {
        if (error.status >= 500) return ["Couldn't save the workflow. Try again."]
        if (error.message) {
            const messages: string[] = []
            for (const rawMessage of error.message.split(";")) {
                const message = rawMessage.trim()
                if (message) messages.push(message)
            }
            return messages
        }
        return ["An unexpected error occurred."]
    }
    if (error instanceof Error) {
        return [error.message]
    }
    return ["An unexpected error occurred."]
}

export type WorkflowBuilderState = {
    hydratedWorkflowId: string | null
    validationError: string | null
    serverErrors: string[]
    workflowName: string
    workflowDescription: string
    workflowScope: WorkflowScope
    subjectType: WorkflowSubjectType
    triggerType: string
    triggerConfig: JsonObject
    conditions: EditableCondition[]
    conditionLogic: "AND" | "OR"
    actions: EditableAction[]
}

export type StateUpdate<T> = T | ((current: T) => T)

export type WorkflowBuilderAction =
    | { type: "reset"; scope?: WorkflowScope }
    | {
        type: "hydrateWorkflow"
        workflow: WorkflowCreate & { scope: WorkflowScope }
        workflowId: string
        statusOptions: StatusOption[]
    }
    | { type: "setValidationError"; value: string | null }
    | { type: "setServerErrors"; value: string[] }
    | { type: "setWorkflowName"; value: string }
    | { type: "setWorkflowDescription"; value: string }
    | { type: "setWorkflowScope"; value: WorkflowScope }
    | { type: "setSubjectType"; value: WorkflowSubjectType }
    | { type: "setTriggerType"; value: string }
    | { type: "setTriggerConfig"; value: StateUpdate<JsonObject> }
    | { type: "normalizeTriggerConfig"; value: JsonObject }
    | { type: "setConditionLogic"; value: "AND" | "OR" }
    | { type: "addCondition" }
    | { type: "removeCondition"; index: number }
    | { type: "updateCondition"; index: number; updates: Partial<Condition> }
    | { type: "addAction"; clientId?: string; action?: Partial<ActionConfig> }
    | { type: "removeAction"; index: number }
    | { type: "moveAction"; index: number; direction: -1 | 1 }
    | { type: "updateAction"; index: number; updates: Partial<ActionConfig> }

export function createInitialWorkflowBuilderState(scope: WorkflowScope = "personal"): WorkflowBuilderState {
    return {
        hydratedWorkflowId: null,
        validationError: null,
        serverErrors: [],
        workflowName: "",
        workflowDescription: "",
        workflowScope: scope,
        subjectType: "surrogate",
        triggerType: "",
        triggerConfig: {},
        conditions: [],
        conditionLogic: "AND",
        actions: [],
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

export function workflowBuilderReducer(state: WorkflowBuilderState, action: WorkflowBuilderAction): WorkflowBuilderState {
    switch (action.type) {
        case "reset":
            return createInitialWorkflowBuilderState(action.scope ?? state.workflowScope)
        case "hydrateWorkflow": {
            const workflow = action.workflow
            const logic =
                workflow.condition_logic === "AND" || workflow.condition_logic === "OR"
                    ? workflow.condition_logic
                    : "AND"
            return {
                ...state,
                hydratedWorkflowId: action.workflowId,
                workflowName: workflow.name,
                workflowDescription: workflow.description ?? "",
                workflowScope: workflow.scope,
                subjectType: workflow.subject_type ?? "surrogate",
                triggerType: workflow.trigger_type,
                triggerConfig: normalizeTriggerConfigForUi(
                    workflow.trigger_type,
                    workflow.trigger_config ?? {},
                    action.statusOptions,
                ),
                conditions: normalizeEditableConditionsForUi(workflow.conditions ?? []),
                conditionLogic: logic,
                actions: normalizeEditableActionsForUi(workflow.actions ?? []),
                validationError: null,
                serverErrors: [],
            }
        }
        case "setValidationError":
            return { ...state, validationError: action.value }
        case "setServerErrors":
            return { ...state, serverErrors: action.value }
        case "setWorkflowName":
            return { ...state, workflowName: action.value, serverErrors: [] }
        case "setWorkflowDescription":
            return { ...state, workflowDescription: action.value, serverErrors: [] }
        case "setWorkflowScope":
            return { ...state, workflowScope: action.value, serverErrors: [] }
        case "setSubjectType":
            if (action.value === state.subjectType) return state
            return {
                ...state,
                subjectType: action.value,
                triggerType: "",
                triggerConfig: {},
                conditions: [],
                actions: [],
                validationError: null,
                serverErrors: [],
            }
        case "setTriggerType":
            if (action.value === state.triggerType) return state
            return {
                ...state,
                triggerType: action.value,
                triggerConfig: normalizeTriggerConfigForUi(action.value, {}, []),
                serverErrors: [],
            }
        case "setTriggerConfig":
            return {
                ...state,
                triggerConfig: typeof action.value === "function" ? action.value(state.triggerConfig) : action.value,
                serverErrors: [],
            }
        case "normalizeTriggerConfig":
            return { ...state, triggerConfig: action.value }
        case "setConditionLogic":
            return { ...state, conditionLogic: action.value, serverErrors: [] }
        case "addCondition":
            return {
                ...state,
                conditions: [
                    ...state.conditions,
                    { clientId: createClientRowId(), field: "", operator: "equals", value: "" },
                ],
                serverErrors: [],
            }
        case "removeCondition":
            return {
                ...state,
                conditions: state.conditions.filter((_, index) => index !== action.index),
                serverErrors: [],
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
                serverErrors: [],
            }
        case "addAction":
            return {
                ...state,
                actions: [
                    ...state.actions,
                    mergeActionConfig(
                        { clientId: action.clientId ?? createClientRowId(), action_type: "" },
                        action.action ?? {},
                    ),
                ],
                serverErrors: [],
            }
        case "removeAction":
            return {
                ...state,
                actions: state.actions.filter((_, index) => index !== action.index),
                serverErrors: [],
            }
        case "moveAction": {
            const target = action.index + action.direction
            if (action.index < 0 || action.index >= state.actions.length) return state
            if (target < 0 || target >= state.actions.length) return state
            const actions = [...state.actions]
            const [moved] = actions.splice(action.index, 1)
            if (!moved) return state
            actions.splice(target, 0, moved)
            return { ...state, actions, serverErrors: [] }
        }
        case "updateAction":
            return {
                ...state,
                actions: state.actions.map((currentAction, index) =>
                    index === action.index ? mergeActionConfig(currentAction, action.updates) : currentAction
                ),
                serverErrors: [],
            }
        default:
            return state
    }
}

// Trigger types that fire on time rather than on a record event; the editor groups them under
// "Date or scheduled" like the reference layout.
export const TIME_TRIGGER_TYPES = new Set(["scheduled", "inactivity", "task_due", "task_overdue"])

export type ScheduleFrequency = "daily" | "weekdays" | "weekly" | "custom"

export type SimpleSchedule = {
    frequency: ScheduleFrequency
    /** HH:MM, 24-hour. */
    time: string
    /** 0 (Sunday) to 6; used when frequency is weekly. */
    dayOfWeek: number
}

export const WEEKDAY_LABELS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"] as const

/**
 * Reads a cron string into the presets the editor offers. The presets stay inside the subset
 * that schemas.workflow.is_supported_simple_cron accepts; anything else is "custom".
 */
export function parseSimpleCron(cron: string): SimpleSchedule | null {
    const trimmed = cron.trim()
    if (!trimmed) return null
    const match = /^(\d{1,2}) (\d{1,2}) \* \* (\*|1-5|[0-7])$/.exec(trimmed)
    if (!match) return { frequency: "custom", time: "09:00", dayOfWeek: 1 }
    const [, minuteText = "0", hourText = "0", dayText = "*"] = match
    const minute = Number(minuteText)
    const hour = Number(hourText)
    if (minute > 59 || hour > 23) return { frequency: "custom", time: "09:00", dayOfWeek: 1 }
    const time = `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`
    if (dayText === "*") return { frequency: "daily", time, dayOfWeek: 1 }
    if (dayText === "1-5") return { frequency: "weekdays", time, dayOfWeek: 1 }
    return { frequency: "weekly", time, dayOfWeek: Number(dayText) % 7 }
}

export function buildSimpleCron(schedule: SimpleSchedule): string {
    const [hourText = "9", minuteText = "0"] = schedule.time.split(":")
    const hour = Math.min(Math.max(Number(hourText) || 0, 0), 23)
    const minute = Math.min(Math.max(Number(minuteText) || 0, 0), 59)
    const day =
        schedule.frequency === "weekdays" ? "1-5" : schedule.frequency === "weekly" ? String(schedule.dayOfWeek) : "*"
    return `${minute} ${hour} * * ${day}`
}

export function describeSchedule(cron: string): string | null {
    const schedule = parseSimpleCron(cron)
    if (!schedule) return null
    if (schedule.frequency === "custom") return `Cron ${cron.trim()}`
    if (schedule.frequency === "daily") return `Every day at ${schedule.time}`
    if (schedule.frequency === "weekdays") return `Every weekday at ${schedule.time}`
    return `Every ${WEEKDAY_LABELS[schedule.dayOfWeek]} at ${schedule.time}`
}
