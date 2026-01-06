"use client"

import { useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
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
    ClockIcon,
    ZapIcon,
    FileTextIcon,
    LoaderIcon,
    AlertCircleIcon,
} from "lucide-react"
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
import type { WorkflowListItem, Condition, ActionConfig, WorkflowCreate, WorkflowTestResponse } from "@/lib/api/workflows"
import { useCreateEmailTemplate, useUpdateEmailTemplate, useDeleteEmailTemplate } from "@/lib/hooks/use-email-templates"
import type { EmailTemplateListItem } from "@/lib/api/email-templates"
import { parseDateInput } from "@/lib/utils/date"

// Icon mapping for trigger types
const triggerIcons: Record<string, React.ElementType> = {
    case_created: FileTextIcon,
    status_changed: ZapIcon,
    case_assigned: UserIcon,
    case_updated: FileTextIcon,
    task_due: ClockIcon,
    task_overdue: AlertCircleIcon,
    scheduled: CalendarIcon,
    inactivity: ClockIcon,
}

const triggerLabels: Record<string, string> = {
    case_created: "Case Created",
    status_changed: "Status Changed",
    case_assigned: "Case Assigned",
    case_updated: "Field Updated",
    task_due: "Task Due",
    task_overdue: "Task Overdue",
    scheduled: "Scheduled",
    inactivity: "Inactivity",
}

