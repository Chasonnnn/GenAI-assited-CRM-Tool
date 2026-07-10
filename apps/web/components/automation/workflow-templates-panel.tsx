"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import api from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
    LayoutTemplateIcon,
    MailIcon,
    ClockIcon,
    BellIcon,
    ActivityIcon,
    AlertCircleIcon,
    GlobeIcon,
    BuildingIcon,
    SparklesIcon,
    Loader2Icon,
    PlayIcon,
    PlusIcon,
    UserIcon,
} from "lucide-react"
import { toast } from "@/components/ui/toast"
import { useEmailTemplates } from "@/lib/hooks/use-email-templates"
import { useAuth } from "@/lib/auth-context"
import { cn } from "@/lib/utils"
import type { EmailTemplateListItem } from "@/lib/api/email-templates"
import { listForms, type FormSummary } from "@/lib/api/forms"
import type { WorkflowScope } from "@/lib/api/workflows"

interface TemplateAction {
    action_type?: string
    template_id?: string | null
    [key: string]: unknown
}

interface WorkflowTemplateListItem {
    id: string
    name: string
    description: string | null
    icon: string
    category: string
    trigger_type: string
    is_global: boolean
    usage_count: number
    created_at: string
}

interface WorkflowTemplateDetail extends WorkflowTemplateListItem {
    trigger_config: Record<string, unknown>
    conditions: Record<string, unknown>[]
    condition_logic: string
    actions: TemplateAction[]
}

interface UseTemplateFormData {
    name: string
    description: string
    is_enabled: boolean
    action_overrides?: Record<string, { template_id: string | null }>
}

interface UseTemplatePayload extends UseTemplateFormData {
    scope: WorkflowScope
    trigger_form_id?: string
}

interface TemplateCategory {
    value: string
    label: string
}

interface TemplateCategoriesResponse {
    categories: TemplateCategory[]
}

type MissingEmailAction = {
    action: TemplateAction
    index: number
    key: string
}

type FormDataUpdater = (updater: (prev: UseTemplateFormData) => UseTemplateFormData) => void

type UseTemplateDialogState = {
    selectedTemplate: WorkflowTemplateListItem | null
    selectedWorkflowScope: WorkflowScope
    formData: UseTemplateFormData
    isAdmin: boolean
    isTemplateDetailLoading: boolean
    isTemplateDetailError: boolean
    templateDetailErrorMessage: string
    templateRequiresPublishedForm: boolean
    isLoadingForms: boolean
    publishedForms: FormSummary[]
    effectiveTriggerFormId: string
    hasMissingEmailTemplates: boolean
    missingEmailActions: MissingEmailAction[]
    isLoadingEmailTemplates: boolean
    emailTemplates: EmailTemplateListItem[]
    canCreateWorkflow: boolean
    isCreatePending: boolean
}

type UseTemplateDialogHandlers = {
    onOpenChange: (open: boolean) => void
    onWorkflowScopeChange: (value: WorkflowScope) => void
    onFormDataChange: FormDataUpdater
    onTriggerFormIdChange: (value: string) => void
    onCreateWorkflow: () => void
}

const DEFAULT_CATEGORY_LABELS: Record<string, string> = {
    onboarding: "Onboarding",
    "follow-up": "Follow-up",
    notifications: "Notifications",
    compliance: "Compliance",
    general: "General",
}

const CATEGORY_COLORS: Record<string, string> = {
    onboarding: "bg-blue-500/10 text-blue-500 border-blue-500/20",
    "follow-up": "bg-yellow-500/10 text-yellow-500 border-yellow-500/20",
    notifications: "bg-purple-500/10 text-purple-500 border-purple-500/20",
    compliance: "bg-red-500/10 text-red-500 border-red-500/20",
    general: "bg-zinc-500/10 text-zinc-500 border-zinc-500/20",
}

const DEFAULT_CATEGORIES = Object.entries(DEFAULT_CATEGORY_LABELS).map(([value, label]) => ({
    value,
    label,
}))

