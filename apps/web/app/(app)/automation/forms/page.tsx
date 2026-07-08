"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import {
    ArrowLeftIcon,
    EditIcon,
    FileTextIcon,
    LinkIcon,
    Loader2Icon,
    MoreVerticalIcon,
    PlusIcon,
    QrCodeIcon,
    Trash2Icon,
} from "lucide-react"
import { QRCodeSVG } from "qrcode.react"
import { toast } from "sonner"

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
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ApiError } from "@/lib/api"
import {
    listFormIntakeLinks,
    type FormIntakeLinkRead,
    type FormSummary,
    type FormTemplateLibraryItem,
} from "@/lib/api/forms"
import {
    useCreateForm,
    useDeleteForm,
    useDeleteFormTemplate,
    useForms,
    useFormTemplates,
    useUseFormTemplate,
} from "@/lib/hooks/use-forms"
import { parseDateInput } from "@/lib/utils/date"

type FormsTab = "forms" | "templates"
type DeleteTarget = { id: string; name: string }

function formatRelativeTime(dateString: string): string {
    const date = parseDateInput(dateString)
    const now = new Date()
    if (Number.isNaN(date.getTime())) {
        return "Updated recently"
    }

    if (date.getTime() > now.getTime()) {
        return `Saved ${date.toLocaleTimeString("en-US", {
            hour: "numeric",
            minute: "2-digit",
        })}`
    }

    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 60) return `Updated ${diffMins}m ago`
    if (diffHours < 24) return `Updated ${diffHours}h ago`
    if (diffDays === 1) return "Updated Yesterday"
    return `Updated ${diffDays}d ago`
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

const pickShareLink = (links: FormIntakeLinkRead[]): FormIntakeLinkRead | null => {
    return (
        links.find((link) => link.is_active && Boolean(link.intake_url)) ||
        links.find((link) => Boolean(link.intake_url)) ||
        null
    )
}

const getShareQrSvgMarkup = () => {
    const svg = document.querySelector("#forms-share-qr svg")
    if (!(svg instanceof SVGSVGElement)) {
        toast.error("QR code is not ready yet")
        return null
    }

    let markup = new XMLSerializer().serializeToString(svg)
    if (!markup.includes("xmlns=\"http://www.w3.org/2000/svg\"")) {
        markup = markup.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"')
    }
    return markup
}

const downloadBlob = (blob: Blob, filename: string) => {
    const downloadUrl = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = downloadUrl
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(downloadUrl)
}

function FormsPageHeader({
    onBack,
    onCreateForm,
}: {
    onBack: () => void
    onCreateForm: () => void
}) {
    return (
        <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="flex h-16 items-center justify-between px-6">
                <div className="flex items-center gap-4">
                    <Button
                        variant="ghost"
                        size="icon"
                        aria-label="Back to automation"
                        onClick={onBack}
                    >
                        <ArrowLeftIcon className="size-4" aria-hidden="true" />
                    </Button>
                    <h1 className="text-2xl font-semibold">Form Builder</h1>
                </div>
                <Button onClick={onCreateForm}>
                    <PlusIcon className="mr-2 size-4" />
                    Create Form
                </Button>
            </div>
        </div>
    )
}