// Labels for condition fields
const conditionFieldLabels: Record<string, string> = {
    status: "Stage",
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

export default function AutomationPage() {
    const router = useRouter()
    const searchParams = useSearchParams()
    const validTabs = ["workflows", "email-templates", "campaigns"]
    const tabParam = searchParams.get("tab")
    const createParam = searchParams.get("create")
    const initialTab = tabParam && validTabs.includes(tabParam) ? tabParam : "workflows"
    const [activeTab] = useState(initialTab)

    // Workflow state - initialize create modal from query param
    const [showCreateModal, setShowCreateModal] = useState(createParam === "true")
    const [showHistoryPanel, setShowHistoryPanel] = useState(false)
    const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null)
    const [editingWorkflowId, setEditingWorkflowId] = useState<string | null>(null)
    const [hydratedWorkflowId, setHydratedWorkflowId] = useState<string | null>(null)
    const [wizardStep, setWizardStep] = useState(1)
    const [validationError, setValidationError] = useState<string | null>(null)

    // Test workflow state
    const [showTestModal, setShowTestModal] = useState(false)
    const [testWorkflowId, setTestWorkflowId] = useState<string | null>(null)
    const [testCaseId, setTestCaseId] = useState("")
    const [testResult, setTestResult] = useState<WorkflowTestResponse | null>(null)

    // Form state
    const [workflowName, setWorkflowName] = useState("")
    const [workflowDescription, setWorkflowDescription] = useState("")
    const [triggerType, setTriggerType] = useState("")
    const [triggerConfig, setTriggerConfig] = useState<Record<string, unknown>>({})
    const [conditions, setConditions] = useState<Condition[]>([])
    const [conditionLogic, setConditionLogic] = useState<"AND" | "OR">("AND")
    const [actions, setActions] = useState<ActionConfig[]>([])

    // Email template state (preserved from original)
    const [isTemplateModalOpen, setIsTemplateModalOpen] = useState(false)
    const [editingTemplate, setEditingTemplate] = useState<EmailTemplateListItem | null>(null)
    const [templateName, setTemplateName] = useState("")
    const [templateSubject, setTemplateSubject] = useState("")
    const [templateBody, setTemplateBody] = useState("")

    // API hooks
    const { data: workflows, isLoading: workflowsLoading } = useWorkflows()
    const { data: stats, isLoading: statsLoading } = useWorkflowStats()
    const { data: options } = useWorkflowOptions()
    const { data: executions } = useWorkflowExecutions(selectedWorkflowId || "", { limit: 20 })

    const createWorkflow = useCreateWorkflow()
    const updateWorkflow = useUpdateWorkflow()
    const toggleWorkflow = useToggleWorkflow()
    const duplicateWorkflow = useDuplicateWorkflow()
    const deleteWorkflow = useDeleteWorkflow()
    const testWorkflowMutation = useTestWorkflow()

    // Email template hooks
    const createTemplate = useCreateEmailTemplate()
    const updateTemplate = useUpdateEmailTemplate()
    const deleteTemplate = useDeleteEmailTemplate()

    const getActionValidationError = (action: ActionConfig): string | null => {
        if (!action.action_type) return "Select an action type for each action."
        if (action.action_type === "send_email" && !action.template_id) {
            return "Select an email template for all email actions."
        }
        if (action.action_type === "create_task" && !(action.title as string | undefined)?.trim()) {
            return "Task actions need a title."
        }
        if (action.action_type === "send_notification" && !(action.title as string | undefined)?.trim()) {
            return "Notification actions need a title."
        }
        if (action.action_type === "add_note" && !(action.content as string | undefined)?.trim()) {
            return "Note actions need content."
        }
        return null
    }

    const getActionsValidationError = (): string | null => {
        if (actions.length === 0) return "Add at least one action."
        for (const action of actions) {
            const error = getActionValidationError(action)
            if (error) return error
        }
        return null
    }

    const getWorkflowValidationError = (): string | null => {
        if (!workflowName.trim()) return "Workflow name is required."
        if (!triggerType) return "Trigger type is required."
        return getActionsValidationError()
    }

    const getStepValidationError = (step: number): string | null => {
        if (step === 1) {
            if (!workflowName.trim()) return "Workflow name is required."
            if (!triggerType) return "Trigger type is required."
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
        setTestWorkflowId(id)
        setTestCaseId("")
        setTestResult(null)
        setShowTestModal(true)
    }

    const handleRunTest = () => {
        if (!testWorkflowId || !testCaseId) return
        testWorkflowMutation.mutate(
            { id: testWorkflowId, entityId: testCaseId },
            { onSuccess: (result) => setTestResult(result) }
        )
    }

    const resetWorkflowForm = () => {
        setWizardStep(1)
        setWorkflowName("")
        setWorkflowDescription("")
        setTriggerType("")
        setTriggerConfig({})
        setConditions([])
        setConditionLogic("AND")
        setActions([])
        setHydratedWorkflowId(null)
        setValidationError(null)
    }

    const resetWizard = () => {
        resetWorkflowForm()
        setShowCreateModal(false)
        setEditingWorkflowId(null)
    }

    const handleCreate = () => {
        resetWorkflowForm()
        setEditingWorkflowId(null)
        setShowCreateModal(true)
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
        setWorkflowName(editingWorkflow.name)
        setWorkflowDescription(editingWorkflow.description || "")
        setTriggerType(editingWorkflow.trigger_type)
        setTriggerConfig(editingWorkflow.trigger_config || {})
        setConditions(editingWorkflow.conditions || [])
        setConditionLogic((editingWorkflow.condition_logic || "AND") as "AND" | "OR")
        setActions(editingWorkflow.actions || [])
        setHydratedWorkflowId(editingWorkflowId)
    }, [editingWorkflow, editingWorkflowId, hydratedWorkflowId, showCreateModal])

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

        const data: WorkflowCreate = {
            name: workflowName,
            description: workflowDescription || undefined,
            trigger_type: triggerType,
            trigger_config: triggerConfig,
            conditions,
            condition_logic: conditionLogic,
            actions,
            is_enabled: true,
        }

        if (editingWorkflowId) {
            updateWorkflow.mutate({ id: editingWorkflowId, data }, {
                onSuccess: () => resetWizard(),
            })
        } else {
            createWorkflow.mutate(data, {
                onSuccess: () => resetWizard(),
            })
        }
    }

    const addCondition = () => {
        setConditions([...conditions, { field: "", operator: "equals", value: "" }])
    }

    const removeCondition = (index: number) => {
        setConditions(conditions.filter((_, i) => i !== index))
    }

    const updateCondition = (index: number, updates: Partial<Condition>) => {
        setConditions(conditions.map((c, i) => i === index ? { ...c, ...updates } : c))
    }

    const addAction = () => {
        setActions([...actions, { action_type: "" }])
    }

    const removeAction = (index: number) => {
        setActions(actions.filter((_, i) => i !== index))
    }

    const updateAction = (index: number, updates: Partial<ActionConfig>) => {
        setActions(actions.map((a, i) => i === index ? { ...a, ...updates } : a))
    }

    // Email template handlers (preserved)
    const handleOpenTemplateModal = (template?: EmailTemplateListItem) => {
        if (template) {
            setEditingTemplate(template)
            setTemplateName(template.name)
            setTemplateSubject(template.subject)
            // List item doesn't have body, will be fetched on modal open if needed
            setTemplateBody("")
        } else {
            setEditingTemplate(null)
            setTemplateName("")
            setTemplateSubject("")
            setTemplateBody("")
        }
        setIsTemplateModalOpen(true)
    }

    const handleSaveTemplate = () => {
        if (!templateName.trim() || !templateSubject.trim() || !templateBody.trim()) return

        if (editingTemplate) {
            updateTemplate.mutate({
                id: editingTemplate.id,
                data: { name: templateName, subject: templateSubject, body: templateBody },
            }, { onSuccess: () => setIsTemplateModalOpen(false) })
        } else {
            createTemplate.mutate({
                name: templateName,
                subject: templateSubject,
                body: templateBody,
            }, { onSuccess: () => setIsTemplateModalOpen(false) })
        }
    }

    const workflowValidationError = getWorkflowValidationError()

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
                                <div className="text-3xl font-bold">
                                    {statsLoading ? "-" : stats?.total_workflows ?? 0}
                                </div>
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader className="pb-3">
                                <CardTitle className="text-sm font-medium text-muted-foreground">Enabled</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="text-3xl font-bold">
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
                                    <div className="text-3xl font-bold">
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
                                <div className="text-3xl font-bold">
                                    {statsLoading ? "-" : stats?.total_executions_24h ?? 0}
                                </div>
                            </CardContent>
                        </Card>
                    </div>

                    {/* Workflow List */}
                    <div className="space-y-4">
                        <h2 className="text-xl font-semibold">Workflows</h2>

                        {workflowsLoading ? (
                            <div className="flex items-center justify-center py-12">
                                <LoaderIcon className="size-6 animate-spin text-muted-foreground" />
                            </div>
                        ) : !workflows?.length ? (
                            <Card>
                                <CardContent className="flex flex-col items-center justify-center py-12">
                                    <WorkflowIcon className="size-12 text-muted-foreground/50" />
                                    <h3 className="mt-4 text-lg font-medium">No workflows yet</h3>
                                    <p className="mt-1 text-sm text-muted-foreground">
                                        Create your first workflow to automate repetitive tasks
                                    </p>
                                    <Button className="mt-4" onClick={handleCreate}>
                                        <PlusIcon className="mr-2 size-4" />
                                        Create Workflow
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
                                return (
                                    <Card key={workflow.id}>
                                        <CardContent className="flex items-center justify-between p-6">
                                            <div className="flex items-start gap-4">
                                                <div className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-teal-500/10 text-teal-500">
                                                    <IconComponent className="size-6" />
                                                </div>

                                                <div className="flex-1">
                                                    <h3 className="font-semibold">{workflow.name}</h3>
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
                                                    disabled={toggleWorkflow.isPending}
                                                />
                                                <DropdownMenu>
                                                    <DropdownMenuTrigger>
                                                        <span className="inline-flex items-center justify-center size-8 p-0 rounded-md hover:bg-accent hover:text-accent-foreground cursor-pointer">
                                                            <MoreVerticalIcon className="size-4" />
                                                            <span className="sr-only">Open menu</span>
                                                        </span>
                                                    </DropdownMenuTrigger>
                                                    <DropdownMenuContent align="end">
                                                        <DropdownMenuItem onClick={() => handleEdit(workflow.id)}>Edit</DropdownMenuItem>
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
                    </div>
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
                            <div key={step} className="flex items-center" style={{ flex: index < 3 ? 1 : 'none' }}>
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
                                        placeholder="e.g., Welcome New Cases"
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
                                                    return trigger?.label ?? value
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
                                    <div>
                                        <Label>To Status</Label>
                                        <Select
                                            value={triggerConfig.to_status as string || ""}
                                            onValueChange={(v) => v && setTriggerConfig({ ...triggerConfig, to_status: v })}
                                        >
                                            <SelectTrigger className="mt-1.5">
                                                <SelectValue placeholder="Select status">
                                                    {(value: string | null) => {
                                                        if (!value) return "Select status"
                                                        const status = options?.statuses.find(s => s.value === value)
                                                        return status?.label ?? value
                                                    }}
                                                </SelectValue>
                                            </SelectTrigger>
                                            <SelectContent>
                                                {options?.statuses.map((s) => (
                                                    <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
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
                                            <Card key={index}>
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
                                                                        return conditionFieldLabels[value] || value
                                                                    }}
                                                                </SelectValue>
                                                            </SelectTrigger>
                                                            <SelectContent>
                                                                {options?.condition_fields.map((f) => (
                                                                    <SelectItem key={f} value={f}>{conditionFieldLabels[f] || f}</SelectItem>
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
                                                                        const operator = options?.condition_operators.find(o => o.value === value)
                                                                        return operator?.label ?? value
                                                                    }}
                                                                </SelectValue>
                                                            </SelectTrigger>
                                                            <SelectContent>
                                                                {options?.condition_operators.map((o) => (
                                                                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                                                                ))}
                                                            </SelectContent>
                                                        </Select>
                                                        <Input
                                                            placeholder="Value"
                                                            className="flex-1"
                                                            value={condition.value as string || ""}
                                                            onChange={(e) => updateCondition(index, { value: e.target.value })}
                                                        />
                                                        <Button size="icon" variant="ghost" onClick={() => removeCondition(index)}>
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
                                        <Card key={index}>
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
                                                                    const actionType = options?.action_types.find(a => a.value === value)
                                                                    return actionType?.label ?? value
                                                                }}
                                                            </SelectValue>
                                                        </SelectTrigger>
                                                        <SelectContent>
                                                            {options?.action_types.map((a) => (
                                                                <SelectItem key={a.value} value={a.value}>{a.label}</SelectItem>
                                                            ))}
                                                        </SelectContent>
                                                    </Select>
                                                    <Button size="icon" variant="ghost" onClick={() => removeAction(index)}>
                                                        <XIcon className="size-4" />
                                                    </Button>
                                                </div>
                                                {action.action_type === "send_email" && (
                                                    <Select
                                                        value={action.template_id as string || ""}
                                                        onValueChange={(v) => v && updateAction(index, { template_id: v })}
                                                    >
                                                        <SelectTrigger>
                                                            <SelectValue placeholder="Select email template">
                                                                {(value: string | null) => {
                                                                    if (!value) return "Select email template"
                                                                    const template = options?.email_templates.find(t => t.id === value)
                                                                    return template?.name ?? value
                                                                }}
                                                            </SelectValue>
                                                        </SelectTrigger>
                                                        <SelectContent>
                                                            {options?.email_templates.map((t) => (
                                                                <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>
                                                            ))}
                                                        </SelectContent>
                                                    </Select>
                                                )}
                                                {action.action_type === "create_task" && (
                                                    <Input
                                                        placeholder="Task title"
                                                        value={action.title as string || ""}
                                                        onChange={(e) => updateAction(index, { title: e.target.value })}
                                                    />
                                                )}
                                                {action.action_type === "send_notification" && (
                                                    <Input
                                                        placeholder="Notification title"
                                                        value={action.title as string || ""}
                                                        onChange={(e) => updateAction(index, { title: e.target.value })}
                                                    />
                                                )}
                                                {action.action_type === "add_note" && (
                                                    <Textarea
                                                        placeholder="Note content"
                                                        value={action.content as string || ""}
                                                        onChange={(e) => updateAction(index, { content: e.target.value })}
                                                        rows={2}
                                                    />
                                                )}
                                                {/* Requires Approval Toggle */}
                                                {action.action_type && (
                                                    <div className="flex items-center justify-between pt-2 border-t mt-2">
                                                        <div className="flex flex-col">
                                                            <Label htmlFor={`approval-${index}`} className="text-sm font-medium">
                                                                Requires Approval
                                                            </Label>
                                                            <span className="text-xs text-muted-foreground">
                                                                Case owner must approve before this action runs
                                                            </span>
                                                        </div>
                                                        <Switch
                                                            id={`approval-${index}`}
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
                                {!workflowValidationError ? (
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
                                className="bg-teal-500 hover:bg-teal-600"
                                disabled={!!workflowValidationError || createWorkflow.isPending || updateWorkflow.isPending}
                            >
                                {(createWorkflow.isPending || updateWorkflow.isPending) ? (
                                    <LoaderIcon className="mr-2 size-4 animate-spin" />
                                ) : null}
                                {editingWorkflowId ? "Save Changes" : "Create Workflow"}
                            </Button>
                        )}
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Email Template Modal */}
            <Dialog open={isTemplateModalOpen} onOpenChange={setIsTemplateModalOpen}>
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
                                Available variables: {"{{full_name}}"}, {"{{email}}"}, {"{{status}}"}, {"{{org_name}}"}
                            </p>
                        </div>
                    </div>
                    <DialogFooter>
                        {editingTemplate && (
                            <Button
                                variant="destructive"
                                onClick={() => {
                                    deleteTemplate.mutate(editingTemplate.id)
                                    setIsTemplateModalOpen(false)
                                }}
                            >
                                Delete
                            </Button>
                        )}
                        <Button variant="outline" onClick={() => setIsTemplateModalOpen(false)}>
                            Cancel
                        </Button>
                        <Button onClick={handleSaveTemplate} disabled={createTemplate.isPending || updateTemplate.isPending}>
                            {(createTemplate.isPending || updateTemplate.isPending) && (
                                <LoaderIcon className="mr-2 size-4 animate-spin" />
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
            <Dialog open={showTestModal} onOpenChange={setShowTestModal}>
                <DialogContent className="max-w-lg">
                    <DialogHeader>
                        <DialogTitle>Test Workflow</DialogTitle>
                        <DialogDescription>
                            Enter a case ID to test this workflow against (dry run - no changes will be made)
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label>Case ID</Label>
                            <Input
                                placeholder="Enter case UUID..."
                                value={testCaseId}
                                onChange={(e) => setTestCaseId(e.target.value)}
                            />
                        </div>

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
                                        {testResult.conditions_evaluated.map((cond, i) => (
                                            <div key={i} className="flex items-center justify-between rounded bg-muted/50 px-3 py-2 text-sm">
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
                                        {testResult.actions_preview.map((action, i) => (
                                            <div key={i} className="rounded bg-muted/50 px-3 py-2 text-sm">
                                                <span className="font-medium">{action.action_type}:</span> {action.description}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>

                    <DialogFooter>
                        <Button variant="outline" onClick={() => setShowTestModal(false)}>
                            Close
                        </Button>
                        <Button
                            onClick={handleRunTest}
                            disabled={!testCaseId || testWorkflowMutation.isPending}
                            className="bg-teal-500 hover:bg-teal-600"
                        >
                            {testWorkflowMutation.isPending ? (
                                <LoaderIcon className="mr-2 size-4 animate-spin" />
                            ) : null}
                            Run Test
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div >
    )
}