const TRIGGER_LABELS: Record<string, string> = {
    surrogate_created: "Surrogate Created",
    status_changed: "Status Changed",
    surrogate_assigned: "Surrogate Assigned",
    surrogate_updated: "Field Updated",
    task_due: "Task Due",
    task_overdue: "Task Overdue",
    scheduled: "Scheduled",
    inactivity: "Inactivity",
}

const WORKFLOW_SCOPE_LABELS: Record<WorkflowScope, string> = {
    personal: "Personal Workflow",
    org: "Organization Workflow",
}

const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
    template: LayoutTemplateIcon,
    mail: MailIcon,
    clock: ClockIcon,
    bell: BellIcon,
    activity: ActivityIcon,
    "alert-circle": AlertCircleIcon,
}

async function fetchTemplates(category?: string): Promise<WorkflowTemplateListItem[]> {
    const params = category ? `?category=${category}` : ""
    return api.get<WorkflowTemplateListItem[]>(`/templates${params}`)
}

async function fetchTemplate(templateId: string): Promise<WorkflowTemplateDetail> {
    return api.get<WorkflowTemplateDetail>(`/templates/${templateId}`)
}

async function fetchTemplateCategories(): Promise<TemplateCategoriesResponse> {
    return api.get<TemplateCategoriesResponse>("/templates/categories")
}

async function applyTemplateApi(
    templateId: string,
    data: UseTemplateFormData,
    scope: WorkflowScope,
    triggerFormId?: string,
) {
    const payload: UseTemplatePayload = { ...data, scope }
    if (triggerFormId) {
        payload.trigger_form_id = triggerFormId
    }
    return api.post(`/templates/${templateId}/use`, payload)
}

function getCategoryLabels(categoryOptions: TemplateCategory[]) {
    return categoryOptions.reduce<Record<string, string>>((acc, category) => {
        acc[category.value] = category.label
        return acc
    }, { ...DEFAULT_CATEGORY_LABELS })
}

function getAutoSelectedForm(
    triggerFormId: string,
    triggerFormName: string,
    publishedForms: FormSummary[],
) {
    return (
        (triggerFormId ? publishedForms.find((form) => form.id === triggerFormId) : undefined) ??
        (triggerFormName
            ? publishedForms.find((form) => form.name === triggerFormName)
            : undefined) ??
        (publishedForms.length === 1 ? publishedForms[0] : undefined)
    )
}

function getPublishedFormLabel(
    formId: string | null | undefined,
    publishedForms: FormSummary[],
) {
    if (!formId) return "Choose a published form"
    return publishedForms.find((form) => form.id === formId)?.name ?? "Unknown published form"
}

function getMissingEmailActions(
    selectedTemplate: WorkflowTemplateListItem | null,
    selectedTemplateDetail: WorkflowTemplateDetail | undefined,
) {
    if (!selectedTemplate || !selectedTemplateDetail?.actions) return []

    return selectedTemplateDetail.actions.flatMap((action, index): MissingEmailAction[] => {
        const actionType = typeof action.action_type === "string" ? action.action_type : ""
        const templateId = typeof action.template_id === "string" ? action.template_id : null
        if (actionType !== "send_email" || templateId) return []
        return [{ action, index, key: getTemplateActionKey(action) }]
    })
}

function getTemplateActionKey(action: TemplateAction) {
    for (const field of ["id", "key", "name", "label"]) {
        const value = action[field]
        if (typeof value === "string" && value.trim()) {
            return `${field}:${value}`
        }
    }
    return `action:${JSON.stringify(action)}`
}

function getEmailTemplateLabel(
    templateId: string | null | undefined,
    emailTemplates: EmailTemplateListItem[],
) {
    if (!templateId) return "Choose an email template"
    return emailTemplates.find((template) => template.id === templateId)?.name ?? "Unknown template"
}

