"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
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
import { toast } from "sonner"
import { useEmailTemplates } from "@/lib/hooks/use-email-templates"
import { useAuth } from "@/lib/auth-context"
import { cn } from "@/lib/utils"
import type { EmailTemplateListItem } from "@/lib/api/email-templates"
import type { WorkflowScope } from "@/lib/api/workflows"

// Types
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

interface TemplateCategory {
    value: string
    label: string
}

interface TemplateCategoriesResponse {
    categories: TemplateCategory[]
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
    general: "bg-gray-500/10 text-gray-500 border-gray-500/20",
}

const DEFAULT_CATEGORIES = Object.entries(DEFAULT_CATEGORY_LABELS).map(([value, label]) => ({
    value,
    label,
}))

// Trigger type labels for display
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

// Icon map
const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
    template: LayoutTemplateIcon,
    mail: MailIcon,
    clock: ClockIcon,
    bell: BellIcon,
    activity: ActivityIcon,
    "alert-circle": AlertCircleIcon,
}

// API functions using the shared api module
import api from "@/lib/api"

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
    scope: WorkflowScope
) {
    return api.post(`/templates/${templateId}/use`, { ...data, scope })
}

interface WorkflowTemplatesPanelProps {
    embedded?: boolean
}

export default function WorkflowTemplatesPanel({ embedded = false }: WorkflowTemplatesPanelProps) {
    const router = useRouter()
    const queryClient = useQueryClient()
    const { user } = useAuth()
    const isAdmin = user?.role === "admin" || user?.role === "developer"

    const [categoryFilter, setCategoryFilter] = useState("all")
    const [selectedTemplate, setSelectedTemplate] = useState<WorkflowTemplateListItem | null>(null)
    const [workflowScope, setWorkflowScope] = useState<WorkflowScope>("personal")
    const [formData, setFormData] = useState<UseTemplateFormData>({
        name: "",
        description: "",
        is_enabled: true,
        action_overrides: {},
    })

    useEffect(() => {
        if (!isAdmin && workflowScope !== "personal") {
            setWorkflowScope("personal")
        }
    }, [isAdmin, workflowScope])

    const { data: emailTemplates = [], isLoading: isLoadingEmailTemplates } = useEmailTemplates({
        activeOnly: true,
        scope: workflowScope === "org" ? "org" : undefined,
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

    const useTemplateMutation = useMutation({
        mutationFn: () => applyTemplateApi(selectedTemplate!.id, formData, workflowScope),
        onSuccess: () => {
            toast.success("Workflow created from template!")
            queryClient.invalidateQueries({ queryKey: ["workflows"] })
            setSelectedTemplate(null)
            setFormData({ name: "", description: "", is_enabled: true, action_overrides: {} })
        },
        onError: (err: Error) => {
            toast.error(err.message)
        },
    })

    const handleSelectTemplate = (template: WorkflowTemplateListItem) => {
        setSelectedTemplate(template)
        setFormData({
            name: template.name,
            description: template.description || "",
            is_enabled: true,
            action_overrides: {},
        })
    }

    const globalTemplates = templates.filter((t) => t.is_global)
    const orgTemplates = templates.filter((t) => !t.is_global)
    const missingEmailActions =
        selectedTemplate && selectedTemplateDetail?.actions
            ? selectedTemplateDetail.actions
                .map((action, index) => {
                    const actionType = typeof action.action_type === "string" ? action.action_type : ""
                    const templateId =
                        typeof action.template_id === "string" ? action.template_id : null
                    return { action, actionType, templateId, index }
                })
                .filter(({ actionType, templateId }) => actionType === "send_email" && !templateId)
            : []
    const hasMissingEmailTemplates = missingEmailActions.length > 0
    const hasAllEmailSelections =
        !hasMissingEmailTemplates ||
        missingEmailActions.every(
            ({ index }) => formData.action_overrides?.[String(index)]?.template_id
        )
    const isTemplateDetailLoading =
        !!selectedTemplate && (isLoadingTemplateDetail || (!selectedTemplateDetail && !isTemplateDetailError))
    const hasTemplateDetail = !selectedTemplate || !!selectedTemplateDetail
    const templateDetailErrorMessage =
        templateDetailError instanceof Error ? templateDetailError.message : "Failed to load template details"
    const canCreateWorkflow =
        !!formData.name &&
        !useTemplateMutation.isPending &&
        hasAllEmailSelections &&
        !isTemplateDetailLoading &&
        hasTemplateDetail &&
        !isTemplateDetailError
    const categoryOptions = categoriesData?.categories ?? DEFAULT_CATEGORIES
    const categoryLabels = categoryOptions.reduce<Record<string, string>>((acc, category) => {
        acc[category.value] = category.label
        return acc
    }, { ...DEFAULT_CATEGORY_LABELS })

    return (
        <div className={cn("flex flex-col gap-6", embedded ? "" : "flex-1 p-6")}>
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-semibold">Workflow Templates</h1>
                    <p className="text-sm text-muted-foreground">Use templates to quickly create workflows</p>
                </div>
                <Button onClick={() => router.push("/automation?create=true")}>
                    <PlusIcon className="mr-2 h-4 w-4" />
                    Create Workflow
                </Button>
            </div>

            {/* Category Filter */}
            <div className="flex flex-wrap items-center gap-2">
                <Button
                    variant={categoryFilter === "all" ? "default" : "outline"}
                    size="sm"
                    onClick={() => setCategoryFilter("all")}
                >
                    All Templates
                </Button>
                {categoryOptions.map((category) => (
                    <Button
                        key={category.value}
                        variant={categoryFilter === category.value ? "default" : "outline"}
                        size="sm"
                        onClick={() => setCategoryFilter(category.value)}
                    >
                        {category.label}
                    </Button>
                ))}
            </div>

            {/* Templates Grid */}
            {isLoading ? (
                <div className="flex items-center justify-center py-12">
                    <Loader2Icon className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
            ) : templates.length === 0 ? (
                <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12">
                    <LayoutTemplateIcon className="h-12 w-12 text-muted-foreground" />
                    <h3 className="mt-4 text-lg font-semibold">No templates found</h3>
                    <p className="text-sm text-muted-foreground">Try adjusting your filters.</p>
                </div>
            ) : (
                <>
                    {globalTemplates.length > 0 && (
                        <div>
                            <div className="mb-4 flex items-center gap-2">
                                <GlobeIcon className="h-4 w-4 text-muted-foreground" />
                                <h2 className="text-lg font-semibold">Global Templates</h2>
                            </div>
                            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                                {globalTemplates.map((template) => (
                                    <TemplateCard
                                        key={template.id}
                                        template={template}
                                        categoryLabels={categoryLabels}
                                        onSelect={() => handleSelectTemplate(template)}
                                    />
                                ))}
                            </div>
                        </div>
                    )}

                    {orgTemplates.length > 0 && (
                        <div>
                            <div className="mb-4 flex items-center gap-2">
                                <BuildingIcon className="h-4 w-4 text-muted-foreground" />
                                <h2 className="text-lg font-semibold">Organization Templates</h2>
                            </div>
                            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                                {orgTemplates.map((template) => (
                                    <TemplateCard
                                        key={template.id}
                                        template={template}
                                        categoryLabels={categoryLabels}
                                        onSelect={() => handleSelectTemplate(template)}
                                    />
                                ))}
                            </div>
                        </div>
                    )}
                </>
            )}

            {/* Use Template Dialog */}
            <Dialog open={!!selectedTemplate} onOpenChange={(open) => !open && setSelectedTemplate(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <SparklesIcon className="h-5 w-5 text-teal-500" />
                            Use Template
                        </DialogTitle>
                        <DialogDescription>
                            Create a new workflow based on "{selectedTemplate?.name}"
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4 py-4">
                        {isAdmin && (
                            <div className="space-y-2">
                                <Label htmlFor="workflow-scope">Workflow Scope</Label>
                                <Select
                                    value={workflowScope}
                                    onValueChange={(value) => setWorkflowScope(value as WorkflowScope)}
                                >
                                    <SelectTrigger id="workflow-scope">
                                        <SelectValue placeholder="Select scope" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="personal">
                                            <div className="flex items-center gap-2">
                                                <UserIcon className="h-4 w-4" />
                                                Personal Workflow
                                            </div>
                                        </SelectItem>
                                        <SelectItem value="org">
                                            <div className="flex items-center gap-2">
                                                <BuildingIcon className="h-4 w-4" />
                                                Organization Workflow
                                            </div>
                                        </SelectItem>
                                    </SelectContent>
                                </Select>
                                <p className="text-xs text-muted-foreground">
                                    Personal workflows are visible only to you. Organization workflows are shared with your team.
                                </p>
                            </div>
                        )}

                        <div className="space-y-2">
                            <Label htmlFor="name">Workflow Name</Label>
                            <Input
                                id="name"
                                value={formData.name}
                                onChange={(e) => setFormData((f) => ({ ...f, name: e.target.value }))}
                                placeholder="Enter workflow name"
                            />
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="description">Description (optional)</Label>
                            <Input
                                id="description"
                                value={formData.description}
                                onChange={(e) => setFormData((f) => ({ ...f, description: e.target.value }))}
                                placeholder="Describe what this workflow does"
                            />
                        </div>

                        {isTemplateDetailLoading && (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                <Loader2Icon className="h-4 w-4 animate-spin" />
                                Loading template details...
                            </div>
                        )}
                        {isTemplateDetailError && (
                            <div className="flex items-center gap-2 text-sm text-red-500">
                                <AlertCircleIcon className="h-4 w-4" />
                                {templateDetailErrorMessage}
                            </div>
                        )}

                        {hasMissingEmailTemplates && (
                            <div className="space-y-3 rounded-lg border border-dashed border-muted-foreground/40 p-3">
                                <div className="flex items-center gap-2 text-sm font-medium">
                                    <MailIcon className="h-4 w-4 text-teal-500" />
                                    Select email templates for this workflow
                                </div>
                                {isLoadingEmailTemplates ? (
                                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                        <Loader2Icon className="h-4 w-4 animate-spin" />
                                        Loading email templates...
                                    </div>
                                ) : emailTemplates.length === 0 ? (
                                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                        <AlertCircleIcon className="h-4 w-4" />
                                        Create an email template before using this workflow template.
                                    </div>
                                ) : (
                                    <div className="space-y-3">
                                        {missingEmailActions.map(({ action, index }) => {
                                            const override =
                                                formData.action_overrides?.[String(index)]?.template_id ?? ""
                                            const actionLabel =
                                                typeof action.name === "string"
                                                    ? action.name
                                                    : `Email action ${index + 1}`
                                            return (
                                                <div key={`email-action-${index}`} className="space-y-2">
                                                    <Label className="text-sm">{actionLabel}</Label>
                                                    <Select
                                                        value={override}
                                                        onValueChange={(value) =>
                                                            setFormData((prev) => ({
                                                                ...prev,
                                                                action_overrides: {
                                                                    ...(prev.action_overrides ?? {}),
                                                                    [String(index)]: { template_id: value },
                                                                },
                                                            }))
                                                        }
                                                    >
                                                        <SelectTrigger>
                                                            <SelectValue placeholder="Choose an email template">
                                                                {(value: string | null) => {
                                                                    if (!value) return "Choose an email template"
                                                                    const template = emailTemplates.find((t: EmailTemplateListItem) => t.id === value)
                                                                    return template?.name ?? value
                                                                }}
                                                            </SelectValue>
                                                        </SelectTrigger>
                                                        <SelectContent>
                                                            {emailTemplates.map(
                                                                (template: EmailTemplateListItem) => (
                                                                    <SelectItem
                                                                        key={template.id}
                                                                        value={template.id}
                                                                    >
                                                                        {template.name}
                                                                    </SelectItem>
                                                                )
                                                            )}
                                                        </SelectContent>
                                                    </Select>
                                                </div>
                                            )
                                        })}
                                    </div>
                                )}
                            </div>
                        )}

                        <div className="flex items-center gap-2">
                            <input
                                type="checkbox"
                                id="is_enabled"
                                checked={formData.is_enabled}
                                onChange={(e) => setFormData((f) => ({ ...f, is_enabled: e.target.checked }))}
                                className="h-4 w-4 rounded border-gray-300"
                            />
                            <Label htmlFor="is_enabled">Enable workflow immediately</Label>
                        </div>
                    </div>

                    <DialogFooter>
                        <Button variant="outline" onClick={() => setSelectedTemplate(null)}>
                            Cancel
                        </Button>
                        <Button
                            onClick={() => useTemplateMutation.mutate()}
                            disabled={!canCreateWorkflow}
                        >
                            {useTemplateMutation.isPending ? (
                                <Loader2Icon className="mr-2 h-4 w-4 animate-spin" />
                            ) : (
                                <PlayIcon className="mr-2 h-4 w-4" />
                            )}
                            Create Workflow
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}

// Template Card Component
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

    return (
        <Card className="group cursor-pointer transition-all hover:border-teal-500/50 hover:shadow-md" onClick={onSelect}>
            <CardHeader className="pb-2">
                <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                        <div className="flex size-10 items-center justify-center rounded-lg bg-teal-500/10">
                            <IconComponent className="size-5 text-teal-500" />
                        </div>
                        <div>
                            <CardTitle className="text-base">{template.name}</CardTitle>
                            <div className="mt-1 flex items-center gap-2">
                                <Badge variant="secondary" className={categoryColor}>
                                    {categoryLabel}
                                </Badge>
                                {template.is_global && (
                                    <Badge variant="outline" className="text-xs">
                                        <GlobeIcon className="mr-1 h-3 w-3" />
                                        Global
                                    </Badge>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            </CardHeader>
            <CardContent>
                <CardDescription className="line-clamp-2">
                    {template.description || "No description"}
                </CardDescription>
                <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
                    <span>Trigger: {TRIGGER_LABELS[template.trigger_type] || template.trigger_type}</span>
                    <span>{template.usage_count} uses</span>
                </div>
            </CardContent>
        </Card>
    )
}
