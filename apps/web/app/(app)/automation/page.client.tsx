"use client"

import { useReducer, useState } from "react"
import { useRouter } from "next/navigation"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
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
import {
    PlusIcon,
    MoreVerticalIcon,
    UserIcon,
    CheckCircle2Icon,
    XIcon,
    WorkflowIcon,
    LayoutTemplateIcon,
    Loader2Icon,
    BuildingIcon,
    SparklesIcon,
    HistoryIcon,
} from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import {
    useWorkflows,
    useWorkflowStats,
    useWorkflowOptions,
    useWorkflowExecutions,
    useDeleteWorkflow,
    useToggleWorkflow,
    useDuplicateWorkflow,
    usePublishWorkflow,
    useTestWorkflow,
} from "@/lib/hooks/use-workflows"
import type {
    WorkflowListItem,
    WorkflowTestResponse,
    WorkflowScope,
    WorkflowExecution,
} from "@/lib/api/workflows"
import { useAuth } from "@/lib/auth-context"
import { usePermissionCheck } from "@/lib/hooks/use-permission-check"
import { EmptyState } from "@/components/empty-state"
import { QueryErrorState } from "@/components/error-state"
import { toast } from "@/components/ui/toast"
import { useCreateEmailTemplate, useUpdateEmailTemplate, useDeleteEmailTemplate } from "@/lib/hooks/use-email-templates"
import type { EmailTemplateListItem } from "@/lib/api/email-templates"
import { globalSearch } from "@/lib/api/search"
import WorkflowTemplatesPanel from "@/components/automation/workflow-templates-panel"
import Link from "@/components/app-link"
import { getAppointments } from "@/lib/api/appointments"
import { listMatches, type ListMatchesParams } from "@/lib/api/matches"
import { getTasks, type TaskListParams } from "@/lib/api/tasks"
import { getSurrogates, type SurrogateListParams } from "@/lib/api/surrogates"
import { listDonors } from "@/lib/api/donors"
import { getWorkflowExecutionStatusLabel } from "@/lib/constants/workflow-execution-status"
import { parseDateInput } from "@/lib/utils/date"
import { TRIGGER_ICONS } from "@/components/automation/workflow-editor/node-meta"
import {
    WORKFLOW_SUBJECT_LABELS,
    getTriggerLabel,
    isDonorSubject,
} from "@/lib/workflows/workflow-editor-state"
import { AutomationPageHeader } from "./components/automation-page-header"
import { WorkflowStatsCards } from "./components/workflow-stats-cards"

function getDonorExecutionLink(execution: WorkflowExecution): string | null {
    if (
        execution.subject_type &&
        isDonorSubject(execution.subject_type) &&
        execution.subject_id &&
        getDonorExecutionIdentityLabel(execution)
    ) {
        return `/donors/${execution.subject_id}`
    }
    return null
}

function getDonorExecutionIdentityLabel(execution: WorkflowExecution): string | null {
    const name = execution.entity_name?.trim()
    const number = execution.entity_number?.trim()
    if (number && name) return `${number} — ${name}`
    return number || name || null
}

