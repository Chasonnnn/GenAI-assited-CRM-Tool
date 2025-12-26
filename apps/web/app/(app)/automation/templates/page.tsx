"use client"

import { useState } from "react"
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
    CheckCircleIcon,
    GlobeIcon,
    BuildingIcon,
    SparklesIcon,
    LoaderIcon,
    PlayIcon,
} from "lucide-react"
import { toast } from "sonner"
import { useEmailTemplates } from "@/lib/hooks/use-email-templates"
import { EmailTemplateListItem } from "@/lib/api/email-templates"

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
    action_overrides?: Record<string, { template_id: string }>
}

// Category config
const categoryConfig: Record<string, { label: string; color: string }> = {
    onboarding: { label: "Onboarding", color: "bg-blue-500/10 text-blue-500 border-blue-500/20" },
    "follow-up": { label: "Follow-up", color: "bg-yellow-500/10 text-yellow-500 border-yellow-500/20" },
    notifications: { label: "Notifications", color: "bg-purple-500/10 text-purple-500 border-purple-500/20" },
    compliance: { label: "Compliance", color: "bg-red-500/10 text-red-500 border-red-500/20" },
    general: { label: "General", color: "bg-gray-500/10 text-gray-500 border-gray-500/20" },
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

async function useTemplateApi(templateId: string, data: UseTemplateFormData) {
    return api.post(`/templates/${templateId}/use`, data)
}

export default function TemplatesPage() {
    const queryClient = useQueryClient()
    const [categoryFilter, setCategoryFilter] = useState("all")
    const [selectedTemplate, setSelectedTemplate] = useState<WorkflowTemplateListItem | null>(null)
    const [formData, setFormData] = useState<UseTemplateFormData>({
        name: "",
        description: "",
        is_enabled: true,
        action_overrides: {},
    })
    const { data: emailTemplates = [], isLoading: isLoadingEmailTemplates } = useEmailTemplates(true)

    const { data: templates = [], isLoading } = useQuery({
        queryKey: ["templates", categoryFilter],
        queryFn: () => fetchTemplates(categoryFilter === "all" ? undefined : categoryFilter),
    })
    const { data: selectedTemplateDetail, isLoading: isLoadingTemplateDetail } = useQuery({
        queryKey: ["template", selectedTemplate?.id],
        queryFn: () => fetchTemplate(selectedTemplate!.id),
        enabled: !!selectedTemplate?.id,
    })

    const useTemplateMutation = useMutation({
        mutationFn: () => useTemplateApi(selectedTemplate!.id, formData),
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
        !!selectedTemplate && (isLoadingTemplateDetail || !selectedTemplateDetail)
    const canCreateWorkflow =
        !!formData.name &&
        !useTemplateMutation.isPending &&
        hasAllEmailSelections &&
        !isTemplateDetailLoading

    return (
        <div className="flex flex-1 flex-col gap-6 p-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold">Workflow Templates</h1>
                    <p className="text-sm text-muted-foreground">
                        Start with a pre-built template to create workflows faster
                    </p>
                </div>
                <Select value={categoryFilter} onValueChange={(v) => v && setCategoryFilter(v)}>
                    <SelectTrigger className="w-[180px]">
                        <SelectValue placeholder="All Categories" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All Categories</SelectItem>
                        <SelectItem value="onboarding">Onboarding</SelectItem>
                        <SelectItem value="follow-up">Follow-up</SelectItem>
                        <SelectItem value="notifications">Notifications</SelectItem>
                        <SelectItem value="compliance">Compliance</SelectItem>
                        <SelectItem value="general">General</SelectItem>
                    </SelectContent>
                </Select>
            </div>

            {isLoading ? (
                <div className="flex items-center justify-center py-12">
                    <LoaderIcon className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
            ) : templates.length === 0 ? (
                <Card>
                    <CardContent className="flex flex-col items-center justify-center py-12">
                        <LayoutTemplateIcon className="h-12 w-12 text-muted-foreground/50" />
                        <p className="mt-4 text-lg font-medium">No templates available</p>
                        <p className="text-sm text-muted-foreground">
                            Templates will appear here once created
                        </p>
                    </CardContent>
                </Card>
            ) : (
                <>
                    {/* Global Templates */}
                    {globalTemplates.length > 0 && (
                        <div>
                            <div className="mb-4 flex items-center gap-2">
                                <GlobeIcon className="h-5 w-5 text-teal-500" />
                                <h2 className="text-xl font-semibold">System Templates</h2>
                            </div>
                            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                                {globalTemplates.map((template) => (
                                    <TemplateCard
                                        key={template.id}
                                        template={template}
                                        onSelect={() => handleSelectTemplate(template)}
                                    />
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Org Templates */}
                    {orgTemplates.length > 0 && (
                        <div>
                            <div className="mb-4 flex items-center gap-2">
                                <BuildingIcon className="h-5 w-5 text-blue-500" />
                                <h2 className="text-xl font-semibold">Your Templates</h2>
                            </div>
                            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                                {orgTemplates.map((template) => (
                                    <TemplateCard
                                        key={template.id}
                                        template={template}
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
                                <LoaderIcon className="h-4 w-4 animate-spin" />
                                Loading template details...
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
                                        <LoaderIcon className="h-4 w-4 animate-spin" />
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
                                                            <SelectValue placeholder="Choose an email template" />
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
                                <LoaderIcon className="mr-2 h-4 w-4 animate-spin" />
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
    onSelect,
}: {
    template: WorkflowTemplateListItem
    onSelect: () => void
}) {
    const IconComponent = iconMap[template.icon] || LayoutTemplateIcon
    const category = categoryConfig[template.category] || categoryConfig.general

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
                                <Badge variant="secondary" className={category.color}>
                                    {category.label}
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
                    <span>Trigger: {template.trigger_type.replace(/_/g, " ")}</span>
                    <span>{template.usage_count} uses</span>
                </div>
            </CardContent>
        </Card>
    )
}