function WorkflowTemplatesHeader({
    onCreateWorkflow,
}: {
    onCreateWorkflow: () => void
}) {
    return (
        <div className="flex items-center justify-between">
            <div>
                <h1 className="text-2xl font-semibold">Workflow Templates</h1>
                <p className="text-sm text-muted-foreground">Use templates to quickly create workflows</p>
            </div>
            <Button onClick={onCreateWorkflow}>
                <PlusIcon className="mr-2 size-4" />
                Create Workflow
            </Button>
        </div>
    )
}

function TemplateCategoryFilter({
    categoryFilter,
    categoryOptions,
    onCategoryFilterChange,
}: {
    categoryFilter: string
    categoryOptions: TemplateCategory[]
    onCategoryFilterChange: (value: string) => void
}) {
    return (
        <div className="flex flex-wrap items-center gap-2">
            <Button
                variant={categoryFilter === "all" ? "default" : "outline"}
                size="sm"
                onClick={() => onCategoryFilterChange("all")}
            >
                All Templates
            </Button>
            {categoryOptions.map((category) => (
                <Button
                    key={category.value}
                    variant={categoryFilter === category.value ? "default" : "outline"}
                    size="sm"
                    onClick={() => onCategoryFilterChange(category.value)}
                >
                    {category.label}
                </Button>
            ))}
        </div>
    )
}

function TemplateSections({
    isLoading,
    templates,
    globalTemplates,
    orgTemplates,
    categoryLabels,
    onSelectTemplate,
}: {
    isLoading: boolean
    templates: WorkflowTemplateListItem[]
    globalTemplates: WorkflowTemplateListItem[]
    orgTemplates: WorkflowTemplateListItem[]
    categoryLabels: Record<string, string>
    onSelectTemplate: (template: WorkflowTemplateListItem) => void
}) {
    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-12">
                <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (templates.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12">
                <LayoutTemplateIcon className="size-12 text-muted-foreground" />
                <h3 className="mt-4 text-lg font-semibold">No templates found</h3>
                <p className="text-sm text-muted-foreground">Try adjusting your filters.</p>
            </div>
        )
    }

    return (
        <>
            {globalTemplates.length > 0 ? (
                <TemplateSection
                    title="Global Templates"
                    icon="global"
                    templates={globalTemplates}
                    categoryLabels={categoryLabels}
                    onSelectTemplate={onSelectTemplate}
                />
            ) : null}

            {orgTemplates.length > 0 ? (
                <TemplateSection
                    title="Organization Templates"
                    icon="organization"
                    templates={orgTemplates}
                    categoryLabels={categoryLabels}
                    onSelectTemplate={onSelectTemplate}
                />
            ) : null}
        </>
    )
}

function TemplateSection({
    title,
    icon,
    templates,
    categoryLabels,
    onSelectTemplate,
}: {
    title: string
    icon: "global" | "organization"
    templates: WorkflowTemplateListItem[]
    categoryLabels: Record<string, string>
    onSelectTemplate: (template: WorkflowTemplateListItem) => void
}) {
    const SectionIcon = icon === "global" ? GlobeIcon : BuildingIcon

    return (
        <div>
            <div className="mb-4 flex items-center gap-2">
                <SectionIcon className="size-4 text-muted-foreground" />
                <h2 className="text-lg font-semibold">{title}</h2>
            </div>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {templates.map((template) => (
                    <TemplateCard
                        key={template.id}
                        template={template}
                        categoryLabels={categoryLabels}
                        onSelect={() => onSelectTemplate(template)}
                    />
                ))}
            </div>
        </div>
    )
}

function UseTemplateDialog({
    state,
    handlers,
}: {
    state: UseTemplateDialogState
    handlers: UseTemplateDialogHandlers
}) {
    return (
        <Dialog open={!!state.selectedTemplate} onOpenChange={handlers.onOpenChange}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <SparklesIcon className="size-5 text-teal-500" />
                        Use Template
                    </DialogTitle>
                    <DialogDescription>
                        Create a new workflow based on "{state.selectedTemplate?.name}"
                    </DialogDescription>
                </DialogHeader>

                <UseTemplateDialogBody state={state} handlers={handlers} />
                <UseTemplateDialogFooter
                    state={state}
                    onCancel={() => handlers.onOpenChange(false)}
                    onCreateWorkflow={handlers.onCreateWorkflow}
                />
            </DialogContent>
        </Dialog>
    )
}

