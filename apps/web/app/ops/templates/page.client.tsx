"use client"

import { type ReactNode, startTransition, useState } from "react"
import { useMountEffect } from "@/lib/hooks/use-mount-effect"
import Link from "@/components/app-link"
import { useRouter } from "next/navigation"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { buttonVariants } from "@/components/ui/button-variants"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import { RelativeTime } from "@/components/ui/time-display"
import {
    MailIcon,
    ClipboardListIcon,
    WorkflowIcon,
    PlusIcon,
    Loader2Icon,
    ArrowRightIcon,
    ShieldCheckIcon,
    TriangleAlertIcon,
} from "lucide-react"
import {
    usePlatformEmailTemplates,
    usePlatformFormTemplates,
    usePlatformWorkflowTemplates,
    usePlatformSystemEmailTemplates,
} from "@/lib/hooks/use-platform-templates"
import type { SystemEmailTemplate } from "@/lib/api/platform"

const TABS = ["email", "forms", "workflows", "system"] as const
type TemplatesTab = (typeof TABS)[number]

const STATUS_STYLES: Record<string, string> = {
    draft: "bg-stone-100 text-stone-700 dark:bg-stone-800 dark:text-stone-300",
    published: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
    archived: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
}

function StatusBadge({ status }: { status: string }) {
    return (
        <Badge variant="outline" className={STATUS_STYLES[status] || ""}>
            {status}
        </Badge>
    )
}

function PublishScopeBadge({ isGlobal }: { isGlobal: boolean }) {
    return (
        <Badge variant="secondary" className={isGlobal ? "bg-teal-500/10 text-teal-600" : ""}>
            {isGlobal ? "All orgs" : "Selected orgs"}
        </Badge>
    )
}

function resolveErrorMessage(error: unknown, fallback: string) {
    if (error instanceof Error && error.message) return error.message
    if (typeof error === "string" && error.trim()) return error
    return fallback
}

function QueryErrorState({
    title,
    error,
    onRetry,
}: {
    title: string
    error: unknown
    onRetry: () => void
}) {
    return (
        <div className="rounded-lg border border-dashed bg-white p-10 text-center dark:bg-stone-900">
            <div className="mx-auto mb-3 flex size-12 items-center justify-center rounded-full bg-amber-500/10 text-amber-600">
                <TriangleAlertIcon className="size-6" />
            </div>
            <h3 className="text-lg font-semibold text-stone-900 dark:text-stone-100">{title}</h3>
            <p className="mt-2 text-sm text-muted-foreground">
                {resolveErrorMessage(error, "Failed to load templates.")}
            </p>
            <Button className="mt-4" variant="outline" onClick={onRetry}>
                Try again
            </Button>
        </div>
    )
}

function EmptyState({
    title,
    description,
    ctaHref,
    ctaLabel,
}: {
    title: string
    description: string
    ctaHref: string
    ctaLabel: string
}) {
    return (
        <div className="rounded-lg border border-dashed bg-white p-10 text-center dark:bg-stone-900">
            <h3 className="text-lg font-semibold text-stone-900 dark:text-stone-100">{title}</h3>
            <p className="mt-2 text-sm text-muted-foreground">{description}</p>
            <Link href={ctaHref} className={buttonVariants({ className: "mt-4" })}>
                <PlusIcon className="mr-2 size-4" />
                {ctaLabel}
            </Link>
        </div>
    )
}

function TemplatesLoadingState() {
    return (
        <div className="flex items-center justify-center py-16">
            <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
        </div>
    )
}

type PublishedTemplateListItem = {
    id: string
    status: string
    published_version: number
    is_published_globally: boolean
    published_at?: string | null
    updated_at: string
    draft: {
        name: string
    }
}

function TemplateTableFrame({
    children,
    showScope = true,
}: {
    children: ReactNode
    showScope?: boolean
}) {
    return (
        <div className="border rounded-lg bg-white dark:bg-stone-900">
            <Table>
                <TableHeader>
                    <TableRow>
                        <TableHead>Template</TableHead>
                        <TableHead>Status</TableHead>
                        {showScope && <TableHead>Scope</TableHead>}
                        <TableHead>Updated</TableHead>
                        <TableHead className="w-12"></TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>{children}</TableBody>
            </Table>
        </div>
    )
}

function PublishedScopeCell({ template }: { template: PublishedTemplateListItem }) {
    if (template.published_version <= 0) {
        return <span className="text-xs text-muted-foreground">Not published</span>
    }

    return (
        <div className="space-y-1">
            <PublishScopeBadge isGlobal={template.is_published_globally} />
            <div className="text-xs text-muted-foreground">
                <RelativeTime value={template.published_at} />
            </div>
        </div>
    )
}

