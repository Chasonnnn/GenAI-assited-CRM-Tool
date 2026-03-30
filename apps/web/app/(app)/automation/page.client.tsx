"use client"

import { useEffect, useMemo, useReducer, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
    PlusIcon,
    MoreVerticalIcon,
    UserIcon,
    CalendarIcon,
    CheckCircle2Icon,
    TrendingUpIcon,
    ActivityIcon,
    XIcon,
    GripVerticalIcon,
    ChevronRightIcon,
    WorkflowIcon,
    LayoutTemplateIcon,
    ClockIcon,
    ZapIcon,
    FileTextIcon,
    Loader2Icon,
    AlertCircleIcon,
    BuildingIcon,
    SparklesIcon,
} from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import {
    useWorkflows,
    useWorkflow,
    useWorkflowStats,
    useWorkflowOptions,
    useWorkflowExecutions,
    useCreateWorkflow,
    useUpdateWorkflow,
    useDeleteWorkflow,
    useToggleWorkflow,
    useDuplicateWorkflow,
    useTestWorkflow,
} from "@/lib/hooks/use-workflows"
import type {
    WorkflowListItem,
    Condition,
    ActionConfig,
    WorkflowCreate,
    WorkflowTestResponse,
    WorkflowOptions,
    WorkflowScope,
} from "@/lib/api/workflows"
import { useAuth } from "@/lib/auth-context"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"
import { useCreateEmailTemplate, useUpdateEmailTemplate, useDeleteEmailTemplate } from "@/lib/hooks/use-email-templates"
import type { EmailTemplateListItem } from "@/lib/api/email-templates"
import { ApiError } from "@/lib/api"
import { globalSearch } from "@/lib/api/search"
import WorkflowTemplatesPanel from "@/components/automation/workflow-templates-panel"
import Link from "@/components/app-link"
import { getAppointments } from "@/lib/api/appointments"
import { listMatches, type ListMatchesParams } from "@/lib/api/matches"
import { getTasks, type TaskListParams } from "@/lib/api/tasks"
import { getSurrogates, type SurrogateListParams } from "@/lib/api/surrogates"
import { getSurrogateFieldLabel } from "@/lib/constants/surrogate-field-labels"
import { US_STATES } from "@/lib/constants/us-states"
import { parseDateInput } from "@/lib/utils/date"
import type { JsonObject, JsonValue } from "@/lib/types/json"
import { completeWorkflowSetup, startWorkflowSetup } from "@/lib/workflow-metrics"
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
    normalizeEditableActionsForSave as normalizeActionsForSave,
    normalizeEditableActionsForUi as normalizeActionsForUi,
    normalizeEditableConditionsForSave as normalizeConditionsForSave,
    normalizeEditableConditionsForUi as normalizeConditionsForUi,
    toListArray,
    type EditableAction,
    type EditableCondition,
    type SelectOption,
} from "@/components/automation/workflow-editor/shared"

// Icon mapping for trigger types
const triggerIcons: Record<string, React.ElementType> = {
    surrogate_created: FileTextIcon,
    status_changed: ZapIcon,
    surrogate_assigned: UserIcon,
    surrogate_updated: FileTextIcon,
    form_started: FileTextIcon,
    form_submitted: FileTextIcon,
    intake_lead_created: FileTextIcon,
    task_due: ClockIcon,
    task_overdue: AlertCircleIcon,
    scheduled: CalendarIcon,
    inactivity: ClockIcon,
    match_proposed: ActivityIcon,
    match_accepted: CheckCircle2Icon,
    match_rejected: XIcon,
    appointment_scheduled: CalendarIcon,
    appointment_completed: CheckCircle2Icon,
    note_added: FileTextIcon,
    document_uploaded: FileTextIcon,
}

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

function getConditionFieldLabel(value: string): string {
    return getSurrogateFieldLabel(value) ?? conditionFieldLabels[value] ?? "Unknown field"
}

// Labels for condition fields
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
    status: "Status",
    source_mode: "Submission Source",
    match_status: "Match Status",
    created_at: "Created At",
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

const ENTITY_LABELS: Record<string, string> = {
    surrogate: "Surrogate ID",
    form_submission: "Form Submission ID",
    intake_lead: "Intake Lead ID",
    task: "Task ID",
    match: "Match ID",
    appointment: "Appointment ID",
    note: "Note ID",
    document: "Document ID",
}

const ENTITY_PLURALS: Record<string, string> = {
    surrogate: "surrogates",
    form_submission: "form submissions",
    intake_lead: "intake leads",
    task: "tasks",
    match: "matches",
    appointment: "appointments",
    note: "notes",
    document: "documents",
}

function formatRelativeTime(dateString: string | null): string {
    if (!dateString) return "Never"
    const date = parseDateInput(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays === 1) return "Yesterday"
    return `${diffDays}d ago`
}

type StatusOption = WorkflowOptions["statuses"][number]
const EMPTY_STATUS_OPTIONS: StatusOption[] = []
type TestEntitySuggestion = { id: string; label: string; meta?: string }

const buildTestEntitySuggestion = (
    id: string,
    label: string,
    meta?: string | null
): TestEntitySuggestion => (meta == null ? { id, label } : { id, label, meta })

async function fetchTestEntities(
    entityType: string,
    query: string
): Promise<TestEntitySuggestion[]> {
    if (entityType === "surrogate") {
        const params: SurrogateListParams = {
            per_page: 5,
            sort_by: "created_at",
            sort_order: "desc",
        }
        if (query.trim()) params.q = query.trim()
        const response = await getSurrogates(params)
        return response.items.map((item) =>
            buildTestEntitySuggestion(
                item.id,
                `${item.surrogate_number} • ${item.full_name}`,
                item.status_label ?? null
            )
        )
    }
    if (entityType === "task") {
        const params: TaskListParams = {
            per_page: 5,
            exclude_approvals: true,
        }
        if (query.trim()) params.q = query.trim()
        const response = await getTasks(params)
        return response.items.map((item) =>
            buildTestEntitySuggestion(
                item.id,
                item.title,
                item.surrogate_number ?? null
            )
        )
    }
    if (entityType === "match") {
        const params: ListMatchesParams = {
            per_page: 5,
        }
        if (query.trim()) params.q = query.trim()
        const response = await listMatches(params)
        return response.items.map((item) =>
            buildTestEntitySuggestion(
                item.id,
                item.match_number,
                item.surrogate_name ?? item.ip_name ?? null
            )
        )
    }
    if (entityType === "appointment") {
        const now = new Date()
        const end = new Date(now.getTime() + 1000 * 60 * 60 * 24 * 30)
        const response = await getAppointments({
            per_page: 5,
            date_start: now.toISOString(),
            date_end: end.toISOString(),
        })
        return response.items.map((item) =>
            buildTestEntitySuggestion(
                item.id,
                item.appointment_type_name ?? "Appointment",
                item.surrogate_number ?? item.intended_parent_name ?? null
            )
        )
    }
    if (entityType === "note") {
        if (!query.trim()) return []
        const response = await globalSearch({ q: query, types: "note", limit: 5 })
        return response.results.map((result) =>
            buildTestEntitySuggestion(
                result.entity_id,
                result.title,
                result.surrogate_name ?? null
            )
        )
    }
    if (entityType === "document") {
        if (!query.trim()) return []
        const response = await globalSearch({ q: query, types: "attachment", limit: 5 })
        return response.results.map((result) =>
            buildTestEntitySuggestion(
                result.entity_id,
                result.title,
                result.surrogate_name ?? null
            )
        )
    }
    if (entityType === "intake_lead") {
        return []
    }
    if (entityType === "form_submission") {
        return []
    }
    return []
}