function UseTemplateDialogBody({
    state,
    handlers,
}: {
    state: UseTemplateDialogState
    handlers: UseTemplateDialogHandlers
}) {
    return (
        <div className="space-y-4 py-4">
            {state.isAdmin ? (
                <WorkflowScopeField
                    selectedWorkflowScope={state.selectedWorkflowScope}
                    onWorkflowScopeChange={handlers.onWorkflowScopeChange}
                />
            ) : null}

            <WorkflowTemplateFormFields
                formData={state.formData}
                onFormDataChange={handlers.onFormDataChange}
            />
            <TemplateDetailStatus
                isTemplateDetailLoading={state.isTemplateDetailLoading}
                isTemplateDetailError={state.isTemplateDetailError}
                templateDetailErrorMessage={state.templateDetailErrorMessage}
            />
            <PublishedFormSelector
                templateRequiresPublishedForm={state.templateRequiresPublishedForm}
                isLoadingForms={state.isLoadingForms}
                publishedForms={state.publishedForms}
                effectiveTriggerFormId={state.effectiveTriggerFormId}
                onTriggerFormIdChange={handlers.onTriggerFormIdChange}
            />
            <MissingEmailTemplateSelector
                hasMissingEmailTemplates={state.hasMissingEmailTemplates}
                missingEmailActions={state.missingEmailActions}
                isLoadingEmailTemplates={state.isLoadingEmailTemplates}
                emailTemplates={state.emailTemplates}
                formData={state.formData}
                onFormDataChange={handlers.onFormDataChange}
            />
            <EnableWorkflowCheckbox
                isEnabled={state.formData.is_enabled}
                onFormDataChange={handlers.onFormDataChange}
            />
        </div>
    )
}

function WorkflowScopeField({
    selectedWorkflowScope,
    onWorkflowScopeChange,
}: {
    selectedWorkflowScope: WorkflowScope
    onWorkflowScopeChange: (value: WorkflowScope) => void
}) {
    return (
        <div className="space-y-2">
            <Label htmlFor="workflow-scope">Workflow Scope</Label>
            <Select
                value={selectedWorkflowScope}
                onValueChange={(value) => onWorkflowScopeChange(value as WorkflowScope)}
            >
                <SelectTrigger id="workflow-scope">
                    <SelectValue placeholder="Select scope">
                        {(value: string | null) =>
                            value ? WORKFLOW_SCOPE_LABELS[value as WorkflowScope] : "Select scope"}
                    </SelectValue>
                </SelectTrigger>
                <SelectContent>
                    <SelectItem value="personal">
                        <div className="flex items-center gap-2">
                            <UserIcon className="size-4" />
                            Personal Workflow
                        </div>
                    </SelectItem>
                    <SelectItem value="org">
                        <div className="flex items-center gap-2">
                            <BuildingIcon className="size-4" />
                            Organization Workflow
                        </div>
                    </SelectItem>
                </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
                Personal workflows are visible only to you. Organization workflows are shared with your team.
            </p>
        </div>
    )
}

function WorkflowTemplateFormFields({
    formData,
    onFormDataChange,
}: {
    formData: UseTemplateFormData
    onFormDataChange: FormDataUpdater
}) {
    return (
        <>
            <div className="space-y-2">
                <Label htmlFor="name">Workflow Name</Label>
                <Input
                    id="name"
                    value={formData.name}
                    onChange={(e) => onFormDataChange((f) => ({ ...f, name: e.target.value }))}
                    placeholder="Enter workflow name"
                />
            </div>

            <div className="space-y-2">
                <Label htmlFor="description">Description (optional)</Label>
                <Input
                    id="description"
                    value={formData.description}
                    onChange={(e) => onFormDataChange((f) => ({ ...f, description: e.target.value }))}
                    placeholder="Describe what this workflow does"
                />
            </div>
        </>
    )
}