function WorkflowExecutionRecordLink({ execution }: { execution: WorkflowExecution }) {
    const isDonorExecution = execution.subject_type
        ? isDonorSubject(execution.subject_type)
        : false
    const donorLabel = isDonorExecution
        ? getDonorExecutionIdentityLabel(execution) ?? "Donor unavailable"
        : null
    const donorLink = getDonorExecutionLink(execution)
    if (donorLink && donorLabel) {
        return (
            <Link href={donorLink} className="font-medium text-primary hover:underline">
                {donorLabel}
            </Link>
        )
    }
    if (donorLabel) return <p className="font-medium">{donorLabel}</p>
    return (
        <p className="font-medium">
            {execution.entity_type}: {execution.entity_id.slice(0, 8)}&hellip;
        </p>
    )
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
    egg_donor: "Egg Donor ID",
    sperm_donor: "Sperm Donor ID",
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
    egg_donor: "egg donors",
    sperm_donor: "sperm donors",
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
    if (entityType === "egg_donor" || entityType === "sperm_donor") {
        const response = await listDonors({
            donor_type: entityType === "egg_donor" ? "egg" : "sperm",
            per_page: 5,
            page: 1,
            ...(query.trim() ? { q: query.trim() } : {}),
        })
        return response.items.map((item) =>
            buildTestEntitySuggestion(
                item.id,
                `${item.donor_number} — ${item.full_name}`,
                item.status_label,
            ),
        )
    }
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

type AutomationTab = "workflows" | "email-templates" | "campaigns"
type AutomationWorkflowScopeTab = "personal" | "org" | "templates"

type AutomationPageClientProps = {
    initialTab: AutomationTab
    initialWorkflowScopeTab: AutomationWorkflowScopeTab
    hasInitialScopeParam?: boolean
}

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

function useAutomationPageView({
    initialTab,
    initialWorkflowScopeTab,
    hasInitialScopeParam = false,
}: AutomationPageClientProps) {
    const { push } = useRouter()
    const { user } = useAuth()
    const { can, policyVersion } = usePermissionCheck()
    const canUseAI = Boolean(user?.ai_enabled) && can("use_ai_assistant")
    const canManageAutomation = can("manage_automation")
    const policyV2 = (policyVersion ?? 1) >= 2
    const canManageOrgWorkflows = canManageAutomation && (!policyV2 || can("manage_org_workflows"))
    const [detailsWorkflow, setDetailsWorkflow] = useState<WorkflowListItem | null>(null)
    const [activeTab] = useState(initialTab)

    const [workflowScopeSelection, setWorkflowScopeSelection] = useState<{
        tab: "personal" | "org" | "templates"
        touched: boolean
    }>({
        tab: initialWorkflowScopeTab,
        touched: false,
    })
    const workflowScopeTab =
        !hasInitialScopeParam &&
        canManageOrgWorkflows &&
        !workflowScopeSelection.touched &&
        workflowScopeSelection.tab === "personal"
            ? "org"
            : workflowScopeSelection.tab
    const [testWorkflowState, dispatchTestWorkflow] = useReducer(
        testWorkflowReducer,
        INITIAL_TEST_WORKFLOW_STATE
    )
    const [emailTemplateModal, setEmailTemplateModal] = useState(INITIAL_EMAIL_TEMPLATE_MODAL_STATE)
    const [showHistoryDialog, setShowHistoryDialog] = useState(false)
    const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null)

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
    // Mirrors workflow_access.can_create: org workflows need manage_automation (plus
    // manage_org_workflows under policy v2); personal workflows are open under v1 and need
    // manage_automation under v2.
    const canCreatePersonal = !policyV2 || canManageAutomation
    const canCreateInActiveScope = activeWorkflowScope === "org" ? canManageOrgWorkflows : canCreatePersonal

    // API hooks
    const workflowsQuery = useWorkflows({ scope: activeWorkflowScope })
    const { data: workflows, isLoading: workflowsLoading } = workflowsQuery
    const { data: stats, isLoading: statsLoading } = useWorkflowStats()
    const { data: executions } = useWorkflowExecutions(selectedWorkflowId || "", { limit: 20 })
    const historyWorkflowName = workflows?.find((workflow) => workflow.id === selectedWorkflowId)?.name

    const selectedTestWorkflow = workflows?.find((workflow) => workflow.id === testWorkflowId)
    const testTriggerType = selectedTestWorkflow?.trigger_type
    const testSubjectType = selectedTestWorkflow?.subject_type ?? "surrogate"
    const { data: testOptions } = useWorkflowOptions(activeWorkflowScope, testSubjectType)
    const testTriggerEntityTypes = testOptions?.trigger_entity_types ?? {}
    const testEntityType = isDonorSubject(testSubjectType)
        ? testSubjectType
        : testTriggerType
            ? testTriggerEntityTypes[testTriggerType] ?? "surrogate"
            : "surrogate"
    const isTestDonorEntity = testEntityType === "egg_donor" || testEntityType === "sperm_donor"
    const testEntityInputLabel = isTestDonorEntity
        ? WORKFLOW_SUBJECT_LABELS[testEntityType]
        : ENTITY_LABELS[testEntityType] ?? "Entity ID"
    const testEntityLabel = testEntityInputLabel.replace(/ ID$/, "")

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

    const toggleWorkflow = useToggleWorkflow()
    const duplicateWorkflow = useDuplicateWorkflow()
    const publishWorkflow = usePublishWorkflow()
    const deleteWorkflow = useDeleteWorkflow()
    const testWorkflowMutation = useTestWorkflow()

    // Email template hooks
    const createTemplate = useCreateEmailTemplate()
    const updateTemplate = useUpdateEmailTemplate()
    const deleteTemplate = useDeleteEmailTemplate()

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
        setShowHistoryDialog(true)
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

    // The editor is its own page; the scope decides which list the editor returns to.
    const handleCreate = (scope: WorkflowScope = activeWorkflowScope) => {
        push(`/automation/workflows/new?scope=${scope}`)
    }

    const handleEdit = (workflowId: string) => {
        push(`/automation/workflows/${workflowId}`)
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

    return (
        <div className="flex min-h-screen flex-col">
            <AutomationPageHeader
                activeTab={activeTab}
                onOpenExecutions={() => push("/automation/executions")}
                onCreateTemplate={() => handleOpenTemplateModal()}
                canViewExecutions={canManageOrgWorkflows}
                onCreateWorkflow={isTemplatesTab && canCreatePersonal ? () => handleCreate("personal") : undefined}
            />

            <Dialog open={detailsWorkflow !== null} onOpenChange={(open) => !open && setDetailsWorkflow(null)}>
                <DialogContent>
                    <DialogHeader><DialogTitle>{detailsWorkflow?.name}</DialogTitle></DialogHeader>
                    <dl className="grid grid-cols-2 gap-x-6 gap-y-4 text-sm">
                        <dt className="text-muted-foreground">Scope</dt><dd>{detailsWorkflow?.scope === "personal" ? "Personal" : "Organization"}</dd>
                        {detailsWorkflow?.owner_name && <><dt className="text-muted-foreground">Owner</dt><dd>{detailsWorkflow.owner_name}</dd></>}
                        <dt className="text-muted-foreground">Proposed by</dt><dd>{detailsWorkflow?.proposed_by_name ?? "—"}</dd>
                        <dt className="text-muted-foreground">Created</dt><dd>{detailsWorkflow ? new Date(detailsWorkflow.created_at).toLocaleDateString() : "—"}</dd>
                    </dl>
                </DialogContent>
            </Dialog>
            {/* Main Content */}
            <div className="flex-1 p-6">
                <div className="space-y-6">
                    <WorkflowStatsCards stats={stats} isLoading={statsLoading} />

                    {/* Workflow Tabs */}
                    <Tabs
                        value={workflowScopeTab}
                        onValueChange={(v) => {
                            setWorkflowScopeSelection({
                                tab: v as "personal" | "org" | "templates",
                                touched: true,
                            })
                        }}
                        className="space-y-4"
                    >
                        <div className="flex flex-wrap items-center justify-between gap-3">
                            <TabsList
                                aria-label="Workflow scope"
                                className="max-w-full justify-start overflow-x-auto"
                            >
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
                            {!isTemplatesTab && canCreateInActiveScope && (
                                <div className="flex flex-wrap items-center gap-2">
                                    {canUseAI ? (
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
                                            title="AI is disabled or permission is missing"
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
                        ) : workflowsQuery.isError && workflows === undefined ? (
                            <Card className="py-0">
                                <QueryErrorState
                                    error={workflowsQuery.error}
                                    onRetry={() => {
                                        void workflowsQuery.refetch()
                                    }}
                                    isRetrying={workflowsQuery.isFetching}
                                    title="Couldn't load workflows"
                                    headingLevel={3}
                                />
                            </Card>
                        ) : !workflows?.length ? (
                            <Card className="py-0">
                                <EmptyState
                                    icon={activeWorkflowScope === "personal" ? UserIcon : BuildingIcon}
                                    title={
                                        activeWorkflowScope === "personal"
                                            ? "No personal workflows yet"
                                            : "No org workflows yet"
                                    }
                                    headingLevel={3}
                                    action={
                                        canCreateInActiveScope ? (
                                            <Button onClick={() => handleCreate(activeWorkflowScope)}>
                                                <PlusIcon className="mr-2 size-4" />
                                                {activeWorkflowScope === "personal"
                                                    ? "Create Workflow"
                                                    : "Create Org Workflow"}
                                            </Button>
                                        ) : undefined
                                    }
                                />
                            </Card>
                        ) : (
                            workflows.toSorted((a, b) => {
                                // Enabled workflows first
                                if (a.is_enabled !== b.is_enabled) return b.is_enabled ? 1 : -1
                                // Then by name
                                return a.name.localeCompare(b.name)
                            }).map((workflow: WorkflowListItem) => {
                                const IconComponent = TRIGGER_ICONS[workflow.trigger_type] || WorkflowIcon
                                const canEdit = workflow.can_edit !== false
                                return (
                                    <Card key={workflow.id} className="py-0">
                                        <CardContent className="flex items-center justify-between gap-4 px-4 py-3">
                                            <div className="flex min-w-0 items-start gap-3">
                                                <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-teal-500/10 text-teal-500">
                                                    <IconComponent className="size-5" />
                                                </div>

                                                <div className="min-w-0 flex-1">
                                                    <div className="flex items-center gap-2">
                                                        <h3 className="font-semibold">{workflow.name}</h3>
                                                        {workflow.owner_name && (
                                                            <span className="text-xs text-muted-foreground flex items-center gap-1">
                                                                <UserIcon className="size-3" />
                                                                {workflow.owner_name}
                                                            </span>
                                                        )}
                                                    </div>
                                                    <p className="truncate text-sm text-muted-foreground">{workflow.description || "No description"}</p>
                                                    <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
                                                        <Badge variant="outline" className="text-xs">
                                                            {WORKFLOW_SUBJECT_LABELS[workflow.subject_type ?? "surrogate"]}
                                                        </Badge>
                                                        <Badge variant="secondary" className="text-xs">
                                                            {getTriggerLabel(workflow.trigger_type)}
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
                                                                <MoreVerticalIcon className="size-4" aria-hidden="true" />
                                                            </Button>
                                                        }
                                                    />
                                                    <DropdownMenuContent align="end">
                                                        <DropdownMenuItem onClick={() => handleEdit(workflow.id)} disabled={!canEdit}>
                                                            Edit
                                                        </DropdownMenuItem>
                                                        <DropdownMenuItem disabled={!canEdit} onClick={() => handleDuplicate(workflow.id)}>
                                                            Duplicate
                                                        </DropdownMenuItem>
                                                        <DropdownMenuItem onClick={() => setDetailsWorkflow(workflow)}>Details</DropdownMenuItem>
                                                        {workflow.can_publish && <DropdownMenuItem disabled={publishWorkflow.isPending} onClick={() => publishWorkflow.mutate(workflow.id, {
                                                            onSuccess: () => { toast.success("Organization workflow created"); setWorkflowScopeSelection({ tab: "org", touched: true }) },
                                                            onError: (error) => toast.error(error instanceof Error ? error.message : "Could not publish workflow"),
                                                        })}>Publish to organization</DropdownMenuItem>}
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
            {/* Email Template Modal */}
            <Dialog open={isTemplateModalOpen} onOpenChange={handleTemplateModalOpenChange}>
                <DialogContent size="2xl">
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
                                placeholder="Email body content"
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

            {/* Execution History Dialog */}
            <Dialog open={showHistoryDialog} onOpenChange={setShowHistoryDialog}>
                <DialogContent size="2xl" className="max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] grid-rows-[auto_minmax(0,1fr)] gap-0 overflow-hidden p-0">
                    <DialogHeader className="shrink-0 border-b px-6 py-5 pr-14">
                        <DialogTitle>
                            {historyWorkflowName ? `History: ${historyWorkflowName}` : "History"}
                        </DialogTitle>
                    </DialogHeader>
                    <div className="max-h-[min(70dvh,40rem)] min-h-0 overflow-y-auto">
                        <div className="space-y-4 p-6">
                            {!executions?.items?.length ? (
                                <EmptyState icon={HistoryIcon} title="No runs yet" className="py-6" />
                            ) : (
                                executions.items.map((execution, index) => (
                                    <div key={execution.id} className="relative">
                                        {index < executions.items.length - 1 && (
                                            <div className="absolute left-2 top-8 h-full w-0.5 bg-border" />
                                        )}
                                        <div className="flex gap-3">
                                            <div
                                                className={`relative z-10 mt-1 flex size-4 shrink-0 items-center justify-center rounded-full ${execution.status === "success" ? "bg-green-500" :
                                                    execution.status === "running" ? "bg-blue-500" :
                                                        execution.status === "partial" ? "bg-yellow-500" :
                                                            execution.status === "skipped" ? "bg-gray-400" : "bg-red-500"
                                                    }`}
                                            >
                                                <div className="size-2 rounded-full bg-white" />
                                            </div>
                                            <div className="flex-1 pb-4">
                                                <div className="flex items-start justify-between">
                                                    <div>
                                                        <WorkflowExecutionRecordLink execution={execution} />
                                                        <p className="text-sm text-muted-foreground">{formatRelativeTime(execution.executed_at)}</p>
                                                    </div>
                                                    <Badge
                                                        variant={execution.status === "success" ? "default" :
                                                            execution.status === "skipped" || execution.status === "running" ? "secondary" : "destructive"}
                                                        className={`text-xs ${execution.status === "running" ? "border-blue-500/20 bg-blue-500/10 text-blue-500" : ""}`}
                                                    >
                                                        {getWorkflowExecutionStatusLabel(execution.status)}
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
                    </div>
                </DialogContent>
            </Dialog>

            {/* Test Workflow Dialog */}
            <Dialog open={showTestModal} onOpenChange={handleTestDialogOpenChange}>
                <DialogContent size="lg">
                    <DialogHeader>
                        <DialogTitle>Test Workflow</DialogTitle>
                        <DialogDescription>
                            Test this workflow against a specific {testEntityLabel.toLowerCase()} (dry run - no changes will be made)
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label htmlFor="workflow-test-record">
                                {testEntityInputLabel}
                            </Label>
                            <Input
                                id="workflow-test-record"
                                aria-label={testEntityInputLabel}
                                placeholder={isTestDonorEntity
                                    ? `Search ${ENTITY_PLURALS[testEntityType]}`
                                    : `Enter ${testEntityInputLabel}`}
                                list={isTestDonorEntity ? undefined : "workflow-test-entity-options"}
                                value={testEntityQuery}
                                onChange={(e) => {
                                    setTestEntityQuery(e.target.value)
                                    setTestEntityId(isTestDonorEntity ? "" : e.target.value)
                                }}
                            />
                            {!isTestDonorEntity && (
                                <datalist id="workflow-test-entity-options">
                                    {testEntitySuggestions.map((item) => (
                                        <option key={item.id} value={item.id}>
                                            {item.label}
                                        </option>
                                    ))}
                                </datalist>
                            )}
                            <p className="text-xs text-muted-foreground">
                                {testEntityType === "note" || testEntityType === "document"
                                    ? "Type a keyword to search notes or documents."
                                    : "Start typing to see recent suggestions."}
                            </p>
                        </div>

                        {testEntitySuggestionsLoading ? (
                            <div className="text-xs text-muted-foreground">Loading suggestions</div>
                        ) : testEntitySuggestions.length > 0 ? (
                            <div className="space-y-2 rounded-lg border p-3">
                                <p className="text-xs font-medium text-muted-foreground">
                                    Suggested {ENTITY_PLURALS[testEntityType] ?? `${testEntityType}s`}
                                </p>
                                <div className="space-y-2">
                                    {testEntitySuggestions.map((item) => (
                                        <Button unstyled
                                            key={item.id}
                                            type="button"
                                            className="flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-sm hover:bg-muted"
                                            onClick={() => {
                                                setTestEntityId(item.id)
                                                setTestEntityQuery(isTestDonorEntity ? item.label : item.id)
                                            }}
                                        >
                                            <span className="font-medium">{item.label}</span>
                                            {item.meta && (
                                                <span className="text-xs text-muted-foreground">{item.meta}</span>
                                            )}
                                        </Button>
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
                                                {action.description.startsWith(`${action.action_type}: `)
                                                    ? action.description.slice(action.action_type.length + 2)
                                                    : action.description}
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

export default function AutomationPageClient(
    props: Parameters<typeof useAutomationPageView>[0],
) {
    return useAutomationPageView(props)
}