function normalizeTriggerConfigForUi(
    triggerType: string,
    triggerConfig: JsonObject,
    statuses: StatusOption[],
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

type AutomationTab = "workflows" | "email-templates" | "campaigns"
type AutomationWorkflowScopeTab = "personal" | "org" | "templates"

type AutomationPageClientProps = {
    initialTab: AutomationTab
    initialWorkflowScopeTab: AutomationWorkflowScopeTab
    initialCreateOpen: boolean
    hasInitialScopeParam?: boolean
}

type WorkflowBuilderState = {
    hydratedWorkflowId: string | null
    wizardStep: number
    validationError: string | null
    serverErrors: string[]
    workflowName: string
    workflowDescription: string
    workflowScope: WorkflowScope
    triggerType: string
    triggerConfig: JsonObject
    conditions: EditableCondition[]
    conditionLogic: "AND" | "OR"
    actions: EditableAction[]
}

type WorkflowBuilderAction =
    | { type: "reset"; scope?: WorkflowScope }
    | { type: "hydrateWorkflow"; workflow: WorkflowCreate & { scope: WorkflowScope }; workflowId: string; statusOptions: StatusOption[] }
    | { type: "setWizardStep"; value: number }
    | { type: "setValidationError"; value: string | null }
    | { type: "setServerErrors"; value: string[] }
    | { type: "clearServerErrors" }
    | { type: "setWorkflowName"; value: string }
    | { type: "setWorkflowDescription"; value: string }
    | { type: "setWorkflowScope"; value: WorkflowScope }
    | { type: "setTriggerType"; value: string }
    | { type: "setTriggerConfig"; value: JsonObject }
    | { type: "setConditionLogic"; value: "AND" | "OR" }
    | { type: "addCondition" }
    | { type: "removeCondition"; index: number }
    | { type: "updateCondition"; index: number; updates: Partial<Condition> }
    | { type: "addAction" }
    | { type: "removeAction"; index: number }
    | { type: "updateAction"; index: number; updates: Partial<ActionConfig> }

type TestWorkflowState = {
    open: boolean
    workflowId: string | null
    entityId: string
    entityQuery: string
    result: WorkflowTestResponse | null
}

type TestWorkflowAction =
    | { type: "open"; workflowId: string }
    | { type: "close" }
    | { type: "setEntityId"; value: string }
    | { type: "setEntityQuery"; value: string }
    | { type: "setResult"; value: WorkflowTestResponse | null }

type EmailTemplateModalState = {
    open: boolean
    editingTemplate: EmailTemplateListItem | null
    templateName: string
    templateSubject: string
    templateBody: string
}

const INITIAL_TEST_WORKFLOW_STATE: TestWorkflowState = {
    open: false,
    workflowId: null,
    entityId: "",
    entityQuery: "",
    result: null,
}

const INITIAL_EMAIL_TEMPLATE_MODAL_STATE: EmailTemplateModalState = {
    open: false,
    editingTemplate: null,
    templateName: "",
    templateSubject: "",
    templateBody: "",
}

function createInitialWorkflowBuilderState(scope: WorkflowScope = "personal"): WorkflowBuilderState {
    return {
        hydratedWorkflowId: null,
        wizardStep: 1,
        validationError: null,
        serverErrors: [],
        workflowName: "",
        workflowDescription: "",
        workflowScope: scope,
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

function workflowBuilderReducer(state: WorkflowBuilderState, action: WorkflowBuilderAction): WorkflowBuilderState {
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
                triggerType: workflow.trigger_type,
                triggerConfig: normalizeTriggerConfigForUi(
                    workflow.trigger_type,
                    workflow.trigger_config ?? {},
                    action.statusOptions
                ),
                conditions: normalizeConditionsForUi(workflow.conditions ?? []),
                conditionLogic: logic,
                actions: normalizeActionsForUi(workflow.actions ?? []),
                validationError: null,
                serverErrors: [],
            }
        }
        case "setWizardStep":
            return { ...state, wizardStep: action.value }
        case "setValidationError":
            return { ...state, validationError: action.value }
        case "setServerErrors":
            return { ...state, serverErrors: action.value }
        case "clearServerErrors":
            return state.serverErrors.length > 0 ? { ...state, serverErrors: [] } : state
        case "setWorkflowName":
            return { ...state, workflowName: action.value }
        case "setWorkflowDescription":
            return { ...state, workflowDescription: action.value }
        case "setWorkflowScope":
            return { ...state, workflowScope: action.value }
        case "setTriggerType":
            return { ...state, triggerType: action.value }
        case "setTriggerConfig":
            return { ...state, triggerConfig: action.value }
        case "setConditionLogic":
            return { ...state, conditionLogic: action.value }
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

function testWorkflowReducer(state: TestWorkflowState, action: TestWorkflowAction): TestWorkflowState {
    switch (action.type) {
        case "open":
            return {
                open: true,
                workflowId: action.workflowId,
                entityId: "",
                entityQuery: "",
                result: null,
            }
        case "close":
            return INITIAL_TEST_WORKFLOW_STATE
        case "setEntityId":
            return { ...state, entityId: action.value }
        case "setEntityQuery":
            return { ...state, entityQuery: action.value }
        case "setResult":
            return { ...state, result: action.value }
        default:
            return state
    }
}

export default function AutomationPageClient({
    initialTab,
    initialWorkflowScopeTab,
    initialCreateOpen,
    hasInitialScopeParam = false,
}: AutomationPageClientProps) {
    const router = useRouter()
    const { user } = useAuth()
    const { data: effectivePermissions } = useEffectivePermissions(user?.user_id ?? null)
    const permissions = effectivePermissions?.permissions || []
    const canUseAI = Boolean(user?.ai_enabled) && permissions.includes("use_ai_assistant")
    const canManageAutomation = permissions.includes("manage_automation")
    const [activeTab] = useState(initialTab)

    const [workflowScopeTab, setWorkflowScopeTab] = useState<"personal" | "org" | "templates">(
        initialWorkflowScopeTab
    )
    const workflowScopeTabTouchedRef = useRef(false)
    const [workflowBuilderState, dispatchWorkflowBuilder] = useReducer(
        workflowBuilderReducer,
        undefined,
        () => createInitialWorkflowBuilderState("personal")
    )
    const [testWorkflowState, dispatchTestWorkflow] = useReducer(
        testWorkflowReducer,
        INITIAL_TEST_WORKFLOW_STATE
    )
    const [emailTemplateModal, setEmailTemplateModal] = useState(INITIAL_EMAIL_TEMPLATE_MODAL_STATE)
    const [showCreateModal, setShowCreateModal] = useState(initialCreateOpen)
    const [showHistoryPanel, setShowHistoryPanel] = useState(false)
    const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null)
    const [editingWorkflowId, setEditingWorkflowId] = useState<string | null>(null)

    const {
        hydratedWorkflowId,
        wizardStep,
        validationError,
        serverErrors,
        workflowName,
        workflowDescription,
        workflowScope,
        triggerType,
        triggerConfig,
        conditions,
        conditionLogic,
        actions,
    } = workflowBuilderState
    const {
        open: showTestModal,
        workflowId: testWorkflowId,
        entityId: testEntityId,
        entityQuery: testEntityQuery,
        result: testResult,
    } = testWorkflowState
    const {
        open: isTemplateModalOpen,
        editingTemplate,
        templateName,
        templateSubject,
        templateBody,
    } = emailTemplateModal

    const setWizardStep = (value: number) =>
        dispatchWorkflowBuilder({ type: "setWizardStep", value })
    const setValidationError = (value: string | null) =>
        dispatchWorkflowBuilder({ type: "setValidationError", value })
    const setServerErrors = (value: string[]) =>
        dispatchWorkflowBuilder({ type: "setServerErrors", value })
    const setWorkflowName = (value: string) =>
        dispatchWorkflowBuilder({ type: "setWorkflowName", value })
    const setWorkflowDescription = (value: string) =>
        dispatchWorkflowBuilder({ type: "setWorkflowDescription", value })
    const setTriggerType = (value: string) =>
        dispatchWorkflowBuilder({ type: "setTriggerType", value })
    const setTriggerConfig = (value: JsonObject) =>
        dispatchWorkflowBuilder({ type: "setTriggerConfig", value })
    const setConditionLogic = (value: "AND" | "OR") =>
        dispatchWorkflowBuilder({ type: "setConditionLogic", value })
    const setTestEntityId = (value: string) =>
        dispatchTestWorkflow({ type: "setEntityId", value })
    const setTestEntityQuery = (value: string) =>
        dispatchTestWorkflow({ type: "setEntityQuery", value })
    const handleTestDialogOpenChange = (open: boolean) => {
        if (!open) {
            dispatchTestWorkflow({ type: "close" })
        }
    }
    const setTemplateName = (value: string) =>
        setEmailTemplateModal((current) => ({ ...current, templateName: value }))
    const setTemplateSubject = (value: string) =>
        setEmailTemplateModal((current) => ({ ...current, templateSubject: value }))
    const setTemplateBody = (value: string) =>
        setEmailTemplateModal((current) => ({ ...current, templateBody: value }))
    const handleTemplateModalOpenChange = (open: boolean) => {
        if (!open) {
            setEmailTemplateModal(INITIAL_EMAIL_TEMPLATE_MODAL_STATE)
        }
    }

    const isTemplatesTab = workflowScopeTab === "templates"
    const activeWorkflowScope: WorkflowScope = workflowScopeTab === "templates" ? "personal" : workflowScopeTab

    // Default admins to org workflows when no explicit scope is set.
    // This avoids "personal" workflows unexpectedly failing for queue-owned cases.
    useEffect(() => {
        if (hasInitialScopeParam) return
        if (!canManageAutomation) return
        if (workflowScopeTabTouchedRef.current) return
        if (workflowScopeTab !== "personal") return
        setWorkflowScopeTab("org")
    }, [canManageAutomation, hasInitialScopeParam, workflowScopeTab])

    const workflowSetupSessionIdRef = useRef<string | null>(null)

    // API hooks
    const { data: workflows, isLoading: workflowsLoading } = useWorkflows({ scope: activeWorkflowScope })
    const { data: stats, isLoading: statsLoading } = useWorkflowStats()
    const { data: options } = useWorkflowOptions(workflowScope)
    const statusOptions = options?.statuses ?? EMPTY_STATUS_OPTIONS
    const activeStatusOptions = statusOptions.filter((status) => status.is_active !== false)
    const actionTypeOptions = options?.action_types ?? []
    const actionTypeValuesForTrigger = triggerType && options?.action_types_by_trigger?.[triggerType]
        ? new Set(options.action_types_by_trigger[triggerType])
        : null
    const filteredActionTypes = actionTypeValuesForTrigger
        ? actionTypeOptions.filter((action) => actionTypeValuesForTrigger.has(action.value))
        : actionTypeOptions
    const userOptions = useMemo(() => options?.users ?? [], [options?.users])
    const queueOptions = useMemo(() => options?.queues ?? [], [options?.queues])
    const formOptions = useMemo<SelectOption[]>(
        () => (options?.forms ?? []).map((form) => ({ value: form.id, label: form.name })),
        [options?.forms],
    )
    const updateFields = options?.update_fields ?? []
    const conditionOperators = options?.condition_operators ?? []
    const { data: executions } = useWorkflowExecutions(selectedWorkflowId || "", { limit: 20 })

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

    const triggerEntityTypes = options?.trigger_entity_types ?? {}
    const selectedTestWorkflow = useMemo(
        () => workflows?.find((workflow) => workflow.id === testWorkflowId),
        [testWorkflowId, workflows]
    )
    const testTriggerType = selectedTestWorkflow?.trigger_type
    const testEntityType = testTriggerType ? triggerEntityTypes[testTriggerType] ?? "surrogate" : "surrogate"

    const {
        data: testEntitySuggestionsData,
        isLoading: testEntitySuggestionsLoading,
    } = useQuery({
        queryKey: ["workflow-test-entities", testEntityType, testEntityQuery],
        queryFn: () => fetchTestEntities(testEntityType, testEntityQuery),
        enabled: showTestModal && !!testEntityType,
        staleTime: 30 * 1000,
    })
    const testEntitySuggestions = testEntitySuggestionsData ?? []

    const createWorkflow = useCreateWorkflow()
    const updateWorkflow = useUpdateWorkflow()
    const toggleWorkflow = useToggleWorkflow()
    const duplicateWorkflow = useDuplicateWorkflow()
    const deleteWorkflow = useDeleteWorkflow()
    const testWorkflowMutation = useTestWorkflow()

    const parseServerErrors = (error: unknown): string[] => {
        if (error instanceof ApiError) {
            if (error.message) {
                return error.message
                    .split(";")
                    .map((message) => message.trim())
                    .filter(Boolean)
            }
            return ["An unexpected error occurred."]
        }
        if (error instanceof Error) {
            return [error.message]
        }
        return ["An unexpected error occurred."]
    }

    useEffect(() => {
        dispatchWorkflowBuilder({ type: "clearServerErrors" })
    }, [workflowName, workflowDescription, triggerType, triggerConfig, conditions, actions])

    // Email template hooks
    const createTemplate = useCreateEmailTemplate()
    const updateTemplate = useUpdateEmailTemplate()
    const deleteTemplate = useDeleteEmailTemplate()

    const selectedTriggerFields = Array.isArray(triggerConfig.fields)
        ? triggerConfig.fields.filter((field): field is string => typeof field === "string")
        : []
    const availableConditionFields = options?.condition_fields ?? []

    const getActionValidationError = (action: ActionConfig): string | null => {
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

    const getActionsValidationError = (): string | null => {
        if (actions.length === 0) return "Add at least one action."
        if (triggerType === "form_submitted") {
            const autoMatchIndex = actions.findIndex(
                (action) => action.action_type === "auto_match_submission"
            )
            const createLeadIndex = actions.findIndex(
                (action) => action.action_type === "create_intake_lead"
            )
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

    const getTriggerConfigValidationError = (): string | null => {
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
        if (triggerType === "form_started") {
            const formId = triggerConfig.form_id
            if (!formId || typeof formId !== "string") return "Select a form."
        }
        if (triggerType === "form_submitted") {
            const formId = triggerConfig.form_id
            if (!formId || typeof formId !== "string") return "Select a form."
        }
        if (triggerType === "intake_lead_created") {
            const formId = triggerConfig.form_id
            if (!formId || typeof formId !== "string") return "Select a form."
        }
        if (triggerType === "surrogate_updated") {
            const fields = triggerConfig.fields
            if (!Array.isArray(fields) || fields.length === 0) return "Select at least one field to watch."
        }
        return null
    }

    const getWorkflowValidationError = (): string | null => {
        if (!workflowName.trim()) return "Workflow name is required."
        if (!triggerType) return "Trigger type is required."
        const triggerError = getTriggerConfigValidationError()
        if (triggerError) return triggerError
        return getActionsValidationError()
    }

    const getStepValidationError = (step: number): string | null => {
        if (step === 1) {
            if (!workflowName.trim()) return "Workflow name is required."
            if (!triggerType) return "Trigger type is required."
            const triggerError = getTriggerConfigValidationError()
            if (triggerError) return triggerError
        }
        if (step === 3) {
            return getActionsValidationError()
        }
        return null
    }

    const handleToggle = (id: string) => {
        toggleWorkflow.mutate(id)
    }

    const handleDuplicate = (id: string) => {
        duplicateWorkflow.mutate(id)
    }

    const handleDelete = (id: string) => {
        if (confirm("Are you sure you want to delete this workflow?")) {
            deleteWorkflow.mutate(id)
        }
    }

    const handleViewHistory = (id: string) => {
        setSelectedWorkflowId(id)
        setShowHistoryPanel(true)
    }

    const handleTest = (id: string) => {
        dispatchTestWorkflow({ type: "open", workflowId: id })
    }

    const handleRunTest = () => {
        if (!testWorkflowId || !testEntityId) return
        testWorkflowMutation.mutate(
            { id: testWorkflowId, entityId: testEntityId, entityType: testEntityType },
            { onSuccess: (result) => dispatchTestWorkflow({ type: "setResult", value: result }) }
        )
    }

    const resetWorkflowForm = () => {
        dispatchWorkflowBuilder({ type: "reset" })
    }

    const resetWizard = () => {
        resetWorkflowForm()
        setShowCreateModal(false)
        setEditingWorkflowId(null)
        workflowSetupSessionIdRef.current = null
    }

    const handleCreate = (scope: WorkflowScope = activeWorkflowScope) => {
        dispatchWorkflowBuilder({ type: "reset", scope })
        setEditingWorkflowId(null)
        setShowCreateModal(true)
        workflowSetupSessionIdRef.current = startWorkflowSetup(scope)
    }

    const handleEdit = async (workflowId: string) => {
        resetWorkflowForm()
        setEditingWorkflowId(workflowId)
        setShowCreateModal(true)
        // The full workflow data will be fetched by useWorkflow hook
    }

    // Fetch full workflow when editing
    const { data: editingWorkflow } = useWorkflow(editingWorkflowId || "")

    useEffect(() => {
        if (!editingWorkflow || !editingWorkflowId || !showCreateModal) return
        if (hydratedWorkflowId === editingWorkflowId) return
        dispatchWorkflowBuilder({
            type: "hydrateWorkflow",
            workflow: editingWorkflow as WorkflowCreate & { scope: WorkflowScope },
            workflowId: editingWorkflowId,
            statusOptions,
        })
    }, [editingWorkflow, editingWorkflowId, hydratedWorkflowId, showCreateModal, statusOptions])

    useEffect(() => {
        if (triggerType !== "status_changed" || statusOptions.length === 0) return
        const normalized = normalizeTriggerConfigForUi(triggerType, triggerConfig, statusOptions)
        if (areJsonObjectsEqual(normalized, triggerConfig)) return
        setTriggerConfig(normalized)
    }, [triggerConfig, triggerType, statusOptions])

    useEffect(() => {
        if (!triggerType) return
        const next: JsonObject = { ...triggerConfig }
        if (triggerType === "status_changed") {
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
        if (triggerType === "form_started") {
            if (typeof next.form_id !== "string") next.form_id = ""
        }
        if (triggerType === "form_submitted") {
            if (typeof next.form_id !== "string") next.form_id = ""
        }
        if (triggerType === "intake_lead_created") {
            if (typeof next.form_id !== "string") next.form_id = ""
        }
        if (triggerType === "surrogate_updated") {
            if (!Array.isArray(next.fields)) next.fields = []
        }
        if (triggerType === "surrogate_assigned") {
            if (typeof next.to_user_id !== "string") delete next.to_user_id
        }
        if (areJsonObjectsEqual(next, triggerConfig)) return
        setTriggerConfig(next)
    }, [triggerConfig, triggerType])

    const handleNextStep = () => {
        const error = getStepValidationError(wizardStep)
        if (error) {
            setValidationError(error)
            return
        }
        setValidationError(null)
        setWizardStep(wizardStep + 1)
    }

    const handleSaveWorkflow = () => {
        const error = getWorkflowValidationError()
        if (error) {
            setValidationError(error)
            return
        }
        setValidationError(null)

        const buildTriggerConfig = (): JsonObject => {
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
            if (triggerType === "form_started") {
                if (typeof next.form_id !== "string" || !next.form_id) delete next.form_id
            }
            if (triggerType === "form_submitted") {
                if (typeof next.form_id !== "string" || !next.form_id) delete next.form_id
            }
            if (triggerType === "intake_lead_created") {
                if (typeof next.form_id !== "string" || !next.form_id) delete next.form_id
            }
            if (triggerType === "surrogate_updated") {
                if (!Array.isArray(next.fields)) next.fields = []
            }
            if (triggerType === "surrogate_assigned") {
                if (typeof next.to_user_id !== "string") delete next.to_user_id
            }
            return next
        }

        const data: WorkflowCreate = {
            name: workflowName,
            trigger_type: triggerType,
            trigger_config: buildTriggerConfig(),
            conditions: normalizeConditionsForSave(conditions),
            condition_logic: conditionLogic,
            actions: normalizeActionsForSave(actions),
            is_enabled: true,
            scope: workflowScope,
            ...(workflowDescription ? { description: workflowDescription } : {}),
        }

        if (editingWorkflowId) {
            updateWorkflow.mutate(
                { id: editingWorkflowId, data },
                {
                    onSuccess: () => resetWizard(),
                    onError: (error) => setServerErrors(parseServerErrors(error)),
                }
            )
        } else {
            createWorkflow.mutate(data, {
                onSuccess: () => {
                    completeWorkflowSetup(workflowSetupSessionIdRef.current, workflowScope)
                    resetWizard()
                },
                onError: (error) => setServerErrors(parseServerErrors(error)),
            })
        }
    }

    const addCondition = () => {
        dispatchWorkflowBuilder({ type: "addCondition" })
    }

    const removeCondition = (index: number) => {
        dispatchWorkflowBuilder({ type: "removeCondition", index })
    }

    const updateCondition = (index: number, updates: Partial<Condition>) => {
        dispatchWorkflowBuilder({ type: "updateCondition", index, updates })
    }

    const addAction = () => {
        dispatchWorkflowBuilder({ type: "addAction" })
    }

    const removeAction = (index: number) => {
        dispatchWorkflowBuilder({ type: "removeAction", index })
    }

    const updateAction = (index: number, updates: Partial<ActionConfig>) => {
        dispatchWorkflowBuilder({ type: "updateAction", index, updates })
    }

    // Email template handlers (preserved)
    const handleOpenTemplateModal = (template?: EmailTemplateListItem) => {
        if (template) {
            setEmailTemplateModal({
                open: true,
                editingTemplate: template,
                templateName: template.name,
                templateSubject: template.subject,
                templateBody: "",
            })
        } else {
            setEmailTemplateModal(INITIAL_EMAIL_TEMPLATE_MODAL_STATE)
        }
        setEmailTemplateModal((current) => ({ ...current, open: true }))
    }

    const handleSaveTemplate = () => {
        if (!templateName.trim() || !templateSubject.trim() || !templateBody.trim()) return

        if (editingTemplate) {
            updateTemplate.mutate({
                id: editingTemplate.id,
                data: { name: templateName, subject: templateSubject, body: templateBody },
            }, {
                onSuccess: () => setEmailTemplateModal(INITIAL_EMAIL_TEMPLATE_MODAL_STATE),
            })
        } else {
            createTemplate.mutate({
                name: templateName,
                subject: templateSubject,
                body: templateBody,
            }, {
                onSuccess: () => setEmailTemplateModal(INITIAL_EMAIL_TEMPLATE_MODAL_STATE),
            })
        }
    }

    const workflowValidationError = getWorkflowValidationError()
    const hasServerErrors = serverErrors.length > 0

    return (
        <div className="flex min-h-screen flex-col">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <h1 className="text-2xl font-semibold">Workflows</h1>
                    <div className="flex gap-3">
                        {activeTab === "workflows" && (
                            <Button variant="outline" onClick={() => router.push("/automation/executions")}>
                                <ActivityIcon className="mr-2 size-4" />
                                Execution History
                            </Button>
                        )}
                        {activeTab === "email-templates" && (
                            <Button onClick={() => handleOpenTemplateModal()}>
                                <PlusIcon className="mr-2 size-4" />
                                New Template
                            </Button>
                        )}
                    </div>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 p-6">
                <div className="space-y-6">
                    {/* Stats Cards */}
                    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
                        <Card>
                            <CardHeader className="pb-3">
                                <CardTitle className="text-sm font-medium text-muted-foreground">Total Workflows</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="text-2xl font-bold">
                                    {statsLoading ? "-" : stats?.total_workflows ?? 0}
                                </div>
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader className="pb-3">
                                <CardTitle className="text-sm font-medium text-muted-foreground">Enabled</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="text-2xl font-bold">
                                    {statsLoading ? "-" : stats?.enabled_workflows ?? 0}
                                </div>
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader className="pb-3">
                                <CardTitle className="text-sm font-medium text-muted-foreground">Success Rate 24h</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="flex items-baseline gap-2">
                                    <div className="text-2xl font-bold">
                                        {statsLoading ? "-" : `${stats?.success_rate_24h?.toFixed(1) ?? 0}%`}
                                    </div>
                                    {stats?.success_rate_24h && stats.success_rate_24h > 95 && (
                                        <div className="flex items-center text-xs font-medium text-green-600">
                                            <TrendingUpIcon className="mr-1 h-3 w-3" />
                                            Good
                                        </div>
                                    )}
                                </div>
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader className="pb-3">
                                <CardTitle className="text-sm font-medium text-muted-foreground">Executions 24h</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="text-2xl font-bold">
                                    {statsLoading ? "-" : stats?.total_executions_24h ?? 0}
                                </div>
                            </CardContent>
                        </Card>
                    </div>

                    {/* Workflow Tabs */}
                    <Tabs
                        value={workflowScopeTab}
                        onValueChange={(v) => {
                            workflowScopeTabTouchedRef.current = true
                            setWorkflowScopeTab(v as "personal" | "org" | "templates")
                        }}
                        className="space-y-4"
                    >
                        <div className="flex items-center justify-between">
                            <TabsList>
                                <TabsTrigger value="personal" className="gap-2">
                                    <UserIcon className="size-4" />
                                    My Workflows
                                </TabsTrigger>
                                <TabsTrigger value="org" className="gap-2">
                                    <BuildingIcon className="size-4" />
                                    Org Workflows
                                </TabsTrigger>
                                <TabsTrigger value="templates" className="gap-2">
                                    <LayoutTemplateIcon className="size-4" />
                                    Workflow Templates
                                </TabsTrigger>
                            </TabsList>
                            {!isTemplatesTab && (
                                <div className="flex items-center gap-2">
                                    {canUseAI && !(activeWorkflowScope === "org" && !canManageAutomation) ? (
                                        <Button
                                            variant="outline"
                                            title="Generate workflow with AI"
                                            render={
                                                <Link
                                                    href={`/automation/ai-builder?mode=workflow&scope=${activeWorkflowScope}`}
                                                />
                                            }
                                        >
                                            <SparklesIcon className="mr-2 size-4" />
                                            Generate with AI
                                        </Button>
                                    ) : (
                                        <Button
                                            variant="outline"
                                            disabled
                                            title={
                                                !canUseAI
                                                    ? "AI is disabled or permission is missing"
                                                    : "Requires manage automation permission"
                                            }
                                        >
                                            <SparklesIcon className="mr-2 size-4" />
                                            Generate with AI
                                        </Button>
                                    )}
                                    <Button onClick={() => handleCreate(activeWorkflowScope)}>
                                        <PlusIcon className="mr-2 size-4" />
                                        {activeWorkflowScope === "personal"
                                            ? "Create Workflow"
                                            : "Create Org Workflow"}
                                    </Button>
                                </div>
                            )}
                        </div>

                        {isTemplatesTab ? (
                            <WorkflowTemplatesPanel embedded />
                        ) : workflowsLoading ? (
                            <div className="flex items-center justify-center py-12">
                                <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                            </div>
                        ) : !workflows?.length ? (
                            <Card>
                                <CardContent className="flex flex-col items-center justify-center py-12">
                                    {activeWorkflowScope === "personal" ? (
                                        <UserIcon className="size-12 text-muted-foreground/50" />
                                    ) : (
                                        <BuildingIcon className="size-12 text-muted-foreground/50" />
                                    )}
                                    <h3 className="mt-4 text-lg font-medium">
                                        {activeWorkflowScope === "personal"
                                            ? "No personal workflows yet"
                                            : "No org workflows yet"}
                                    </h3>
                                    <p className="mt-1 text-sm text-muted-foreground">
                                        {activeWorkflowScope === "personal"
                                            ? "Create personal workflows to automate your tasks"
                                            : "Create organization workflows visible to all team members"
                                        }
                                    </p>
                                    <Button className="mt-4" onClick={() => handleCreate(activeWorkflowScope)}>
                                        <PlusIcon className="mr-2 size-4" />
                                        {activeWorkflowScope === "personal"
                                            ? "Create Workflow"
                                            : "Create Org Workflow"}
                                    </Button>
                                </CardContent>
                            </Card>
                        ) : (
                            [...workflows].sort((a, b) => {
                                // Enabled workflows first
                                if (a.is_enabled !== b.is_enabled) return b.is_enabled ? 1 : -1
                                // Then by name
                                return a.name.localeCompare(b.name)
                            }).map((workflow: WorkflowListItem) => {
                                const IconComponent = triggerIcons[workflow.trigger_type] || WorkflowIcon
                                const canEdit = workflow.can_edit !== false
                                return (
                                    <Card key={workflow.id}>
                                        <CardContent className="flex items-center justify-between p-6">
                                            <div className="flex items-start gap-4">
                                                <div className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-teal-500/10 text-teal-500">
                                                    <IconComponent className="size-6" />
                                                </div>

                                                <div className="flex-1">
                                                    <div className="flex items-center gap-2">
                                                        <h3 className="font-semibold">{workflow.name}</h3>
                                                        {workflow.owner_name && (
                                                            <span className="text-xs text-muted-foreground flex items-center gap-1">
                                                                <UserIcon className="size-3" />
                                                                {workflow.owner_name}
                                                            </span>
                                                        )}
                                                    </div>
                                                    <p className="text-sm text-muted-foreground">{workflow.description || "No description"}</p>
                                                    <div className="mt-2 flex items-center gap-3">
                                                        <Badge variant="secondary" className="text-xs">
                                                            {triggerLabels[workflow.trigger_type] || workflow.trigger_type}
                                                        </Badge>
                                                        <span className="text-xs text-muted-foreground">
                                                            {workflow.run_count} runs • Last run {formatRelativeTime(workflow.last_run_at)}
                                                        </span>
                                                        {workflow.last_error && (
                                                            <Badge variant="destructive" className="text-xs">Has Error</Badge>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>

                                            <div className="flex items-center gap-3">
                                                <Switch
                                                    checked={workflow.is_enabled}
                                                    onCheckedChange={() => handleToggle(workflow.id)}
                                                    disabled={toggleWorkflow.isPending || !canEdit}
                                                    aria-label={`Toggle workflow ${workflow.name}`}
                                                />
                                                <DropdownMenu>
                                                    <DropdownMenuTrigger
                                                        render={
                                                            <Button
                                                                type="button"
                                                                variant="ghost"
                                                                size="icon"
                                                                className="size-8"
                                                                aria-label={`Actions for workflow ${workflow.name}`}
                                                            >
                                                                <MoreVerticalIcon className="size-4" />
                                                            </Button>
                                                        }
                                                    />
                                                    <DropdownMenuContent align="end">
                                                        <DropdownMenuItem onClick={() => handleEdit(workflow.id)} disabled={!canEdit}>
                                                            Edit
                                                        </DropdownMenuItem>
                                                        <DropdownMenuItem onClick={() => handleDuplicate(workflow.id)}>
                                                            Duplicate
                                                        </DropdownMenuItem>
                                                        <DropdownMenuItem onClick={() => handleViewHistory(workflow.id)}>
                                                            View History
                                                        </DropdownMenuItem>
                                                        <DropdownMenuItem onClick={() => handleTest(workflow.id)}>
                                                            Test Workflow
                                                        </DropdownMenuItem>
                                                        <DropdownMenuItem
                                                            className="text-destructive"
                                                            disabled={!canEdit}
                                                            onClick={() => handleDelete(workflow.id)}
                                                        >
                                                            Delete
                                                        </DropdownMenuItem>
                                                    </DropdownMenuContent>
                                                </DropdownMenu>
                                            </div>
                                        </CardContent>
                                    </Card>
                                )
                            })
                        )}
                    </Tabs>
                </div>
            </div>
            <Dialog open={showCreateModal} onOpenChange={setShowCreateModal}>
                <DialogContent className="max-w-2xl">
                    <DialogHeader>
                        <DialogTitle>{editingWorkflowId ? "Edit Workflow" : "Create Workflow"}</DialogTitle>
                        <DialogDescription>Step {wizardStep} of 4</DialogDescription>
                    </DialogHeader>

                    {/* Step Progress */}
                    <div className="flex items-center justify-between w-full">
                        {[1, 2, 3, 4].map((step, index) => (
                            <div key={step} className={`flex items-center ${index < 3 ? 'flex-1' : 'flex-none'}`}>
                                <div
                                    className={`flex size-8 items-center justify-center rounded-full text-sm font-medium ${step === wizardStep
                                        ? "bg-teal-500 text-white"
                                        : step < wizardStep
                                            ? "bg-teal-500/20 text-teal-500"
                                            : "bg-muted text-muted-foreground"
                                        }`}
                                >
                                    {step}
                                </div>
                                {step < 4 && <div className="mx-2 h-0.5 flex-1 bg-muted" />}
                            </div>
                        ))}
                    </div>

                    <div className="py-4">
                        {/* Step 1: Trigger */}
                        {wizardStep === 1 && (
                            <div className="space-y-4">
                                <div>
                                    <Label>Workflow Name *</Label>
                                    <Input
                                        placeholder="e.g., Welcome New Surrogates"
                                        className="mt-1.5"
                                        value={workflowName}
                                        onChange={(e) => setWorkflowName(e.target.value)}
                                    />
                                </div>
                                <div>
                                    <Label>Trigger Type *</Label>
                                    <Select value={triggerType} onValueChange={(v) => v && setTriggerType(v)}>
                                        <SelectTrigger className="mt-1.5 w-full">
                                            <SelectValue placeholder="Select trigger">
                                                {(value: string | null) => {
                                                    if (!value) return "Select trigger"
                                                    const trigger = options?.trigger_types.find(t => t.value === value)
                                                    return trigger?.label ?? triggerLabels[value] ?? "Unknown trigger"
                                                }}
                                            </SelectValue>
                                        </SelectTrigger>
                                        <SelectContent className="min-w-[300px]">
                                            {options?.trigger_types.map((t) => (
                                                <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                                {triggerType === "status_changed" && (
                                    <div className="grid gap-4 md:grid-cols-2">
                                        <div>
                                            <Label>To Stage (Optional)</Label>
                                            <Select
                                                value={typeof triggerConfig.to_stage_id === "string" ? triggerConfig.to_stage_id : ""}
                                                onValueChange={(v) => setTriggerConfig({ ...triggerConfig, to_stage_id: v })}
                                            >
                                                <SelectTrigger className="mt-1.5">
                                                    <SelectValue placeholder="Any stage">
                                                        {(value: string | null) => {
                                                            if (!value) return "Any stage"
                                                            const status = statusOptions.find((s) => s.id === value)
                                                            return status?.label ?? "Unknown stage"
                                                        }}
                                                    </SelectValue>
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="">Any stage</SelectItem>
                                                    {activeStatusOptions.map((s) => (
                                                        <SelectItem key={s.id ?? s.value} value={s.id ?? s.value}>{s.label}</SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        </div>
                                        <div>
                                            <Label>From Stage (Optional)</Label>
                                            <Select
                                                value={typeof triggerConfig.from_stage_id === "string" ? triggerConfig.from_stage_id : ""}
                                                onValueChange={(v) => setTriggerConfig({ ...triggerConfig, from_stage_id: v })}
                                            >
                                                <SelectTrigger className="mt-1.5">
                                                    <SelectValue placeholder="Any stage">
                                                        {(value: string | null) => {
                                                            if (!value) return "Any stage"
                                                            const status = statusOptions.find((s) => s.id === value)
                                                            return status?.label ?? "Unknown stage"
                                                        }}
                                                    </SelectValue>
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="">Any stage</SelectItem>
                                                    {statusOptions.map((s) => (
                                                        <SelectItem key={s.id ?? s.value} value={s.id ?? s.value}>{s.label}</SelectItem>
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
                                                onChange={(e) => setTriggerConfig({ ...triggerConfig, cron: e.target.value })}
                                            />
                                        </div>
                                        <div>
                                            <Label>Timezone</Label>
                                            <Input
                                                placeholder="America/Los_Angeles"
                                                className="mt-1.5"
                                                value={typeof triggerConfig.timezone === "string" ? triggerConfig.timezone : "America/Los_Angeles"}
                                                onChange={(e) => setTriggerConfig({ ...triggerConfig, timezone: e.target.value })}
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
                                            onChange={(e) => setTriggerConfig({ ...triggerConfig, days: Number(e.target.value) })}
                                        />
                                    </div>
                                )}
                                {triggerType === "form_started" && (
                                    <div>
                                        <Label>Form *</Label>
                                        <Select
                                            value={typeof triggerConfig.form_id === "string" ? triggerConfig.form_id : ""}
                                            onValueChange={(value) =>
                                                setTriggerConfig({ ...triggerConfig, form_id: value })
                                            }
                                        >
                                            <SelectTrigger className="mt-1.5">
                                                <SelectValue placeholder="Select form">
                                                    {(value: string | null) => {
                                                        if (!value) return "Select form"
                                                        const form = formOptions.find((option) => option.value === value)
                                                        return form?.label ?? "Unknown form"
                                                    }}
                                                </SelectValue>
                                            </SelectTrigger>
                                            <SelectContent>
                                                {formOptions.map((form) => (
                                                    <SelectItem key={form.value} value={form.value}>
                                                        {form.label}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                        {formOptions.length === 0 && (
                                            <p className="mt-2 text-xs text-muted-foreground">
                                                Publish a form to use this trigger.
                                            </p>
                                        )}
                                    </div>
                                )}
                                {triggerType === "form_submitted" && (
                                    <div>
                                        <Label>Form *</Label>
                                        <Select
                                            value={typeof triggerConfig.form_id === "string" ? triggerConfig.form_id : ""}
                                            onValueChange={(value) =>
                                                setTriggerConfig({ ...triggerConfig, form_id: value })
                                            }
                                        >
                                            <SelectTrigger className="mt-1.5">
                                                <SelectValue placeholder="Select form">
                                                    {(value: string | null) => {
                                                        if (!value) return "Select form"
                                                        const form = formOptions.find((option) => option.value === value)
                                                        return form?.label ?? "Unknown form"
                                                    }}
                                                </SelectValue>
                                            </SelectTrigger>
                                            <SelectContent>
                                                {formOptions.map((form) => (
                                                    <SelectItem key={form.value} value={form.value}>
                                                        {form.label}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                        {formOptions.length === 0 && (
                                            <p className="mt-2 text-xs text-muted-foreground">
                                                Publish a form to use this trigger.
                                            </p>
                                        )}
                                    </div>
                                )}
                                {triggerType === "intake_lead_created" && (
                                    <div>
                                        <Label>Form *</Label>
                                        <Select
                                            value={typeof triggerConfig.form_id === "string" ? triggerConfig.form_id : ""}
                                            onValueChange={(value) =>
                                                setTriggerConfig({ ...triggerConfig, form_id: value })
                                            }
                                        >
                                            <SelectTrigger className="mt-1.5">
                                                <SelectValue placeholder="Select form">
                                                    {(value: string | null) => {
                                                        if (!value) return "Select form"
                                                        const form = formOptions.find((option) => option.value === value)
                                                        return form?.label ?? "Unknown form"
                                                    }}
                                                </SelectValue>
                                            </SelectTrigger>
                                            <SelectContent>
                                                {formOptions.map((form) => (
                                                    <SelectItem key={form.value} value={form.value}>
                                                        {form.label}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                        {formOptions.length === 0 && (
                                            <p className="mt-2 text-xs text-muted-foreground">
                                                Publish a form to use this trigger.
                                            </p>
                                        )}
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
                                            onChange={(e) => setTriggerConfig({ ...triggerConfig, hours_before: Number(e.target.value) })}
                                        />
                                    </div>
                                )}
                                {triggerType === "surrogate_updated" && (
                                    <div className="space-y-3">
                                        <Label>Fields to Watch *</Label>
                                        <div className="flex items-center gap-3">
                                            <Select
                                                value=""
                                                onValueChange={(value) => {
                                                    if (!value || selectedTriggerFields.includes(value)) return
                                                    setTriggerConfig({
                                                        ...triggerConfig,
                                                        fields: [...selectedTriggerFields, value],
                                                    })
                                                }}
                                            >
                                                <SelectTrigger className="flex-1">
                                                    <SelectValue placeholder="Select field to add" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {availableConditionFields.map((field) => (
                                                        <SelectItem key={field} value={field}>
                                                            {getConditionFieldLabel(field)}
                                                        </SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        </div>
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
                                                <SelectValue placeholder="Any user">
                                                    {(value: string | null) => {
                                                        if (!value) return "Any user"
                                                        const user = userOptions.find((u) => u.id === value)
                                                        return user?.display_name ?? "Unknown user"
                                                    }}
                                                </SelectValue>
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="">Any user</SelectItem>
                                                {userOptions.map((user) => (
                                                    <SelectItem key={user.id} value={user.id}>{user.display_name}</SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                )}
                                <div>
                                    <Label>Description</Label>
                                    <Textarea
                                        placeholder="Describe what this workflow does"
                                        className="mt-1.5"
                                        value={workflowDescription}
                                        onChange={(e) => setWorkflowDescription(e.target.value)}
                                    />
                                </div>
                            </div>
                        )}

                        {/* Step 2: Conditions */}
                        {wizardStep === 2 && (
                            <div className="space-y-4">
                                <div className="flex items-center justify-between">
                                    <Label>Conditions (Optional)</Label>
                                    <Button size="sm" variant="outline" onClick={addCondition}>
                                        <PlusIcon className="mr-1 size-3" />
                                        Add Condition
                                    </Button>
                                </div>
                                {conditions.length === 0 ? (
                                    <p className="text-sm text-muted-foreground">No conditions - workflow will run for all matching triggers</p>
                                ) : (
                                    <>
                                        {conditions.map((condition, index) => (
                                            <Card key={condition.clientId}>
                                                <CardContent className="space-y-3 p-4">
                                                    <div className="flex items-center gap-3">
                                                        <Select
                                                            value={condition.field}
                                                            onValueChange={(v) => v && updateCondition(index, { field: v })}
                                                        >
                                                            <SelectTrigger className="flex-1">
                                                                <SelectValue placeholder="Field">
                                                                    {(value: string | null) => {
                                                                        if (!value) return "Field"
                                                                        return getConditionFieldLabel(value)
                                                                    }}
                                                                </SelectValue>
                                                            </SelectTrigger>
                                                            <SelectContent>
                                                                {availableConditionFields.map((f) => (
                                                                    <SelectItem key={f} value={f}>{getConditionFieldLabel(f)}</SelectItem>
                                                                ))}
                                                            </SelectContent>
                                                        </Select>
                                                        <Select
                                                            value={condition.operator}
                                                            onValueChange={(v) => v && updateCondition(index, { operator: v })}
                                                        >
                                                            <SelectTrigger className="w-32">
                                                                <SelectValue placeholder="Operator">
                                                                    {(value: string | null) => {
                                                                        if (!value) return "Operator"
                                                                        const operator = conditionOperators.find(o => o.value === value)
                                                                        return operator?.label ?? "Unknown operator"
                                                                    }}
                                                                </SelectValue>
                                                            </SelectTrigger>
                                                            <SelectContent>
                                                                {conditionOperators.map((o) => (
                                                                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                                                                ))}
                                                            </SelectContent>
                                                        </Select>
                                                        <ConditionValueInput
                                                            condition={condition}
                                                            options={getConditionOptions(condition.field)}
                                                            onChange={(value) => updateCondition(index, { value })}
                                                        />
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
                            </div>
                        )}

                        {/* Step 3: Actions */}
                        {wizardStep === 3 && (
                            <div className="space-y-4">
                                <div className="flex items-center justify-between">
                                    <Label>Actions *</Label>
                                    <Button size="sm" variant="outline" onClick={addAction}>
                                        <PlusIcon className="mr-1 size-3" />
                                        Add Action
                                    </Button>
                                </div>
                                {actions.length === 0 ? (
                                    <p className="text-sm text-muted-foreground">Add at least one action</p>
                                ) : (
                                    actions.map((action, index) => (
                                        <Card key={action.clientId}>
                                            <CardContent className="space-y-3 p-4">
                                                <div className="flex items-center gap-3">
                                                    <GripVerticalIcon className="size-4 text-muted-foreground" />
                                                    <Select
                                                        value={action.action_type}
                                                        onValueChange={(v) => v && updateAction(index, { action_type: v })}
                                                    >
                                                        <SelectTrigger className="flex-1">
                                                            <SelectValue placeholder="Action type">
                                                                {(value: string | null) => {
                                                                    if (!value) return "Action type"
                                                                    const actionType = actionTypeOptions.find(a => a.value === value)
                                                                    return actionType?.label ?? "Unknown action type"
                                                                }}
                                                            </SelectValue>
                                                        </SelectTrigger>
                                                        <SelectContent>
                                                            {filteredActionTypes.map((a) => (
                                                                <SelectItem key={a.value} value={a.value}>{a.label}</SelectItem>
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
                                                    <div className="space-y-3">
                                                        <Select
                                                            value={typeof action.template_id === "string" ? action.template_id : ""}
                                                            onValueChange={(v) => v && updateAction(index, { template_id: v })}
                                                        >
                                                            <SelectTrigger>
                                                                <SelectValue placeholder="Select email template">
                                                                    {(value: string | null) => {
                                                                        if (!value) return "Select email template"
                                                                        const template = options?.email_templates.find(t => t.id === value)
                                                                        return template?.name ?? "Unknown template"
                                                                    }}
                                                                </SelectValue>
                                                            </SelectTrigger>
                                                            <SelectContent>
                                                                {options?.email_templates.map((t) => (
                                                                    <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>
                                                                ))}
                                                            </SelectContent>
                                                        </Select>
                                                        <div className="grid gap-2">
                                                            <Label>Recipient</Label>
                                                            <Select
                                                                value={getEmailRecipientKind(action)}
                                                                onValueChange={(value) => {
                                                                    if (value === "user") {
                                                                        const currentUser = getEmailRecipientUserId(action)
                                                                        updateAction(index, {
                                                                            recipients: currentUser ? [currentUser] : [],
                                                                        })
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
                                                                onValueChange={(value) =>
                                                                    updateAction(index, { recipients: value ? [value] : [] })
                                                                }
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
                                                )}
                                                {action.action_type === "create_task" && (
                                                    <div className="space-y-3">
                                                        <Input
                                                            placeholder="Task title"
                                                            value={typeof action.title === "string" ? action.title : ""}
                                                            onChange={(e) => updateAction(index, { title: e.target.value })}
                                                        />
                                                        <Textarea
                                                            placeholder="Task description (optional)"
                                                            value={typeof action.description === "string" ? action.description : ""}
                                                            onChange={(e) => updateAction(index, { description: e.target.value })}
                                                            rows={2}
                                                        />
                                                        <div className="grid gap-3 md:grid-cols-2">
                                                            <Input
                                                                type="number"
                                                                min={0}
                                                                max={365}
                                                                placeholder="Due in days"
                                                                value={typeof action.due_days === "number" ? action.due_days : 1}
                                                                onChange={(e) =>
                                                                    updateAction(index, { due_days: Number(e.target.value) })
                                                                }
                                                            />
                                                            <Select
                                                                value={typeof action.assignee === "string" ? action.assignee : "owner"}
                                                                onValueChange={(v) => v && updateAction(index, { assignee: v })}
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
                                                )}
                                                {action.action_type === "send_notification" && (
                                                    <div className="space-y-3">
                                                        <Input
                                                            placeholder="Notification title"
                                                            value={typeof action.title === "string" ? action.title : ""}
                                                            onChange={(e) => updateAction(index, { title: e.target.value })}
                                                        />
                                                        <Textarea
                                                            placeholder="Notification body (optional)"
                                                            value={typeof action.body === "string" ? action.body : ""}
                                                            onChange={(e) => updateAction(index, { body: e.target.value })}
                                                            rows={2}
                                                        />
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
                                                                <SelectValue placeholder="Recipients" />
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
                                                    </div>
                                                )}
                                                {action.action_type === "assign_surrogate" && (
                                                    <div className="space-y-3">
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
                                                                <SelectItem value="user">User</SelectItem>
                                                                <SelectItem value="queue">Queue</SelectItem>
                                                            </SelectContent>
                                                        </Select>
                                                        <Select
                                                            value={typeof action.owner_id === "string" ? action.owner_id : ""}
                                                            onValueChange={(value) => value && updateAction(index, { owner_id: value })}
                                                        >
                                                            <SelectTrigger>
                                                                <SelectValue placeholder="Select owner" />
                                                            </SelectTrigger>
                                                            <SelectContent>
                                                                {(action.owner_type === "queue" ? queueOptions : userOptions).map(
                                                                    (owner) => (
                                                                        <SelectItem key={owner.id} value={owner.id}>
                                                                            {"name" in owner ? owner.name : owner.display_name}
                                                                        </SelectItem>
                                                                    )
                                                                )}
                                                            </SelectContent>
                                                        </Select>
                                                    </div>
                                                )}
                                                {action.action_type === "update_field" && (
                                                    <div className="space-y-3">
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
                                                        {action.field === "stage_id" ? (
                                                            <Select
                                                                value={typeof action.value === "string" ? action.value : ""}
                                                                onValueChange={(value) => value && updateAction(index, { value })}
                                                            >
                                                                <SelectTrigger>
                                                                    <SelectValue placeholder="Select stage" />
                                                                </SelectTrigger>
                                                                <SelectContent>
                                                                    {statusOptions.map((stage) => (
                                                                        <SelectItem key={stage.id ?? stage.value} value={stage.id ?? stage.value}>
                                                                            {stage.label}
                                                                        </SelectItem>
                                                                    ))}
                                                                </SelectContent>
                                                            </Select>
                                                        ) : action.field === "is_priority" ? (
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
                                                        ) : action.field === "owner_type" ? (
                                                            <Select
                                                                value={typeof action.value === "string" ? action.value : ""}
                                                                onValueChange={(value) => value && updateAction(index, { value })}
                                                            >
                                                                <SelectTrigger>
                                                                    <SelectValue placeholder="Select owner type" />
                                                                </SelectTrigger>
                                                                <SelectContent>
                                                                    <SelectItem value="user">User</SelectItem>
                                                                    <SelectItem value="queue">Queue</SelectItem>
                                                                </SelectContent>
                                                            </Select>
                                                        ) : action.field === "owner_id" ? (
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
                                                        ) : (
                                                            <Input
                                                                placeholder="Value"
                                                                value={typeof action.value === "string" ? action.value : ""}
                                                                onChange={(e) => updateAction(index, { value: e.target.value })}
                                                            />
                                                        )}
                                                    </div>
                                                )}
                                                {action.action_type === "add_note" && (
                                                    <Textarea
                                                        placeholder="Note content"
                                                        value={typeof action.content === "string" ? action.content : ""}
                                                        onChange={(e) => updateAction(index, { content: e.target.value })}
                                                        rows={2}
                                                    />
                                                )}
                                                {action.action_type === "auto_match_submission" && (
                                                    <p className="rounded-md border p-3 text-sm text-muted-foreground">
                                                        Runs deterministic matching using name + DOB + phone/email and updates the
                                                        submission to linked or ambiguous review.
                                                    </p>
                                                )}
                                                {action.action_type === "create_intake_lead" && (
                                                    <div className="space-y-2">
                                                        <Input
                                                            placeholder="Source (optional, e.g. event_qr)"
                                                            value={typeof action.source === "string" ? action.source : ""}
                                                            onChange={(e) => updateAction(index, { source: e.target.value })}
                                                        />
                                                        <p className="text-xs text-muted-foreground">
                                                            Skips automatically if the submission is already linked or has ambiguous
                                                            match candidates.
                                                        </p>
                                                    </div>
                                                )}
                                                {action.action_type === "promote_intake_lead" && (
                                                    <div className="space-y-3">
                                                        <Input
                                                            placeholder="Source (optional, e.g. manual)"
                                                            value={typeof action.source === "string" ? action.source : ""}
                                                            onChange={(e) => updateAction(index, { source: e.target.value })}
                                                        />
                                                        <div className="flex items-center justify-between rounded-md border p-3">
                                                            <div className="text-sm">Mark as priority</div>
                                                            <Switch
                                                                checked={typeof action.is_priority === "boolean" ? action.is_priority : false}
                                                                onCheckedChange={(checked) =>
                                                                    updateAction(index, { is_priority: checked })
                                                                }
                                                            />
                                                        </div>
                                                        <div className="flex items-center justify-between rounded-md border p-3">
                                                            <div className="text-sm">Assign to workflow owner if available</div>
                                                            <Switch
                                                                checked={typeof action.assign_to_user === "boolean" ? action.assign_to_user : false}
                                                                onCheckedChange={(checked) =>
                                                                    updateAction(index, { assign_to_user: checked })
                                                                }
                                                            />
                                                        </div>
                                                    </div>
                                                )}
                                                {/* Requires Approval Toggle */}
                                                {action.action_type &&
                                                    !["promote_intake_lead"].includes(
                                                        action.action_type
                                                    ) && (
                                                    <div className="flex items-center justify-between pt-2 border-t mt-2">
                                                        <div className="flex flex-col">
                                                            <Label htmlFor={`approval-${action.clientId}`} className="text-sm font-medium">
                                                                Requires Approval
                                                            </Label>
                                                            <span className="text-xs text-muted-foreground">
                                                                Surrogate owner must approve before this action runs
                                                            </span>
                                                        </div>
                                                        <Switch
                                                            id={`approval-${action.clientId}`}
                                                            checked={!!action.requires_approval}
                                                            onCheckedChange={(checked) => updateAction(index, { requires_approval: checked })}
                                                        />
                                                    </div>
                                                )}
                                            </CardContent>
                                        </Card>
                                    ))
                                )}
                            </div>
                        )}

                        {/* Step 4: Review */}
                        {wizardStep === 4 && (
                            <div className="space-y-4">
                                <div className="rounded-lg border p-4">
                                    <h3 className="mb-3 font-semibold">Workflow Summary</h3>
                                    <div className="space-y-2 text-sm">
                                        <div className="flex justify-between">
                                            <span className="text-muted-foreground">Name:</span>
                                            <span className="font-medium">{workflowName || "Untitled"}</span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-muted-foreground">Trigger:</span>
                                            <Badge variant="secondary">{triggerLabels[triggerType] || triggerType}</Badge>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-muted-foreground">Conditions:</span>
                                            <span>{conditions.length} condition{conditions.length !== 1 ? "s" : ""}</span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-muted-foreground">Actions:</span>
                                            <span>{actions.length} action{actions.length !== 1 ? "s" : ""}</span>
                                        </div>
                                    </div>
                                </div>
                                {!workflowValidationError && !hasServerErrors ? (
                                    <div className="flex items-center gap-2 rounded-lg border border-teal-500/20 bg-teal-500/5 p-3 text-sm">
                                        <CheckCircle2Icon className="size-4 text-teal-500" />
                                        <span>Ready to activate workflow</span>
                                    </div>
                                ) : (
                                    <div className="flex items-center gap-2 rounded-lg border border-destructive/20 bg-destructive/5 p-3 text-sm">
                                        <AlertCircleIcon className="size-4 text-destructive" />
                                        <span>Please fill in all required fields</span>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>

                    {hasServerErrors && (
                        <div className="mt-4 flex items-start gap-3 rounded-lg border border-destructive/20 bg-destructive/5 p-3 text-sm">
                            <AlertCircleIcon className="mt-0.5 size-4 text-destructive" />
                            <div className="space-y-2">
                                <p className="font-medium text-destructive">Fix these errors</p>
                                <ul className="space-y-1 text-xs text-destructive">
                                    {serverErrors.map((message) => (
                                        <li key={message}>• {message}</li>
                                    ))}
                                </ul>
                            </div>
                        </div>
                    )}
                    {validationError && (
                        <div className="mt-4 flex items-center gap-2 rounded-lg border border-destructive/20 bg-destructive/5 p-3 text-sm">
                            <AlertCircleIcon className="size-4 text-destructive" />
                            <span>{validationError}</span>
                        </div>
                    )}
                    <DialogFooter>
                        {wizardStep > 1 && (
                            <Button
                                variant="outline"
                                onClick={() => {
                                    setValidationError(null)
                                    setWizardStep(wizardStep - 1)
                                }}
                            >
                                Back
                            </Button>
                        )}
                        {wizardStep < 4 ? (
                            <Button onClick={handleNextStep}>
                                Next
                                <ChevronRightIcon className="ml-1 size-4" />
                            </Button>
                        ) : (
                            <Button
                                onClick={handleSaveWorkflow}
                                disabled={!!workflowValidationError || hasServerErrors || createWorkflow.isPending || updateWorkflow.isPending}
                            >
                                {(createWorkflow.isPending || updateWorkflow.isPending) ? (
                                    <Loader2Icon className="mr-2 size-4 animate-spin" />
                                ) : null}
                                {editingWorkflowId ? "Save Changes" : "Create Workflow"}
                            </Button>
                        )}
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Email Template Modal */}
            <Dialog open={isTemplateModalOpen} onOpenChange={handleTemplateModalOpenChange}>
                <DialogContent className="max-w-2xl">
                    <DialogHeader>
                        <DialogTitle>{editingTemplate ? "Edit Template" : "New Email Template"}</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        <div>
                            <Label>Template Name</Label>
                            <Input
                                value={templateName}
                                onChange={(e) => setTemplateName(e.target.value)}
                                placeholder="e.g., Welcome Email"
                                className="mt-1.5"
                            />
                        </div>
                        <div>
                            <Label>Subject</Label>
                            <Input
                                value={templateSubject}
                                onChange={(e) => setTemplateSubject(e.target.value)}
                                placeholder="Email subject line"
                                className="mt-1.5"
                            />
                        </div>
                        <div>
                            <Label>Body</Label>
                            <Textarea
                                value={templateBody}
                                onChange={(e) => setTemplateBody(e.target.value)}
                                placeholder="Email body content..."
                                className="mt-1.5 min-h-[200px]"
                            />
                            <p className="mt-1 text-xs text-muted-foreground">
                                Available variables: {"{{first_name}}"}, {"{{full_name}}"}, {"{{email}}"}, {"{{status_label}}"}, {"{{org_name}}"}, {"{{unsubscribe_url}}"}
                            </p>
                        </div>
                    </div>
                    <DialogFooter>
                        {editingTemplate && (
                            <Button
                                variant="destructive"
                                onClick={() => {
                                    deleteTemplate.mutate(editingTemplate.id)
                                    setEmailTemplateModal(INITIAL_EMAIL_TEMPLATE_MODAL_STATE)
                                }}
                            >
                                Delete
                            </Button>
                        )}
                        <Button
                            variant="outline"
                            onClick={() => setEmailTemplateModal(INITIAL_EMAIL_TEMPLATE_MODAL_STATE)}
                        >
                            Cancel
                        </Button>
                        <Button onClick={handleSaveTemplate} disabled={createTemplate.isPending || updateTemplate.isPending}>
                            {(createTemplate.isPending || updateTemplate.isPending) && (
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                            )}
                            {editingTemplate ? "Save Changes" : "Create Template"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Execution History Panel */}
            <Sheet open={showHistoryPanel} onOpenChange={setShowHistoryPanel}>
                <SheetContent className="w-[500px] sm:max-w-[500px]">
                    <SheetHeader>
                        <SheetTitle>Execution History</SheetTitle>
                        <SheetDescription>Recent workflow execution logs</SheetDescription>
                    </SheetHeader>
                    <ScrollArea className="h-[calc(100vh-8rem)] pr-4">
                        <div className="mt-6 space-y-4">
                            {!executions?.items?.length ? (
                                <p className="text-sm text-muted-foreground">No execution history yet</p>
                            ) : (
                                executions.items.map((execution, index) => (
                                    <div key={execution.id} className="relative">
                                        {index < executions.items.length - 1 && (
                                            <div className="absolute left-2 top-8 h-full w-0.5 bg-border" />
                                        )}
                                        <div className="flex gap-3">
                                            <div
                                                className={`relative z-10 mt-1 flex size-4 shrink-0 items-center justify-center rounded-full ${execution.status === "success" ? "bg-green-500" :
                                                    execution.status === "partial" ? "bg-yellow-500" :
                                                        execution.status === "skipped" ? "bg-gray-400" : "bg-red-500"
                                                    }`}
                                            >
                                                <div className="size-2 rounded-full bg-white" />
                                            </div>
                                            <div className="flex-1 pb-4">
                                                <div className="flex items-start justify-between">
                                                    <div>
                                                        <p className="font-medium">{execution.entity_type}: {execution.entity_id.slice(0, 8)}...</p>
                                                        <p className="text-sm text-muted-foreground">{formatRelativeTime(execution.executed_at)}</p>
                                                    </div>
                                                    <Badge
                                                        variant={execution.status === "success" ? "default" :
                                                            execution.status === "skipped" ? "secondary" : "destructive"}
                                                        className="text-xs"
                                                    >
                                                        {execution.status}
                                                    </Badge>
                                                </div>
                                                <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
                                                    <span>Duration: {execution.duration_ms}ms</span>
                                                    <span>Actions: {execution.actions_executed.length}</span>
                                                </div>
                                                {execution.error_message && (
                                                    <p className="mt-2 rounded-md bg-destructive/10 p-2 text-xs text-destructive">
                                                        {execution.error_message}
                                                    </p>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </ScrollArea>
                </SheetContent>
            </Sheet>

            {/* Test Workflow Dialog */}
            <Dialog open={showTestModal} onOpenChange={handleTestDialogOpenChange}>
                <DialogContent className="max-w-lg">
                    <DialogHeader>
                        <DialogTitle>Test Workflow</DialogTitle>
                        <DialogDescription>
                            Test this workflow against a specific {testEntityType} (dry run - no changes will be made)
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label>{ENTITY_LABELS[testEntityType] ?? "Entity ID"}</Label>
                            <Input
                                placeholder={`Enter ${testEntityType} UUID...`}
                                list="workflow-test-entity-options"
                                value={testEntityQuery}
                                onChange={(e) => {
                                    setTestEntityQuery(e.target.value)
                                    setTestEntityId(e.target.value)
                                }}
                            />
                            <datalist id="workflow-test-entity-options">
                                {testEntitySuggestions.map((item) => (
                                    <option key={item.id} value={item.id}>
                                        {item.label}
                                    </option>
                                ))}
                            </datalist>
                            <p className="text-xs text-muted-foreground">
                                {testEntityType === "note" || testEntityType === "document"
                                    ? "Type a keyword to search notes or documents."
                                    : "Start typing to see recent suggestions."}
                            </p>
                        </div>

                        {testEntitySuggestionsLoading ? (
                            <div className="text-xs text-muted-foreground">Loading suggestions...</div>
                        ) : testEntitySuggestions.length > 0 ? (
                            <div className="space-y-2 rounded-lg border p-3">
                                <p className="text-xs font-medium text-muted-foreground">
                                    Suggested {ENTITY_PLURALS[testEntityType] ?? `${testEntityType}s`}
                                </p>
                                <div className="space-y-2">
                                    {testEntitySuggestions.map((item) => (
                                        <button
                                            key={item.id}
                                            type="button"
                                            className="flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-sm hover:bg-muted"
                                            onClick={() => {
                                                setTestEntityId(item.id)
                                                setTestEntityQuery(item.id)
                                            }}
                                        >
                                            <span className="font-medium">{item.label}</span>
                                            {item.meta && (
                                                <span className="text-xs text-muted-foreground">{item.meta}</span>
                                            )}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        ) : null}

                        {testResult && (
                            <div className="space-y-3 rounded-lg border p-4">
                                <div className="flex items-center gap-2">
                                    {testResult.conditions_matched ? (
                                        <CheckCircle2Icon className="size-5 text-emerald-500" />
                                    ) : (
                                        <XIcon className="size-5 text-red-500" />
                                    )}
                                    <span className="font-medium">
                                        {testResult.conditions_matched ? "Conditions Match" : "Conditions Not Met"}
                                    </span>
                                </div>

                                {testResult.conditions_evaluated.length > 0 && (
                                    <div className="space-y-2">
                                        <p className="text-sm font-medium">Condition Results:</p>
                                        {testResult.conditions_evaluated.map((cond) => (
                                            <div
                                                key={`${cond.field}-${cond.operator}-${String(cond.expected)}-${String(cond.actual)}-${cond.result ? "matched" : "unmatched"}`}
                                                className="flex items-center justify-between rounded bg-muted/50 px-3 py-2 text-sm"
                                            >
                                                <span>{cond.field} {cond.operator} {String(cond.expected)}</span>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-muted-foreground">Actual: {cond.actual}</span>
                                                    {cond.result ? (
                                                        <CheckCircle2Icon className="size-4 text-emerald-500" />
                                                    ) : (
                                                        <XIcon className="size-4 text-red-500" />
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}

                                {testResult.conditions_matched && testResult.actions_preview.length > 0 && (
                                    <div className="space-y-2">
                                        <p className="text-sm font-medium">Actions that would run:</p>
                                        {testResult.actions_preview.map((action) => (
                                            <div key={`${action.action_type}-${action.description}`} className="rounded bg-muted/50 px-3 py-2 text-sm">
                                                <span className="font-medium">{action.action_type}:</span> {action.description}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>

                    <DialogFooter>
                        <Button
                            variant="outline"
                            onClick={() => dispatchTestWorkflow({ type: "close" })}
                        >
                            Close
                        </Button>
                        <Button
                            onClick={handleRunTest}
                            disabled={!testEntityId || testWorkflowMutation.isPending}
                        >
                            {testWorkflowMutation.isPending ? (
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                            ) : null}
                            Run Test
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div >
    )
}
