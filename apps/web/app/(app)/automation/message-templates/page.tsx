"use client"

import { useMemo, useState } from "react"
import type { Route } from "next"
import { useRouter } from "next/navigation"
import { MessageSquareTextIcon, PlusIcon, SearchIcon } from "lucide-react"

import Link from "@/components/app-link"
import { EmptyState } from "@/components/empty-state"
import { PermissionDeniedState, QueryErrorState } from "@/components/error-state"
import { SendTestMessageDialog } from "@/components/messaging/send-test-message-dialog"
import { PageHeader } from "@/components/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { TwilioMessagingPurpose, TwilioReadiness } from "@/lib/api/twilio"
import { formatDate } from "@/lib/formatters"
import {
    useMessagingAccess,
    useMessagingTemplateUsage,
    useMessagingTemplateVersions,
} from "@/lib/hooks/use-messaging-templates"
import { useTwilioReadiness } from "@/lib/hooks/use-twilio"
import {
    routeStatus,
    templateHref,
    testTemplateOptions,
    usageSummary,
} from "@/lib/messaging/template-library"
import {
    groupTemplateFamilies,
    PURPOSE_LABELS,
    type TemplateFamily,
} from "@/lib/messaging/sms-content"
import { cn } from "@/lib/utils"

type PurposeFilter = "all" | TwilioMessagingPurpose

function StatusBadges({ family }: { family: TemplateFamily }) {
    return (
        <div className="flex flex-wrap gap-1.5">
            {family.live ? (
                <Badge variant="outline" className="border-success/30 bg-success/10 text-success">
                    Published · v{family.live.version}
                </Badge>
            ) : null}
            {family.draft ? <Badge variant="outline">Draft{family.live ? ` v${family.draft.version}` : ""}</Badge> : null}
        </div>
    )
}

function RouteStatusBar({ readiness }: { readiness: TwilioReadiness | undefined }) {
    const routes = (["operational", "promotional"] as const).map((purpose) => ({
        purpose,
        status: routeStatus(readiness, purpose),
    }))
    if (!readiness) return null
    return (
        <div
            role="status"
            aria-label="Messaging routes"
            className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-lg border bg-card px-4 py-2.5 text-sm"
        >
            {routes.map(({ purpose, status }) => (
                <span key={purpose} className="flex items-center gap-2">
                    <span
                        aria-hidden="true"
                        className={cn("size-2 rounded-full", status?.ready ? "bg-success" : "bg-warning")}
                    />
                    {PURPOSE_LABELS[purpose]} route: {status?.text}
                </span>
            ))}
            <Link href="/settings/integrations/messaging" className="ml-auto text-primary hover:underline">
                Messaging settings
            </Link>
        </div>
    )
}

