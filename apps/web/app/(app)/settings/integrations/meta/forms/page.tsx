"use client"

import Link from "@/components/app-link"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import { useMetaForms, useSyncMetaForms } from "@/lib/hooks/use-meta-forms"
import { formatRelativeTime } from "@/lib/formatters"
import { AlertTriangleIcon, CheckCircleIcon, Loader2Icon, RefreshCwIcon } from "lucide-react"

const statusBadge = (status: string) => {
    if (status === "mapped") {
        return (
            <Badge variant="default" className="gap-1 bg-green-500/10 text-green-600 border-green-500/20">
                <CheckCircleIcon className="size-3" />
                Mapped
            </Badge>
        )
    }
    if (status === "outdated") {
        return (
            <Badge variant="destructive" className="gap-1">
                <AlertTriangleIcon className="size-3" />
                Outdated
            </Badge>
        )
    }
    return (
        <Badge variant="secondary" className="gap-1 bg-yellow-500/10 text-yellow-700 border-yellow-500/30">
            <AlertTriangleIcon className="size-3" />
            Unmapped
        </Badge>
    )
}

export default function MetaFormsPage() {
    const { data: forms = [], isLoading } = useMetaForms()
    const syncMutation = useSyncMetaForms()

    const needsMapping = forms.filter((form) => form.mapping_status !== "mapped")

    return (
        <div className="flex min-h-screen flex-col">
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <div>
                        <h1 className="text-2xl font-semibold">Meta Lead Forms</h1>
                        <p className="text-sm text-muted-foreground">
                            Map Meta lead forms to surrogate fields.
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        <Button
                            variant="outline"
                            onClick={() => syncMutation.mutate({})}
                            disabled={syncMutation.isPending}
                        >
                            {syncMutation.isPending ? (
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                            ) : (
                                <RefreshCwIcon className="mr-2 size-4" />
                            )}
                            Sync forms
                        </Button>
                        <Button render={<Link href="/settings/integrations/meta" />} variant="ghost">
                            Back to Meta
                        </Button>
                    </div>
                </div>
            </div>

            <div className="flex-1 space-y-6 p-6">
                {needsMapping.length > 0 && (
                    <Alert>
                        <AlertTitle>Forms need mapping</AlertTitle>
                        <AlertDescription>
                            {needsMapping.length} form(s) require mapping before leads can convert to cases.
                        </AlertDescription>
                    </Alert>
                )}

                <Card>
                    <CardHeader>
                        <CardTitle>Forms</CardTitle>
                        <CardDescription>Choose a form to configure mappings.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        {isLoading ? (
                            <div className="flex items-center justify-center py-12">
                                <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                            </div>
                        ) : forms.length === 0 ? (
                            <div className="text-sm text-muted-foreground">
                                No forms synced yet. Click Sync forms to fetch.
                            </div>
                        ) : (
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Form</TableHead>
                                        <TableHead>Page</TableHead>
                                        <TableHead>Status</TableHead>
                                        <TableHead>Unconverted</TableHead>
                                        <TableHead>Last lead</TableHead>
                                        <TableHead className="text-right">Actions</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {forms.map((form) => (
                                        <TableRow key={form.id}>
                                            <TableCell>
                                                <div className="font-medium">{form.form_name}</div>
                                                <div className="text-xs text-muted-foreground">
                                                    {form.form_external_id}
                                                </div>
                                            </TableCell>
                                            <TableCell>
                                                <div>{form.page_name || "—"}</div>
                                                <div className="text-xs text-muted-foreground">{form.page_id}</div>
                                            </TableCell>
                                            <TableCell>{statusBadge(form.mapping_status)}</TableCell>
                                            <TableCell>
                                                {form.unconverted_leads > 0 ? (
                                                    <Badge variant="secondary">{form.unconverted_leads}</Badge>
                                                ) : (
                                                    <span className="text-muted-foreground">0</span>
                                                )}
                                            </TableCell>
                                            <TableCell className="text-sm text-muted-foreground">
                                                {form.last_lead_at
                                                    ? formatRelativeTime(form.last_lead_at, "—")
                                                    : "—"}
                                            </TableCell>
                                            <TableCell className="text-right">
                                                <Button
                                                    size="sm"
                                                    variant="outline"
                                                    render={<Link href={`/settings/integrations/meta/forms/${form.id}`} />}
                                                >
                                                    Manage mapping
                                                </Button>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