function FormsPageTabs({
    activeTab,
    onActiveTabChange,
    forms,
    isFormsLoading,
    onCreateForm,
    onOpenForm,
    isDeletingForm,
    onDeleteForm,
    onShareForm,
    templates,
    templatesLoading,
    applyingTemplateId,
    isTemplateActionPending,
    onUseTemplate,
    onDeleteTemplate,
}: {
    activeTab: FormsTab
    onActiveTabChange: (value: FormsTab) => void
    forms: FormSummary[] | undefined
    isFormsLoading: boolean
    onCreateForm: () => void
    onOpenForm: (formId: string) => void
    isDeletingForm: boolean
    onDeleteForm: (target: DeleteTarget) => void
    onShareForm: (form: FormSummary) => void
    templates: FormTemplateLibraryItem[] | undefined
    templatesLoading: boolean
    applyingTemplateId: string | null
    isTemplateActionPending: boolean
    onUseTemplate: (templateId: string, templateName: string) => void
    onDeleteTemplate: (target: DeleteTarget) => void
}) {
    return (
        <Tabs
            value={activeTab}
            onValueChange={(value) => onActiveTabChange(value as FormsTab)}
        >
            <div className="flex items-center justify-between">
                <TabsList>
                    <TabsTrigger value="forms">Forms</TabsTrigger>
                    <TabsTrigger value="templates">Form Templates</TabsTrigger>
                </TabsList>
            </div>

            <TabsContent value="forms" className="space-y-6">
                <FormsGrid
                    forms={forms}
                    isLoading={isFormsLoading}
                    onCreateForm={onCreateForm}
                    onOpenForm={onOpenForm}
                    isDeletingForm={isDeletingForm}
                    onDeleteForm={onDeleteForm}
                    onShareForm={onShareForm}
                />
            </TabsContent>

            <TabsContent value="templates" className="space-y-6">
                <Card>
                    <CardContent className="py-6 text-sm text-muted-foreground">
                        Platform templates are shared across your organization for consistent intake flows.
                        Apply a template to create a new form that you can customize and send.
                    </CardContent>
                </Card>

                <FormTemplatesGrid
                    templates={templates}
                    isLoading={templatesLoading}
                    applyingTemplateId={applyingTemplateId}
                    isTemplateActionPending={isTemplateActionPending}
                    onUseTemplate={onUseTemplate}
                    onDeleteTemplate={onDeleteTemplate}
                />
            </TabsContent>
        </Tabs>
    )
}

function FormsGrid({
    forms,
    isLoading,
    onCreateForm,
    onOpenForm,
    isDeletingForm,
    onDeleteForm,
    onShareForm,
}: {
    forms: FormSummary[] | undefined
    isLoading: boolean
    onCreateForm: () => void
    onOpenForm: (formId: string) => void
    isDeletingForm: boolean
    onDeleteForm: (target: DeleteTarget) => void
    onShareForm: (form: FormSummary) => void
}) {
    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-12">
                <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (!forms?.length) {
        return (
            <Card>
                <CardContent className="flex flex-col items-center justify-center py-12">
                    <FileTextIcon className="size-12 text-muted-foreground/50" />
                    <h3 className="mt-4 text-lg font-medium">No forms yet</h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                        Create your first form to start collecting applications
                    </p>
                    <Button className="mt-4" onClick={onCreateForm}>
                        <PlusIcon className="mr-2 size-4" />
                        Create Form
                    </Button>
                </CardContent>
            </Card>
        )
    }

    return (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {forms.toSorted(compareForms).map((form) => (
                <FormCard
                    key={form.id}
                    form={form}
                    onOpenForm={onOpenForm}
                    isDeletingForm={isDeletingForm}
                    onDeleteForm={onDeleteForm}
                    onShareForm={onShareForm}
                />
            ))}
        </div>
    )
}

function compareForms(a: FormSummary, b: FormSummary) {
    const order = { published: 0, draft: 1, archived: 2 } as const
    const isOrderKey = (value: string): value is keyof typeof order =>
        Object.prototype.hasOwnProperty.call(order, value)
    const aOrder = isOrderKey(a.status) ? order[a.status] : 3
    const bOrder = isOrderKey(b.status) ? order[b.status] : 3
    if (aOrder !== bOrder) return aOrder - bOrder
    return parseDateInput(b.updated_at).getTime() - parseDateInput(a.updated_at).getTime()
}