function TemplateListSection<TTemplate extends PublishedTemplateListItem>({
    rows,
    isLoading,
    isError,
    error,
    errorTitle,
    onRetry,
    emptyTitle,
    emptyDescription,
    emptyHref,
    emptyLabel,
    getDescription,
    onOpen,
}: {
    rows: TTemplate[]
    isLoading: boolean
    isError: boolean
    error: unknown
    errorTitle: string
    onRetry: () => void
    emptyTitle: string
    emptyDescription: string
    emptyHref: string
    emptyLabel: string
    getDescription: (template: TTemplate) => string
    onOpen: (template: TTemplate) => void
}) {
    if (isError) {
        return <QueryErrorState title={errorTitle} error={error} onRetry={onRetry} />
    }

    if (isLoading) {
        return <TemplatesLoadingState />
    }

    if (rows.length === 0) {
        return (
            <EmptyState
                title={emptyTitle}
                description={emptyDescription}
                ctaHref={emptyHref}
                ctaLabel={emptyLabel}
            />
        )
    }

    return (
        <TemplateTableFrame>
            {rows.map((template) => (
                <TableRow
                    key={template.id}
                    className="cursor-pointer hover:bg-stone-50 dark:hover:bg-stone-800/50"
                    onClick={() => onOpen(template)}
                >
                    <TableCell>
                        <div className="font-medium text-stone-900 dark:text-stone-100">
                            {template.draft.name}
                        </div>
                        <div className="text-xs text-muted-foreground truncate">
                            {getDescription(template)}
                        </div>
                    </TableCell>
                    <TableCell>
                        <StatusBadge status={template.status} />
                    </TableCell>
                    <TableCell>
                        <PublishedScopeCell template={template} />
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                        <RelativeTime value={template.updated_at} />
                    </TableCell>
                    <TableCell>
                        <ArrowRightIcon className="size-4 text-muted-foreground" />
                    </TableCell>
                </TableRow>
            ))}
        </TemplateTableFrame>
    )
}

function SystemTemplatesSection({
    rows,
    isLoading,
    isError,
    error,
    onRetry,
    onOpen,
}: {
    rows: SystemEmailTemplate[]
    isLoading: boolean
    isError: boolean
    error: unknown
    onRetry: () => void
    onOpen: (template: SystemEmailTemplate) => void
}) {
    if (isError) {
        return (
            <QueryErrorState
                title="Failed to load system email templates"
                error={error}
                onRetry={onRetry}
            />
        )
    }

    if (isLoading) {
        return <TemplatesLoadingState />
    }

    if (rows.length === 0) {
        return (
            <EmptyState
                title="No system templates found"
                description="System emails are managed at the platform level."
                ctaHref="/ops/templates"
                ctaLabel="Refresh"
            />
        )
    }

    return (
        <TemplateTableFrame showScope={false}>
            {rows.map((template) => (
                <TableRow
                    key={template.system_key}
                    className="cursor-pointer hover:bg-stone-50 dark:hover:bg-stone-800/50"
                    onClick={() => onOpen(template)}
                >
                    <TableCell>
                        <div className="font-medium text-stone-900 dark:text-stone-100">
                            {template.name}
                        </div>
                        <div className="text-xs text-muted-foreground">
                            {template.system_key}
                        </div>
                    </TableCell>
                    <TableCell>
                        <Badge
                            variant="outline"
                            className={
                                template.is_active
                                    ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                                    : "bg-stone-100 text-stone-700 dark:bg-stone-800 dark:text-stone-300"
                            }
                        >
                            {template.is_active ? "Active" : "Inactive"}
                        </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                        <RelativeTime value={template.updated_at} />
                    </TableCell>
                    <TableCell>
                        <ArrowRightIcon className="size-4 text-muted-foreground" />
                    </TableCell>
                </TableRow>
            ))}
        </TemplateTableFrame>
    )
}

