"use client"

import { useState, useSyncExternalStore, type ReactNode } from "react"
import type { Route } from "next"
import Link from "next/link"
import { useRouter } from "next/navigation"
import {
    EditIcon,
    FileTextIcon,
    LinkIcon,
    Loader2Icon,
    MoreHorizontalIcon,
    PlusIcon,
    QrCodeIcon,
    SearchIcon,
    Trash2Icon,
} from "lucide-react"
import { QRCodeSVG } from "qrcode.react"
import { toast } from "@/components/ui/toast"

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
import { EmptyState } from "@/components/empty-state"
import { LoadErrorState, PermissionDeniedState, QueryErrorState } from "@/components/error-state"
import { FORM_BUILDER_DENIED } from "@/components/forms/builder/FormBuilderAccessStates"
import { PageHeader } from "@/components/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { useCurrentMinuteTimestamp } from "@/components/ui/use-current-minute-timestamp"
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
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { ApiError } from "@/lib/api"
import { usePermissionCheck } from "@/lib/hooks/use-permission-check"
import {
    listFormIntakeLinks,
    type FormIntakeLinkRead,
    type FormLeadKind,
    type FormListItem,
    type FormSummary,
    type FormTemplateLibraryItem,
} from "@/lib/api/forms"
import {
    FORM_LEAD_KIND_LABELS,
    FORM_LEAD_KIND_OPTIONS,
} from "@/lib/forms/form-lead-kind"
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

let browserTimeZoneSnapshot: string | null = null

function subscribeBrowserTimeZone() {
    return () => undefined
}

function getBrowserTimeZoneSnapshot() {
    if (browserTimeZoneSnapshot) return browserTimeZoneSnapshot
    try {
        browserTimeZoneSnapshot = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"
    } catch {
        browserTimeZoneSnapshot = "UTC"
    }
    return browserTimeZoneSnapshot
}

function getServerTimeZoneSnapshot() {
    return null
}

