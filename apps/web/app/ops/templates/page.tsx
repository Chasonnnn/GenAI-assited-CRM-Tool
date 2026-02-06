"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "@/components/app-link"
import { useRouter } from "next/navigation"
import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import { formatDistanceToNow } from "date-fns"
import {
    MailIcon,
    ClipboardListIcon,
    WorkflowIcon,
    PlusIcon,
    Loader2Icon,
    ArrowRightIcon,
    ShieldCheckIcon,
} from "lucide-react"
import {
    usePlatformEmailTemplates,
    usePlatformFormTemplates,
    usePlatformWorkflowTemplates,
    usePlatformSystemEmailTemplates,
} from "@/lib/hooks/use-platform-templates"
import type {
    PlatformEmailTemplateListItem,
    PlatformFormTemplateListItem,
    PlatformWorkflowTemplateListItem,
    SystemEmailTemplate,
} from "@/lib/api/platform"

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

export default function TemplatesPage() {
    const router = useRouter()
    const [activeTab, setActiveTab] = useState<TemplatesTab>("email")

    useEffect(() => {
        const readTabFromUrl = (): TemplatesTab => {
            const tabParam = new URLSearchParams(window.location.search).get("tab")
            return TABS.includes(tabParam as TemplatesTab) ? (tabParam as TemplatesTab) : "email"
        }

        setActiveTab(readTabFromUrl())
        const handlePopState = () => setActiveTab(readTabFromUrl())
        window.addEventListener("popstate", handlePopState)
        return () => window.removeEventListener("popstate", handlePopState)
    }, [])

    const { data: emailTemplates = [], isLoading: emailLoading } = usePlatformEmailTemplates()
    const { data: formTemplates = [], isLoading: formLoading } = usePlatformFormTemplates()
    const { data: workflowTemplates = [], isLoading: workflowLoading } = usePlatformWorkflowTemplates()
    const { data: systemTemplates = [], isLoading: systemLoading } = usePlatformSystemEmailTemplates()

    const handleTabChange = (next: string) => {
        const value = TABS.includes(next as TemplatesTab) ? (next as TemplatesTab) : "email"
        setActiveTab(value)
        router.replace(`/ops/templates?tab=${value}`)
    }

    const emailRows = useMemo(() => emailTemplates, [emailTemplates])
    const formRows = useMemo(() => formTemplates, [formTemplates])
    const workflowRows = useMemo(() => workflowTemplates, [workflowTemplates])
    const systemRows = useMemo(() => systemTemplates, [systemTemplates])
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
                    <Button onClick={() => router.push(`/ops/templates/${activeTab}/new`)}>
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
                    {emailLoading ? (
                        <div className="flex items-center justify-center py-16">
                            <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                        </div>
                    ) : emailRows.length === 0 ? (
                        <EmptyState
                            title="No email templates yet"
                            description="Create platform email templates to seed org libraries."
                            ctaHref="/ops/templates/email/new"
                            ctaLabel="Create Email Template"
                        />
                    ) : (
                        <div className="border rounded-lg bg-white dark:bg-stone-900">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Template</TableHead>
                                        <TableHead>Status</TableHead>
                                        <TableHead>Scope</TableHead>
                                        <TableHead>Updated</TableHead>
                                        <TableHead className="w-12"></TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {emailRows.map((template: PlatformEmailTemplateListItem) => (
                                        <TableRow
                                            key={template.id}
                                            className="cursor-pointer hover:bg-stone-50 dark:hover:bg-stone-800/50"
                                            onClick={() => router.push(`/ops/templates/email/${template.id}`)}
                                        >
                                            <TableCell>
                                                <div className="font-medium text-stone-900 dark:text-stone-100">
                                                    {template.draft.name}
                                                </div>
                                                <div className="text-xs text-muted-foreground truncate">
                                                    {template.draft.subject}
                                                </div>
                                            </TableCell>
                                            <TableCell>
                                                <StatusBadge status={template.status} />
                                            </TableCell>
                                            <TableCell>
                                                {template.published_version > 0 ? (
                                                    <div className="space-y-1">
                                                        <PublishScopeBadge isGlobal={template.is_published_globally} />
                                                        <div className="text-xs text-muted-foreground">
                                                            {template.published_at
                                                                ? formatDistanceToNow(new Date(template.published_at), { addSuffix: true })
                                                                : "—"}
                                                        </div>
                                                    </div>
                                                ) : (
                                                    <span className="text-xs text-muted-foreground">Not published</span>
                                                )}
                                            </TableCell>
                                            <TableCell className="text-sm text-muted-foreground">
                                                {formatDistanceToNow(new Date(template.updated_at), { addSuffix: true })}
                                            </TableCell>
                                            <TableCell>
                                                <ArrowRightIcon className="size-4 text-muted-foreground" />
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    )}
                </TabsContent>

                <TabsContent value="forms" className="mt-6">
                    {formLoading ? (
                        <div className="flex items-center justify-center py-16">
                            <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                        </div>
                    ) : formRows.length === 0 ? (
                        <EmptyState
                            title="No form templates yet"
                            description="Design form templates to publish into org libraries."
                            ctaHref="/ops/templates/forms/new"
                            ctaLabel="Create Form Template"
                        />
                    ) : (
                        <div className="border rounded-lg bg-white dark:bg-stone-900">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Template</TableHead>
                                        <TableHead>Status</TableHead>
                                        <TableHead>Scope</TableHead>
                                        <TableHead>Updated</TableHead>
                                        <TableHead className="w-12"></TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {formRows.map((template: PlatformFormTemplateListItem) => (
                                        <TableRow
                                            key={template.id}
                                            className="cursor-pointer hover:bg-stone-50 dark:hover:bg-stone-800/50"
                                            onClick={() => router.push(`/ops/templates/forms/${template.id}`)}
                                        >
                                            <TableCell>
                                                <div className="font-medium text-stone-900 dark:text-stone-100">
                                                    {template.draft.name}
                                                </div>
                                                <div className="text-xs text-muted-foreground truncate">
                                                    {template.draft.description || "No description"}
                                                </div>
                                            </TableCell>
                                            <TableCell>
                                                <StatusBadge status={template.status} />
                                            </TableCell>
                                            <TableCell>
                                                {template.published_version > 0 ? (
                                                    <div className="space-y-1">
                                                        <PublishScopeBadge isGlobal={template.is_published_globally} />
                                                        <div className="text-xs text-muted-foreground">
                                                            {template.published_at
                                                                ? formatDistanceToNow(new Date(template.published_at), { addSuffix: true })
                                                                : "—"}
                                                        </div>
                                                    </div>
                                                ) : (
                                                    <span className="text-xs text-muted-foreground">Not published</span>
                                                )}
                                            </TableCell>
                                            <TableCell className="text-sm text-muted-foreground">
                                                {formatDistanceToNow(new Date(template.updated_at), { addSuffix: true })}
                                            </TableCell>
                                            <TableCell>
                                                <ArrowRightIcon className="size-4 text-muted-foreground" />
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    )}
                </TabsContent>

                <TabsContent value="workflows" className="mt-6">
                    {workflowLoading ? (
                        <div className="flex items-center justify-center py-16">
                            <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                        </div>
                    ) : workflowRows.length === 0 ? (
                        <EmptyState
                            title="No workflow templates yet"
                            description="Build workflow templates to publish across orgs."
                            ctaHref="/ops/templates/workflows/new"
                            ctaLabel="Create Workflow Template"
                        />
                    ) : (
                        <div className="border rounded-lg bg-white dark:bg-stone-900">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Template</TableHead>
                                        <TableHead>Status</TableHead>
                                        <TableHead>Scope</TableHead>
                                        <TableHead>Updated</TableHead>
                                        <TableHead className="w-12"></TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {workflowRows.map((template: PlatformWorkflowTemplateListItem) => (
                                        <TableRow
                                            key={template.id}
                                            className="cursor-pointer hover:bg-stone-50 dark:hover:bg-stone-800/50"
                                            onClick={() => router.push(`/ops/templates/workflows/${template.id}`)}
                                        >
                                            <TableCell>
                                                <div className="font-medium text-stone-900 dark:text-stone-100">
                                                    {template.draft.name}
                                                </div>
                                                <div className="text-xs text-muted-foreground truncate">
                                                    {template.draft.description || "No description"}
                                                </div>
                                            </TableCell>
                                            <TableCell>
                                                <StatusBadge status={template.status} />
                                            </TableCell>
                                            <TableCell>
                                                {template.published_version > 0 ? (
                                                    <div className="space-y-1">
                                                        <PublishScopeBadge isGlobal={template.is_published_globally} />
                                                        <div className="text-xs text-muted-foreground">
                                                            {template.published_at
                                                                ? formatDistanceToNow(new Date(template.published_at), { addSuffix: true })
                                                                : "—"}
                                                        </div>
                                                    </div>
                                                ) : (
                                                    <span className="text-xs text-muted-foreground">Not published</span>
                                                )}
                                            </TableCell>
                                            <TableCell className="text-sm text-muted-foreground">
                                                {formatDistanceToNow(new Date(template.updated_at), { addSuffix: true })}
                                            </TableCell>
                                            <TableCell>
                                                <ArrowRightIcon className="size-4 text-muted-foreground" />
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    )}
                </TabsContent>

                <TabsContent value="system" className="mt-6">
                    {systemLoading ? (
                        <div className="flex items-center justify-center py-16">
                            <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                        </div>
                    ) : systemRows.length === 0 ? (
                        <EmptyState
                            title="No system templates found"
                            description="System emails are managed at the platform level."
                            ctaHref="/ops/templates"
                            ctaLabel="Refresh"
                        />
                    ) : (
                        <div className="border rounded-lg bg-white dark:bg-stone-900">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Template</TableHead>
                                        <TableHead>Status</TableHead>
                                        <TableHead>Updated</TableHead>
                                        <TableHead className="w-12"></TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {systemRows.map((template: SystemEmailTemplate) => (
                                        <TableRow
                                            key={template.system_key}
                                            className="cursor-pointer hover:bg-stone-50 dark:hover:bg-stone-800/50"
                                            onClick={() =>
                                                router.push(`/ops/templates/system/${template.system_key}`)
                                            }
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
                                                {template.updated_at
                                                    ? formatDistanceToNow(new Date(template.updated_at), {
                                                          addSuffix: true,
                                                      })
                                                    : "—"}
                                            </TableCell>
                                            <TableCell>
                                                <ArrowRightIcon className="size-4 text-muted-foreground" />
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    )}
                </TabsContent>
            </Tabs>
        </div>
    )
}