function TemplateDetailStatus({
    isTemplateDetailLoading,
    isTemplateDetailError,
    templateDetailErrorMessage,
}: {
    isTemplateDetailLoading: boolean
    isTemplateDetailError: boolean
    templateDetailErrorMessage: string
}) {
    return (
        <>
            {isTemplateDetailLoading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2Icon className="size-4 animate-spin" />
                    Loading template details
                </div>
            ) : null}
            {isTemplateDetailError ? (
                <div className="flex items-center gap-2 text-sm text-red-500">
                    <AlertCircleIcon className="size-4" />
                    {templateDetailErrorMessage}
                </div>
            ) : null}
        </>
    )
}

function PublishedFormSelector({
    templateRequiresPublishedForm,
    isLoadingForms,
    publishedForms,
    effectiveTriggerFormId,
    onTriggerFormIdChange,
}: {
    templateRequiresPublishedForm: boolean
    isLoadingForms: boolean
    publishedForms: FormSummary[]
    effectiveTriggerFormId: string
    onTriggerFormIdChange: (value: string) => void
}) {
    if (!templateRequiresPublishedForm) {
        return null
    }

    return (
        <div className="space-y-2">
            <Label htmlFor="trigger-form-id">Published form</Label>
            {isLoadingForms ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2Icon className="size-4 animate-spin" />
                    Loading published forms
                </div>
            ) : publishedForms.length === 0 ? (
                <div className="flex items-center gap-2 rounded-md border border-dashed border-muted-foreground/40 p-3 text-sm text-muted-foreground">
                    <AlertCircleIcon className="size-4" />
                    Publish a form before using this workflow template.
                </div>
            ) : (
                <Select
                    value={effectiveTriggerFormId}
                    onValueChange={(value) => onTriggerFormIdChange(value ?? "")}
                >
                    <SelectTrigger id="trigger-form-id">
                        <SelectValue placeholder="Choose a published form">
                            {(value: string | null) => getPublishedFormLabel(value, publishedForms)}
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        {publishedForms.map((form) => (
                            <SelectItem key={form.id} value={form.id}>
                                {form.name}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            )}
        </div>
    )
}

function MissingEmailTemplateSelector({
    hasMissingEmailTemplates,
    missingEmailActions,
    isLoadingEmailTemplates,
    emailTemplates,
    formData,
    onFormDataChange,
}: {
    hasMissingEmailTemplates: boolean
    missingEmailActions: MissingEmailAction[]
    isLoadingEmailTemplates: boolean
    emailTemplates: EmailTemplateListItem[]
    formData: UseTemplateFormData
    onFormDataChange: FormDataUpdater
}) {
    if (!hasMissingEmailTemplates) {
        return null
    }

    return (
        <div className="space-y-3 rounded-lg border border-dashed border-muted-foreground/40 p-3">
            <div className="flex items-center gap-2 text-sm font-medium">
                <MailIcon className="size-4 text-teal-500" />
                Select email templates for this workflow
            </div>
            {isLoadingEmailTemplates ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2Icon className="size-4 animate-spin" />
                    Loading email templates
                </div>
            ) : emailTemplates.length === 0 ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <AlertCircleIcon className="size-4" />
                    Create an email template before using this workflow template.
                </div>
            ) : (
                <div className="space-y-3">
                    {missingEmailActions.map(({ action, index, key }) => (
                        <MissingEmailTemplateField
                            key={key}
                            action={action}
                            index={index}
                            emailTemplates={emailTemplates}
                            override={formData.action_overrides?.[String(index)]?.template_id ?? ""}
                            onFormDataChange={onFormDataChange}
                        />
                    ))}
                </div>
            )}
        </div>
    )
}