function FormCard({
    form,
    onOpenForm,
    isDeletingForm,
    onDeleteForm,
    onShareForm,
}: {
    form: FormSummary
    onOpenForm: (formId: string) => void
    isDeletingForm: boolean
    onDeleteForm: (target: DeleteTarget) => void
    onShareForm: (form: FormSummary) => void
}) {
    return (
        <Card
            className="cursor-pointer transition-colors hover:bg-accent/50"
            onClick={() => onOpenForm(form.id)}
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
                                    className="size-8"
                                    aria-label={`Open menu for ${form.name}`}
                                    onClick={(event) => event.stopPropagation()}
                                >
                                    <MoreVerticalIcon className="size-4" aria-hidden="true" />
                                </Button>
                            }
                        />
                        <DropdownMenuContent align="end">
                            <DropdownMenuItem
                                onClick={(event) => {
                                    event.stopPropagation()
                                    onOpenForm(form.id)
                                }}
                            >
                                <EditIcon className="mr-2 size-4" />
                                Edit
                            </DropdownMenuItem>
                            <DropdownMenuItem
                                disabled={form.status !== "published"}
                                onClick={(event) => {
                                    event.stopPropagation()
                                    onShareForm(form)
                                }}
                            >
                                <LinkIcon className="mr-2 size-4" />
                                Share
                            </DropdownMenuItem>
                            <DropdownMenuItem
                                className="text-destructive focus:text-destructive"
                                disabled={isDeletingForm}
                                onClick={(event) => {
                                    event.stopPropagation()
                                    onDeleteForm({ id: form.id, name: form.name })
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
                <p className="text-xs text-muted-foreground">{formatRelativeTime(form.updated_at)}</p>
            </CardContent>
        </Card>
    )
}

function FormTemplatesGrid({
    templates,
    isLoading,
    applyingTemplateId,
    isTemplateActionPending,
    onUseTemplate,
    onDeleteTemplate,
}: {
    templates: FormTemplateLibraryItem[] | undefined
    isLoading: boolean
    applyingTemplateId: string | null
    isTemplateActionPending: boolean
    onUseTemplate: (templateId: string, templateName: string) => void
    onDeleteTemplate: (target: DeleteTarget) => void
}) {
    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-12">
                <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (!templates?.length) {
        return (
            <Card>
                <CardContent className="flex flex-col items-center justify-center py-12">
                    <FileTextIcon className="size-12 text-muted-foreground/50" />
                    <h3 className="mt-4 text-lg font-medium">No templates yet</h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                        Platform templates will appear here once available
                    </p>
                </CardContent>
            </Card>
        )
    }

    return (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {templates.map((template) => (
                <FormTemplateCard
                    key={template.id}
                    template={template}
                    isApplying={applyingTemplateId === template.id}
                    isTemplateActionPending={isTemplateActionPending}
                    onUseTemplate={onUseTemplate}
                    onDeleteTemplate={onDeleteTemplate}
                />
            ))}
        </div>
    )
}

function FormTemplateCard({
    template,
    isApplying,
    isTemplateActionPending,
    onUseTemplate,
    onDeleteTemplate,
}: {
    template: FormTemplateLibraryItem
    isApplying: boolean
    isTemplateActionPending: boolean
    onUseTemplate: (templateId: string, templateName: string) => void
    onDeleteTemplate: (target: DeleteTarget) => void
}) {
    return (
        <Card>
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
                            onClick={() => onUseTemplate(template.id, template.name)}
                            disabled={isTemplateActionPending || isApplying}
                        >
                            {isApplying && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                            Use Template
                        </Button>
                        <DropdownMenu>
                            <DropdownMenuTrigger
                                render={
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        className="size-8"
                                        aria-label={`Open menu for template ${template.name}`}
                                    >
                                        <MoreVerticalIcon className="size-4" aria-hidden="true" />
                                    </Button>
                                }
                            />
                            <DropdownMenuContent align="end">
                                <DropdownMenuItem
                                    className="text-destructive focus:text-destructive"
                                    disabled={isTemplateActionPending}
                                    onClick={(event) => {
                                        event.stopPropagation()
                                        onDeleteTemplate({ id: template.id, name: template.name })
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
                    {formatRelativeTime(template.updated_at)}
                </p>
            </CardContent>
        </Card>
    )
}

function CreateFormDialog({
    open,
    onOpenChange,
    formName,
    onFormNameChange,
    formDescription,
    onFormDescriptionChange,
    isCreating,
    onCreate,
}: {
    open: boolean
    onOpenChange: (value: boolean) => void
    formName: string
    onFormNameChange: (value: string) => void
    formDescription: string
    onFormDescriptionChange: (value: string) => void
    isCreating: boolean
    onCreate: () => void
}) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
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
                            onChange={(event) => onFormNameChange(event.target.value)}
                        />
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="form-description">Description (optional)</Label>
                        <Input
                            id="form-description"
                            placeholder="Brief description of the form"
                            value={formDescription}
                            onChange={(event) => onFormDescriptionChange(event.target.value)}
                        />
                    </div>
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>
                        Cancel
                    </Button>
                    <Button onClick={onCreate} disabled={!formName.trim() || isCreating}>
                        {isCreating && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                        Create Form
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

function DeleteFormDialog({
    open,
    title,
    actionLabel,
    isPending,
    onClose,
    onConfirm,
    children,
}: {
    open: boolean
    title: string
    actionLabel: string
    isPending: boolean
    onClose: () => void
    onConfirm: () => void
    children: React.ReactNode
}) {
    return (
        <AlertDialog open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
            <AlertDialogContent>
                <AlertDialogHeader>
                    <AlertDialogTitle>{title}</AlertDialogTitle>
                    <AlertDialogDescription>{children}</AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                    <AlertDialogCancel disabled={isPending}>Cancel</AlertDialogCancel>
                    <AlertDialogAction
                        className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        disabled={isPending}
                        onClick={onConfirm}
                    >
                        {isPending && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                        {actionLabel}
                    </AlertDialogAction>
                </AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>
    )
}

function ShareFormDialog({
    targetForm,
    shareLink,
    isPreparingShare,
    isShareActionPending,
    onClose,
    onCopyLink,
    onDownloadQrCode,
}: {
    targetForm: DeleteTarget | null
    shareLink: FormIntakeLinkRead | null
    isPreparingShare: boolean
    isShareActionPending: boolean
    onClose: () => void
    onCopyLink: () => void
    onDownloadQrCode: () => void
}) {
    return (
        <AlertDialog open={!!targetForm} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
            <AlertDialogContent>
                <AlertDialogHeader>
                    <AlertDialogTitle>Share Application Form</AlertDialogTitle>
                    <AlertDialogDescription>
                        Choose how you want to share{" "}
                        <span className="font-medium text-foreground">{targetForm?.name}</span>.
                    </AlertDialogDescription>
                </AlertDialogHeader>

                {isPreparingShare ? (
                    <div className="flex items-center gap-2 rounded-md border border-stone-200 bg-stone-50 p-3 text-sm text-stone-600">
                        <Loader2Icon className="size-4 animate-spin" />
                        Preparing link and QR code
                    </div>
                ) : shareLink?.intake_url ? (
                    <div className="space-y-3 rounded-md border border-stone-200 bg-stone-50 p-3">
                        <div className="break-all text-xs text-stone-600">{shareLink.intake_url}</div>
                        <div className="inline-flex rounded-md border border-stone-200 bg-white p-2">
                            <div id="forms-share-qr">
                                <QRCodeSVG value={shareLink.intake_url} size={120} includeMargin />
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-700">
                        No share link is ready yet. Open this form and publish it first.
                    </div>
                )}

                <AlertDialogFooter>
                    <AlertDialogCancel disabled={isPreparingShare || isShareActionPending}>
                        Cancel
                    </AlertDialogCancel>
                    <Button
                        type="button"
                        variant="outline"
                        disabled={!shareLink || isPreparingShare || isShareActionPending}
                        onClick={onCopyLink}
                    >
                        {isShareActionPending ? (
                            <Loader2Icon className="mr-2 size-4 animate-spin" />
                        ) : (
                            <LinkIcon className="mr-2 size-4" />
                        )}
                        Copy Link
                    </Button>
                    <Button
                        type="button"
                        disabled={!shareLink || isPreparingShare || isShareActionPending}
                        onClick={onDownloadQrCode}
                    >
                        {isShareActionPending ? (
                            <Loader2Icon className="mr-2 size-4 animate-spin" />
                        ) : (
                            <QrCodeIcon className="mr-2 size-4" />
                        )}
                        Download QR Code
                    </Button>
                </AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>
    )
}

export default function FormsListPage() {
    const { push } = useRouter()
    const { data: forms, isLoading } = useForms()
    const createFormMutation = useCreateForm()
    const deleteFormMutation = useDeleteForm()
    const deleteFormTemplateMutation = useDeleteFormTemplate()
    const { data: templates, isLoading: templatesLoading } = useFormTemplates()
    const useTemplateMutation = useUseFormTemplate()

    const [showCreateModal, setShowCreateModal] = useState(false)
    const [formName, setFormName] = useState("")
    const [formDescription, setFormDescription] = useState("")
    const [activeTab, setActiveTab] = useState<FormsTab>("forms")
    const [applyingTemplateId, setApplyingTemplateId] = useState<string | null>(null)
    const [formToDelete, setFormToDelete] = useState<DeleteTarget | null>(null)
    const [templateToDelete, setTemplateToDelete] = useState<DeleteTarget | null>(null)
    const [shareTargetForm, setShareTargetForm] = useState<DeleteTarget | null>(null)
    const [shareLink, setShareLink] = useState<FormIntakeLinkRead | null>(null)
    const [isPreparingShare, setIsPreparingShare] = useState(false)
    const [isShareActionPending, setIsShareActionPending] = useState(false)

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
            push(`/automation/forms/${newForm.id}`)
        } catch {
            // Error handling is done by React Query
        }
    }

    const handleUseTemplate = async (templateId: string, templateName: string) => {
        if (useTemplateMutation.isPending) return
        setApplyingTemplateId(templateId)
        const finishTemplateApply = () => setApplyingTemplateId(null)
        try {
            const newForm = await useTemplateMutation.mutateAsync({
                templateId,
                payload: { name: templateName },
            })
            push(`/automation/forms/${newForm.id}`)
            finishTemplateApply()
        } catch {
            // Error handling is done by React Query
            finishTemplateApply()
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

    const resetSharePrompt = () => {
        setShareTargetForm(null)
        setShareLink(null)
        setIsPreparingShare(false)
        setIsShareActionPending(false)
    }

    const handleOpenSharePrompt = async (form: FormSummary) => {
        if (form.status !== "published") {
            toast.error("Publish this form before sharing.")
            return
        }

        setShareTargetForm({ id: form.id, name: form.name })
        setShareLink(null)
        setIsPreparingShare(true)
        const finishSharePreparation = () => setIsPreparingShare(false)

        try {
            const links = await listFormIntakeLinks(form.id, true)
            const selected = pickShareLink(links)
            if (!selected?.intake_url) {
                toast.error("No shared link is available yet for this form.")
                finishSharePreparation()
                return
            }
            setShareLink(selected)
            finishSharePreparation()
        } catch (error) {
            const message =
                error instanceof ApiError
                    ? error.message
                    : "Failed to prepare share link. Please try again."
            toast.error(message)
            finishSharePreparation()
        }
    }

    const handleCopyShareLink = async () => {
        if (!shareLink?.intake_url) return
        setIsShareActionPending(true)
        const finishShareAction = () => setIsShareActionPending(false)
        try {
            await navigator.clipboard.writeText(shareLink.intake_url)
            toast.success("Application link copied")
            resetSharePrompt()
            finishShareAction()
        } catch {
            toast.error("Failed to copy link")
            finishShareAction()
        }
    }

    const buildShareQrFilename = () => {
        const baseRaw =
            shareLink?.event_name || shareLink?.campaign_name || shareTargetForm?.name || "application-link"
        const base = baseRaw
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/^-+|-+$/g, "")
        return `${base || "application-link"}-qr.png`
    }

    const handleDownloadQrCode = async () => {
        const markup = getShareQrSvgMarkup()
        if (!markup) return

        setIsShareActionPending(true)
        const svgBlob = new Blob([markup], { type: "image/svg+xml;charset=utf-8" })
        const svgUrl = URL.createObjectURL(svgBlob)
        const finishShareAction = () => {
            URL.revokeObjectURL(svgUrl)
            setIsShareActionPending(false)
        }
        try {
            const image = new Image()
            image.crossOrigin = "anonymous"

            await new Promise<void>((resolve, reject) => {
                image.onload = () => resolve()
                image.onerror = () => reject(new Error("Failed to render QR image"))
                image.src = svgUrl
            })

            const canvas = document.createElement("canvas")
            canvas.width = image.width || 120
            canvas.height = image.height || 120
            const context = canvas.getContext("2d")
            if (!context) {
                toast.error("Could not prepare QR download")
                finishShareAction()
                return
            }
            context.drawImage(image, 0, 0)

            const blob = await new Promise<Blob | null>((resolve) =>
                canvas.toBlob((result) => resolve(result), "image/png"),
            )
            if (!blob) {
                toast.error("Could not generate QR code")
                finishShareAction()
                return
            }

            downloadBlob(blob, buildShareQrFilename())
            toast.success("QR code downloaded")
            resetSharePrompt()
            finishShareAction()
        } catch {
            toast.error("Failed to download QR code")
            finishShareAction()
        }
    }

    return (
        <div className="flex min-h-screen flex-col">
            <FormsPageHeader
                onBack={() => push("/automation")}
                onCreateForm={() => setShowCreateModal(true)}
            />

            <div className="flex-1 p-6">
                <div className="space-y-6">
                    <p className="max-w-2xl text-sm text-muted-foreground">
                        Create dynamic application forms to collect information from candidates.
                        Forms can be sent via secure links and submissions can be reviewed and approved.
                    </p>

                    <FormsPageTabs
                        activeTab={activeTab}
                        onActiveTabChange={setActiveTab}
                        forms={forms}
                        isFormsLoading={isLoading}
                        onCreateForm={() => setShowCreateModal(true)}
                        onOpenForm={(formId) => push(`/automation/forms/${formId}`)}
                        isDeletingForm={deleteFormMutation.isPending}
                        onDeleteForm={setFormToDelete}
                        onShareForm={(form) => void handleOpenSharePrompt(form)}
                        templates={templates}
                        templatesLoading={templatesLoading}
                        applyingTemplateId={applyingTemplateId}
                        isTemplateActionPending={
                            useTemplateMutation.isPending || deleteFormTemplateMutation.isPending
                        }
                        onUseTemplate={(templateId, templateName) =>
                            void handleUseTemplate(templateId, templateName)
                        }
                        onDeleteTemplate={setTemplateToDelete}
                    />
                </div>
            </div>

            <CreateFormDialog
                open={showCreateModal}
                onOpenChange={setShowCreateModal}
                formName={formName}
                onFormNameChange={setFormName}
                formDescription={formDescription}
                onFormDescriptionChange={setFormDescription}
                isCreating={createFormMutation.isPending}
                onCreate={() => void handleCreate()}
            />

            <DeleteFormDialog
                open={!!formToDelete}
                title="Delete form?"
                actionLabel="Delete"
                isPending={deleteFormMutation.isPending}
                onClose={() => setFormToDelete(null)}
                onConfirm={() => void confirmDeleteForm()}
            >
                This will permanently delete{" "}
                <span className="font-medium text-foreground">{formToDelete?.name}</span>{" "}
                and any related submissions. This action cannot be undone.
            </DeleteFormDialog>

            <DeleteFormDialog
                open={!!templateToDelete}
                title="Remove template from library?"
                actionLabel="Remove"
                isPending={deleteFormTemplateMutation.isPending}
                onClose={() => setTemplateToDelete(null)}
                onConfirm={() => void confirmDeleteTemplate()}
            >
                This will remove{" "}
                <span className="font-medium text-foreground">{templateToDelete?.name}</span> from
                your organization&apos;s Form Templates tab only. Existing forms created from this
                template are not affected.
            </DeleteFormDialog>

            <ShareFormDialog
                targetForm={shareTargetForm}
                shareLink={shareLink}
                isPreparingShare={isPreparingShare}
                isShareActionPending={isShareActionPending}
                onClose={resetSharePrompt}
                onCopyLink={() => void handleCopyShareLink()}
                onDownloadQrCode={() => void handleDownloadQrCode()}
            />
        </div>
    )
}