function formatRelativeTime(dateString: string, nowTimestamp: number, timeZone: string): string {
    const date = parseDateInput(dateString)
    if (Number.isNaN(date.getTime())) {
        return "Updated recently"
    }

    // nowTimestamp is floored to the minute, so a save in the current minute is up to a minute ahead of it.
    const diffMs = nowTimestamp - date.getTime()
    if (diffMs < -60000) {
        return `Saved ${date.toLocaleTimeString("en-US", {
            hour: "numeric",
            minute: "2-digit",
            timeZone,
        })}`
    }

    const diffMins = Math.floor(Math.max(diffMs, 0) / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return "Updated just now"
    if (diffMins < 60) return `Updated ${diffMins}m ago`
    if (diffHours < 24) return `Updated ${diffHours}h ago`
    if (diffDays === 1) return "Updated Yesterday"
    return `Updated ${diffDays}d ago`
}

function FormRelativeTime({ dateString }: { dateString: string }) {
    const nowTimestamp = useCurrentMinuteTimestamp()
    const timeZone = useSyncExternalStore(
        subscribeBrowserTimeZone,
        getBrowserTimeZoneSnapshot,
        getServerTimeZoneSnapshot,
    )

    if (nowTimestamp === null || timeZone === null) return "Updated recently"
    return formatRelativeTime(dateString, nowTimestamp, timeZone)
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

async function runWithPendingState(
    setPending: (pending: boolean) => void,
    action: () => Promise<void>,
) {
    setPending(true)
    try {
        await action()
    } finally {
        setPending(false)
    }
}

type LoadErrorInfo = {
    error: unknown
    retry: () => void
    isRetrying: boolean
}

function FormsPageHeader({ onCreateForm }: { onCreateForm?: (() => void) | undefined }) {
    return (
        <PageHeader
            title="Form Builder"
            actions={
                onCreateForm ? (
                    <Button onClick={onCreateForm}>
                        <PlusIcon className="mr-2 size-4" />
                        Create Form
                    </Button>
                ) : null
            }
        />
    )
}

type FormStatusFilter = "all" | "published" | "draft" | "archived"

const FORM_STATUS_FILTERS: { value: FormStatusFilter; label: string }[] = [
    { value: "all", label: "All" },
    { value: "published", label: "Published" },
    { value: "draft", label: "Drafts" },
    { value: "archived", label: "Archived" },
]

function matchesSearch(name: string, search: string) {
    const query = search.trim().toLowerCase()
    return !query || name.toLowerCase().includes(query)
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
    templatesLoadError,
    applyingTemplateId,
    isTemplateActionPending,
    onUseTemplate,
    onDeleteTemplate,
}: {
    activeTab: FormsTab
    onActiveTabChange: (value: FormsTab) => void
    forms: FormListItem[] | undefined
    isFormsLoading: boolean
    onCreateForm: () => void
    onOpenForm: (formId: string) => void
    isDeletingForm: boolean
    onDeleteForm: (target: DeleteTarget) => void
    onShareForm: (form: FormSummary) => void
    templates: FormTemplateLibraryItem[] | undefined
    templatesLoading: boolean
    templatesLoadError: LoadErrorInfo | null
    applyingTemplateId: string | null
    isTemplateActionPending: boolean
    onUseTemplate: (templateId: string, templateName: string) => void
    onDeleteTemplate: (target: DeleteTarget) => void
}) {
    const [search, setSearch] = useState("")
    const [statusFilter, setStatusFilter] = useState<FormStatusFilter>("all")
    const visibleForms = forms?.filter(
        (form) =>
            (statusFilter === "all" || form.status === statusFilter) && matchesSearch(form.name, search),
    )
    const visibleTemplates = templates?.filter((template) => matchesSearch(template.name, search))

    return (
        <Tabs
            value={activeTab}
            onValueChange={(value) => onActiveTabChange(value as FormsTab)}
        >
            <div className="flex flex-wrap items-center justify-between gap-3">
                <TabsList>
                    <TabsTrigger value="forms" className="gap-1.5">
                        Forms{" "}
                        {forms ? <span className="text-muted-foreground tabular-nums">{forms.length}</span> : null}
                    </TabsTrigger>
                    <TabsTrigger value="templates" className="gap-1.5">
                        Form Templates{" "}
                        {templates ? (
                            <span className="text-muted-foreground tabular-nums">{templates.length}</span>
                        ) : null}
                    </TabsTrigger>
                </TabsList>
                <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
                    {activeTab === "forms" ? (
                        <ToggleGroup
                            aria-label="Form status"
                            variant="outline"
                            size="sm"
                            spacing={1}
                            value={[statusFilter]}
                            onValueChange={(value) => {
                                const next = value[0] as FormStatusFilter | undefined
                                if (next) setStatusFilter(next)
                            }}
                        >
                            {FORM_STATUS_FILTERS.map((filter) => (
                                <ToggleGroupItem
                                    key={filter.value}
                                    value={filter.value}
                                    className="rounded-full px-3 aria-pressed:border-foreground aria-pressed:bg-foreground aria-pressed:text-background"
                                >
                                    {filter.label}
                                </ToggleGroupItem>
                            ))}
                        </ToggleGroup>
                    ) : null}
                    <div className="relative w-full sm:w-56">
                        <SearchIcon
                            aria-hidden="true"
                            className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
                        />
                        <Input
                            type="search"
                            aria-label={activeTab === "forms" ? "Search forms" : "Search form templates"}
                            placeholder="Search"
                            value={search}
                            onChange={(event) => setSearch(event.target.value)}
                            className="pl-8"
                        />
                    </div>
                </div>
            </div>

            <TabsContent value="forms" className="space-y-6">
                <FormsGrid
                    forms={visibleForms}
                    hasForms={Boolean(forms?.length)}
                    isLoading={isFormsLoading}
                    onCreateForm={onCreateForm}
                    onOpenForm={onOpenForm}
                    isDeletingForm={isDeletingForm}
                    onDeleteForm={onDeleteForm}
                    onShareForm={onShareForm}
                />
            </TabsContent>

            <TabsContent value="templates" className="space-y-6">
                <FormTemplatesGrid
                    templates={visibleTemplates}
                    hasTemplates={Boolean(templates?.length)}
                    isLoading={templatesLoading}
                    loadError={templatesLoadError}
                    applyingTemplateId={applyingTemplateId}
                    isTemplateActionPending={isTemplateActionPending}
                    onUseTemplate={onUseTemplate}
                    onDeleteTemplate={onDeleteTemplate}
                />
            </TabsContent>
        </Tabs>
    )
}

function NoMatchingItems({ label }: { label: string }) {
    return (
        <Card className="py-0">
            <EmptyState icon={SearchIcon} title={label} headingLevel={2} />
        </Card>
    )
}

function FormsGrid({
    forms,
    hasForms,
    isLoading,
    onCreateForm,
    onOpenForm,
    isDeletingForm,
    onDeleteForm,
    onShareForm,
}: {
    forms: FormListItem[] | undefined
    hasForms: boolean
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

    if (!hasForms) {
        return (
            <Card className="py-0">
                <EmptyState
                    icon={FileTextIcon}
                    title="No forms yet"
                    headingLevel={2}
                    action={
                        <Button onClick={onCreateForm}>
                            <PlusIcon className="mr-2 size-4" />
                            Create Form
                        </Button>
                    }
                />
            </Card>
        )
    }

    if (!forms?.length) {
        return <NoMatchingItems label="No matching forms" />
    }

    return (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
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

function compareForms(a: FormListItem, b: FormListItem) {
    const order = { published: 0, draft: 1, archived: 2 } as const
    const isOrderKey = (value: string): value is keyof typeof order =>
        Object.prototype.hasOwnProperty.call(order, value)
    const aOrder = isOrderKey(a.status) ? order[a.status] : 3
    const bOrder = isOrderKey(b.status) ? order[b.status] : 3
    if (aOrder !== bOrder) return aOrder - bOrder
    return parseDateInput(b.updated_at).getTime() - parseDateInput(a.updated_at).getTime()
}

const statusBadgeClassName: Record<string, string> = {
    published: "border-transparent bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300",
    draft: "border-transparent bg-amber-50 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
    archived: "border-transparent bg-muted text-muted-foreground",
}

function FormCard({
    form,
    onOpenForm,
    isDeletingForm,
    onDeleteForm,
    onShareForm,
}: {
    form: FormListItem
    onOpenForm: (formId: string) => void
    isDeletingForm: boolean
    onDeleteForm: (target: DeleteTarget) => void
    onShareForm: (form: FormSummary) => void
}) {
    const href = `/automation/forms/${form.id}` as Route
    return (
        <Card className="relative gap-3 py-4 transition-colors hover:bg-accent/40">
            <div className="flex items-start gap-2 px-4">
                <Link
                    href={href}
                    className="min-w-0 flex-1 break-words text-[15px] font-semibold leading-snug after:absolute after:inset-0 after:rounded-xl focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-ring"
                >
                    {form.name}
                </Link>
                <DropdownMenu>
                    <DropdownMenuTrigger
                        render={
                            <Button
                                variant="ghost"
                                size="icon"
                                className="relative z-10 -mr-2 -mt-1 size-8"
                                aria-label={`Open menu for ${form.name}`}
                            >
                                <MoreHorizontalIcon className="size-4" aria-hidden="true" />
                            </Button>
                        }
                    />
                    <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => onOpenForm(form.id)}>
                            <EditIcon className="mr-2 size-4" />
                            Edit
                        </DropdownMenuItem>
                        <DropdownMenuItem
                            disabled={form.status !== "published"}
                            onClick={() => onShareForm(form)}
                        >
                            <LinkIcon className="mr-2 size-4" />
                            Share
                        </DropdownMenuItem>
                        <DropdownMenuItem
                            className="text-destructive focus:text-destructive"
                            disabled={isDeletingForm}
                            onClick={() => onDeleteForm({ id: form.id, name: form.name })}
                        >
                            <Trash2Icon className="mr-2 size-4" />
                            Delete
                        </DropdownMenuItem>
                    </DropdownMenuContent>
                </DropdownMenu>
            </div>
            <div className="flex flex-wrap items-center gap-1.5 px-4">
                <Badge variant="outline" className={statusBadgeClassName[form.status]}>
                    {statusLabel(form.status)}
                </Badge>
                <Badge variant="outline">{FORM_LEAD_KIND_LABELS[form.lead_kind ?? "surrogate"]}</Badge>
                {form.is_default_surrogate_application ? <Badge variant="outline">Default</Badge> : null}
            </div>
            <div className="flex flex-wrap gap-x-3.5 gap-y-1 px-4 text-xs text-muted-foreground">
                <span>{formatSubmissionCount(form.submission_count)}</span>
                <span>
                    <FormRelativeTime dateString={form.updated_at} />
                </span>
            </div>
        </Card>
    )
}

function formatSubmissionCount(count: number) {
    if (count === 0) return "No submissions"
    return `${count.toLocaleString("en-US")} ${count === 1 ? "submission" : "submissions"}`
}

function FormTemplatesGrid({
    templates,
    hasTemplates,
    isLoading,
    loadError,
    applyingTemplateId,
    isTemplateActionPending,
    onUseTemplate,
    onDeleteTemplate,
}: {
    templates: FormTemplateLibraryItem[] | undefined
    hasTemplates: boolean
    isLoading: boolean
    loadError: LoadErrorInfo | null
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

    if (loadError) {
        return (
            <Card className="py-0">
                <QueryErrorState
                    error={loadError.error}
                    onRetry={loadError.retry}
                    isRetrying={loadError.isRetrying}
                    title="Couldn't load form templates"
                    forbidden={FORM_BUILDER_DENIED}
                    headingLevel={2}
                />
            </Card>
        )
    }

    if (!hasTemplates) {
        return (
            <Card className="py-0">
                <EmptyState icon={FileTextIcon} title="No form templates yet" headingLevel={2} />
            </Card>
        )
    }

    if (!templates?.length) {
        return <NoMatchingItems label="No matching form templates" />
    }

    return (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
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
        <Card className="gap-3 py-4">
            <div className="flex items-start gap-2 px-4">
                <h3 className="min-w-0 flex-1 break-words text-[15px] font-semibold leading-snug">
                    {template.name}
                </h3>
                <DropdownMenu>
                    <DropdownMenuTrigger
                        render={
                            <Button
                                variant="ghost"
                                size="icon"
                                className="-mr-2 -mt-1 size-8"
                                aria-label={`Open menu for template ${template.name}`}
                            >
                                <MoreHorizontalIcon className="size-4" aria-hidden="true" />
                            </Button>
                        }
                    />
                    <DropdownMenuContent align="end">
                        <DropdownMenuItem
                            className="text-destructive focus:text-destructive"
                            disabled={isTemplateActionPending}
                            onClick={() => onDeleteTemplate({ id: template.id, name: template.name })}
                        >
                            <Trash2Icon className="mr-2 size-4" />
                            Remove from library
                        </DropdownMenuItem>
                    </DropdownMenuContent>
                </DropdownMenu>
            </div>
            {template.published_at ? (
                <div className="px-4">
                    <Badge variant="outline">Published</Badge>
                </div>
            ) : null}
            {template.description ? (
                <p className="line-clamp-2 px-4 text-sm text-muted-foreground">{template.description}</p>
            ) : null}
            <div className="mt-auto flex items-center justify-between gap-3 px-4">
                <p className="text-xs text-muted-foreground">
                    <FormRelativeTime dateString={template.updated_at} />
                </p>
                <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onUseTemplate(template.id, template.name)}
                    disabled={isTemplateActionPending || isApplying}
                    aria-label={`Use template ${template.name}`}
                >
                    {isApplying && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                    Use Template
                </Button>
            </div>
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
    formLeadKind,
    onFormLeadKindChange,
    isCreating,
    onCreate,
}: {
    open: boolean
    onOpenChange: (value: boolean) => void
    formName: string
    onFormNameChange: (value: string) => void
    formDescription: string
    onFormDescriptionChange: (value: string) => void
    formLeadKind: FormLeadKind
    onFormLeadKindChange: (value: FormLeadKind) => void
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
                        <Label htmlFor="form-lead-kind">Lead Type</Label>
                        <Select
                            value={formLeadKind}
                            onValueChange={(value) => onFormLeadKindChange(value as FormLeadKind)}
                        >
                            <SelectTrigger id="form-lead-kind">
                                <SelectValue placeholder="Select lead type">
                                    {(value: string | null) =>
                                        FORM_LEAD_KIND_LABELS[
                                            (value as FormLeadKind | null) ?? "surrogate"
                                        ] ?? value ?? "Select lead type"
                                    }
                                </SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                {FORM_LEAD_KIND_OPTIONS.map((option) => (
                                    <SelectItem key={option.value} value={option.value}>
                                        {option.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
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
                        variant="destructive"
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
    const permissionCheck = usePermissionCheck()
    // Every /forms route requires manage_forms.
    const canManageForms = permissionCheck.can("manage_forms")
    const formsQuery = useForms({ enabled: canManageForms })
    const { data: forms, isLoading } = formsQuery
    const createFormMutation = useCreateForm()
    const deleteFormMutation = useDeleteForm()
    const deleteFormTemplateMutation = useDeleteFormTemplate()
    const templatesQuery = useFormTemplates({
        enabled: canManageForms,
    })
    const { data: templates, isLoading: templatesLoading } = templatesQuery
    const useTemplateMutation = useUseFormTemplate()

    const [showCreateModal, setShowCreateModal] = useState(false)
    const [formName, setFormName] = useState("")
    const [formDescription, setFormDescription] = useState("")
    const [formLeadKind, setFormLeadKind] = useState<FormLeadKind>("surrogate")
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
                lead_kind: formLeadKind,
                ...(description ? { description } : {}),
            })
            setShowCreateModal(false)
            setFormName("")
            setFormDescription("")
            setFormLeadKind("surrogate")
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
        await runWithPendingState(setIsPreparingShare, async () => {
            try {
                const links = await listFormIntakeLinks(form.id, true)
                const selected = pickShareLink(links)
                if (!selected?.intake_url) {
                    toast.error("No shared link is available yet for this form.")
                    return
                }
                setShareLink(selected)
            } catch (error) {
                const message =
                    error instanceof ApiError
                        ? error.message
                        : "Failed to prepare share link. Please try again."
                toast.error(message)
            }
        })
    }

    const handleCopyShareLink = async () => {
        const intakeUrl = shareLink?.intake_url
        if (!intakeUrl) return
        await runWithPendingState(setIsShareActionPending, async () => {
            try {
                await navigator.clipboard.writeText(intakeUrl)
                toast.success("Application link copied")
                resetSharePrompt()
            } catch {
                toast.error("Failed to copy link")
            }
        })
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

        await runWithPendingState(setIsShareActionPending, async () => {
            try {
                const image = new Image()
                image.crossOrigin = "anonymous"

                await new Promise<void>((resolve, reject) => {
                    image.onload = () => resolve()
                    image.onerror = () => reject(new Error("Failed to render QR image"))
                    image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(markup)}`
                })

                const canvas = document.createElement("canvas")
                canvas.width = image.width || 120
                canvas.height = image.height || 120
                const context = canvas.getContext("2d")
                if (!context) {
                    toast.error("Could not prepare QR download")
                    return
                }
                context.drawImage(image, 0, 0)

                const blob = await new Promise<Blob | null>((resolve) =>
                    canvas.toBlob((result) => resolve(result), "image/png"),
                )
                if (!blob) {
                    toast.error("Could not generate QR code")
                    return
                }

                downloadBlob(blob, buildShareQrFilename())
                toast.success("QR code downloaded")
                resetSharePrompt()
            } catch {
                toast.error("Failed to download QR code")
            }
        })
    }

    let blockedState: ReactNode = null
    if (permissionCheck.isLoading) {
        blockedState = (
            <div className="flex items-center justify-center py-12">
                <Loader2Icon className="size-6 animate-spin text-muted-foreground" aria-hidden="true" />
            </div>
        )
    } else if (permissionCheck.isError) {
        blockedState = (
            <LoadErrorState
                title="Couldn't load forms"
                onRetry={permissionCheck.retry}
                isRetrying={permissionCheck.isRetrying}
            />
        )
    } else if (!canManageForms) {
        blockedState = <PermissionDeniedState {...FORM_BUILDER_DENIED} />
    } else if (formsQuery.isError) {
        blockedState = (
            <QueryErrorState
                error={formsQuery.error}
                onRetry={() => {
                    void formsQuery.refetch()
                }}
                isRetrying={formsQuery.isFetching}
                title="Couldn't load forms"
                forbidden={FORM_BUILDER_DENIED}
            />
        )
    }

    if (blockedState) {
        return (
            <div className="flex min-h-screen flex-col">
                <FormsPageHeader />
                {blockedState}
            </div>
        )
    }

    return (
        <div className="flex min-h-screen flex-col">
            <FormsPageHeader onCreateForm={() => setShowCreateModal(true)} />

            <div className="flex-1 p-6">
                <div className="space-y-6">
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
                        templatesLoadError={
                            templatesQuery.isError && templates === undefined
                                ? {
                                      error: templatesQuery.error,
                                      retry: () => void templatesQuery.refetch(),
                                      isRetrying: templatesQuery.isFetching,
                                  }
                                : null
                        }
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
                formLeadKind={formLeadKind}
                onFormLeadKindChange={setFormLeadKind}
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
