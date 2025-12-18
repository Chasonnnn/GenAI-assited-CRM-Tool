"use client"

import { useState } from "react"
import { useSearchParams } from "next/navigation"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent } from "@/components/ui/tabs"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
    PlusIcon,
    MoreVerticalIcon,
    MailIcon,
    BellIcon,
    UserIcon,
    CalendarIcon,
    ClockIcon,
    CheckCircle2Icon,
    WorkflowIcon,
    ChevronDownIcon,
    CopyIcon,
    LoaderIcon,
    TrashIcon,
} from "lucide-react"
import {
    useEmailTemplates,
    useCreateEmailTemplate,
    useUpdateEmailTemplate,
    useDeleteEmailTemplate,
} from "@/lib/hooks/use-email-templates"
import type { EmailTemplateListItem } from "@/lib/api/email-templates"

// Sample automation workflows - TODO: Replace with API data
const automations = [
    {
        id: 1,
        name: "New Case Welcome Email",
        description: "Send welcome email when new case created",
        trigger: "Status → New",
        enabled: true,
        icon: MailIcon,
    },
    {
        id: 2,
        name: "Task Reminder Notifications",
        description: "Send reminder 24 hours before due",
        trigger: "24h before task",
        enabled: true,
        icon: BellIcon,
    },
    {
        id: 3,
        name: "Auto-assign to Team Lead",
        description: "Assign Meta leads to team lead",
        trigger: "Source = Meta",
        enabled: false,
        icon: UserIcon,
    },
    {
        id: 4,
        name: "Weekly Status Report",
        description: "Generate weekly case status report",
        trigger: "Mon 9:00 AM",
        enabled: true,
        icon: CalendarIcon,
    },
    {
        id: 5,
        name: "Case Follow-up Reminder",
        description: "Create task if inactive 7 days",
        trigger: "7 days inactive",
        enabled: false,
        icon: ClockIcon,
    },
    {
        id: 6,
        name: "Match Notification",
        description: "Notify all when case matched",
        trigger: "Status → Matched",
        enabled: true,
        icon: CheckCircle2Icon,
    },
]