export default function TemplatesPage() {
    const { push, replace } = useRouter()
    const [activeTab, setActiveTab] = useState<TemplatesTab>("email")

    useMountEffect(() => {
        const readTabFromUrl = (): TemplatesTab => {
            const tabParam = new URLSearchParams(window.location.search).get("tab")
            return TABS.includes(tabParam as TemplatesTab) ? (tabParam as TemplatesTab) : "email"
        }

        startTransition(() => {
            setActiveTab(readTabFromUrl())
        })
        const handlePopState = () => {
            startTransition(() => {
                setActiveTab(readTabFromUrl())
            })
        }
        window.addEventListener("popstate", handlePopState)
        return () => window.removeEventListener("popstate", handlePopState)
    })

    const {
        data: emailTemplates = [],
        isLoading: emailLoading,
        isError: emailIsError,
        error: emailError,
        refetch: refetchEmailTemplates,
    } = usePlatformEmailTemplates()
    const {
        data: formTemplates = [],
        isLoading: formLoading,
        isError: formIsError,
        error: formError,
        refetch: refetchFormTemplates,
    } = usePlatformFormTemplates()
    const {
        data: workflowTemplates = [],
        isLoading: workflowLoading,
        isError: workflowIsError,
        error: workflowError,
        refetch: refetchWorkflowTemplates,
    } = usePlatformWorkflowTemplates()
    const {
        data: systemTemplates = [],
        isLoading: systemLoading,
        isError: systemIsError,
        error: systemError,
        refetch: refetchSystemTemplates,
    } = usePlatformSystemEmailTemplates()

    const handleTabChange = (next: string) => {
        const value = TABS.includes(next as TemplatesTab) ? (next as TemplatesTab) : "email"
        setActiveTab(value)
        replace(`/ops/templates?tab=${value}`)
    }

    const emailRows = emailTemplates
    const formRows = formTemplates
    const workflowRows = workflowTemplates
    const systemRows = systemTemplates
    const canCreate = true

    const createLabel =
        activeTab === "email"
            ? "Email"
            : activeTab === "forms"
              ? "Form"
              : activeTab === "workflows"
                ? "Workflow"
                : "System Email"

    return (
        <div className="p-6 space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">
                        Templates Studio
                    </h1>
                    <p className="text-sm text-stone-500 dark:text-stone-400 mt-1">
                        Design shared templates and manage platform system emails. Published templates sync to org libraries.
                    </p>
                </div>
                {canCreate && (
                    <Button onClick={() => push(`/ops/templates/${activeTab}/new`)}>
                        <PlusIcon className="mr-2 size-4" />
                        New {createLabel}
                    </Button>
                )}
            </div>

            <Tabs value={activeTab} onValueChange={handleTabChange}>
                <TabsList>
                    <TabsTrigger value="email" className="gap-2">
                        <MailIcon className="size-4" />
                        Email
                    </TabsTrigger>
                    <TabsTrigger value="forms" className="gap-2">
                        <ClipboardListIcon className="size-4" />
                        Forms
                    </TabsTrigger>
                    <TabsTrigger value="workflows" className="gap-2">
                        <WorkflowIcon className="size-4" />
                        Workflows
                    </TabsTrigger>
                    <TabsTrigger value="system" className="gap-2">
                        <ShieldCheckIcon className="size-4" />
                        System Emails
                    </TabsTrigger>
                </TabsList>

                <TabsContent value="email" className="mt-6">
                    <TemplateListSection
                        rows={emailRows}
                        isLoading={emailLoading}
                        isError={emailIsError}
                        error={emailError}
                        errorTitle="Failed to load email templates"
                        onRetry={() => void refetchEmailTemplates()}
                        emptyTitle="No email templates yet"
                        emptyDescription="Create platform email templates to seed org libraries."
                        emptyHref="/ops/templates/email/new"
                        emptyLabel="Create Email Template"
                        getDescription={(template) => template.draft.subject}
                        onOpen={(template) => push(`/ops/templates/email/${template.id}`)}
                    />
                </TabsContent>

                <TabsContent value="forms" className="mt-6">
                    <TemplateListSection
                        rows={formRows}
                        isLoading={formLoading}
                        isError={formIsError}
                        error={formError}
                        errorTitle="Failed to load form templates"
                        onRetry={() => void refetchFormTemplates()}
                        emptyTitle="No form templates yet"
                        emptyDescription="Design form templates to publish into org libraries."
                        emptyHref="/ops/templates/forms/new"
                        emptyLabel="Create Form Template"
                        getDescription={(template) => template.draft.description || "No description"}
                        onOpen={(template) => push(`/ops/templates/forms/${template.id}`)}
                    />
                </TabsContent>

                <TabsContent value="workflows" className="mt-6">
                    <TemplateListSection
                        rows={workflowRows}
                        isLoading={workflowLoading}
                        isError={workflowIsError}
                        error={workflowError}
                        errorTitle="Failed to load workflow templates"
                        onRetry={() => void refetchWorkflowTemplates()}
                        emptyTitle="No workflow templates yet"
                        emptyDescription="Build workflow templates to publish across orgs."
                        emptyHref="/ops/templates/workflows/new"
                        emptyLabel="Create Workflow Template"
                        getDescription={(template) => template.draft.description || "No description"}
                        onOpen={(template) => push(`/ops/templates/workflows/${template.id}`)}
                    />
                </TabsContent>

                <TabsContent value="system" className="mt-6">
                    <SystemTemplatesSection
                        rows={systemRows}
                        isLoading={systemLoading}
                        isError={systemIsError}
                        error={systemError}
                        onRetry={() => void refetchSystemTemplates()}
                        onOpen={(template) => push(`/ops/templates/system/${template.system_key}`)}
                    />
                </TabsContent>
            </Tabs>
        </div>
    )
}