function MissingEmailTemplateField({
    action,
    index,
    emailTemplates,
    override,
    onFormDataChange,
}: {
    action: TemplateAction
    index: number
    emailTemplates: EmailTemplateListItem[]
    override: string
    onFormDataChange: FormDataUpdater
}) {
    const actionLabel =
        typeof action.name === "string"
            ? action.name
            : `Email action ${index + 1}`
    const overrideSelectId = `email-action-template-${index}`

    return (
        <div className="space-y-2">
            <Label htmlFor={overrideSelectId} className="text-sm">
                {actionLabel}
            </Label>
            <Select
                value={override}
                onValueChange={(value) =>
                    onFormDataChange((prev) => ({
                        ...prev,
                        action_overrides: {
                            ...(prev.action_overrides ?? {}),
                            [String(index)]: { template_id: value },
                        },
                    }))
                }
            >
                <SelectTrigger id={overrideSelectId}>
                    <SelectValue placeholder="Choose an email template">
                        {(value: string | null) => getEmailTemplateLabel(value, emailTemplates)}
                    </SelectValue>
                </SelectTrigger>
                <SelectContent>
                    {emailTemplates.map((template) => (
                        <SelectItem key={template.id} value={template.id}>
                            {template.name}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
        </div>
    )
}

function EnableWorkflowCheckbox({
    isEnabled,
    onFormDataChange,
}: {
    isEnabled: boolean
    onFormDataChange: FormDataUpdater
}) {
    return (
        <div className="flex items-center gap-2">
            <Checkbox
                id="is_enabled"
                aria-label="Enable workflow immediately"
                checked={isEnabled}
                onCheckedChange={(checked) =>
                    onFormDataChange((formData) => ({ ...formData, is_enabled: checked }))
                }
                className="size-4 rounded border-zinc-300"
            />
            <Label htmlFor="is_enabled">Enable workflow immediately</Label>
        </div>
    )
}

function UseTemplateDialogFooter({
    state,
    onCancel,
    onCreateWorkflow,
}: {
    state: UseTemplateDialogState
    onCancel: () => void
    onCreateWorkflow: () => void
}) {
    return (
        <DialogFooter>
            <Button variant="outline" onClick={onCancel}>
                Cancel
            </Button>
            <Button onClick={onCreateWorkflow} disabled={!state.canCreateWorkflow}>
                {state.isCreatePending ? (
                    <Loader2Icon className="mr-2 size-4 animate-spin" />
                ) : (
                    <PlayIcon className="mr-2 size-4" />
                )}
                Create Workflow
            </Button>
        </DialogFooter>
    )
}

interface WorkflowTemplatesPanelProps {
    embedded?: boolean
}

export default function WorkflowTemplatesPanel({ embedded = false }: WorkflowTemplatesPanelProps) {
    const { push } = useRouter()
    const queryClient = useQueryClient()
    const { user } = useAuth()
    const isAdmin = user?.role === "admin" || user?.role === "developer"

    const [categoryFilter, setCategoryFilter] = useState("all")
    const [selectedTemplate, setSelectedTemplate] = useState<WorkflowTemplateListItem | null>(null)
    const [selectedWorkflowScope, setSelectedWorkflowScope] = useState<WorkflowScope>("personal")
    const [formData, setFormData] = useState<UseTemplateFormData>({
        name: "",
        description: "",
        is_enabled: true,
        action_overrides: {},
    })
    const [selectedTriggerFormId, setSelectedTriggerFormId] = useState("")

    const workflowScope: WorkflowScope = isAdmin ? selectedWorkflowScope : "personal"

    const { data: emailTemplates = [], isLoading: isLoadingEmailTemplates } = useEmailTemplates({
        activeOnly: true,
        scope: workflowScope === "org" ? "org" : null,
    })

    const { data: categoriesData } = useQuery({
        queryKey: ["template-categories"],
        queryFn: fetchTemplateCategories,
    })
    const { data: templates = [], isLoading } = useQuery({
        queryKey: ["templates", categoryFilter],
        queryFn: () => fetchTemplates(categoryFilter === "all" ? undefined : categoryFilter),
    })
    const {
        data: selectedTemplateDetail,
        isLoading: isLoadingTemplateDetail,
        isError: isTemplateDetailError,
        error: templateDetailError,
    } = useQuery({
        queryKey: ["template", selectedTemplate?.id],
        queryFn: () => fetchTemplate(selectedTemplate!.id),
        enabled: !!selectedTemplate?.id,
    })
    const { data: forms = [], isLoading: isLoadingForms } = useQuery({
        queryKey: ["forms", "list"],
        queryFn: listForms,
        enabled: !!selectedTemplateDetail,
    })

    const handleSelectTemplate = (template: WorkflowTemplateListItem) => {
        setSelectedTemplate(template)
        setFormData({
            name: template.name,
            description: template.description || "",
            is_enabled: true,
            action_overrides: {},
        })
        setSelectedTriggerFormId("")
    }

    const globalTemplates = templates.filter((t) => t.is_global)
    const orgTemplates = templates.filter((t) => !t.is_global)
    const triggerConfig = selectedTemplateDetail?.trigger_config ?? {}
    const triggerFormName =
        typeof triggerConfig.form_name === "string" ? triggerConfig.form_name.trim() : ""
    const triggerFormId =
        typeof triggerConfig.form_id === "string" ? triggerConfig.form_id.trim() : ""
    const templateRequiresPublishedForm =
        !!selectedTemplateDetail &&
        (selectedTemplateDetail.trigger_type === "form_started" ||
            !!triggerFormName ||
            !!triggerFormId)
    const publishedForms = forms.filter((form: FormSummary) => form.status === "published")
    const autoSelectedForm = getAutoSelectedForm(triggerFormId, triggerFormName, publishedForms)
    const selectedPublishedForm = selectedTriggerFormId
        ? publishedForms.find((form) => form.id === selectedTriggerFormId)
        : undefined
    const effectiveTriggerFormId = selectedPublishedForm?.id ?? autoSelectedForm?.id ?? ""
    const missingEmailActions = getMissingEmailActions(selectedTemplate, selectedTemplateDetail)
    const hasMissingEmailTemplates = missingEmailActions.length > 0
    const hasAllEmailSelections =
        !hasMissingEmailTemplates ||
        missingEmailActions.every(
            ({ index }) => formData.action_overrides?.[String(index)]?.template_id,
        )
    const isTemplateDetailLoading =
        !!selectedTemplate && (isLoadingTemplateDetail || (!selectedTemplateDetail && !isTemplateDetailError))
    const hasTemplateDetail = !selectedTemplate || !!selectedTemplateDetail
    const templateDetailErrorMessage =
        templateDetailError instanceof Error ? templateDetailError.message : "Failed to load template details"
    const hasRequiredFormSelection =
        !templateRequiresPublishedForm || (!isLoadingForms && !!effectiveTriggerFormId)

    const useTemplateMutation = useMutation({
        mutationFn: () =>
            applyTemplateApi(
                selectedTemplate!.id,
                formData,
                workflowScope,
                templateRequiresPublishedForm ? effectiveTriggerFormId : undefined,
            ),
        onSuccess: () => {
            toast.success("Workflow created from template!")
            void queryClient.invalidateQueries({ queryKey: ["workflows"] })
            setSelectedTemplate(null)
            setSelectedTriggerFormId("")
            setFormData({ name: "", description: "", is_enabled: true, action_overrides: {} })
        },
        onError: (err: Error) => {
            toast.error(err.message)
        },
    })

    const canCreateWorkflow =
        !!formData.name &&
        !useTemplateMutation.isPending &&
        hasAllEmailSelections &&
        hasRequiredFormSelection &&
        !isTemplateDetailLoading &&
        hasTemplateDetail &&
        !isTemplateDetailError
    const categoryOptions = categoriesData?.categories ?? DEFAULT_CATEGORIES
    const categoryLabels = getCategoryLabels(categoryOptions)

    const dialogState: UseTemplateDialogState = {
        selectedTemplate,
        selectedWorkflowScope,
        formData,
        isAdmin,
        isTemplateDetailLoading,
        isTemplateDetailError,
        templateDetailErrorMessage,
        templateRequiresPublishedForm,
        isLoadingForms,
        publishedForms,
        effectiveTriggerFormId,
        hasMissingEmailTemplates,
        missingEmailActions,
        isLoadingEmailTemplates,
        emailTemplates,
        canCreateWorkflow,
        isCreatePending: useTemplateMutation.isPending,
    }

    const dialogHandlers: UseTemplateDialogHandlers = {
        onOpenChange: (open) => {
            if (!open) setSelectedTemplate(null)
        },
        onWorkflowScopeChange: setSelectedWorkflowScope,
        onFormDataChange: (updater) => setFormData(updater),
        onTriggerFormIdChange: setSelectedTriggerFormId,
        onCreateWorkflow: () => useTemplateMutation.mutate(),
    }

    return (
        <div className={cn("flex flex-col gap-6", embedded ? "" : "flex-1 p-6")}>
            <WorkflowTemplatesHeader onCreateWorkflow={() => push("/automation?create=true")} />
            <TemplateCategoryFilter
                categoryFilter={categoryFilter}
                categoryOptions={categoryOptions}
                onCategoryFilterChange={setCategoryFilter}
            />
            <TemplateSections
                isLoading={isLoading}
                templates={templates}
                globalTemplates={globalTemplates}
                orgTemplates={orgTemplates}
                categoryLabels={categoryLabels}
                onSelectTemplate={handleSelectTemplate}
            />
            <UseTemplateDialog state={dialogState} handlers={dialogHandlers} />
        </div>
    )
}

function TemplateCard({
    template,
    categoryLabels,
    onSelect,
}: {
    template: WorkflowTemplateListItem
    categoryLabels: Record<string, string>
    onSelect: () => void
}) {
    const IconComponent = iconMap[template.icon] || LayoutTemplateIcon
    const categoryLabel = categoryLabels[template.category] ?? template.category
    const categoryColor = CATEGORY_COLORS[template.category] || CATEGORY_COLORS.general
    const accessibleLabel = `Use template ${template.name}`

    return (
        <Card
            className="group cursor-pointer transition-all hover:border-teal-500/50 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            onClick={onSelect}
            onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault()
                    onSelect()
                }
            }}
            role="button"
            tabIndex={0}
            aria-label={accessibleLabel}
        >
            <CardHeader className="pb-2">
                <div className="flex items-start justify-between">
                    <div className="flex min-w-0 items-center gap-3">
                        <div className="flex size-10 items-center justify-center rounded-lg bg-teal-500/10">
                            <IconComponent className="size-5 text-teal-500" aria-hidden="true" />
                        </div>
                        <div className="min-w-0">
                            <CardTitle className="text-base break-words">{template.name}</CardTitle>
                            <div className="mt-1 flex items-center gap-2">
                                <Badge variant="secondary" className={categoryColor}>
                                    {categoryLabel}
                                </Badge>
                                {template.is_global && (
                                    <Badge variant="outline" className="text-xs">
                                        <GlobeIcon className="mr-1 size-3" aria-hidden="true" />
                                        Global
                                    </Badge>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            </CardHeader>
            <CardContent>
                <CardDescription className="line-clamp-2 break-words">
                    {template.description || "No description"}
                </CardDescription>
                <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
                    <span className="min-w-0 pr-3 break-words">
                        Trigger: {TRIGGER_LABELS[template.trigger_type] || template.trigger_type}
                    </span>
                    <span>{template.usage_count} uses</span>
                </div>
            </CardContent>
        </Card>
    )
}
