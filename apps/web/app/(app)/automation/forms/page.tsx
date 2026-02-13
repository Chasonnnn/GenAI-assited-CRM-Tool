"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
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
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
    PlusIcon,
    MoreVerticalIcon,
    FileTextIcon,
    EditIcon,
    Trash2Icon,
    Loader2Icon,
    ArrowLeftIcon,
} from "lucide-react"
import { toast } from "sonner"
import { ApiError } from "@/lib/api"
import {
    useForms,
    useCreateForm,
    useDeleteForm,
    useDeleteFormTemplate,
    useFormTemplates,
    useUseFormTemplate,
} from "@/lib/hooks/use-forms"
import { parseDateInput } from "@/lib/utils/date"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

function formatRelativeTime(dateString: string): string {
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

export default function FormsListPage() {
    const router = useRouter()
    const { data: forms, isLoading } = useForms()
    const createFormMutation = useCreateForm()
    const deleteFormMutation = useDeleteForm()
    const deleteFormTemplateMutation = useDeleteFormTemplate()
    const { data: templates, isLoading: templatesLoading } = useFormTemplates()
    const useTemplateMutation = useUseFormTemplate()

    const [showCreateModal, setShowCreateModal] = useState(false)
    const [formName, setFormName] = useState("")
    const [formDescription, setFormDescription] = useState("")
    const [activeTab, setActiveTab] = useState<"forms" | "templates">("forms")
    const [applyingTemplateId, setApplyingTemplateId] = useState<string | null>(null)
    const [formToDelete, setFormToDelete] = useState<{ id: string; name: string } | null>(null)
    const [templateToDelete, setTemplateToDelete] = useState<{ id: string; name: string } | null>(null)

    const handleCreate = async () => {
        if (!formName.trim()) return
        try {
            const description = formDescription.trim()
            const newForm = await createFormMutation.mutateAsync({
                name: formName.trim(),
                ...(description ? { description } : {}),
            })
            setShowCreateModal(false)
            setFormName("")
            setFormDescription("")
            router.push(`/automation/forms/${newForm.id}`)
        } catch {
            // Error handling is done by React Query
        }
    }

    const handleUseTemplate = async (templateId: string, templateName: string) => {
        if (useTemplateMutation.isPending) return
        setApplyingTemplateId(templateId)
        try {
            const newForm = await useTemplateMutation.mutateAsync({
                templateId,
                payload: { name: templateName },
            })
            router.push(`/automation/forms/${newForm.id}`)
        } catch {
            // Error handling is done by React Query
        } finally {
            setApplyingTemplateId(null)
        }
    }

    const confirmDeleteForm = async () => {
        if (!formToDelete || deleteFormMutation.isPending) return
        try {
            await deleteFormMutation.mutateAsync(formToDelete.id)
            toast.success("Form deleted")
            setFormToDelete(null)
        } catch (error) {
            const message =
                error instanceof ApiError ? error.message : "Failed to delete form. Please try again."
            toast.error(message)
        }
    }

    const confirmDeleteTemplate = async () => {
        if (!templateToDelete || deleteFormTemplateMutation.isPending) return
        try {
            await deleteFormTemplateMutation.mutateAsync(templateToDelete.id)
            toast.success("Template removed from library")
            setTemplateToDelete(null)
        } catch (error) {
            const message =
                error instanceof ApiError
                    ? error.message
                    : "Failed to remove template. Please try again."
            toast.error(message)
        }
    }

    const statusVariant = (status: string) => {
        switch (status) {
            case "published":
                return "default"
            case "draft":
                return "secondary"
            case "archived":
                return "outline"
            default:
                return "secondary"
        }
    }

    const statusLabel = (status: string) => {
        switch (status) {
            case "published":
                return "Published"
            case "draft":
                return "Draft"
            case "archived":
                return "Archived"
            default:
                return status
        }
    }

    return (
        <div className="flex min-h-screen flex-col">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <div className="flex items-center gap-4">
                        <Button variant="ghost" size="icon" onClick={() => router.push("/automation")}>
                            <ArrowLeftIcon className="size-4" />
                        </Button>
                        <h1 className="text-2xl font-semibold">Form Builder</h1>
                    </div>
                    <Button onClick={() => setShowCreateModal(true)}>
                        <PlusIcon className="mr-2 size-4" />
                        Create Form
                    </Button>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 p-6">
                <div className="space-y-6">
                    {/* Description */}
                    <p className="text-sm text-muted-foreground max-w-2xl">
                        Create dynamic application forms to collect information from candidates.
                        Forms can be sent via secure links and submissions can be reviewed and approved.
                    </p>

                    <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as "forms" | "templates")}>
                        <div className="flex items-center justify-between">
                            <TabsList>
                                <TabsTrigger value="forms">Forms</TabsTrigger>
                                <TabsTrigger value="templates">Form Templates</TabsTrigger>
                            </TabsList>
                        </div>

                        <TabsContent value="forms" className="space-y-6">
                            {/* Form List */}
                            {isLoading ? (
                                <div className="flex items-center justify-center py-12">
                                    <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                                </div>
                            ) : !forms?.length ? (
                                <Card>
                                    <CardContent className="flex flex-col items-center justify-center py-12">
                                        <FileTextIcon className="size-12 text-muted-foreground/50" />
                                        <h3 className="mt-4 text-lg font-medium">No forms yet</h3>
                                        <p className="mt-1 text-sm text-muted-foreground">
                                            Create your first form to start collecting applications
                                        </p>
                                        <Button className="mt-4" onClick={() => setShowCreateModal(true)}>
                                            <PlusIcon className="mr-2 size-4" />
                                            Create Form
                                        </Button>
                                    </CardContent>
                                </Card>
                            ) : (
                                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                                    {[...forms]
                                        .sort((a, b) => {
                                            // Published first, then draft, then archived
                                            const order = { published: 0, draft: 1, archived: 2 } as const
                                            const isOrderKey = (value: string): value is keyof typeof order =>
                                                Object.prototype.hasOwnProperty.call(order, value)
                                            const aOrder = isOrderKey(a.status) ? order[a.status] : 3
                                            const bOrder = isOrderKey(b.status) ? order[b.status] : 3
                                            if (aOrder !== bOrder) return aOrder - bOrder
                                            // Then by updated_at descending
                                            return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
                                        })
                                        .map((form) => (
                                            <Card
                                                key={form.id}
                                                className="cursor-pointer hover:bg-accent/50 transition-colors"
                                                onClick={() => router.push(`/automation/forms/${form.id}`)}
                                            >
                                                <CardHeader className="pb-3">
                                                    <div className="flex items-start justify-between">
                                                        <div className="flex items-center gap-3">
                                                            <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-teal-500/10 text-teal-500">
                                                                <FileTextIcon className="size-5" />
                                                            </div>
                                                            <div>
                                                                <CardTitle className="text-base">{form.name}</CardTitle>
                                                                <Badge
                                                                    variant={statusVariant(form.status)}
                                                                    className={`mt-1 text-xs ${form.status === "published" ? "bg-green-500 hover:bg-green-500/80" : ""}`}
                                                                >
                                                                    {statusLabel(form.status)}
                                                                </Badge>
                                                            </div>
                                                        </div>
                                                        <DropdownMenu>
                                                            <DropdownMenuTrigger
                                                                render={
                                                                    <Button
                                                                        variant="ghost"
                                                                        size="icon"
                                                                        className="h-8 w-8"
                                                                        aria-label={`Open menu for ${form.name}`}
                                                                        onClick={(e) => e.stopPropagation()}
                                                                    >
                                                                        <MoreVerticalIcon className="size-4" />
                                                                    </Button>
                                                                }
                                                            />
                                                            <DropdownMenuContent align="end">
                                                                <DropdownMenuItem
                                                                    onClick={(e) => {
                                                                        e.stopPropagation()
                                                                        router.push(`/automation/forms/${form.id}`)
                                                                    }}
                                                                >
                                                                    <EditIcon className="mr-2 size-4" />
                                                                    Edit
                                                                </DropdownMenuItem>
                                                                <DropdownMenuItem
                                                                    className="text-destructive focus:text-destructive"
                                                                    disabled={deleteFormMutation.isPending}
                                                                    onClick={(e) => {
                                                                        e.stopPropagation()
                                                                        setFormToDelete({ id: form.id, name: form.name })
                                                                    }}
                                                                >
                                                                    <Trash2Icon className="mr-2 size-4" />
                                                                    Delete
                                                                </DropdownMenuItem>
                                                            </DropdownMenuContent>
                                                        </DropdownMenu>
                                                    </div>
                                                </CardHeader>
                                                <CardContent className="pt-0">
                                                    <p className="text-xs text-muted-foreground">
                                                        Updated {formatRelativeTime(form.updated_at)}
                                                    </p>
                                                </CardContent>
                                            </Card>
                                        ))}
                                </div>
                            )}
                        </TabsContent>

                        <TabsContent value="templates" className="space-y-6">
                            <Card>
                                <CardContent className="py-6 text-sm text-muted-foreground">
                                    Platform templates are shared across your organization for consistent intake flows.
                                    Apply a template to create a new form that you can customize and send.
                                </CardContent>
                            </Card>

                            {templatesLoading ? (
                                <div className="flex items-center justify-center py-12">
                                    <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                                </div>
                            ) : !templates?.length ? (
                                <Card>
                                    <CardContent className="flex flex-col items-center justify-center py-12">
                                        <FileTextIcon className="size-12 text-muted-foreground/50" />
                                        <h3 className="mt-4 text-lg font-medium">No templates yet</h3>
                                        <p className="mt-1 text-sm text-muted-foreground">
                                            Platform templates will appear here once available
                                        </p>
                                    </CardContent>
                                </Card>
                            ) : (
                                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                                    {templates.map((template) => {
                                        const isApplying = applyingTemplateId === template.id
                                        return (
                                            <Card key={template.id}>
                                                <CardHeader className="pb-3">
                                                    <div className="flex items-start justify-between gap-3">
                                                        <div className="flex items-center gap-3">
                                                            <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-teal-500/10 text-teal-500">
                                                                <FileTextIcon className="size-5" />
                                                            </div>
                                                            <div>
                                                                <CardTitle className="text-base">{template.name}</CardTitle>
                                                                {template.published_at && (
                                                                    <Badge variant="outline" className="mt-1 text-xs">
                                                                        Published
                                                                    </Badge>
                                                                )}
                                                            </div>
                                                        </div>
                                                        <div className="flex items-center gap-1">
                                                            <Button
                                                                size="sm"
                                                                onClick={() => handleUseTemplate(template.id, template.name)}
                                                                disabled={
                                                                    useTemplateMutation.isPending ||
                                                                    deleteFormTemplateMutation.isPending ||
                                                                    isApplying
                                                                }
                                                            >
                                                                {isApplying && (
                                                                    <Loader2Icon className="mr-2 size-4 animate-spin" />
                                                                )}
                                                                Use Template
                                                            </Button>
                                                            <DropdownMenu>
                                                                <DropdownMenuTrigger
                                                                    render={
                                                                        <Button
                                                                            variant="ghost"
                                                                            size="icon"
                                                                            className="h-8 w-8"
                                                                            aria-label={`Open menu for template ${template.name}`}
                                                                        >
                                                                            <MoreVerticalIcon className="size-4" />
                                                                        </Button>
                                                                    }
                                                                />
                                                                <DropdownMenuContent align="end">
                                                                    <DropdownMenuItem
                                                                        className="text-destructive focus:text-destructive"
                                                                        disabled={deleteFormTemplateMutation.isPending}
                                                                        onClick={(e) => {
                                                                            e.stopPropagation()
                                                                            setTemplateToDelete({
                                                                                id: template.id,
                                                                                name: template.name,
                                                                            })
                                                                        }}
                                                                    >
                                                                        <Trash2Icon className="mr-2 size-4" />
                                                                        Remove from library
                                                                    </DropdownMenuItem>
                                                                </DropdownMenuContent>
                                                            </DropdownMenu>
                                                        </div>
                                                    </div>
                                                </CardHeader>
                                                <CardContent className="pt-0">
                                                    <p className="text-sm text-muted-foreground">
                                                        {template.description || "No description provided."}
                                                    </p>
                                                    <p className="mt-2 text-xs text-muted-foreground">
                                                        Updated {formatRelativeTime(template.updated_at)}
                                                    </p>
                                                </CardContent>
                                            </Card>
                                        )
                                    })}
                                </div>
                            )}
                        </TabsContent>
                    </Tabs>
                </div>
            </div>

            {/* Create Form Modal */}
            <Dialog open={showCreateModal} onOpenChange={setShowCreateModal}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Create New Form</DialogTitle>
                        <DialogDescription>
                            Give your form a name and optional description.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label htmlFor="form-name">Form Name *</Label>
                            <Input
                                id="form-name"
                                placeholder="e.g., Surrogate Application"
                                value={formName}
                                onChange={(e) => setFormName(e.target.value)}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="form-description">Description (optional)</Label>
                            <Input
                                id="form-description"
                                placeholder="Brief description of the form"
                                value={formDescription}
                                onChange={(e) => setFormDescription(e.target.value)}
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setShowCreateModal(false)}>
                            Cancel
                        </Button>
                        <Button
                            onClick={handleCreate}
                            disabled={!formName.trim() || createFormMutation.isPending}
                        >
                            {createFormMutation.isPending && (
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                            )}
                            Create Form
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            <AlertDialog open={!!formToDelete} onOpenChange={(open) => !open && setFormToDelete(null)}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Delete form?</AlertDialogTitle>
                        <AlertDialogDescription>
                            This will permanently delete{" "}
                            <span className="font-medium text-foreground">{formToDelete?.name}</span>{" "}
                            and any related submissions. This action cannot be undone.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={deleteFormMutation.isPending}>
                            Cancel
                        </AlertDialogCancel>
                        <AlertDialogAction
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                            disabled={deleteFormMutation.isPending}
                            onClick={confirmDeleteForm}
                        >
                            {deleteFormMutation.isPending && (
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                            )}
                            Delete
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            <AlertDialog
                open={!!templateToDelete}
                onOpenChange={(open) => !open && setTemplateToDelete(null)}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Remove template from library?</AlertDialogTitle>
                        <AlertDialogDescription>
                            This will remove{" "}
                            <span className="font-medium text-foreground">{templateToDelete?.name}</span>{" "}
                            from your organization&apos;s Form Templates tab only. Existing forms created
                            from this template are not affected.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={deleteFormTemplateMutation.isPending}>
                            Cancel
                        </AlertDialogCancel>
                        <AlertDialogAction
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                            disabled={deleteFormTemplateMutation.isPending}
                            onClick={confirmDeleteTemplate}
                        >
                            {deleteFormTemplateMutation.isPending && (
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                            )}
                            Remove
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    )
}
