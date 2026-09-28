"use client"

import Link from "@/components/app-link"
import { EmptyState } from "@/components/empty-state"
import { QueryErrorState } from "@/components/error-state"
import { PageHeader } from "@/components/page-header"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import { useDeleteMetaForm, useMetaForms, useSyncMetaForms } from "@/lib/hooks/use-meta-forms"
import { formatRelativeTime } from "@/lib/formatters"
import { AlertTriangleIcon, CheckCircleIcon, FileTextIcon, Loader2Icon, RefreshCwIcon, TrashIcon } from "lucide-react"
import { toast } from "@/components/ui/toast"
import { getActionErrorMessage } from "@/lib/forms/api-field-errors"
import { SettingsPageGate } from "../../../settings-page-gate"
import { getMetaLeadKindLabel, isZapierMetaForm } from "./meta-form-labels"

const statusBadge = (status: string) => {
    if (status === "mapped") {
        return (
            <Badge variant="default" className="gap-1 bg-green-500/10 text-green-600 border-green-500/20">
                <CheckCircleIcon className="size-3" aria-hidden="true" />
                Mapped
            </Badge>
        )
    }
    if (status === "outdated") {
        return (
            <Badge variant="destructive" className="gap-1">
                <AlertTriangleIcon className="size-3" aria-hidden="true" />
                Outdated
            </Badge>
        )
    }
    return (
        <Badge variant="secondary" className="gap-1 bg-yellow-500/10 text-yellow-700 border-yellow-500/30">
            <AlertTriangleIcon className="size-3" aria-hidden="true" />
            Unmapped
        </Badge>
    )
}

export default function MetaFormsPage() {
    return (
        <SettingsPageGate
            title="Meta Lead Form Mapping"
            permission="manage_meta_leads"
            deniedDescription="Meta lead forms need the Manage Meta Leads permission. Ask an admin to update your role."
            back={{ href: "/settings/integrations/meta", label: "Back to Meta" }}
        >
            <MetaFormsContent />
        </SettingsPageGate>
    )
}

function MetaFormsContent() {
    const formsQuery = useMetaForms()
    const forms = formsQuery.data ?? []
    // A failed background refetch keeps the last list; only a failed first load replaces it.
    const formsLoadFailed = formsQuery.isError && !formsQuery.data
    const syncMutation = useSyncMetaForms()
    const deleteForm = useDeleteMetaForm()

    const needsMapping = forms.filter((form) => form.mapping_status !== "mapped")

    // Errors propagate so the confirm dialog stays open and shows them inline.
    const handleDelete = async (formId: string) => {
        await deleteForm.mutateAsync(formId)
        toast.success("Form deleted")
    }

    const handleSync = () => {
        syncMutation.mutate({}, {
            onSuccess: () => toast.success("Forms synced"),
            onError: (error) => {
                const message = getActionErrorMessage(error, "Couldn't sync forms. Try again.")
                if (message) toast.error(message)
            },
        })
    }

    return (
        <div className="flex min-h-screen flex-col">
            <PageHeader
                title="Meta Lead Form Mapping"
                back={{ href: "/settings/integrations/meta", label: "Back to Meta" }}
                actions={
                    <Button
                        variant="outline"
                        onClick={handleSync}
                        disabled={syncMutation.isPending}
                    >
                        {syncMutation.isPending ? (
                            <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                        ) : (
                            <RefreshCwIcon className="mr-2 size-4" aria-hidden="true" />
                        )}
                        Sync forms
                    </Button>
                }
            />

            <div className="flex-1 space-y-6 p-6">
                {needsMapping.length > 0 && (
                    <Alert>
                        <AlertTitle>Forms need mapping</AlertTitle>
                        <AlertDescription>
                            {needsMapping.length} form(s) require mapping before leads can convert.
                        </AlertDescription>
                    </Alert>
                )}

                <Card>
                    <CardHeader>
                        <CardTitle>Forms</CardTitle>
                    </CardHeader>
                    <CardContent>
                        {formsQuery.isLoading ? (
                            <div className="flex items-center justify-center py-12">
                                <Loader2Icon className="size-8 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
                            </div>
                        ) : formsLoadFailed ? (
                            <QueryErrorState
                                error={formsQuery.error}
                                onRetry={() => void formsQuery.refetch()}
                                isRetrying={formsQuery.isFetching}
                                title="Couldn't load lead forms"
                                className="min-h-0 py-10"
                            />
                        ) : forms.length === 0 ? (
                            <EmptyState icon={FileTextIcon} title="No lead forms" />
                        ) : (
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Form</TableHead>
                                        <TableHead>Page</TableHead>
                                        <TableHead>Lead type</TableHead>
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
                                                {isZapierMetaForm(form) ? (
                                                    <div>Zapier</div>
                                                ) : (
                                                    <>
                                                        <div>{form.page_name || "—"}</div>
                                                        <div className="text-xs text-muted-foreground">{form.page_id}</div>
                                                    </>
                                                )}
                                            </TableCell>
                                            <TableCell>
                                                {getMetaLeadKindLabel(form.lead_kind)}
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
                                                <div className="flex justify-end gap-2">
                                                    <Button
                                                        size="sm"
                                                        variant="outline"
                                                        render={<Link href={`/settings/integrations/meta/forms/${form.id}`} />}
                                                    >
                                                        Manage mapping
                                                    </Button>
                                                    <ConfirmDialog
                                                        trigger={
                                                            <Button
                                                                size="sm"
                                                                variant="destructive-ghost"
                                                                disabled={deleteForm.isPending}
                                                            >
                                                                <TrashIcon aria-hidden="true" />
                                                                Delete
                                                            </Button>
                                                        }
                                                        title={`Delete ${form.form_name}?`}
                                                        description="This removes the form and its mapping rules. Incoming leads for this form will pause until you re‑sync or paste fields again."
                                                        confirmLabel="Delete form"
                                                        errorFallback="Couldn't delete the form. Try again."
                                                        onConfirm={() => handleDelete(form.id)}
                                                    />
                                                </div>
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