export default function AutomationPage() {
    const searchParams = useSearchParams()
    const tabParam = searchParams?.get("tab")
    const activeTab = tabParam === "email-templates" ? "email-templates" : "workflows"

    const [enabledStates, setEnabledStates] = useState<Record<number, boolean>>(
        automations.reduce(
            (acc, auto) => {
                acc[auto.id] = auto.enabled
                return acc
            },
            {} as Record<number, boolean>,
        ),
    )

    // Email Templates state
    const [isTemplateModalOpen, setIsTemplateModalOpen] = useState(false)
    const [isVariablesOpen, setIsVariablesOpen] = useState(false)
    const [editingTemplate, setEditingTemplate] = useState<EmailTemplateListItem | null>(null)
    const [templateName, setTemplateName] = useState("")
    const [templateSubject, setTemplateSubject] = useState("")
    const [templateBody, setTemplateBody] = useState("")
    const [templateActive, setTemplateActive] = useState(true)

    // API hooks
    const { data: templates = [], isLoading: templatesLoading } = useEmailTemplates(true)
    const createMutation = useCreateEmailTemplate()
    const updateMutation = useUpdateEmailTemplate()
    const deleteMutation = useDeleteEmailTemplate()

    const handleToggle = (id: number) => {
        setEnabledStates((prev) => ({
            ...prev,
            [id]: !prev[id],
        }))
    }

    const resetForm = () => {
        setTemplateName("")
        setTemplateSubject("")
        setTemplateBody("")
        setTemplateActive(true)
        setEditingTemplate(null)
    }

    const openCreateModal = () => {
        resetForm()
        setIsTemplateModalOpen(true)
    }

    const openEditModal = (template: EmailTemplateListItem) => {
        setEditingTemplate(template)
        setTemplateName(template.name)
        setTemplateSubject(template.subject)
        setTemplateBody("")
        setTemplateActive(template.is_active)
        setIsTemplateModalOpen(true)
    }

    const handleSaveTemplate = async () => {
        if (editingTemplate) {
            await updateMutation.mutateAsync({
                id: editingTemplate.id,
                data: {
                    name: templateName,
                    subject: templateSubject,
                    body: templateBody || undefined,
                    is_active: templateActive,
                },
            })
        } else {
            await createMutation.mutateAsync({
                name: templateName,
                subject: templateSubject,
                body: templateBody,
            })
        }
        setIsTemplateModalOpen(false)
        resetForm()
    }

    const handleDeleteTemplate = async (id: string) => {
        if (confirm("Are you sure you want to delete this template?")) {
            await deleteMutation.mutateAsync(id)
        }
    }

    const insertVariable = (variable: string | null) => {
        if (variable) {
            setTemplateSubject((prev) => prev + variable)
        }
    }

    const formatDate = (dateStr: string) => {
        const date = new Date(dateStr)
        const now = new Date()
        const diffMs = now.getTime() - date.getTime()
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

        if (diffDays === 0) return "Today"
        if (diffDays === 1) return "Yesterday"
        if (diffDays < 7) return `${diffDays} days ago`
        if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`
        return date.toLocaleDateString()
    }

    return (
        <div className="flex min-h-screen flex-col">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <h1 className="text-2xl font-semibold">Automation</h1>
                    {activeTab === "workflows" && (
                        <Button>
                            <PlusIcon className="mr-2 size-4" />
                            Create Workflow
                        </Button>
                    )}
                    {activeTab === "email-templates" && (
                        <Button className="bg-teal-600 hover:bg-teal-700" onClick={openCreateModal}>
                            <PlusIcon className="mr-2 size-4" />
                            New Template
                        </Button>
                    )}
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 p-6">
                <Tabs value={activeTab} className="space-y-6">
                    {/* Workflows Tab */}
                    <TabsContent value="workflows" className="space-y-4">
                        {automations.map((automation) => {
                            const IconComponent = automation.icon
                            return (
                                <Card key={automation.id}>
                                    <CardContent className="flex items-center justify-between p-6">
                                        <div className="flex items-start gap-4">
                                            <div className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                                                <IconComponent className="size-6" />
                                            </div>
                                            <div className="flex-1">
                                                <h3 className="font-semibold">{automation.name}</h3>
                                                <p className="text-sm text-muted-foreground">{automation.description}</p>
                                                <div className="mt-2">
                                                    <Badge variant="secondary" className="text-xs">
                                                        Trigger: {automation.trigger}
                                                    </Badge>
                                                </div>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-3">
                                            <Switch
                                                checked={enabledStates[automation.id]}
                                                onCheckedChange={() => handleToggle(automation.id)}
                                            />
                                            <DropdownMenu>
                                                <DropdownMenuTrigger className="inline-flex items-center justify-center size-8 p-0 rounded-md hover:bg-accent hover:text-accent-foreground">
                                                    <MoreVerticalIcon className="size-4" />
                                                    <span className="sr-only">Open menu</span>
                                                </DropdownMenuTrigger>
                                                <DropdownMenuContent align="end">
                                                    <DropdownMenuItem>Edit</DropdownMenuItem>
                                                    <DropdownMenuItem>Duplicate</DropdownMenuItem>
                                                    <DropdownMenuItem className="text-destructive">Delete</DropdownMenuItem>
                                                </DropdownMenuContent>
                                            </DropdownMenu>
                                        </div>
                                    </CardContent>
                                </Card>
                            )
                        })}

                        <div className="flex justify-center pt-4">
                            <Button variant="ghost">
                                <WorkflowIcon className="mr-2 size-4" />
                                View automation logs
                            </Button>
                        </div>
                    </TabsContent>

                    {/* Email Templates Tab */}
                    <TabsContent value="email-templates" className="space-y-4">
                        {templatesLoading ? (
                            <Card className="flex items-center justify-center p-12">
                                <LoaderIcon className="size-6 animate-spin text-muted-foreground" />
                                <span className="ml-2 text-muted-foreground">Loading templates...</span>
                            </Card>
                        ) : templates.length === 0 ? (
                            <Card>
                                <CardContent className="flex flex-col items-center justify-center py-12 text-center">
                                    <div className="mb-4 flex size-16 items-center justify-center rounded-full bg-muted">
                                        <MailIcon className="size-8 text-muted-foreground" />
                                    </div>
                                    <h3 className="mb-2 text-lg font-medium">No email templates yet</h3>
                                    <p className="mb-4 text-sm text-muted-foreground">
                                        Create your first template to get started with automated emails
                                    </p>
                                    <Button className="bg-teal-600 hover:bg-teal-700" onClick={openCreateModal}>
                                        <PlusIcon className="mr-2 size-4" />
                                        Create Template
                                    </Button>
                                </CardContent>
                            </Card>
                        ) : (
                            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                                {templates.map((template) => (
                                    <Card key={template.id} className="group relative hover:shadow-md transition-shadow">
                                        <CardContent className="p-4">
                                            <div className="mb-3 flex items-start justify-between">
                                                <div className="flex-1">
                                                    <h3 className="font-medium">{template.name}</h3>
                                                    <p className="mt-1 text-sm text-muted-foreground line-clamp-1">{template.subject}</p>
                                                </div>
                                                <DropdownMenu>
                                                    <DropdownMenuTrigger className="inline-flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity h-8 w-8 p-0 rounded-md hover:bg-accent hover:text-accent-foreground">
                                                        <MoreVerticalIcon className="size-4" />
                                                    </DropdownMenuTrigger>
                                                    <DropdownMenuContent align="end">
                                                        <DropdownMenuItem onClick={() => openEditModal(template)}>Edit</DropdownMenuItem>
                                                        <DropdownMenuItem>
                                                            <CopyIcon className="mr-2 size-4" />
                                                            Duplicate
                                                        </DropdownMenuItem>
                                                        <DropdownMenuItem
                                                            className="text-destructive"
                                                            onClick={() => handleDeleteTemplate(template.id)}
                                                        >
                                                            <TrashIcon className="mr-2 size-4" />
                                                            Delete
                                                        </DropdownMenuItem>
                                                    </DropdownMenuContent>
                                                </DropdownMenu>
                                            </div>
                                            <div className="flex items-center justify-between">
                                                <Badge
                                                    className={
                                                        template.is_active
                                                            ? "bg-green-500/10 text-green-500 border-green-500/20"
                                                            : "bg-gray-500/10 text-gray-500 border-gray-500/20"
                                                    }
                                                >
                                                    {template.is_active ? "Active" : "Inactive"}
                                                </Badge>
                                                <span className="text-xs text-muted-foreground">Updated {formatDate(template.updated_at)}</span>
                                            </div>
                                        </CardContent>
                                    </Card>
                                ))}
                            </div>
                        )}
                    </TabsContent>
                </Tabs>
            </div>

            {/* Template Modal */}
            <Dialog
                open={isTemplateModalOpen}
                onOpenChange={(open) => {
                    setIsTemplateModalOpen(open)
                    if (!open) resetForm()
                }}
            >
                <DialogContent className="max-w-2xl">
                    <DialogHeader>
                        <DialogTitle>{editingTemplate ? "Edit Template" : "Create Email Template"}</DialogTitle>
                        <DialogDescription>
                            {editingTemplate
                                ? "Update your email template"
                                : "Create a new email template for automated communications"}
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="template-name">
                                Template Name <span className="text-destructive">*</span>
                            </Label>
                            <Input
                                id="template-name"
                                placeholder="e.g., Welcome Email"
                                value={templateName}
                                onChange={(e) => setTemplateName(e.target.value)}
                            />
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="subject">
                                Subject Line <span className="text-destructive">*</span>
                            </Label>
                            <div className="flex gap-2">
                                <Input
                                    id="subject"
                                    placeholder="e.g., Welcome to {{organization_name}}"
                                    className="flex-1"
                                    value={templateSubject}
                                    onChange={(e) => setTemplateSubject(e.target.value)}
                                />
                                <Select onValueChange={insertVariable}>
                                    <SelectTrigger className="w-[180px]">
                                        <SelectValue placeholder="Insert variable" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="{{full_name}}">{"{{full_name}}"}</SelectItem>
                                        <SelectItem value="{{case_number}}">{"{{case_number}}"}</SelectItem>
                                        <SelectItem value="{{status}}">{"{{status}}"}</SelectItem>
                                        <SelectItem value="{{organization_name}}">{"{{organization_name}}"}</SelectItem>
                                        <SelectItem value="{{agent_name}}">{"{{agent_name}}"}</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="body">Email Body</Label>
                            <Textarea
                                id="body"
                                rows={8}
                                placeholder="Write your email template here. Use variables like {{full_name}}, {{case_number}}, etc."
                                value={templateBody}
                                onChange={(e) => setTemplateBody(e.target.value)}
                            />
                        </div>

                        <Collapsible open={isVariablesOpen} onOpenChange={setIsVariablesOpen}>
                            <CollapsibleTrigger className="flex w-full items-center justify-between rounded-lg border border-border bg-muted/50 px-4 py-3 text-sm font-medium hover:bg-muted">
                                Available Variables
                                <ChevronDownIcon className={`size-4 transition-transform ${isVariablesOpen ? "rotate-180" : ""}`} />
                            </CollapsibleTrigger>
                            <CollapsibleContent className="mt-2 space-y-2 rounded-lg border border-border bg-muted/30 p-4">
                                <p className="text-xs text-muted-foreground mb-3">Click to copy a variable to your clipboard:</p>
                                <div className="grid grid-cols-2 gap-2">
                                    {[
                                        { var: "{{full_name}}", desc: "Recipient's full name" },
                                        { var: "{{first_name}}", desc: "Recipient's first name" },
                                        { var: "{{case_number}}", desc: "Case number" },
                                        { var: "{{status}}", desc: "Case status" },
                                        { var: "{{organization_name}}", desc: "Your organization name" },
                                        { var: "{{agent_name}}", desc: "Assigned agent name" },
                                    ].map((item) => (
                                        <button
                                            key={item.var}
                                            onClick={() => navigator.clipboard.writeText(item.var)}
                                            className="flex items-start gap-2 rounded-lg border border-border bg-background px-3 py-2 text-left hover:bg-accent"
                                        >
                                            <code className="text-xs font-mono text-teal-600">{item.var}</code>
                                            <div className="flex-1">
                                                <p className="text-xs text-muted-foreground">{item.desc}</p>
                                            </div>
                                            <CopyIcon className="size-3 text-muted-foreground" />
                                        </button>
                                    ))}
                                </div>
                            </CollapsibleContent>
                        </Collapsible>

                        <div className="flex items-center justify-between rounded-lg border border-border bg-muted/30 px-4 py-3">
                            <div className="space-y-0.5">
                                <Label htmlFor="active-toggle">Active</Label>
                                <p className="text-xs text-muted-foreground">Enable this template for automated emails</p>
                            </div>
                            <Switch id="active-toggle" checked={templateActive} onCheckedChange={setTemplateActive} />
                        </div>
                    </div>

                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsTemplateModalOpen(false)}>
                            Cancel
                        </Button>
                        <Button
                            className="bg-teal-600 hover:bg-teal-700"
                            onClick={handleSaveTemplate}
                            disabled={createMutation.isPending || updateMutation.isPending || !templateName || !templateSubject}
                        >
                            {(createMutation.isPending || updateMutation.isPending) && (
                                <LoaderIcon className="mr-2 size-4 animate-spin" />
                            )}
                            {editingTemplate ? "Update Template" : "Save Template"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}