export default function MessageTemplatesPage() {
    const router = useRouter()
    const access = useMessagingAccess()
    const versionsQuery = useMessagingTemplateVersions(access.allowed)
    const usageQuery = useMessagingTemplateUsage(access.allowed)
    const readinessQuery = useTwilioReadiness(access.allowed)
    const [purpose, setPurpose] = useState<PurposeFilter>("all")
    const [search, setSearch] = useState("")
    const [testOpen, setTestOpen] = useState(false)

    const families = useMemo(() => groupTemplateFamilies(versionsQuery.data ?? []), [versionsQuery.data])
    const usage = useMemo(
        () => new Map((usageQuery.data ?? []).map((item) => [item.template_key, item.uses])),
        [usageQuery.data],
    )
    const query = search.trim().toLocaleLowerCase()
    const visible = families.filter(
        (family) =>
            (purpose === "all" || family.purpose === purpose) &&
            (!query ||
                family.name.toLocaleLowerCase().includes(query) ||
                family.latest.body.toLocaleLowerCase().includes(query)),
    )
    const newTemplate = () => router.push("/automation/message-templates/new" as Route)

    if (access.loading || !access.allowed) {
        return (
            <div className="flex min-h-full flex-col">
                <PageHeader title="Message Templates" />
                {access.loading ? (
                    <div className="p-6"><Skeleton className="h-64 w-full" /></div>
                ) : (
                    <PermissionDeniedState
                        title="Message templates are restricted"
                        description="Only organization administrators and developers with integration access can manage text message templates."
                        headingLevel={2}
                    />
                )}
            </div>
        )
    }

    return (
        <div className="flex min-h-full flex-col">
            <PageHeader
                title="Message Templates"
                actions={
                    <>
                        <Button variant="outline" onClick={() => setTestOpen(true)} disabled={families.length === 0}>
                            Send test message
                        </Button>
                        <Button onClick={newTemplate}>
                            <PlusIcon className="size-4" aria-hidden="true" />
                            New template
                        </Button>
                    </>
                }
            />
            <div className="flex-1 space-y-5 p-6">
                <RouteStatusBar readiness={readinessQuery.data} />

                <div className="flex flex-wrap items-center gap-3">
                    <Tabs value={purpose} onValueChange={(value) => setPurpose(value as PurposeFilter)}>
                        <TabsList aria-label="Purpose">
                            <TabsTrigger value="all">All</TabsTrigger>
                            <TabsTrigger value="operational">Operational</TabsTrigger>
                            <TabsTrigger value="promotional">Promotional</TabsTrigger>
                        </TabsList>
                    </Tabs>
                    <div className="relative ml-auto w-full sm:w-64">
                        <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
                        <Input
                            type="search"
                            aria-label="Search templates"
                            placeholder="Search"
                            value={search}
                            onChange={(event) => setSearch(event.target.value)}
                            className="pl-8"
                        />
                    </div>
                </div>

                {versionsQuery.isLoading ? (
                    <Skeleton className="h-64 w-full" />
                ) : versionsQuery.isError ? (
                    <Card className="py-0">
                        <QueryErrorState
                            error={versionsQuery.error}
                            onRetry={() => void versionsQuery.refetch()}
                            isRetrying={versionsQuery.isFetching}
                            title="Couldn't load message templates"
                            headingLevel={2}
                        />
                    </Card>
                ) : families.length === 0 ? (
                    <EmptyState
                        icon={MessageSquareTextIcon}
                        title="No message templates"
                        headingLevel={2}
                        action={
                            <Button onClick={newTemplate}>
                                <PlusIcon className="size-4" aria-hidden="true" />
                                New template
                            </Button>
                        }
                    />
                ) : visible.length === 0 ? (
                    <EmptyState
                        icon={MessageSquareTextIcon}
                        title="No matching templates"
                        headingLevel={2}
                        onClearFilters={() => {
                            setPurpose("all")
                            setSearch("")
                        }}
                    />
                ) : (
                    <Card className="overflow-hidden py-0">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Name</TableHead>
                                    <TableHead>Purpose</TableHead>
                                    <TableHead>Status</TableHead>
                                    <TableHead>Preview</TableHead>
                                    <TableHead>Used by</TableHead>
                                    <TableHead>Updated</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {visible.map((family) => (
                                    <TableRow key={family.key}>
                                        <TableCell>
                                            <div className="flex flex-col items-start gap-1">
                                                <Link href={templateHref(family.key)} className="font-medium text-primary hover:underline">
                                                    {family.name}
                                                </Link>
                                                {family.isEnrollmentConfirmation ? (
                                                    <Badge variant="secondary">Opt-in confirmation</Badge>
                                                ) : null}
                                            </div>
                                        </TableCell>
                                        <TableCell>{PURPOSE_LABELS[family.purpose]}</TableCell>
                                        <TableCell><StatusBadges family={family} /></TableCell>
                                        <TableCell className="max-w-80 truncate text-muted-foreground">{family.latest.body}</TableCell>
                                        <TableCell>
                                            {usageSummary(usage.get(family.key)) ?? <span className="text-muted-foreground">—</span>}
                                        </TableCell>
                                        <TableCell className="text-muted-foreground">
                                            {formatDate(family.latest.created_at, { month: "short", day: "numeric" })}
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </Card>
                )}
            </div>
            <SendTestMessageDialog
                open={testOpen}
                onOpenChange={setTestOpen}
                templates={testTemplateOptions(families)}
            />
        </div>
    )
}
